from fastapi import APIRouter, HTTPException, Query, status
from app.database import get_db_connection_avis
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
        logger.error("Impossible de se connecter à AvisDB")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur de connexion à la base de données."
        )

    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT NumAvis, CodeEtape, DescEtape, DateTerm, HeureTerm,
                   NumPartenaire, Prenom, Nom, Telephone
              FROM dbo.AvisEtapes
             WHERE NumAvis = ?
             ORDER BY CodeEtape
            """,
            num_avis,
        )
        rows = cursor.fetchall()

        if not rows:
            logger.info(f"Avis {num_avis} non trouvé en base")
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=ERR_NOT_FOUND)

        first = rows[0]
        client = ClientSchema(
            num_partenaire=first.NumPartenaire,
            prenom=first.Prenom,
            nom=first.Nom,
            telephone=first.Telephone,
        )

        etapes = []
        nb_terminees = 0
        for r in rows:
            termine = bool(r.DateTerm and r.DateTerm.strip())
            if termine:
                nb_terminees += 1
            etapes.append(EtapeSchema(
                code_etape=r.CodeEtape,
                description=r.DescEtape,
                date_term=r.DateTerm,
                heure_term=r.HeureTerm,
                termine=termine,
            ))

        response = AvisResponseSchema(
            num_avis=num_avis,
            client=client,
            etapes=etapes,
            nb_etapes_terminees=nb_terminees,
            nb_etapes_total=len(etapes),
        )

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

    # Vérifier le cache (clé incluant le téléphone pour éviter les fuites cross-client)
    cache_key = CACHE_KEYS["AVIS_BY_NUM"].format(
        num_avis=num_avis, telephone=telephone_normalise
    )
    try:
        cached = await cache_get(cache_key)
        if cached:
            logger.info(f"Cache HIT pour avis {num_avis}")
            return json.loads(cached)
    except Exception:
        pass  # Continuer si le cache est indisponible

    conn = get_db_connection_avis()
    if not conn:
        logger.error("Impossible de se connecter à AvisDB")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur de connexion à la base de données."
        )

    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT NumAvis, CodeEtape, DescEtape, DateTerm, HeureTerm,
                   NumPartenaire, Prenom, Nom, Telephone
              FROM dbo.AvisEtapes
             WHERE NumAvis = ?
             ORDER BY CodeEtape
            """,
            num_avis,
        )
        rows = cursor.fetchall()

        # Avis introuvable → erreur générique
        if not rows:
            logger.info(f"Avis {num_avis} non trouvé en base")
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=ERR_NOT_FOUND)

        # Vérification de la paire (avis, téléphone) : même message d'erreur
        db_phone = _normalize_phone(rows[0].Telephone or "")
        if not db_phone or db_phone != telephone_normalise:
            logger.info(f"Téléphone non correspondant pour avis {num_avis}")
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=ERR_NOT_FOUND)

        # Construction de la réponse
        first = rows[0]
        client = ClientSchema(
            num_partenaire=first.NumPartenaire,
            prenom=first.Prenom,
            nom=first.Nom,
            telephone=first.Telephone,
        )

        etapes = []
        nb_terminees = 0
        for r in rows:
            termine = bool(r.DateTerm and r.DateTerm.strip())
            if termine:
                nb_terminees += 1
            etapes.append(EtapeSchema(
                code_etape=r.CodeEtape,
                description=r.DescEtape,
                date_term=r.DateTerm,
                heure_term=r.HeureTerm,
                termine=termine,
            ))

        response = AvisResponseSchema(
            num_avis=num_avis,
            client=client,
            etapes=etapes,
            nb_etapes_terminees=nb_terminees,
            nb_etapes_total=len(etapes),
        )

        # Mise en cache
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
