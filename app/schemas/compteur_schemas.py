from datetime import datetime
from typing import Optional
from pydantic import BaseModel

class CompteurBaseSchema(BaseModel):
    numero: str
    type_compteur: Optional[int]
    class Config:
        from_attributes = True

class CompteurCreateSchema(CompteurBaseSchema):
    pass

class CompteurUpdateSchema(CompteurBaseSchema):
    id:int
    updated_at:datetime = datetime.now()

class CompteurResponseSchema(CompteurBaseSchema):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
