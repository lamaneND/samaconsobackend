from typing import Counter
from fastapi import APIRouter, Depends, HTTPException,status
import json
from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session,joinedload
from app.models.models import Agence, Compteur, Notification, User, UserCompteur
from app.routers.notification_routers import  for_user_notif
from app.schemas.postpaid_schemas import NumCCParamSchema
from app.schemas.sic_schemas import TransactionsByMeterPoc
from app.schemas.user_compteur_schemas import ActivateUserCompteur, UserCompteurCreateSchema, UserCompteurCreateSchemaV2,UserCompteurUpdate,CompteurWoyofalResponseSchema,CompteurPostpaidResponseSchema
from app.database import get_db_connection_postpaid, get_db_samaconso,get_db_connection_sic
from app.cache import cache_get, cache_set, cache_delete
from app.config import CACHE_KEYS, CACHE_TTL
from app.queries import * 
import pyodbc

user_compteur_router = APIRouter(prefix="/user_compteur", tags=["UserCompteur"])

@user_compteur_router.get("/cache/inspect")
async def inspect_cache():
    """🔍 Inspection du cache pour User Compteur"""
    cache_info = {
        "entity": "user_compteur",
        "cache_keys": {
            "all_user_compteurs": CACHE_KEYS["USER_COMPTEURS"].format(user_id="all"),
            "user_specific": CACHE_KEYS["USER_COMPTEURS"].format(user_id="{user_id}"),
            "active_user_compteurs": "user_compteur:active:user:{user_id}",
        },
        "ttl_config": {
            "compteurs": f"{CACHE_TTL['COMPTEURS']}s ({CACHE_TTL['COMPTEURS']//60}min)",
        }
    }
    
    # Test de quelques clés courantes
    active_keys = []
    test_keys = [
        CACHE_KEYS["USER_COMPTEURS"].format(user_id="all"),
        "user_compteur:active:user:1",
        "user_compteur:active:user:2"
    ]
    
    for key in test_keys:
        try:
            cached = await cache_get(key)
            if cached:
                active_keys.append({
                    "key": key,
                    "size": len(cached),
                    "type": "JSON string"
                })
        except Exception:
            pass
    
    cache_info["active_keys"] = active_keys
    cache_info["total_active"] = len(active_keys)
    
    return cache_info

@user_compteur_router.post("/")
async def create(data: UserCompteurCreateSchema, db: Session = Depends(get_db_samaconso)):
    
    ##TODO: Vérifier si le numéro de téléphone de l'utilisateur est celui enregistré dans 
    ## la base du commercial, si tel est le cas faire l'ajout rendre is_active à true et mettre l'état validé
    ##Sinon les mettre en attente de validation

    db_obj = UserCompteur(**data.model_dump())
    db.add(db_obj)
    db.commit()
    db.refresh(db_obj)
    try:
        await cache_delete(CACHE_KEYS["USER_COMPTEURS"].format(user_id="all"))
        await cache_delete(CACHE_KEYS["USER_COMPTEURS"].format(user_id=db_obj.user_id))
    except Exception:
        pass
    return db_obj

