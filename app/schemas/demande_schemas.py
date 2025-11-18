# schemas/demande.py
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class DemandeBaseSchema(BaseModel):
    fait_par: Optional[int] = None
    traite_par: Optional[int] = None
    user_compteur_id: Optional[int] = None
    type_demande: Optional[int] = None
    commentaire: Optional[str] = None
    fichier: Optional[str] = None

class DemandeCreateSchema(DemandeBaseSchema):
    pass

class DemandeUpdateSchema(DemandeBaseSchema):
    pass

class DemandeResponseSchema(DemandeBaseSchema):
    id: int
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True
