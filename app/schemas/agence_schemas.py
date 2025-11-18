from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class AgenceCreateSchemas(BaseModel):
    nom: str
    nom_corrige: str

    class Config:
        from_attributes = True


class AgenceBaseSchemas(BaseModel):
    id: int
    nom: str
    nom_corrige: str
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


class AgenceUpdateSchemas(BaseModel):
    nom: Optional[str] = None
    nom_corrige: Optional[str] = None

    class Config:
        from_attributes = True
