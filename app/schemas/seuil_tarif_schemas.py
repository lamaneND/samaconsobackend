from typing import List, Optional
from pydantic import BaseModel

class SeuilTarifBaseSchema(BaseModel):
    code_tarif: str
    id_seuil: int
    kwh_min: float
    kwh_max: Optional[float]
    color_hex: str

    class Config:
        from_attributes = True

class SeuilTarifResponseSchema(SeuilTarifBaseSchema):
    id: int

class SeuilTarifListResponseSchema(BaseModel):
    status: int
    results: int
    seuils_tarif: List[SeuilTarifResponseSchema]