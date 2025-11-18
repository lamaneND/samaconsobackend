import sqlalchemy as _sql
from fastapi import Depends
import sqlalchemy.ext.declarative as _declarative
from sqlalchemy.orm import Session
import sqlalchemy.orm as _orm
import pyodbc
from typing import Annotated


DATABASE_URL = "postgresql://postgres:s3n3l3c123@10.101.1.171:5432/samaconso"
#DATABASE_URL = "postgresql://postgres:postgres@localhost:5432/samaconso"
engine = _sql.create_engine(DATABASE_URL)
# engine = _sql.create_engine(DATABASE_URL,  pool_size=20,     
#     max_overflow=30,   
#     pool_timeout=30,    
#     pool_recycle=1800,  )


SessionLocal = _orm.sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = _declarative.declarative_base()

def get_db_samaconso():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

db_dependency = Annotated[_orm.Session, Depends(get_db_samaconso)]

 # Server1 Chaine de connection à la base de données du woyofal 
# SQL Server connection details
server = 'srv-asreports'  # Replace with your server name or IP
database = 'SIC'   # Replace with your database name
username = 'stagiaireddes'       # Replace with your SQL Server username
password = 'Senelec123'  # Replace with your password
driver = '{ODBC Driver 18 for SQL Server}'  # Adjust based on your installed driver

# Connection string
conn_str = (
    f"DRIVER={driver};"
    f"SERVER={server};"
    f"DATABASE={database};"
    f"UID={username};"
    f"PWD={password};"
    f"TrustServerCertificate=yes;"
)


def get_db_connection_sic():
    try:
        conn = pyodbc.connect(conn_str)
        return conn
    except pyodbc.Error as e:
        print(f"Error connecting to database: {e}")
        return None
    
    # Server2 Chaine de connexion pour les données du postpaiement 
    # SQL Server connection details
server1 = 'srv-commercial' 
database1 = 'HISTH2MC'   
username1 = 'commercial_dev'      
password1 = 'Senelec2023' 
driver1 = '{ODBC Driver 18 for SQL Server}'  

# Connection string
conn_str1 = (
    f"DRIVER={driver1};"
    f"SERVER={server1},1433;"
    f"DATABASE={database1};"
    f"UID={username1};"
    f"PWD={password1};"
    f"Encrypt=no;"
    f"TrustServerCertificate=yes;"
   
)


def get_db_connection_postpaid():
    try:
        conn = pyodbc.connect(conn_str1)
        return conn
    except pyodbc.Error as e:
        print(f"Error connecting to database: {e}")
        return None

       # Server3 Chaine de connexion pour les données clientele  postpaid
    # SQL Server connection details
server2 = 'srv-asreports'  # Replace with your server name or IP
database2 = 'BI_ODS'   # Replace with your database name
username2 = 'stagiaireddes'       # Replace with your SQL Server username
password2 = 'Senelec123'  # Replace with your password
driver2 = '{ODBC Driver 18 for SQL Server}'  # Adjust based on your installed driver

# Connection string
conn_str2 = (
    f"DRIVER={driver2};"
    f"SERVER={server2};"
    f"DATABASE={database2};"
    f"UID={username2};"
    f"PWD={password2}"
    f"TrustServerCertificate=yes;"
)

def get_db_connection_postpaid_customer():
    try:
        conn = pyodbc.connect(conn_str2)
        return conn
    except pyodbc.Error as e:
        print(f"Error connecting to database: {e}")
        return None