@user_compteur_router.post("/ajoutercompteur")
async def createv2(data: UserCompteurCreateSchemaV2, db: Session = Depends(get_db_samaconso)):
    id_compteur:int = 0
    is_owner:bool = False
    active:bool = False
    defaut:bool = False
    user = db.query(User).filter(User.phoneNumber==data.telephone).first()
    if not user:
        HTTPException(status_code=status.HTTP_404_NOT_FOUND,detail="Utilisateur non enregistré")
    
    userCompteurExist = db.query(UserCompteur).filter(and_(UserCompteur.numero_compteur==data.numero_compteur
                                            ,UserCompteur.user_id==user.id))
    if userCompteurExist : 
         HTTPException(status_code=status.HTTP_409_CONFLICT,detail="Liaison entre utilisateur et compteur déjà enregistrée")

    ##TODO: Vérifier si le numéro de téléphone de l'utilisateur est celui enregistré dans 
    ## la base du commercial, si tel est le cas faire l'ajout rendre is_active à true et mettre l'état validé
    ##Sinon les mettre en attente de validation

    if data.type_compteur ==1:
        ##TODO: Connexion à l'api de sic et vérifier que le numéro compteur est valide
        #Sinon envoyer exception compteur non valide
        ## Si compteur existe vérifier sur quel numéro de téléphone est enregistré le compteur
        ## Si les numéros de téléphone correspondent insérer dans la table UserCompteur et l'activer
        ## Sinon l'ajouter et le rendre inactif

        compteurTrouve = verifierCompteur(data.numero_compteur,data.type_compteur)
        if compteurTrouve.status == 0:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,detail="Erreur connexion base de données")
        if compteurTrouve.status == 404:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,detail="Numero compteur incorrect")
        
        if compteurTrouve.status == 200:
            
            #Ajouter le compteur dans la base
            compteur_woyofal = db.query(Compteur).filter(and_(Compteur.numero==data.numero_compteur, Compteur.type_compteur==data.type_compteur)).first()
            if not compteur_woyofal:
                created_compteur = Compteur(numero=data.numero_compteur,type_compteur=data.type_compteur)

                db.add(created_compteur)
                db.commit()
                db.refresh(created_compteur)
                id_compteur = created_compteur.id

                try:
                    conn = get_db_connection_sic()
                    conn.execute(insertCompteur, (data.numero_compteur, data.type_compteur))
                    conn.commit()
                
                except Exception as e:
                    print(f"Erreur lors de l'ajout du compteur : {e}")
                  #  raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Erreur lors de l'ajout du compteur")
            else:
                id_compteur = compteur_woyofal.id
            if compteurTrouve.tel == data.telephone:
                is_owner= True
                active= True
                ### Voir si des users ont rajouté le compteur avant que le owner ne le fasse
                ### Si oui mettre à jour
                #updateUserCompterWhenOwnerFound(numero=data.numero_compteur,owner_id=id_owner,db=db) 
            
            ### Récupérer l'id de l'agence
            ### Mettre le nom de l'agence en minuscule et supprimer les espaces, afin de mieux faire la recheche
            agenceARechercher = compteurTrouve.agence.lower().replace(" ","")
            agenceARechercher = f"%{agenceARechercher}%"

            agence_db = db.query(Agence).filter(
                func.replace(func.lower(Agence.nom)," ","").like(agenceARechercher)
            ).first()

            userACompteur  = db.query(UserCompteur).filter(UserCompteur.user_id==user.id).all()
            if len(userACompteur)==0:
                defaut=True

            userCompteur = UserCompteurCreateSchema(
            compteur_id=id_compteur,
            user_id=user.id,
            autorise_par=None,
            active_par=None,
            etat_id=None,
            nom_client = compteurTrouve.nom_client,
            est_active=active,
            tarif=compteurTrouve.tarif,
            id_client=compteurTrouve.id_client,
            est_proprietaire=is_owner,
            num_compte_contrat=None,
            poc=compteurTrouve.poc,
            adresse=compteurTrouve.adresse,
            default=defaut,
            id_agence = agence_db.id,
            nom_agence=agence_db.nom_corrige,
            numero_compteur=data.numero_compteur,
            type_compteur=data.type_compteur
            )
            
            userCompteurDbObj = UserCompteur(**userCompteur.model_dump())
            db.add(userCompteurDbObj)
            db.commit()
            db.refresh(userCompteurDbObj)

            #Envoyer notification au propriétaire
            if(is_owner==False):

              
                user_compteur_owner = db.query(UserCompteur).filter(and_(UserCompteur.est_proprietaire==True,UserCompteur.numero_compteur==data.numero_compteur,
                                                                         UserCompteur.poc==compteurTrouve.poc)).first()
                if(user_compteur_owner):

                    title:str = f"{user.firstName} {user.lastName}"
                    body :str = f"souhaite accéder au compteur n° {data.numero_compteur} situé à adresse : {compteurTrouve.adresse}"
                    type_notification_id:int = 10
                    # Send notification via Celery (async)
                    for_user_notif(type_notification_id=type_notification_id,title=title,body=body,for_user_id=user_compteur_owner.user_id,event_id=userCompteurDbObj.id,db=db)

                
            
            return userCompteurDbObj

    ### Ajout compteur postpaiement
    if data.type_compteur ==2:
        ##TODO: Connexion à l'api de sic et vérifier que le numéro compteur est valide
        #Sinon envoyer exception compteur non valide
        ## Si compteur existe vérifier sur quel numéro de téléphone est enregistré le compteur
        ## Si les numéros de téléphone correspondent insérer dans la table UserCompteur et l'activer
        ## Sinon l'ajouter et le rendre inactif

        compteurPostpaidTrouve = verifierCompteur(data.numero_compteur,data.type_compteur)
        if compteurPostpaidTrouve.status == 0:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,detail="Erreur connexion base de données")
        if compteurPostpaidTrouve.status == 404:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,detail="Numero compteur incorrect")
        
        if compteurPostpaidTrouve.status == 200:
            
            #Ajouter le compteur dans la base
            compteur_postpaid= db.query(Compteur).filter(and_(Compteur.numero==data.numero_compteur, Compteur.type_compteur==data.type_compteur)).first()
            if not compteur_postpaid:
                compteur_postpaid = Compteur(numero=data.numero_compteur,type_compteur=data.type_compteur)
                db.add(compteur_postpaid)
                db.commit()
                db.refresh(compteur_postpaid)
                id_compteur = compteur_postpaid.id

                try:
                    conn = get_db_connection_sic()
                    conn.execute(insertCompteur, (data.numero_compteur, data.type_compteur))
                    conn.commit()
                
                except Exception as e:
                    print(f"Erreur lors de l'ajout du compteur : {e}")
                    #raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Erreur lors de l'ajout du compteur")
            else:
                id_compteur = compteur_postpaid.id
            if compteurPostpaidTrouve.tel == data.telephone:
                is_owner= True
                active= True
                ### Voir si des users ont rajouté le compteur avant que le owner ne le fasse
                ### Si oui mettre à jour
                #updateUserCompterWhenOwnerFound(numero=data.numero_compteur,owner_id=id_owner,db=db) 
        

        ### Récupération de l'id de l'agence : 



        userACompteur  = db.query(UserCompteur).filter(UserCompteur.user_id==user.id).all()
        if len(userACompteur)==0:
            defaut=True
        
        agenceARechercher = compteurPostpaidTrouve.agence.lower().replace(" ","")
        agenceARechercher = f"%{agenceARechercher}%"

        agence_db = db.query(Agence).filter(
                func.replace(func.lower(Agence.nom)," ","").like(agenceARechercher)
            ).first()

        agence_id:int = None
        agence_nom:str = None

        if agence_db:
            agence_id=agence_db.id
            agence_nom = agence_db.nom_corrige

        userCompteur = UserCompteurCreateSchema(
        compteur_id=id_compteur,
        user_id=user.id,
        autorise_par=None,
        active_par=None,
        etat_id=None,
        tarif=compteurPostpaidTrouve.tarif,
        nom_client = compteurPostpaidTrouve.nom_client,
        est_active=active,
        id_client=None,
        est_proprietaire=is_owner,
        num_compte_contrat=compteurPostpaidTrouve.numCC,
        poc=None,
        id_agence = agence_id,
        nom_agence=agence_nom,
        adresse=compteurPostpaidTrouve.adresse,
        default=defaut,
        numero_compteur=data.numero_compteur,
        type_compteur=data.type_compteur
        )
        
        userCompteurDbObj = UserCompteur(**userCompteur.model_dump())
        db.add(userCompteurDbObj)
        db.commit()
        db.refresh(userCompteurDbObj)

        if(is_owner==False):

              
            user_compteur_owner = db.query(UserCompteur).filter(and_(UserCompteur.est_proprietaire==True,UserCompteur.numero_compteur==data.numero_compteur)).first()
            if(user_compteur_owner):

                title:str = f"{user.firstName} {user.lastName}"
                body :str = f"souhaite accéder au compteur n° {data.numero_compteur} situé à adresse : {compteurTrouve.adresse}"
                type_notification_id:int = 10
                # Send notification via Celery (async)
                for_user_notif(type_notification_id=type_notification_id,title=title,body=body,for_user_id=user_compteur_owner.user_id,event_id=userCompteurDbObj.id,db=db)

                

        return userCompteurDbObj



