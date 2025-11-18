from fastapi import APIRouter, Depends,status,HTTPException
from app.auth import get_current_user
from app.database import get_db_connection_sic
from app.models.models import User
from app.queries import *
from app.schemas.sic_schemas import *
from app.cache import cache_get, cache_set, cache_delete
from app.config import CACHE_KEYS
import pyodbc
import json


sic_router = APIRouter(prefix="/sic",tags=["sic"])


@sic_router.get("/getcustomerbymeter/{meter}")
async def get_customer_by_meter(meter:str):
    # Cache avec TTL de 1 heure pour les données client
    cache_key = CACHE_KEYS["SIC_CUSTOMER_BY_METER"].format(meter=meter)
    try:
        cached = await cache_get(cache_key)
        if cached:
            return json.loads(cached)
    except Exception:
        pass

    conn = get_db_connection_sic()
    if not conn:
        return {"error": "Database connection failed"}
    
    try:
        cursor = conn.cursor()
        # Example SELECT query
        cursor.execute(getCustomerByMeterQuery,(meter))
        rows = cursor.fetchall()
        if not rows:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,detail="Customer not found")
        columns = [column[0] for column in cursor.description]
        customer = [dict(zip(columns, row)) for row in rows]
        
        response = {"status":status.HTTP_200_OK,"results":len(customer),"customer": customer}
        
        # Cache pour 1 heure (3600 secondes)
        try:
            await cache_set(cache_key, json.dumps(response, default=str), 3600)
        except Exception:
            pass
        
        return response
    
    except pyodbc.Error as e:
        return {"error": f"Query failed: {e}"}
    
    finally:
        cursor.close()
        conn.close()


@sic_router.get("/getcustomerbyphone/{phoneNumber}")
async def get_customer_by_phonenumber(phoneNumber:str):
    # Cache avec TTL de 1 heure pour les données client  
    cache_key = CACHE_KEYS["SIC_CUSTOMER_BY_PHONE"].format(phone=phoneNumber)
    try:
        cached = await cache_get(cache_key)
        if cached:
            return json.loads(cached)
    except Exception:
        pass

    conn = get_db_connection_sic()
    if not conn:
        return {"error": "Database connection failed"}
    
    try:
        cursor = conn.cursor()
        # Example SELECT query
        cursor.execute(getCustomerByPhoneQuery,(phoneNumber))
        rows = cursor.fetchall()
        if not rows:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,detail="Customer not found")
        columns = [column[0] for column in cursor.description]
        customers = [dict(zip(columns, row)) for row in rows]
        
        response = {"status":status.HTTP_200_OK,"results":len(customers),"customer": customers}
        
        # Cache pour 1 heure (3600 secondes)
        try:
            await cache_set(cache_key, json.dumps(response, default=str), 3600)
        except Exception:
            pass
        
        return response
    
    except pyodbc.Error as e:
        return {"error": f"Query failed: {e}"}
    
    finally:
        cursor.close()
        conn.close()



@sic_router.post("/gettop10transactions/")
async def get_top_10_transactions(data:TransactionsByMeterPoc):

    conn = get_db_connection_sic()
    if not conn:
        return {"error": "Database connection failed"}
    
    try:
        cursor = conn.cursor()
        # Example SELECT query
        cursor.execute(top10TransactionsQuery,(data.meter,data.poc))
        rows = cursor.fetchall()
        if not rows:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,detail="Customer not found")
        columns = [column[0] for column in cursor.description]
        transactions= [dict(zip(columns, row)) for row in rows]
        arrondi = 0
        montant = sum(transaction["MONTANT_TTC"] for transaction in transactions) 
        for transaction in transactions:
            if transaction["ARRONDI"] is not None:
                arrondi += transaction["ARRONDI"]
        energie_globale = sum(transaction["ENERGIE_VENDUE"] for transaction in transactions) 
        montant_global = montant
        
        if arrondi>0:
            montant_global = montant-arrondi
        # Convert results to a list of dictionaries
       # customer = [{ "first name": row.CUSTOMER_FirstNAME, "name": row.CUSTOMER_NAME} for row in rows]
       
        
        return {"status":status.HTTP_200_OK,"results":len(transactions),"montant_global":montant_global,"energie":energie_globale,"transactions": transactions}
    
    except pyodbc.Error as e:
        return {"error": f"Query failed: {e}"}
    
    finally:
        cursor.close()
        conn.close()

