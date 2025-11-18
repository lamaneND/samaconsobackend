from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel


class UserBaseSchema(BaseModel):
    firstName:Optional[str]
    lastName:Optional[str]
    phoneNumber:Optional[str]
    codePin:Optional[str]
    email:Optional[str]=None
    login:Optional[str]=None
    password:Optional[str]=None
    ldap:Optional[bool]=None
    role:int
    id_agence:Optional[int]=None
    is_activate:bool

    class Config:
        from_attributes = True

class UserCreateSchema(UserBaseSchema): 
    pass

class UserLoginSchema(BaseModel):
    username:str
    password:str

    class Config:
        from_attributes = True

class UserLoginRequestSchema(BaseModel):
    username:str
    password:str
    device_model:Optional[str] = None
    fcm_token: Optional[str] = None

    class Config:
        from_attributes = True

class UserUpdateSchema(UserBaseSchema):
   pass
   

class UserUpdateCodePinSchema(BaseModel):
   user_id:int
   codePin:str

class UserResponseSchema(UserBaseSchema):
    id:int
    created_at:str
    updated_at:str

    class Config:
        from_attributes = True


class UserListResponseSchema():
    status:int
    results:int
    users:List[UserResponseSchema]


class UserSendSmsSchema(BaseModel):
    telephone: str
    message: str
    
class Token(BaseModel):
    access_token:str
    token_type:str

class TokenData(BaseModel):
    email: Optional[str] = None
    login: Optional[str] = None
    phoneNumber: Optional[str] = None


class UserLogoutSchema(BaseModel):
    user_id:Optional[int]=None
    fcmToken: Optional[str] = None
    
    class Config:
        from_attributes = True