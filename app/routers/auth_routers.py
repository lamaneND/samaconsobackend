from fastapi import APIRouter, Body, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from sqlalchemy import or_,and_
from typing import List
from app.models.models import User, UserSession
from app.database import get_db_samaconso
from app.auth import *
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

    # Générer le token JWT
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(data={"sub": str(user.id)}, expires_delta=access_token_expires)
    
    # Log de succès
    logger.info(f"✅ Login successful | User ID: {user.id} | Username: {username} | IP: {client_ip}")
    log_security("Successful login", user.id, client_ip, f"Method: OAuth2, Username: {username}")

    return {"access_token": access_token, "token_type": "bearer"}


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

    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(data={"sub": str(user.id)}, expires_delta=access_token_expires)

    # if json_data.fcm_token and json_data.device_model:
    #     fcm_token = json_data.fcm_token
    #     device_model = json_data.device_model
    #     user_session = UserSession(fcm_token=fcm_token,device_model=device_model,
    #                                user_id=user.id,jti=jti,expires_at=datetime.now() + access_token_expires)
    # user_session = UserSession(
    #     user_id=user.id,
    #     jti=jti,
    #     fcm_token=json_data.fcm_token if hasattr(json_data, 'fcm_token') else None,
    #     device_model=json_data.device_model if hasattr(json_data, 'device_model') else None,
    #     expires_at=datetime.now() + access_token_expires
    # )
    # db.add(user_session)
    # db.commit()
    # db.refresh(user_session)

    # user = db.query(User).filter(or_(User.login == username,User.phoneNumber==username)).first()
    return {"status_code":status.HTTP_200_OK,"user":user,"access_token": access_token, "token_type": "bearer"}


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

    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(data={"sub": str(user.id)}, expires_delta=access_token_expires)

    return {"status_code":status.HTTP_200_OK,"user":user,"access_token": access_token, "token_type": "bearer"}




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

    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(data={"sub": str(user.id)}, expires_delta=access_token_expires)
    return {"status_code":status.HTTP_200_OK,"user":user,"access_token": access_token, "token_type": "bearer"}