@user_compteur_router.get("/")
async def list_all(db: Session = Depends(get_db_samaconso)):
    key_all = CACHE_KEYS["USER_COMPTEURS"].format(user_id="all")
    try:
        cached = await cache_get(key_all)
        if cached:
            return json.loads(cached)
    except Exception:
        pass
    rows = db.query(UserCompteur).order_by(UserCompteur.created_at.desc()).all()
    payload = [
        {
            "id": r.id,
            "compteur_id": r.compteur_id,
            "user_id": r.user_id,
            "est_proprietaire": r.est_proprietaire,
            "etat_id": r.etat_id,
            "est_active": r.est_active,
            "numero_compteur": r.numero_compteur,
            "type_compteur": r.type_compteur,
            "created_at": r.created_at.strftime("%d/%m/%Y %H:%M:%S") if r.created_at else None,
            "updated_at": r.updated_at.strftime("%d/%m/%Y %H:%M:%S") if r.updated_at else None,
        }
        for r in rows
    ]
    try:
        await cache_set(key_all, json.dumps(payload), ttl_seconds=CACHE_TTL["COMPTEURS"])
    except Exception:
        pass
    return payload


@user_compteur_router.get("/usercompteur/{id}")
async def list_all_user_compteur(id:int,db: Session = Depends(get_db_samaconso)):
    key = CACHE_KEYS["USER_COMPTEURS"].format(user_id=id)
    try:
        cached = await cache_get(key)
        if cached:
            return {"compteurs": json.loads(cached)}
    except Exception:
        pass
    compteurs =  db.query(UserCompteur).filter(UserCompteur.user_id==id).order_by(UserCompteur.created_at.desc()).all()
    payload = [
        {
            "id": r.id,
            "compteur_id": r.compteur_id,
            "user_id": r.user_id,
            "est_proprietaire": r.est_proprietaire,
            "etat_id": r.etat_id,
            "est_active": r.est_active,
            "numero_compteur": r.numero_compteur,
            "type_compteur": r.type_compteur,
            "created_at": r.created_at.strftime("%d/%m/%Y %H:%M:%S") if r.created_at else None,
            "updated_at": r.updated_at.strftime("%d/%m/%Y %H:%M:%S") if r.updated_at else None,
        }
        for r in compteurs
    ]
    try:
        await cache_set(key, json.dumps(payload), ttl_seconds=CACHE_TTL["COMPTEURS"])
    except Exception:
        pass
    return {"compteurs":payload}

