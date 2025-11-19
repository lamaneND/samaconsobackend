from fastapi import APIRouter, Body, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from sqlalchemy import or_,and_
from typing import List
from datetime import datetime, timedelta
from app.models.models import User, UserSession
from app.database import get_db_samaconso
from app.auth import *
from app.config import REFRESH_TOKEN_EXPIRE_DAYS
from app.schemas.user_schemas import *
from app.logging_config import get_logger, log_api_request, log_security

logger = get_logger(__name__)
auth_router = APIRouter(prefix="/auth", tags=["Auth"])



# @auth_router.post("/token")
# def loginEmail(login_request: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db_samaconso)):

#     if login_request.username and login_request.password:
#         # Authenticate with login & password
#         user = db.query(User).filter(or_(User.login == login_request.username,User.phoneNumber==login_request.username)).first()
#         if not user or not verify_password(login_request.password, user.password) or not verify_password(login_request.password, user.codePin) :
#               raise HTTPException(status_code=400, detail="Invalid login or password")
        

#     else:
#         raise HTTPException(status_code=400, detail="Invalid login method")

#     # Generate JWT token
#     access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
#     access_token = create_access_token(data={"sub": str(user.id)}, expires_delta=access_token_expires)

#     return {"access_token": access_token, "token_type": "bearer"}



@auth_router.post("/token", summary="Login with OAuth2")
def login_with_oauth2(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db_samaconso),
    request: Request = None
):
    logger.info(f"🔐 Login attempt | Username: {form_data.username[:20]}... | Method: OAuth2")
    log_api_request("/auth/token", "POST")
    
    username = form_data.username
    password = form_data.password
    client_ip = request.client.host if request and request.client else "unknown"

    if username and password:
        # Authenticate with login & password
        user = db.query(User).filter(or_(User.login == username,User.phoneNumber==username)).first()
        if not user:
            logger.warning(f"⚠️ Login failed - User not found | Username: {username} | IP: {client_ip}")
            log_security("User not found", None, client_ip, f"Username: {username}")
            raise HTTPException(status_code=400, detail="Invalid login or password")
        if user.login == username:
        # Password-based authentication
            if not verify_password(password, user.password):
                logger.warning(f"⚠️ Login failed - Invalid password | User ID: {user.id} | IP: {client_ip}")
                log_security("Invalid password", user.id, client_ip, f"Username: {username}")
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
        elif user.phoneNumber == username:
        # Code-based authentication
            if not verify_password(password, user.codePin):
                logger.warning(f"⚠️ Login failed - Invalid PIN code | User ID: {user.id} | IP: {client_ip}")
                log_security("Invalid PIN code", user.id, client_ip, f"Phone: {username}")
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
            user.code = None  # Clear OTP after successful login
        else:
            logger.error(f"❌ Login failed - Unexpected condition | User ID: {user.id} | IP: {client_ip}")
            log_security("Unexpected login condition", user.id, client_ip, f"Username: {username}")
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid login method")


    else:
        logger.error(f"❌ Login failed - Invalid method | Username: {username} | IP: {client_ip}")
        log_security("Invalid login method", None, client_ip, f"Username: {username}")
        raise HTTPException(status_code=400, detail="Invalid login method")

    # Générer la paire access + refresh token
    access_token, refresh_token = create_token_pair(user.id)
    
    # Sauvegarder le refresh token en base (hashé)
    save_refresh_token(db, user.id, refresh_token, device_model=None, fcm_token=None)
    
    # Log de succès
    logger.info(f"✅ Login successful | User ID: {user.id} | Username: {username} | IP: {client_ip}")
    log_security("Successful login", user.id, client_ip, f"Method: OAuth2, Username: {username}")

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer"
    }