@sic_router.get("/gettop10transactionsphonenumber/{phoneNumber}")
async def get_top_10_transactions_phone_number(phoneNumber:str):

    conn = get_db_connection_sic()
    if not conn:
        return {"error": "Database connection failed"}
    
    try:
        cursor = conn.cursor()
        # Example SELECT query
        cursor.execute(top10TransactionsByPhoneNumberQuery,(phoneNumber))
        rows = cursor.fetchall()
        if not rows:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,detail="Customer not found")
        columns = [column[0] for column in cursor.description]
        transactions = [dict(zip(columns, row)) for row in rows]
     

        # Convert results to a list of dictionaries
       # customer = [{ "first name": row.CUSTOMER_FirstNAME, "name": row.CUSTOMER_NAME} for row in rows]
       
        
        return {"status":status.HTTP_200_OK,"results":len(transactions),"transactions": transactions}
    
    except pyodbc.Error as e:
        return {"error": f"Query failed: {e}"}
    
    finally:
        cursor.close()
        conn.close()


@sic_router.post("/gettransactionsbyperiod/")
async def get_transactions_by_period(transac:TransactionByPeriodSchema):

    conn = get_db_connection_sic()
    if not conn:
        return {"error": "Database connection failed"}
    
    try:
        cursor = conn.cursor()
        # Example SELECT query
        cursor.execute(transactionsBetweenDatesQuery,(transac.meter,transac.poc,transac.dateDebut,transac.dateFin))
        rows = cursor.fetchall()
        if not rows:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,detail="transactions not found")
        columns = [column[0] for column in cursor.description]
        transactions= [dict(zip(columns, row)) for row in rows]
        montant_global = sum(transaction["MONTANT_TTC"] for transaction in transactions)
        energie_globale = sum(transaction["ENERGIE_VENDUE"] for transaction in transactions) 


        # Convert results to a list of dictionaries
       # customer = [{ "first name": row.CUSTOMER_FirstNAME, "name": row.CUSTOMER_NAME} for row in rows]
       
        
        return {"status":status.HTTP_200_OK,"results":len(transactions),"montant_global":montant_global,"energie_globale":energie_globale,"transactions": transactions}
    
    except pyodbc.Error as e:
        return {"error": f"Query failed: {e}"}
    
    finally:
        cursor.close()
        conn.close()


@sic_router.get("/dixdernierestransactions")
async def get_top_10_transaction_By_NumCompteur(numCompteur:str):

    conn = get_db_connection_sic()
    if not conn:
        return {"error": "Database connection failed"}
    
    try:
        cursor = conn.cursor()
        # Example SELECT query
        cursor.execute(tenLastWoyofalTransactions,(numCompteur))
        rows = cursor.fetchall()
        if not rows:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,detail="Customer not found")
        columns = [column[0] for column in cursor.description]
        transactions = [dict(zip(columns, row)) for row in rows]
     

        # Convert results to a list of dictionaries
       # customer = [{ "first name": row.CUSTOMER_FirstNAME, "name": row.CUSTOMER_NAME} for row in rows]
       
        
        return {"status":status.HTTP_200_OK,"results":len(transactions),"transactions": transactions}
    
    except pyodbc.Error as e:
        return {"error": f"Query failed: {e}"}
    
    finally:
        cursor.close()
        conn.close()


@sic_router.post("/gettransctionsmonthmeterpoc/")
async def get_transactions_month(trans:TransactionsByMeterPoc):

    conn = get_db_connection_sic()
    if not conn:
        return {"error": "Database connection failed"}
    
    try:
        cursor = conn.cursor()
        # Example SELECT query
        cursor.execute(getTransactionsByMonthMeterPoc,(trans.meter,trans.poc))
        rows = cursor.fetchall()
        if not rows:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,detail="transaction not found")
        columns = [column[0] for column in cursor.description]
        transactions= [dict(zip(columns, row)) for row in rows]
        montant_global = sum(transaction["Total TTC"] for transaction in transactions)
        energie_globale = sum(transaction["Total énergie"] for transaction in transactions) 


        # Convert results to a list of dictionaries
       # customer = [{ "first name": row.CUSTOMER_FirstNAME, "name": row.CUSTOMER_NAME} for row in rows]
       
        
        return {"status":status.HTTP_200_OK,"results":len(transactions),"montant_global":montant_global,"energie":energie_globale,"transactions": transactions}
    
    except pyodbc.Error as e:
        return {"error": f"Query failed: {e}"}
    
    finally:
        cursor.close()
        conn.close()