@user_compteur_router.get("/usercompteuractive/{id}")
async def list_all_user_compteur_active(id:int,db: Session = Depends(get_db_samaconso)):
    key = f"user_compteur:active:user:{id}"
    try:
        cached = await cache_get(key)
        if cached:
            return {"compteurs": json.loads(cached)}
    except Exception:
        pass
        
    compteurs =  db.query(UserCompteur).filter(and_(UserCompteur.user_id==id,UserCompteur.est_active==True)).options(
        joinedload(UserCompteur.user),joinedload(UserCompteur.active_par_user),joinedload(UserCompteur.autorise_par_user)
    ).order_by(UserCompteur.created_at.desc()).all()
    
    # Sérialisation manuelle des objets avec relations
    payload = []
    for r in compteurs:
        compteur_data = {
            "id": r.id,
            "compteur_id": r.compteur_id,
            "user_id": r.user_id,
            "est_proprietaire": r.est_proprietaire,
            "etat_id": r.etat_id,
            "est_active": r.est_active,
            "numero_compteur": r.numero_compteur,
            "type_compteur": r.type_compteur,
            "created_at": r.created_at.strftime("%d/%m/%Y %H:%M:%S") if r.created_at else None,
            "updated_at": r.updated_at.strftime("%d/%m/%Y %H:%M:%S") if r.updated_at else None,
        }
        # Ajout sécurisé des relations si elles existent
        if r.user:
            compteur_data["user"] = {
                "id": r.user.id,
                "firstName": r.user.firstName,
                "lastName": r.user.lastName,
                "phoneNumber": r.user.phoneNumber
            }
        payload.append(compteur_data)
    
    try:
        await cache_set(key, json.dumps(payload), ttl_seconds=CACHE_TTL["COMPTEURS"])
    except Exception:
        pass
        
    return {"compteurs":payload}