@auth_router.post("/token-json", summary="Login with json")
def login_with_json(
    json_data: UserLoginSchema = Body(...),
    db: Session = Depends(get_db_samaconso)
):
    #logger.debug(f"Received json data: username={json_data.username}, password={json_data.password}")

    username = json_data.username
    password = json_data.password

    if username and password:
        # Authenticate with login & password
        user = db.query(User).filter(or_(User.login == username,User.phoneNumber==username)).first()
        if not user:
        
            raise HTTPException(status_code=404, detail="Compte inexistant")
        if user.login == username:
        # Password-based authentication
            if not verify_password(password, user.password):
             #   logger.debug("Password verification failed")
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
        elif user.phoneNumber == username:
        # Code-based authentication
            if not verify_password(password, user.codePin):
              #  logger.debug("Code verification failed")
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
            user.codePin = None  # Clear OTP after successful login
        else:
           # logger.debug("Unexpected login condition")
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid login method")


    else:
        raise HTTPException(status_code=400, detail="Invalid login method")

    # Générer la paire access + refresh token
    access_token, refresh_token = create_token_pair(user.id)
    
    # Récupérer device_model et fcm_token si fournis
    device_model = getattr(json_data, 'device_model', None)
    fcm_token = getattr(json_data, 'fcm_token', None)
    
    # Sauvegarder le refresh token en base (hashé)
    save_refresh_token(db, user.id, refresh_token, device_model=device_model, fcm_token=fcm_token)

    return {
        "status_code": status.HTTP_200_OK,
        "user": user,
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer"
    }


@auth_router.post("/token-json-v2", summary="Login with json v2")
def login_with_json_v2(
    json_data: UserLoginSchema = Body(...),
    db: Session = Depends(get_db_samaconso)
):
    #logger.debug(f"Received json data: username={json_data.username}, password={json_data.password}")

    username = json_data.username
    password = json_data.password

    if username and password:
        # Authenticate with login & password
        user = db.query(User).filter(or_(User.login == username,User.phoneNumber==username)).first()
        if not user:
        
            raise HTTPException(status_code=400, detail="Invalid login or password")
        if user.login == username:
            if user.ldap:
        # Password-based authentication
                connected = authenticate_ldap(username=username,password=password)
                if not connected:
                #   logger.debug("Password verification failed")
                    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
        
            elif not verify_password(password, user.password):
           # logger.debug("Unexpected login condition")
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid login method")

        # Password-based authentication
           # if not verify_password(password, user.password):
             #   logger.debug("Password verification failed")
                #raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
        elif user.phoneNumber == username:
        # Code-based authentication
            if not verify_password(password, user.codePin):
              #  logger.debug("Code verification failed")
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
            user.codePin = None  # Clear OTP after successful login
        else:
           # logger.debug("Unexpected login condition")
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid login method")


    else:
        raise HTTPException(status_code=400, detail="Invalid login method")

    # Générer la paire access + refresh token
    access_token, refresh_token = create_token_pair(user.id)
    
    # Récupérer device_model et fcm_token si fournis
    device_model = getattr(json_data, 'device_model', None)
    fcm_token = getattr(json_data, 'fcm_token', None)
    
    # Sauvegarder le refresh token en base (hashé)
    save_refresh_token(db, user.id, refresh_token, device_model=device_model, fcm_token=fcm_token)

    return {
        "status_code": status.HTTP_200_OK,
        "user": user,
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer"
    }




@auth_router.post("/ldap-json", summary="Login with ldap")
def login_with_ldap(
    json_data: UserLoginSchema = Body(...),
    db: Session = Depends(get_db_samaconso)
):
    #logger.debug(f"Received json data: username={json_data.username}, password={json_data.password}")

    username =  json_data.username
    print(username)
    password = json_data.password

    if username and password:
        # Authenticate with login & password
        user = db.query(User).filter(User.login == username).first()
        if not user:
        
            raise HTTPException(status_code=400, detail="Invalid login or password")
        if user.ldap:
        # Password-based authentication
            connected = authenticate_ldap(username=username,password=password)
            if not connected:
             #   logger.debug("Password verification failed")
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
      
        elif not verify_password(password, user.password):
           # logger.debug("Unexpected login condition")
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid login method")


    else:
        raise HTTPException(status_code=400, detail="Invalid login method")

    # Générer la paire access + refresh token
    access_token, refresh_token = create_token_pair(user.id)
    
    # Récupérer device_model et fcm_token si fournis
    device_model = getattr(json_data, 'device_model', None)
    fcm_token = getattr(json_data, 'fcm_token', None)
    
    # Sauvegarder le refresh token en base (hashé)
    save_refresh_token(db, user.id, refresh_token, device_model=device_model, fcm_token=fcm_token)

    return {
        "status_code": status.HTTP_200_OK,
        "user": user,
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer"
    }


