from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.database import get_db_samaconso
from app.cache import cache_get, cache_set
import json
from app.models.models import SeuilTarif
from app.schemas.seuil_tarif_schemas import SeuilTarifListResponseSchema

seuil_tarif_router = APIRouter(prefix="/seuils_tarif", tags=["seuils_tarif"])

@seuil_tarif_router.get("/", response_model=SeuilTarifListResponseSchema)
async def get_seuils_tarif(
    code_tarif: str,
    db: Session = Depends(get_db_samaconso)
):
    cache_key = f"seuil_tarif:code:{code_tarif.lower()}"
    try:
        cached = await cache_get(cache_key)
        if cached:
            data = json.loads(cached)
            return {
                "status": status.HTTP_200_OK,
                "results": len(data),
                "seuils_tarif": data
            }
    except Exception:
        pass
    seuils = (
        db
        .query(SeuilTarif)
        .filter(
            func.lower(SeuilTarif.code_tarif) == code_tarif.lower()
        )
        .order_by(SeuilTarif.id_seuil)
        .all()
    )
    payload = [
        {
            "id": s.id,
            "code_tarif": s.code_tarif,
            "id_seuil": s.id_seuil,
            "kwh_min": s.kwh_min,
            "kwh_max": s.kwh_max,
            "color_hex": s.color_hex,
            "created_at": s.created_at.strftime("%d/%m/%Y %H:%M:%S") if s.created_at else None,
        }
        for s in seuils
    ]
    try:
        await cache_set(cache_key, json.dumps(payload))
    except Exception:
        pass
    return {
        "status": status.HTTP_200_OK,
        "results": len(payload),
        "seuils_tarif": payload
    }