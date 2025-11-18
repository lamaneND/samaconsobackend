from datetime import datetime
from typing import List
from pydantic import BaseModel


class TypeNotificationBaseSchema(BaseModel):
    label:str
    
    class Config:
        from_attributes = True

class TypeNotificationCreateSchema(TypeNotificationBaseSchema):
    pass    

class TypeNotificationUpdateSchema(TypeNotificationBaseSchema):
    id:int
    updated_at:datetime = datetime.now()

class TypeNotificationResponseSchema(TypeNotificationBaseSchema):
    id:int
    created_at:str
    updated_at:str

class TypeNotificationListResponseSchema():
    status:int
    results:int
    TypeNotifications:List[TypeNotificationResponseSchema]