from fastapi import APIRouter, Depends, HTTPException,status
import json
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session
from app.models.models import Compteur, User, UserCompteur
from app.schemas.postpaid_schemas import NumCCParamSchema
from app.schemas.sic_schemas import TransactionsByMeterPoc
from app.schemas.user_compteur_schemas import ActivateUserCompteur, UserCompteurCreateSchema, UserCompteurCreateSchemaV2,UserCompteurUpdate,CompteurWoyofalResponseSchema,CompteurPostpaidResponseSchema
from app.database import get_db_connection_postpaid, get_db_samaconso,get_db_connection_sic
from app.cache import cache_get, cache_set, cache_delete
from app.queries import * 
import pyodbc

user_compteur_router = APIRouter(prefix="/user_compteur", tags=["UserCompteur"])

@user_compteur_router.post("/")
def create(data: UserCompteurCreateSchema, db: Session = Depends(get_db_samaconso)):
    
    ##TODO: Vérifier si le numéro de téléphone de l'utilisateur est celui enregistré dans 
    ## la base du commercial, si tel est le cas faire l'ajout rendre is_active à true et mettre l'état validé
    ##Sinon les mettre en attente de validation

    db_obj = UserCompteur(**data.model_dump())
    db.add(db_obj)
    db.commit()
    db.refresh(db_obj)
    try:
        from app.cache import cache_delete
        import asyncio
        loop = asyncio.get_event_loop()
        loop.create_task(cache_delete("user_compteur:all"))
        loop.create_task(cache_delete(f"user_compteur:user:{db_obj.user_id}"))
    except Exception:
        pass
    return db_obj

@user_compteur_router.post("/ajoutercompteur")
def createv2(data: UserCompteurCreateSchemaV2, db: Session = Depends(get_db_samaconso)):
    id_compteur:int = 0
    is_owner:bool = False
    active:bool = False
    defaut:bool = False
    user = db.query(User).filter(User.phoneNumber==data.telephone).first()
    if not user:
        HTTPException(status_code=status.HTTP_404_NOT_FOUND,detail="Utilisateur non enregistré")
    
    userCompteurExist = db.query(UserCompteur).filter(and_(UserCompteur.numero_compteur==data.numero_compteur
                                            ,UserCompteur.user_id==user.id)).first()
  
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

        compteursTrouves = verifierCompteur(data.numero_compteur,data.type_compteur)
        ctStatus = compteursTrouves[0].status
        if ctStatus == 0:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,detail="Erreur connexion base de données")
        if ctStatus == 404:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,detail="Numero compteur incorrect")
        
        if ctStatus == 200:
            compteursAjoutes=[]
            for compteurTrouve in compteursTrouves:
                #Ajouter le compteur dans la base
                compteur_woyofal = db.query(Compteur).filter(and_(Compteur.numero==data.numero_compteur, Compteur.type_compteur==data.type_compteur)).first()
                if not compteur_woyofal:
                    created_compteur = Compteur(numero=data.numero_compteur,type_compteur=data.type_compteur)
                    db.add(created_compteur)
                    db.commit()
                    db.refresh(created_compteur)
                    id_compteur = created_compteur.id
                else:
                    id_compteur = compteur_woyofal.id
                if compteurTrouve.tel == data.telephone:
                    is_owner= True
                    active= True
                else:
                    active=False
                    is_owner= False
                    ### Voir si des users ont rajouté le compteur avant que le owner ne le fasse
                    ### Si oui mettre à jour
                    #updateUserCompterWhenOwnerFound(numero=data.numero_compteur,owner_id=id_owner,db=db) 
                

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
                numero_compteur=data.numero_compteur,
                type_compteur=data.type_compteur
                )
                
                userCompteurDbObj = UserCompteur(**userCompteur.model_dump())
                db.add(userCompteurDbObj)
                db.commit()
                db.refresh(userCompteurDbObj)

                compteursAjoutes.append(userCompteurDbObj)
                
        return {"status":status.HTTP_201_CREATED,"user_compteurs":compteursAjoutes}

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
            else:
                id_compteur = compteur_postpaid.id
            if compteurPostpaidTrouve.tel == data.telephone:
                is_owner= True
                active= True
                ### Voir si des users ont rajouté le compteur avant que le owner ne le fasse
                ### Si oui mettre à jour
                #updateUserCompterWhenOwnerFound(numero=data.numero_compteur,owner_id=id_owner,db=db) 
            

        userACompteur  = db.query(UserCompteur).filter(UserCompteur.user_id==user.id).all()
        if len(userACompteur)==0:
            defaut=True

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
        adresse=compteurPostpaidTrouve.adresse,
        default=defaut,
        numero_compteur=data.numero_compteur,
        type_compteur=data.type_compteur
        )
        
        userCompteurDbObj = UserCompteur(**userCompteur.model_dump())
        db.add(userCompteurDbObj)
        db.commit()
        db.refresh(userCompteurDbObj)

        return  {"status":status.HTTP_201_CREATED,"user_compteur":userCompteurDbObj} 



