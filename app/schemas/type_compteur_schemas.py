from datetime import datetime
from pydantic import BaseModel

class TypeCompteurBaseSchema(BaseModel):
    label: str

class TypeCompteurCreateSchema(TypeCompteurBaseSchema):
    pass

class TypeCompteurUpdateSchema(TypeCompteurBaseSchema):
    id:int
    updated_at:datetime = datetime.now()

class TypeCompteurResponseSchema(TypeCompteurBaseSchema):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