@user_compteur_router.get("/usercompteurinactive/{id}")
async def list_all_user_compteur_inactive(id:int,db: Session = Depends(get_db_samaconso)):
    compteurs =  db.query(UserCompteur).filter(and_(UserCompteur.user_id==id,UserCompteur.est_active==False)).order_by(UserCompteur.created_at.desc()).all()
    return {"compteurs":compteurs}


@user_compteur_router.put("/{user_compteur_id}")
async def update_etat(user_compteur_id:int,compteur_update : UserCompteurUpdate,db: Session = Depends(get_db_samaconso)):
    user_compteur_db = db.query(UserCompteur).filter(UserCompteur.id == user_compteur_id).first()
    if not user_compteur_db:
        raise HTTPException(status_code=404, detail="User Compteur not found")
    for key, value in compteur_update.model_dump(exclude_unset=True).items():
        setattr(user_compteur_db, key, value)
    db.commit()
    db.refresh(user_compteur_db)
    try:
        await cache_delete(CACHE_KEYS["USER_COMPTEURS"].format(user_id="all"))
        await cache_delete(CACHE_KEYS["USER_COMPTEURS"].format(user_id=user_compteur_db.user_id))
    except Exception:
        pass
    return user_compteur_db

@user_compteur_router.delete("/{user_compteur_id}")
async def delete_etat(user_compteur_id:int,db: Session = Depends(get_db_samaconso)):
    user_compteur_db = db.query(UserCompteur).filter(UserCompteur.id == user_compteur_id).first()
    if not user_compteur_db:
        raise HTTPException(status_code=404, detail="User Compteur not found")
    uid = user_compteur_db.user_id
    db.delete(user_compteur_db)
    db.commit()
    try:
        await cache_delete(CACHE_KEYS["USER_COMPTEURS"].format(user_id="all"))
        await cache_delete(CACHE_KEYS["USER_COMPTEURS"].format(user_id=uid))
    except Exception:
        pass
    return {"message": "Etat deleted successfully"}


