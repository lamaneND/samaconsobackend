from datetime import datetime
from pydantic import BaseModel

class EtatCompteurBaseSchema(BaseModel):
    label: str

class EtatCompteurCreateSchema(EtatCompteurBaseSchema):
    pass

class EtatCompteurUpdateSchema(EtatCompteurBaseSchema):
    pass

class EtatCompteurResponseSchema(EtatCompteurBaseSchema):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
