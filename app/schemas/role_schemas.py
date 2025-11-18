from datetime import datetime
from typing import List
from pydantic import BaseModel


class RoleBaseSchema(BaseModel):
    label:str
    
    class Config:
        from_attributes = True

class RoleCreateSchema(RoleBaseSchema):
    pass    

class RoleUpdateSchema(RoleBaseSchema):
    id:int
    updated_at:datetime = datetime.now()

class RoleResponseSchema(RoleBaseSchema):
    id:int
    created_at:str
    updated_at:str

class RoleListResponseSchema():
    status:int
    results:int
    roles:List[RoleResponseSchema]

class RoleUpdateSchema(RoleBaseSchema):
    id:int
    updated_at:datetime = datetime.now()