@user_compteur_router.get("usercompteurtransactionsmens/{user_id}")
async def recup_user_compteur_cons_trans(user_id:int,db:Session=Depends(get_db_samaconso)):
    # user_compteur_db = db.query(UserCompteur).filter(and_(UserCompteur.user_id == user_id,UserCompteur.est_active==True)).first()
    user_compteur_db = db.query(UserCompteur).filter(and_(UserCompteur.user_id==user_id,UserCompteur.est_active==True)).first()
    if not user_compteur_db:
        return {"status_code":404, "detail":"Cet utilisateur n'a pas de compteur actif"}
    compteurs = db.query(UserCompteur).filter(and_(UserCompteur.user_id==user_id,UserCompteur.est_active==True)).all()
    #Récupération des consommations suivants le type de compteur :
    if user_compteur_db.type_compteur ==1 : 
        meter=user_compteur_db.numero_compteur
        poc=user_compteur_db.poc
        top_10_woyofal_transactions=get_top_10_woyofal_transactions(data=TransactionsByMeterPoc(meter=meter,poc=poc))
        consommations_mensuelles_woyofal = get_woyofal_transactions_month(trans=TransactionsByMeterPoc(meter=meter,poc=poc))
       
        return {"status":status.HTTP_200_OK,"type_compteur":user_compteur_db.type_compteur,"compteur":user_compteur_db,"top_10_transactions":top_10_woyofal_transactions,"consommations_mensuelles":consommations_mensuelles_woyofal,"factures_annee_en_cours":[],"six_dernieres_factures":[],"compteurs":compteurs}
    elif user_compteur_db.type_compteur ==2 :
        numCC = user_compteur_db.numero_compteur
        factures_annee_en_cours = get_postpaid_bills_current_year(numCC)
        six_dernieres_factures = get_six_dernieres_factures(numCC)
        return {"status":status.HTTP_200_OK,"type_compteur":user_compteur_db.type_compteur,"compteur":user_compteur_db,"top_10_transactions":[],"consommations_mensuelles":[],"factures_annee_en_cours":factures_annee_en_cours,"six_dernieres_factures":six_dernieres_factures,"compteurs":compteurs}
    return

@user_compteur_router.get("compteurtransactionsmens/{user_compteur_id}")
async def recup_compteur_cons_trans(user_compteur_id:int,db:Session=Depends(get_db_samaconso)):
    user_compteur_db = db.query(UserCompteur).filter(and_(UserCompteur.id == user_compteur_id,UserCompteur.est_active==True)).first()
    if not user_compteur_db:
        raise HTTPException(status_code=404, detail="Id not found")
    compteurs = db.query(UserCompteur).filter(and_(UserCompteur.user_id==user_compteur_db.user_id,UserCompteur.est_active==True)).all()
    #Récupération des consommations suivants le type de compteur :
    if user_compteur_db.type_compteur ==1 : 
        meter=user_compteur_db.numero_compteur
        poc=user_compteur_db.poc
        top_10_woyofal_transactions=get_top_10_woyofal_transactions(data=TransactionsByMeterPoc(meter=meter,poc=poc))
        consommations_mensuelles_woyofal = get_woyofal_transactions_month(trans=TransactionsByMeterPoc(meter=meter,poc=poc))

        return {"status":status.HTTP_200_OK,"type_compteur":user_compteur_db.type_compteur,"compteur":user_compteur_db,"top_10_transactions":top_10_woyofal_transactions,"consommations_mensuelles":consommations_mensuelles_woyofal,"factures_annee_en_cours":[],"six_dernieres_factures":[],"compteurs":compteurs}
    elif user_compteur_db.type_compteur ==2 :
        numCC = user_compteur_db.numero_compteur
        factures_annee_en_cours = get_postpaid_bills_current_year(numCC)
        six_dernieres_factures = get_six_dernieres_factures(numCC)
        return {"status":status.HTTP_200_OK,"type_compteur":user_compteur_db.type_compteur,"compteur":user_compteur_db,"top_10_transactions":[],"consommations_mensuelles":[],"factures_annee_en_cours":factures_annee_en_cours,"six_dernieres_factures":six_dernieres_factures,"compteurs":compteurs}
    return

@user_compteur_router.get("/useragence/{user_id}")
async def list_all_for_user(user_id:int,db: Session = Depends(get_db_samaconso)):
    user = db.query(User).filter(User.id==user_id).first()
    if(user):
        if user.role==7:
             return db.query(UserCompteur).all()
        
        if user.role==2:
            return db.query(UserCompteur).filter(UserCompteur.id_agence==user.id_agence).all()
    
    return 