@auth_router.post("/refresh", summary="Refresh access token")
def refresh_access_token(
    token_data: RefreshTokenSchema = Body(...),
    db: Session = Depends(get_db_samaconso),
    request: Request = None
):
    """
    Rafraîchit un access token expiré en utilisant un refresh token valide
    Retourne un nouveau access_token et un nouveau refresh_token
    """
    logger.info("🔄 Refresh token request")
    log_api_request("/auth/refresh", "POST")
    
    refresh_token = token_data.refresh_token
    client_ip = request.client.host if request and request.client else "unknown"
    
    if not refresh_token:
        logger.warning(f"⚠️ Refresh failed - No refresh token provided | IP: {client_ip}")
        log_security("Refresh token missing", None, client_ip, "No refresh token")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Refresh token is required"
        )
    
    # Chercher une session valide avec ce refresh token
    # On doit parcourir toutes les sessions car le token est hashé
    active_sessions = db.query(UserSession).filter(
        and_(
            UserSession.is_active == True,
            UserSession.refresh_token_hash.isnot(None),
            UserSession.refresh_token_expires_at > datetime.now()
        )
    ).all()
    
    valid_session = None
    for session in active_sessions:
        if session.refresh_token_hash and verify_refresh_token(refresh_token, session.refresh_token_hash):
            valid_session = session
            break
    
    if not valid_session:
        logger.warning(f"⚠️ Refresh failed - Invalid refresh token | IP: {client_ip}")
        log_security("Invalid refresh token", None, client_ip, "Token verification failed")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token"
        )
    
    # Vérifier que l'utilisateur existe toujours
    user = db.query(User).filter(User.id == valid_session.user_id).first()
    if not user or not user.is_activate:
        logger.warning(f"⚠️ Refresh failed - User not found or inactive | User ID: {valid_session.user_id} | IP: {client_ip}")
        log_security("Refresh failed - user inactive", valid_session.user_id, client_ip, "User inactive")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive"
        )
    
    # Générer une nouvelle paire de tokens
    new_access_token, new_refresh_token = create_token_pair(user.id)
    
    # Remplacer l'ancien refresh token par le nouveau (rotation de tokens)
    valid_session.refresh_token_hash = hash_refresh_token(new_refresh_token)
    valid_session.refresh_token_expires_at = datetime.now() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    valid_session.last_login = datetime.now()
    db.commit()
    
    logger.info(f"✅ Token refreshed successfully | User ID: {user.id} | IP: {client_ip}")
    log_security("Token refreshed", user.id, client_ip, "Refresh successful")
    
    return {
        "access_token": new_access_token,
        "refresh_token": new_refresh_token,
        "token_type": "bearer"
    }


@auth_router.post("/logout", summary="Logout and revoke refresh token")
def logout(
    token_data: RefreshTokenOptionalSchema = Body(...),
    db: Session = Depends(get_db_samaconso),
    request: Request = None,
    current_user: User = Depends(get_current_user)
):
    """
    Déconnecte un utilisateur en révoquant son refresh token
    Si aucun refresh_token n'est fourni, révoque toutes les sessions de l'utilisateur
    """
    logger.info(f"🚪 Logout request | User ID: {current_user.id}")
    log_api_request("/auth/logout", "POST")
    
    refresh_token = token_data.refresh_token if token_data.refresh_token else None
    client_ip = request.client.host if request and request.client else "unknown"
    
    # Révoquer le refresh token (ou tous les tokens si None)
    revoked = revoke_refresh_token(db, current_user.id, refresh_token)
    
    if revoked:
        logger.info(f"✅ Logout successful | User ID: {current_user.id} | IP: {client_ip}")
        log_security("Logout successful", current_user.id, client_ip, "Token revoked")
        return {
            "status_code": status.HTTP_200_OK,
            "message": "Logout successful",
            "tokens_revoked": True
        }
    else:
        logger.warning(f"⚠️ Logout - No tokens to revoke | User ID: {current_user.id} | IP: {client_ip}")
        return {
            "status_code": status.HTTP_200_OK,
            "message": "No active tokens found",
            "tokens_revoked": False
        }