@user_compteur_router.get("/")
def list_all(db: Session = Depends(get_db_samaconso)):
    # keep v2 sync; skip read cache to avoid blocking here
    return db.query(UserCompteur).all()


@user_compteur_router.get("/usercompteur/{id}")
def list_all_user_compteur(id:int,db: Session = Depends(get_db_samaconso)):
    compteurs =  db.query(UserCompteur).filter(UserCompteur.user_id==id).all()
    return {"compteurs":compteurs}

@user_compteur_router.get("/usercompteuractive/{id}")
def list_all_user_compteur_active(id:int,db: Session = Depends(get_db_samaconso)):
    compteurs =  db.query(UserCompteur).filter(and_(UserCompteur.user_id==id,UserCompteur.est_active==True)).all()
    return {"compteurs":compteurs}

@user_compteur_router.get("/usercompteurinactive/{id}")
def list_all_user_compteur_inactive(id:int,db: Session = Depends(get_db_samaconso)):
    compteurs =  db.query(UserCompteur).filter(and_(UserCompteur.user_id==id,UserCompteur.est_active==False)).all()
    return {"compteurs":compteurs}


@user_compteur_router.put("/{user_compteur_id}")
def update_user_compteur(user_compteur_id:int,compteur_update : UserCompteurUpdate,db: Session = Depends(get_db_samaconso)):
    user_compteur_db = db.query(UserCompteur).filter(UserCompteur.id == user_compteur_id).first()
    if not user_compteur_db:
        raise HTTPException(status_code=404, detail="User Compteur not found")
    for key, value in compteur_update.model_dump(exclude_unset=True).items():
        setattr(user_compteur_db, key, value)
    db.commit()
    db.refresh(user_compteur_db)
    return user_compteur_db

@user_compteur_router.delete("/{user_compteur_id}")
def delete_user_compteur(user_compteur_id:int,db: Session = Depends(get_db_samaconso)):
    user_compteur_db = db.query(UserCompteur).filter(UserCompteur.id == user_compteur_id).first()
    if not user_compteur_db:
        raise HTTPException(status_code=404, detail="User Compteur not found")
    db.delete(user_compteur_db)
    db.commit()
    return {"message": "Etat deleted successfully"}


@user_compteur_router.get("usercompteurtransactionsmens/{user_id}")
def recup_user_compteur_cons_trans(user_id:int,db:Session=Depends(get_db_samaconso)):
    user_compteur_db = db.query(UserCompteur).filter(UserCompteur.user_id == user_id).first()
    if not user_compteur_db:
        raise HTTPException(status_code=404, detail="Cet utilisateur n'a pas de compteur enregistré")
    compteurs = db.query(UserCompteur).filter(UserCompteur.user_id==user_id).all()
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
def recup_compteur_cons_trans(user_compteur_id:int,db:Session=Depends(get_db_samaconso)):
    user_compteur_db = db.query(UserCompteur).filter(UserCompteur.id == user_compteur_id).first()
    if not user_compteur_db:
        raise HTTPException(status_code=404, detail="Id not found")
    compteurs = db.query(UserCompteur).filter(UserCompteur.user_id==user_compteur_db.user_id).all()
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