@user_compteur_router.put("activerCompteur/{user_compteur_id}")
async def validerCompteur(user_compteur_id:int,data:ActivateUserCompteur,db:Session=Depends(get_db_samaconso)):
    user_db = db.query(User).filter(and_(User.id == data.activated_by_user)).first()
    if user_db is None:
        return {"status":status.HTTP_404_NOT_FOUND,"detail":"user not found"}
    user_compteur_db = db.query(UserCompteur).filter(and_(UserCompteur.id == data.user_compteur_id)).first()
    if user_compteur_db is None:
        return {"status":status.HTTP_404_NOT_FOUND,"detail":"user compteur not found"}
    user_compteur_db.est_active = data.activate
    user_compteur_db.active_par = data.activated_by_user

    db.commit()
    db.refresh(user_compteur_db)

    from_user = db.query(User).filter(User.id==user_compteur_db.user_id).first()

    notifications = db.query(Notification).filter(and_(Notification.event_id==user_compteur_db.id,Notification.type_notification_id==10)).all()
    
    for notification in notifications:
        notification.type_notification_id=13
        db.commit()
        db.refresh(notification)

    if(from_user):

                title:str = f"Compteur validé"
                body :str = f"compteur n° {user_compteur_db.numero_compteur} situé à adresse : {user_compteur_db.adresse}"
                type_notification_id:int = 13
                # Send notification via Celery (async)
                for_user_notif(type_notification_id=type_notification_id,title=title,body=body,for_user_id=from_user.id,event_id=user_compteur_db.id,db=db)

    return {"status":status.HTTP_200_OK,"user_compteur":user_compteur_db}
 
@user_compteur_router.get("compteuraccordpar/{user_id}")
async def compteur_accorde_par_user(user_id:int,db:Session=Depends(get_db_samaconso)):

    user_compteurs = db.query(UserCompteur).filter(or_(UserCompteur.active_par==user_id,UserCompteur.autorise_par==user_id)).order_by(UserCompteur.created_at.desc()).options( joinedload(UserCompteur.user)).all()
    
    if not user_compteurs:
        return {"status":status.HTTP_404_NOT_FOUND,"message":"Pas de compteurs accordés"}
    
    return {"status":status.HTTP_200_OK,"compteurs":user_compteurs}



def  verifierCompteur(numero:str,type:int):
       
        if type==1:
            conn = get_db_connection_sic()
            if not conn:
                return CompteurWoyofalResponseSchema(status=0,tel=None,poc=None,id_client=None,adresse=None,tarif=None,nom_client=None,agence=None)
            
            try:
                cursor = conn.cursor()
                result = cursor.execute(verifierSiCompteurWoyofalExiste,(numero,))
            
                #compteur = result.fetchone()
                row = result.fetchone()
                if not row:
                    return CompteurWoyofalResponseSchema(status=404,tel=None,poc=None,id_client=None,adresse=None,tarif=None,nom_client=None,agence=None)
                compteur = {col[0]: value for col, value in zip(cursor.description, row)}            

                return CompteurWoyofalResponseSchema(status=200,tel=compteur["tel"],poc=compteur["poc"],id_client=compteur["id_client"],adresse=compteur["adresse"],tarif=compteur["usage"],nom_client=compteur["nomClient"],agence=compteur["agence"])
            
            except pyodbc.Error as e:
                print(f"Erreur DB : {e}")
                return CompteurWoyofalResponseSchema(status=0,tel=None,poc=None,id_client=None,tarif=None,nom_client=None,agence=None)
            
            finally:
                cursor.close()
                conn.close()
        
        elif type==2:
            conn = get_db_connection_sic()
            if not conn:
                return CompteurPostpaidResponseSchema(status=0,tel=None,numCC=None,id_partenaire=None,adresse=None,tarif=None,nom_client=None,agence=None)
            
            try:
                cursor = conn.cursor()
                result = cursor.execute(verifierSiCompteurClassiqueExiste,(numero))
            
                #compteur = result.fetchone()
                row = result.fetchone()
                if not row:
                    return CompteurPostpaidResponseSchema(status=404,tel=None,numCC=None,id_partenaire=None,adresse=None,tarif=None,nom_client=None,agence=None)
                compteur = {col[0]: value for col, value in zip(cursor.description, row)}            

                return CompteurPostpaidResponseSchema(status=200,tel=compteur["TELEPHONE"],numCC=compteur["COMPTE CONTRAT"],id_partenaire=compteur["N PARTENAIRE"],adresse=compteur["ADRESSE"],tarif=compteur["TARIF"],nom_client=compteur["CLIENT"],agence=compteur["AGENCE"])
            
            except pyodbc.Error as e:
                print(f"Erreur DB : {e}")
                return  CompteurPostpaidResponseSchema(status=0,tel=None,numCC=None,id_partenaire=None,adresse=None,tarif=None,nom_client=None,agence=None)
            
            finally:
                cursor.close()
                conn.close()


