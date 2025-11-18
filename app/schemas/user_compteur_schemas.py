from typing import Optional
from pydantic import BaseModel
from datetime import datetime

class UserCompteurBase(BaseModel):
    compteur_id: Optional[int]
    user_id: Optional[int]
    est_proprietaire:Optional[bool]
    autorise_par: Optional[int]
    active_par: Optional[int]
    etat_id: Optional[int]
    est_active: Optional[bool]
    id_client: Optional[str]
    num_compte_contrat: Optional[str]
    poc: Optional[str]
    default: Optional[bool]
    nom_client:Optional[str]
    numero_compteur :Optional[str]
    id_agence : Optional[int]
    nom_agence:Optional[str]
    adresse:Optional[str]
    tarif:Optional[str]
    type_compteur :Optional[int]
    class Config:
        from_attributes = True

class UserCompteurCreateSchema(UserCompteurBase):
    pass

class UserCompteurCreateSchemaV2(BaseModel):
    telephone:str
    numero_compteur:str
    type_compteur:int

class UserCompteurUpdate(UserCompteurBase):
   pass

class UserCompteurOut(UserCompteurBase):
    id: int

    class Config:
        from_attributes = True

class CompteurWoyofalResponseSchema(BaseModel):
    status:int
    nom_client:Optional[str]
    tel:Optional[str]
    poc:Optional[str]
    id_client:Optional[str]
    adresse:Optional[str]
    tarif:Optional[str]
    agence:Optional[str]


class ActivateUserCompteur(BaseModel):
    user_compteur_id:int
    activate:bool
    activated_by_user:int


class CompteurPostpaidResponseSchema(BaseModel):
    status:int
    tel:Optional[str]
    numCC:Optional[str]
    id_partenaire:Optional[str]
    adresse:Optional[str]
    tarif:Optional[str]
    nom_client:Optional[str]
    agence:Optional[str]