def  verifierCompteur(numero:str,type:int):
       
        if type==1:
            conn = get_db_connection_sic()
            if not conn:
                return CompteurWoyofalResponseSchema(status=0,tel=None,poc=None,id_client=None,adresse=None,tarif=None,nom_client=None)
            
            try:
                cursor = conn.cursor()
                result = cursor.execute(verifierSiCompteurWoyofalExiste,(numero,))
            
                #compteur = result.fetchone()
                #row = result.fetchone()
               # if not row:
                #    return CompteurWoyofalResponseSchema(status=404,tel=None,poc=None,id_client=None,adresse=None,tarif=None,nom_client=None)
                #compteur = {col[0]: value for col, value in zip(cursor.description, row)}            

               # return CompteurWoyofalResponseSchema(status=200,tel=compteur["tel"],poc=compteur["poc"],id_client=compteur["id_client"],adresse=compteur["adresse"],tarif=compteur["usage"],nom_client=compteur["nomClient"])
                rows = result.fetchall()
                if not rows:
                    return []

                compteurs = []
                for row in rows:
                    compteur_dict = {col[0]: value for col, value in zip(cursor.description, row)}
                    compteur = CompteurWoyofalResponseSchema(
                        status=200,
                        tel=compteur_dict["tel"],
                        poc=compteur_dict["poc"],
                        id_client=compteur_dict["id_client"],
                        adresse=compteur_dict["adresse"],
                        tarif=compteur_dict["usage"],
                        nom_client=compteur_dict["nomClient"]
                    )
                    compteurs.append(compteur)

                return compteurs

            except pyodbc.Error as e:
                print(f"Erreur DB : {e}")
                return CompteurWoyofalResponseSchema(status=0,tel=None,poc=None,id_client=None,tarif=None,nom_client=None)
            
            finally:
                cursor.close()
                conn.close()
        
        elif type==2:
            conn = get_db_connection_sic()
            if not conn:
                return CompteurPostpaidResponseSchema(status=0,tel=None,numCC=None,id_partenaire=None,adresse=None,tarif=None,nom_client=None)
            
            try:
                cursor = conn.cursor()
                result = cursor.execute(verifierSiCompteurClassiqueExiste,(numero))
            
                #compteur = result.fetchone()
                row = result.fetchone()
                if not row:
                    return CompteurPostpaidResponseSchema(status=404,tel=None,numCC=None,id_partenaire=None,adresse=None,tarif=None,nom_client=None)
                compteur = {col[0]: value for col, value in zip(cursor.description, row)}            

                return CompteurPostpaidResponseSchema(status=200,tel=compteur["TELEPHONE"],numCC=compteur["COMPTE CONTRAT"],id_partenaire=compteur["N PARTENAIRE"],adresse=compteur["ADRESSE"],tarif=compteur["tarif"],nom_client=compteur["CLIENT"])
            
            except pyodbc.Error as e:
                print(f"Erreur DB : {e}")
                return  CompteurPostpaidResponseSchema(status=0,tel=None,numCC=None,id_partenaire=None,adresse=None,tarif=None,nom_client=None)
            
            finally:
                cursor.close()
                conn.close()

@user_compteur_router.put("/activateordeactivate/{user_compteur_id}")
def activate_user_compteur(user_compteur_id:int,data:ActivateUserCompteur,db: Session = Depends(get_db_samaconso)):
    user_compteur_db = db.query(UserCompteur).filter(UserCompteur.id == user_compteur_id).first()
    if not user_compteur_db:
        raise HTTPException(status_code=404, detail="User Compteur not found")
    user_compteur_db.active_par=data.activated_by
    user_compteur_db.est_active = data.activate
    
    db.commit()
    db.refresh(user_compteur_db)

    return {"status":status.HTTP_200_OK,"user compteur":user_compteur_db}

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