def verifierCompteurClassique():
    pass


def updateUserCompterWhenOwnerFound(numero:str,owner_id:int,db: Session):
    user = db.query(User).filter(User.id==owner_id).first()
    if not user:
        return 
    userCompteur = db.query(UserCompteur).filter(UserCompteur.numero==numero).first()
    if userCompteur.owner_id is None:
        userCompteur.owner_id = owner_id
        db.commit()
        db.refresh(userCompteur)


    

def get_top_10_woyofal_transactions(data:TransactionsByMeterPoc):

    conn = get_db_connection_sic()
    if not conn:
        return {"error": "Database connection failed"}
    
    try:
        cursor = conn.cursor()
        # Example SELECT query
        cursor.execute(top10TransactionsQuery,(data.meter,data.poc))
        rows = cursor.fetchall()
        if not rows:
            return
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
       
        
        return transactions
    
    except pyodbc.Error as e:
        return 
    
    finally:
        cursor.close()
        conn.close()




def get_woyofal_transactions_month(trans:TransactionsByMeterPoc):


    conn = get_db_connection_sic()
    if not conn:
        return {"error": "Database connection failed"}
    
    try:
        cursor = conn.cursor()
        # Example SELECT query
        cursor.execute(getTransactionsByMonthMeterPoc,(trans.meter,trans.poc))
        rows = cursor.fetchall()
        if not rows:
            return
        columns = [column[0] for column in cursor.description]
        transactions= [dict(zip(columns, row)) for row in rows]
        montant_global = sum(transaction["Total TTC"] for transaction in transactions)
        energie_globale = sum(transaction["Total énergie"] for transaction in transactions) 


        # Convert results to a list of dictionaries
       # customer = [{ "first name": row.CUSTOMER_FirstNAME, "name": row.CUSTOMER_NAME} for row in rows]
       
        
        return transactions
    
    except pyodbc.Error as e:
        return
    
    finally:
        cursor.close()
        conn.close()



def get_postpaid_bills_current_year(numCC:str):

    conn = get_db_connection_postpaid()
    if not conn:
        return {"error": "Database connection failed"}
    
    try:
        cursor = conn.cursor()
        # Example SELECT query
        cursor.execute(getBillsByMonth,(numCC,))
        rows = cursor.fetchall()
        if not rows:
            return
        columns = [column[0] for column in cursor.description]
        transactions = [dict(zip(columns, row)) for row in rows] 
        
        return transactions
    
    except pyodbc.Error as e:
        return
    
    finally:
        cursor.close()
        conn.close()



def get_six_dernieres_factures(numCC:str):

    conn = get_db_connection_postpaid()
    if not conn:
        return {"error": "Database connection failed"}
    
    try:
        cursor = conn.cursor()
        # Example SELECT query
        cursor.execute(sixLastBills,(numCC,))
        rows = cursor.fetchall()
        if not rows:
            return
        columns = [column[0] for column in cursor.description]
        transactions = [dict(zip(columns, row)) for row in rows]
        #montant_global = sum(transaction["MONTANT"] for transaction in transactions)
        #energie_globale = sum(transaction["CONSOMMATION TOTALE"] for transaction in transactions) 
        
        return transactions
    
    except pyodbc.Error as e:
        return 
    
    finally:
        cursor.close()
        conn.close()