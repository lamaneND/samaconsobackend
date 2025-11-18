from datetime import datetime
from pydantic import BaseModel
from typing import Optional

class UserSessionBaseSchema(BaseModel):
    user_id: int
    device_model: Optional[str] = None
    fcm_token: Optional[str] = None
 
  
  

    class Config:
        from_attributes = True


class UserSessionCreateSchema(UserSessionBaseSchema):
    pass

class UserSessionUpdateSchema(UserSessionBaseSchema):
    pass


class RegisterFCMToken(BaseModel):
    device_model: Optional[str] = None
    fcm_token: str
    jti: Optional[str] = None
    expires_at: Optional[datetime] = None
