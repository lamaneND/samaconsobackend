from pydantic import BaseModel



class TransactionByPeriodSchema(BaseModel):
    meter:str
    poc:str
    dateDebut:str
    dateFin:str

class TransactionsByMeterPoc(BaseModel):
    meter:str
    poc:str