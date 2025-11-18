from pydantic import BaseModel
from typing import Optional

class NotificationBaseSchema(BaseModel):
    type_notification_id :Optional[int] = None
    event_id : Optional[int] = None
    by_user_id : Optional[int] = None
    for_user_id : Optional[int] = None
    title : Optional[str] = None
    body : Optional[str] = None
    is_read : Optional[bool] =False
    

    class Config:
        from_attributes = True

class NotificationfromCompteurSchema(BaseModel):
    type_notification_id :Optional[int] = None
    num_compteur:Optional[str]=None
    title : Optional[str] = None
    body : Optional[str] = None
    

    class Config:
        from_attributes = True

class NotificationCreateSchema(NotificationBaseSchema):
    pass

class NotificationUserAgenceCreateSchema(BaseModel):
    type_notification_id :Optional[int] = None
    event_id : Optional[int] = None
    by_user_id : Optional[int] = None
    agence:Optional[str]=None
    title : Optional[str] = None
    body : Optional[str] = None
    is_read : Optional[bool] =False

class NotificationAllAgenceCreateSchema(BaseModel):
    type_notification_id :Optional[int] = None
    event_id : Optional[int] = None
    by_user_id : Optional[int] = None
    title : Optional[str] = None
    body : Optional[str] = None
    is_read : Optional[bool] =False

class NotificationAllUserCreateSchema(BaseModel):
    type_notification_id :Optional[int] = None
    event_id : Optional[int] = None
    by_user_id : Optional[int] = None
    title : Optional[str] = None
    body : Optional[str] = None
    is_read : Optional[bool] =False


class NotificationResponseSchema(BaseModel):
    id: int
    type_notification_id :Optional[int] = None
    event_id : Optional[int] = None
    by_user_id : Optional[int] = None
    for_user_id : Optional[int] = None
    title : Optional[str] = None
    body : Optional[str] = None
    is_read : Optional[bool] =False
    created_at: str

    class Config:
        from_attributes = True


class PushNotification(BaseModel):
    token: str
    title: str
    body: str

    class Config:
        from_attributes = True