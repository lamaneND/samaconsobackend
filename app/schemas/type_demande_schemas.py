from datetime import datetime
from typing import List
from pydantic import BaseModel


class TypeDemandeBaseSchema(BaseModel):
    label:str
    
    class Config:
        from_attributes = True

class TypeDemandeCreateSchema(TypeDemandeBaseSchema):
    pass    

class TypeDemandeUpdateSchema(TypeDemandeBaseSchema):
    id:int
    updated_at:datetime = datetime.now()

class TypeDemandeResponseSchema(TypeDemandeBaseSchema):
    id:int
    created_at:str
    updated_at:str

class TypeDemandeListResponseSchema():
    status:int
    results:int
    TypeDemandes:List[TypeDemandeResponseSchema]