from pydantic import BaseModel
class SimulateurSchema(BaseModel):
    numero_compteur: str
    montant: float