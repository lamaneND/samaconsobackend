from pydantic import BaseModel
from typing import List, Optional


class EtapeSchema(BaseModel):
    code_etape: str
    description: Optional[str] = None
    date_term: Optional[str] = None
    heure_term: Optional[str] = None
    termine: bool


class ClientSchema(BaseModel):
    num_partenaire: Optional[str] = None
    prenom: Optional[str] = None
    nom: Optional[str] = None
    telephone: Optional[str] = None


class AvisResponseSchema(BaseModel):
    num_avis: str
    client: ClientSchema
    etapes: List[EtapeSchema]
    nb_etapes_terminees: int
    nb_etapes_total: int
