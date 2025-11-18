import logging
import uuid
from datetime import datetime, timedelta
from typing import Optional
import jwt
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer
from passlib.context import CryptContext
from sqlalchemy import and_
from sqlalchemy.orm import Session
from app.config import SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES
from app.models.models import User, UserSession  
from app.database import get_db_samaconso
from app.schemas.user_schemas import TokenData
from ldap3 import SIMPLE, Server,Connection,ALL
from app.config import LDAP_SEARCH_PASSWORD, LDAP_SEARCH_USER, LDAP_SERVER,LDAP_PORT,LDAP_BASE_DN,LDAP_USER_DN,LDAP_DOMAIN



# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# OAuth2 scheme for token extraction
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/token")

#Vérifier mot de passe
def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

#Crypter mot de passe
def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

#Créer token
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now() + expires_delta
    else:
        expire = datetime.now() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
   # jti = str(uuid.uuid4())
    #to_encode.update({"jti": jti})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

#Décoder token JWT
def decode_access_token(token: str) -> Optional[dict]:
    """
    Décoder et valider un token JWT
    Retourne le payload si valide, None sinon
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        logging.getLogger(__name__).warning("Token expiré")
        return None
    except jwt.InvalidTokenError:
        logging.getLogger(__name__).warning("Token invalide")
        return None
    except Exception as e:
        logging.getLogger(__name__).error(f"Erreur décodage token: {e}")
        return None

#Récupérer l'utilisateur connecté
def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db_samaconso)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
       
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
       # jti: str = payload.get("jti")
        if user_id is None:
            raise credentials_exception
        #token_data = TokenData(email=user_id)
        user = db.query(User).filter(User.id == int(user_id)).first()
        if user is None:
            raise credentials_exception
        
        # session_exists = db.query(UserSession).filter(and_(UserSession.user_id==user.id,UserSession.jti==jti)).first()
        
        # if not session_exists:
        #     raise HTTPException(status_code=401, detail="Session expired or revoked")

        return user
    except jwt.PyJWTError:
        raise credentials_exception
    


def authenticate_ldap(username: str, password: str) -> bool:
    try:
        #user_dn = f"uid={username},{LDAP_USER_DN},{LDAP_BASE_DN}"
        user = f"{LDAP_DOMAIN}\\{username}"
        server = Server(LDAP_SERVER, port=LDAP_PORT, get_info=ALL,connect_timeout=5)
        # conn = Connection(server, user=user_dn, password=password, auto_bind=True)
        #conn = Connection(server, user=user, password=password, auto_bind=True)
        conn = Connection(
            server,
            user=LDAP_SEARCH_USER,
            password=LDAP_SEARCH_PASSWORD,
            authentication=SIMPLE,
            auto_bind=True
        )
        search_filter = f"(sAMAccountName={username})"
        print("conn :", conn.entries)
        conn.search(
            search_base=LDAP_BASE_DN,
            search_filter=search_filter,
            attributes=["distinguishedName"]
        )
        # print("Connexion LDAP bind réussie :", conn.bound)
        # print("Base DN :", LDAP_BASE_DN)
        # print("Filtre de recherche :", search_filter)
        # print('longueur ' +str(len(conn.entries)))
        # print("Résultats :", conn.entries)
        if len(conn.entries) != 1:
            print("Utilisateur introuvable ou doublon")
            return False

        user_dn = conn.entries[0].distinguishedName.value

 
        user_conn = Connection(server, user=user_dn, password=password, auto_bind=True)
        print(user_conn)
        return user_conn.bound
    
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.error(f"LDAP Auth failed: {e}")
        print(f"LDAP Auth failed: {e}")
        return False


def get_client_ip(request: Request) -> str:
    """
    Récupère l'adresse IP du client à partir de la requête
    Gère les proxies et load balancers (X-Forwarded-For, X-Real-IP)
    """
    # Vérifier les en-têtes de proxy
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        # Prendre la première IP (client original)
        return forwarded_for.split(",")[0].strip()
    
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip.strip()
    
    # IP directe du client
    client_host = getattr(request.client, "host", "unknown")
    return client_host if client_host else "unknown"