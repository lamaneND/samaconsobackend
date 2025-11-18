from app.database import get_db_samaconso
from app.models.models import Agence, Compteur, User, UserCompteur
from fastapi import APIRouter, Depends, HTTPException,status
from sqlalchemy.orm import Session

dashboard_router = APIRouter(prefix="/dashboard", tags=["Dashboard"])

@dashboard_router.get("/")
def dashboard(db:Session=Depends(get_db_samaconso)):
           compteurs = db.query(UserCompteur).all()
           total_compteurs = len(compteurs)
           compteurs_actifs = sum(1 for compteur in compteurs if compteur.est_active == True)
           compteurs_inactifs = sum(1 for compteur in compteurs if compteur.est_active == False)
           compteurs_woyofal = sum(1 for compteur in compteurs if compteur.type_compteur == 1)
           compteurs_classique = sum(1 for compteur in compteurs if compteur.type_compteur == 2)
           demandes_traites = sum(1 for compteur in compteurs if compteur.etat_id==13)
           demandes_en_cours = sum(1 for compteur in compteurs if compteur.etat_id==14)
           owners = len(set(compteur.user_id for compteur in compteurs if compteur.est_proprietaire==True))
           not_owners = len(set(compteur.user_id for compteur in compteurs if compteur.est_proprietaire==False))
           users = db.query(User).all()
           total_users= len(users)
        
           return { "status_code":status.HTTP_200_OK,
                     "total_compteurs": total_compteurs,
                     "compteurs_actifs": compteurs_actifs,
                     "compteurs_inactifs": compteurs_inactifs,
                     "compteurs_woyofal": compteurs_woyofal,
                     "compteurs_classique": compteurs_classique,
                     "demandes_traites": demandes_traites,
                     "demandes_en_cours": demandes_en_cours,
                     "owners": owners,
                    "not_owners": not_owners,
                    "total_users":total_users,
                    }
   


@dashboard_router.get("/{user_id}")
def dashboard(user_id:int,db:Session=Depends(get_db_samaconso)):
   compteurs:any=None
   user = db.query(User).filter(User.id==user_id).first()
   if user:
       role = user.role
       #Admin
       if(role==7):
           compteurs = db.query(UserCompteur).all()
        
       elif(role==2):
           agence = db.query(Agence).filter(Agence.id==user.id_agence).first()
           compteurs = db.query(UserCompteur).filter(UserCompteur.nom_agence==agence.nom_corrige).all()
       total_compteurs = len(compteurs)
       compteurs_actifs = sum(1 for compteur in compteurs if compteur.est_active == True)
       compteurs_inactifs = sum(1 for compteur in compteurs if compteur.est_active == False)
       compteurs_woyofal = sum(1 for compteur in compteurs if compteur.type_compteur == 1)
       compteurs_classique = sum(1 for compteur in compteurs if compteur.type_compteur == 2)
       demandes_traites = sum(1 for compteur in compteurs if compteur.etat_id==13)
       demandes_en_cours = sum(1 for compteur in compteurs if compteur.etat_id==14)
       owners = len(set(compteur.user_id for compteur in compteurs if compteur.est_proprietaire==True))
       not_owners = len(set(compteur.user_id for compteur in compteurs if compteur.est_proprietaire==False))
       users = db.query(User).all()
       total_users= len(users)
        
       return { "status_code":status.HTTP_200_OK,
                     "total_compteurs": total_compteurs,
                     "compteurs_actifs": compteurs_actifs,
                     "compteurs_inactifs": compteurs_inactifs,
                     "compteurs_woyofal": compteurs_woyofal,
                     "compteurs_classique": compteurs_classique,
                     "demandes_traites": demandes_traites,
                     "demandes_en_cours": demandes_en_cours,
                     "owners": owners,
                    "not_owners": not_owners,
                    "total_users":total_users,
                    }
   return {"status_code":status.HTTP_404_NOT_FOUND,"message":"Utilisateur non trouvé"}