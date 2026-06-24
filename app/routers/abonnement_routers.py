from fastapi import APIRouter, HTTPException, Query, status
from app.database import get_db_connection_avis,get_db_connection_postpaid
from app.schemas.abonnement_schemas import AvisResponseSchema, ClientSchema, EtapeSchema
from app.cache import cache_get, cache_set
from app.config import CACHE_KEYS, CACHE_TTL
from app.logging_config import get_logger
import pyodbc
import json

logger = get_logger("app.routers.abonnement_routers")

abonnement_router = APIRouter(prefix="/abonnement", tags=["abonnement"])

# Message d'erreur générique : ne pas révéler quel champ est incorrect
# (avis introuvable / téléphone non correspondant → même message)
ERR_NOT_FOUND = "Aucune demande trouvée avec ces informations."

AVIS_QUERY = """
    SELECT NUM_AVIS, CODE_ETAPE, NUM_PARTENAIRE, DESC_ETAPE,
           DATE_TERM, HEURE_TERM, PRENOM, NOM, TELEPHONE,
           STATUT_AVIS, DT_DERNIERE_MAJ
      FROM dbo.AVIS_ETAPES_HANA
     WHERE NUM_AVIS = ?
     ORDER BY CODE_ETAPE
"""


def _normalize_phone(phone: str) -> str:
    """Supprime espaces, tirets, indicatif international pour comparaison (Sénégal : +221 / 00221)."""
    if not phone:
        return ""
    cleaned = phone.replace(" ", "").replace("-", "").replace(".", "")
    if cleaned.startswith("+221"):
        cleaned = cleaned[4:]
    elif cleaned.startswith("00221"):
        cleaned = cleaned[5:]
    return cleaned


def _build_response(rows, num_avis: str) -> AvisResponseSchema:
    """Construit l'AvisResponseSchema à partir des lignes SQL."""
    first = rows[0]
    client = ClientSchema(
        num_partenaire=first.NUM_PARTENAIRE,
        prenom=first.PRENOM,
        nom=first.NOM,
        telephone=first.TELEPHONE,
    )

    etapes = []
    nb_terminees = 0
    for r in rows:
        termine = bool(r.DATE_TERM and str(r.DATE_TERM).strip())
        if termine:
            nb_terminees += 1
        etapes.append(EtapeSchema(
            code_etape=r.CODE_ETAPE,
            description=r.DESC_ETAPE,
            date_term=str(r.DATE_TERM) if r.DATE_TERM else None,
            heure_term=str(r.HEURE_TERM) if r.HEURE_TERM else None,
            termine=termine,
        ))

    return AvisResponseSchema(
        num_avis=num_avis,
        statut_avis=first.STATUT_AVIS,
        dt_derniere_maj=str(first.DT_DERNIERE_MAJ) if first.DT_DERNIERE_MAJ else None,
        client=client,
        etapes=etapes,
        nb_etapes_terminees=nb_terminees,
        nb_etapes_total=len(etapes),
    )


@abonnement_router.get("/avis/details/{num_avis}", response_model=AvisResponseSchema)
async def get_avis_par_numero(num_avis: str):
    """
    Retourne la situation complète d'une demande d'abonnement par numéro d'avis uniquement,
    sans vérification du téléphone.

    - **num_avis** : numéro de l'avis (chemin)
    """
    cache_key = CACHE_KEYS["AVIS_BY_NUM_ONLY"].format(num_avis=num_avis)
    try:
        cached = await cache_get(cache_key)
        if cached:
            logger.info(f"Cache HIT pour avis {num_avis} (sans téléphone)")
            return json.loads(cached)
    except Exception:
        pass

    conn = get_db_connection_avis()
    if not conn:
        logger.error("Impossible de se connecter à BI_ODS")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur de connexion à la base de données."
        )

    try:
        cursor = conn.cursor()
        cursor.execute(AVIS_QUERY, num_avis)
        rows = cursor.fetchall()

        if not rows:
            logger.info(f"Avis {num_avis} non trouvé en base")
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=ERR_NOT_FOUND)

        response = _build_response(rows, num_avis)

        try:
            await cache_set(
                cache_key,
                json.dumps(response.model_dump(), default=str),
                CACHE_TTL["AVIS"]
            )
            logger.info(f"Cache SET pour avis {num_avis} sans téléphone (TTL={CACHE_TTL['AVIS']}s)")
        except Exception:
            pass

        return response

    except HTTPException:
        raise
    except pyodbc.Error as e:
        logger.error(f"Erreur SQL Server pour avis {num_avis}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de la récupération des données."
        )
    finally:
        cursor.close()
        conn.close()


@abonnement_router.get("/avis/{num_avis}", response_model=AvisResponseSchema)
async def get_avis(
    num_avis: str,
    telephone: str = Query(..., description="Numéro de téléphone associé à l'avis (obligatoire)")
):
    """
    Retourne la situation complète d'une demande d'abonnement SI ET SEULEMENT SI
    le numéro de téléphone fourni correspond à celui enregistré sur l'avis.

    - **num_avis** : numéro de l'avis (chemin)
    - **telephone** : numéro de téléphone du client (paramètre obligatoire)

    Retourne 404 si l'avis n'existe pas OU si le téléphone ne correspond pas.
    Le même code d'erreur est utilisé dans les deux cas pour ne pas révéler
    quel élément de la paire est incorrect.
    """
    telephone_normalise = _normalize_phone(telephone)

    cache_key = CACHE_KEYS["AVIS_BY_NUM"].format(
        num_avis=num_avis, telephone=telephone_normalise
    )
    try:
        cached = await cache_get(cache_key)
        if cached:
            logger.info(f"Cache HIT pour avis {num_avis}")
            return json.loads(cached)
    except Exception:
        pass

    conn = get_db_connection_avis()
    if not conn:
        logger.error("Impossible de se connecter à BI_ODS")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur de connexion à la base de données."
        )

    try:
        cursor = conn.cursor()
        cursor.execute(AVIS_QUERY, num_avis)
        rows = cursor.fetchall()

        if not rows:
            logger.info(f"Avis {num_avis} non trouvé en base")
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=ERR_NOT_FOUND)

        # Vérification de la paire (avis, téléphone) : même message d'erreur
        db_phone = _normalize_phone(rows[0].TELEPHONE or "")
        if not db_phone or db_phone != telephone_normalise:
            logger.info(f"Téléphone non correspondant pour avis {num_avis}")
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=ERR_NOT_FOUND)

        response = _build_response(rows, num_avis)

        try:
            await cache_set(
                cache_key,
                json.dumps(response.model_dump(), default=str),
                CACHE_TTL["AVIS"]
            )
            logger.info(f"Cache SET pour avis {num_avis} (TTL={CACHE_TTL['AVIS']}s)")
        except Exception:
            pass

        return response

    except HTTPException:
        raise
    except pyodbc.Error as e:
        logger.error(f"Erreur SQL Server pour avis {num_avis}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de la récupération des données."
        )
    finally:
        cursor.close()
        conn.close()
