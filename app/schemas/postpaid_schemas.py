from pydantic import BaseModel

class BillsParamSchema(BaseModel) : 
    numCC:str
    dateDebut:str
    dateFin:str

class NumCCParamSchema(BaseModel):
    numCC:str