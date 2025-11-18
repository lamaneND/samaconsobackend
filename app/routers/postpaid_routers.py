from fastapi import APIRouter, Depends,status,HTTPException
from app.auth import get_current_user
from app.database import get_db_connection_postpaid,get_db_connection_sic  , get_db_connection_postpaid_customer
from app.models.models import User
from app.queries import *
from app.schemas.postpaid_schemas import *
from app.cache import cache_get, cache_set, cache_delete
from app.config import CACHE_KEYS
import pyodbc
import json


postpaid_router = APIRouter(prefix="/postpaid",tags=["postpaid"])

@postpaid_router.get("/gettop6bills/{numCC}")
async def get_top_6_bills(numCC:str):
    # Cache les données avec TTL de 30 minutes car données externes peuvent changer
    cache_key = CACHE_KEYS["POSTPAID_TOP6_BILLS"].format(numCC=numCC)
    try:
        cached = await cache_get(cache_key)
        if cached:
            return json.loads(cached)
    except Exception:
        pass

    conn = get_db_connection_postpaid()
    if not conn:
        return {"error": "Database connection failed"}
    
    try:
        cursor = conn.cursor()
        # Example SELECT query
        cursor.execute(top6FacturesQuery,(numCC))
        rows = cursor.fetchall()
        if not rows:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,detail="Bills not found")
        columns = [column[0] for column in cursor.description]
        bills = [dict(zip(columns, row)) for row in rows]
        
        response = {"status":status.HTTP_200_OK,"results":len(bills),"bills": bills}
        
        # Cache pour 30 minutes (1800 secondes)
        try:
            await cache_set(cache_key, json.dumps(response, default=str), 1800)
        except Exception:
            pass
        
        return response
    
    except pyodbc.Error as e:
        return {"error": f"Query failed: {e}"}
    
    finally:
        cursor.close()
        conn.close()



#billsbyperiod
@postpaid_router.post("/getbillsbyperiod/")
async def get_bills_by_period(billsParam:BillsParamSchema):

    conn = get_db_connection_postpaid()
    if not conn:
        return {"error": "Database connection failed"}
    
    try:
        cursor = conn.cursor()
        # Example SELECT query
        cursor.execute(FacturesbyPeriodQuery,(billsParam.numCC,billsParam.dateDebut,billsParam.dateFin))
        rows = cursor.fetchall()
        if not rows:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,detail="Bills not found")
        columns = [column[0] for column in cursor.description]
        transactions= [dict(zip(columns, row)) for row in rows]
        montant_global = sum(transaction["MONT_TTC"] for transaction in transactions)
        energie_globale = sum(transaction["BT_CONSTOT"] for transaction in transactions) 
        
       
    

        # Convert results to a list of dictionaries
       # customer = [{ "first name": row.CUSTOMER_FirstNAME, "name": row.CUSTOMER_NAME} for row in rows]
       
        
        return {"status":status.HTTP_200_OK,"results":len(transactions),"energie_globale":energie_globale,"montant_global":montant_global,"factures": transactions}
    
    except pyodbc.Error as e:
        return {"error": f"Query failed: {e}"}
    
    finally:
        cursor.close()
        conn.close()


#Method clientele postpaid

@postpaid_router.get("/getpostpaidcustomer/{phonenumber}")
async def get_postpaid_customer(phonenumber:str):

    conn = get_db_connection_postpaid_customer()
    if not conn:
        return {"error": "Database connection failed"}
    
    try:
        cursor = conn.cursor()
        # Example SELECT query
        cursor.execute(getCustomerPostpaidByPhoneQuery,(phonenumber))
        rows = cursor.fetchall()
        if not rows:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,detail="Customer not found")
        columns = [column[0] for column in cursor.description]
        customer = [dict(zip(columns, row)) for row in rows]
         
        
        return {"status":status.HTTP_200_OK,"results":len(customer),"customer": customer}
    
    except pyodbc.Error as e:
        return {"error": f"Query failed: {e}"}
    
    finally:
        cursor.close()
        conn.close()





@postpaid_router.get("/sixdernieresfactures/{numCC}")
async def get_six_dernieres_factures(numCC:str):

    conn = get_db_connection_postpaid()
    if not conn:
        return {"error": "Database connection failed"}
    
    try:
        cursor = conn.cursor()
        # Example SELECT query
        cursor.execute(sixLastBills,(numCC))
        rows = cursor.fetchall()
        if not rows:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,detail="Customer not found")
        columns = [column[0] for column in cursor.description]
        transactions = [dict(zip(columns, row)) for row in rows]
        montant_global = sum(transaction["MONTANT"] for transaction in transactions)
        energie_globale = sum(transaction["CONSOMMATION TOTALE"] for transaction in transactions) 
        
        return {"status":status.HTTP_200_OK,"results":len(transactions),"energie_globale":energie_globale,"montant_global":montant_global,"transactions": transactions}
    
    except pyodbc.Error as e:
        return {"error": f"Query failed: {e}"}
    
    finally:
        cursor.close()
        conn.close()




@postpaid_router.get("/detailscompteurpostpaiement/{numCC}")
async def get_postpaid_detail(numCC:str):

    conn = get_db_connection_postpaid()
    if not conn:
        return {"error": "Database connection failed"}
    
    try:
        cursor = conn.cursor()
        # Example SELECT query
        cursor.execute(getDetailsCompteurPostpaiement,(numCC))
        rows = cursor.fetchall()
        if not rows:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,detail="Customer not found")
        columns = [column[0] for column in cursor.description]
        customer = [dict(zip(columns, row)) for row in rows]
         
        
        return {"status":status.HTTP_200_OK,"results":len(customer),"customer": customer}
    
    except pyodbc.Error as e:
        return {"error": f"Query failed: {e}"}
    
    finally:
        cursor.close()
        conn.close()


@postpaid_router.post("/facturesanneeencours")
async def get_postpaid_bills_current_year(numCC:NumCCParamSchema):

    conn = get_db_connection_postpaid()
    if not conn:
        return {"error": "Database connection failed"}
    
    try:
        cursor = conn.cursor()
        # Example SELECT query
        cursor.execute(getBillsByMonth,(numCC.numCC))
        rows = cursor.fetchall()
        if not rows:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,detail="Customer not found")
        columns = [column[0] for column in cursor.description]
        transactions = [dict(zip(columns, row)) for row in rows]
        montant_global = sum(transaction["Total TTC"] for transaction in transactions)
        energie_globale = sum(transaction["Total énergie"] for transaction in transactions) 
        
        return {"status":status.HTTP_200_OK,"results":len(transactions),"energie_globale":energie_globale,"montant_global":montant_global,"transactions": transactions}
    
    except pyodbc.Error as e:
        return {"error": f"Query failed: {e}"}
    
    finally:
        cursor.close()
        conn.close()