from datetime import datetime
from app.database import Base, engine
from sqlalchemy import Column, DateTime, Double,String, Integer,ForeignKey,Boolean
from sqlalchemy.orm import relationship



class User(Base):
    __tablename__ = 'user'
    id = Column(Integer,primary_key=True,autoincrement=True)
    firstName = Column(String,nullable=True)
    lastName = Column(String,nullable=True)
    phoneNumber = Column(String,nullable=True)
    codePin = Column(String,nullable=True)
    email = Column(String,nullable=True)
    login = Column(String,nullable=True)
    password = Column(String,nullable=True)
    is_activate = Column(Boolean,nullable=True)
    ldap = Column(Boolean,nullable=True,default=False)
    role = Column(Integer,ForeignKey('role.id'),nullable=True)
    id_agence = Column(Integer,ForeignKey('agence.id'),nullable=True)
    created_at = Column(DateTime(timezone=True),nullable=False, default=datetime.now())
    updated_at = Column(DateTime(timezone=True),nullable=False, default=datetime.now())

    # user_compteurs = relationship("UserCompteur", backref="user")
    # autorise_user_compteurs = relationship("UserCompteur", backref="autorise_par_user")
    # active_user_compteurs = relationship("UserCompteur", backref="active_par_user")
    #user_compteurs = relationship("UserCompteur", back_populates="user")
    #user_sessions = relationship("UserSession", foreign_keys="[UserSession.user_id]", back_populates="user")
    #notifications = relationship("Notification", back_populates="user", cascade="all, delete-orphan")



class Role(Base):
    __tablename__ = 'role'
    id = Column(Integer, primary_key=True, autoincrement=True)
    label = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True),nullable=False, default=datetime.now())
    updated_at = Column(DateTime(timezone=True),nullable=False, default=datetime.now())

class TypeCompteur(Base):
    __tablename__ = 'type_compteur'
    id = Column(Integer, primary_key=True, autoincrement=True)
    label = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True),nullable=False, default=datetime.now())
    updated_at = Column(DateTime(timezone=True),nullable=False, default=datetime.now(),onupdate=datetime.now())

class Compteur(Base):
    __tablename__ = 'compteur'
    id = Column(Integer, primary_key=True, autoincrement=True)
    numero = Column(String, nullable = False)
    type_compteur = Column(Integer,ForeignKey('type_compteur.id'),nullable=True)
    created_at = Column(DateTime(timezone=True),nullable=False, default=datetime.now())
    updated_at = Column(DateTime(timezone=True),nullable=False, default=datetime.now(),onupdate=datetime.now())

class EtatCompteur(Base):
    __tablename__ = 'etat_compteur'
    id = Column(Integer, primary_key=True, autoincrement=True)
    label = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True),nullable=False, default=datetime.now())
    updated_at = Column(DateTime(timezone=True),nullable=False, default=datetime.now(),onupdate=datetime.now())

class UserCompteur(Base):
    __tablename__ = 'user_compteur'
    id = Column(Integer, primary_key=True, autoincrement=True)
    compteur_id = Column(Integer,ForeignKey('compteur.id'),nullable=True)
    type_compteur = Column(Integer,ForeignKey('type_compteur.id'),nullable=True)
    user_id = Column(Integer,ForeignKey('user.id'),nullable=True)
    est_proprietaire = Column(Boolean,default=False)
    autorise_par = Column(Integer,ForeignKey('user.id'),nullable=True)
    active_par = Column(Integer,ForeignKey('user.id'),nullable=True)
    etat_id = Column(Integer,ForeignKey('etat_compteur.id'),nullable=True)
    est_active = Column(Boolean,nullable=True)
    id_client = Column(String, nullable=True)
    num_compte_contrat  = Column(String, nullable=True)
    numero_compteur  = Column(String, nullable=True)
    id_agence = Column(Integer,ForeignKey('agence.id'),nullable=True)
    nom_agence  = Column(String, nullable=True)
    nom_client = Column(String, nullable=True)
    poc = Column(String, nullable=True)
    tarif = Column(String, nullable=True)
    adresse = Column(String, nullable=True)
    default = Column(Boolean, nullable=True)
    date_activation = Column(DateTime(timezone=True),nullable=True)
    created_at = Column(DateTime(timezone=True),nullable=False, default=datetime.now())
    updated_at = Column(DateTime(timezone=True),nullable=False, default=datetime.now(),onupdate=datetime.now())

    user = relationship("User", foreign_keys=[user_id],backref="user_compteurs",uselist=False)
    autorise_par_user = relationship("User", foreign_keys=[autorise_par],backref="autorise_user_compteurs",uselist=False)
    active_par_user = relationship("User",  foreign_keys=[active_par],backref="active_user_compteurs",uselist=False)

class  UserSession(Base):
    __tablename__ = "user_session"

    id = Column(Integer, primary_key=True,autoincrement=True)
    user_id = Column(Integer, ForeignKey("user.id"))
    device_model  = Column(String,nullable=True)
    fcm_token = Column(String,nullable=True)
    is_active = Column(Boolean, default=True)
    last_login = Column(DateTime, default=datetime.now())
    

    #user = relationship("User", foreign_keys=[user_id], back_populates="user_sessions")


class Notification(Base):
    __tablename__ = 'notification'

    id = Column(Integer, primary_key=True, index=True,autoincrement=True)
    type_notification_id = Column(Integer,ForeignKey('type_notification.id'),nullable=True)
    event_id = Column(Integer, nullable=True)
    by_user_id = Column(Integer, ForeignKey("user.id"), nullable=True)
    for_user_id = Column(Integer, ForeignKey("user.id"), nullable=True)
    title = Column(String, nullable=True)
    body = Column(String, nullable=True)
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.now())
    updated_at = Column(DateTime, default=datetime.now(), onupdate=datetime.now())

    #type_notification = relationship("TypeNotification", back_populates="notifications")


class TypeNotification(Base):
    __tablename__ = 'type_notification'

    id = Column(Integer, primary_key=True, autoincrement=True)
    label = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True),nullable=False, default=datetime.now())
    updated_at = Column(DateTime(timezone=True),nullable=False, default=datetime.now())

    #notifications = relationship("Notification", back_populates="type_notification")

class Agence(Base):
    __tablename__ = 'agence'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    nom = Column(String, nullable=False)
    nom_corrige = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True),nullable=False, default=datetime.now())
    updated_at = Column(DateTime(timezone=True),nullable=False, default=datetime.now())






class TypeDemande(Base):
    __tablename__ = 'type_demande'

    id = Column(Integer, primary_key=True, autoincrement=True)
    label = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True),nullable=False, default=datetime.now())
    updated_at = Column(DateTime(timezone=True),nullable=False, default=datetime.now())


class Demande(Base):
    __tablename__ = 'demande'
    id = Column(Integer, primary_key=True,autoincrement=True)
    fait_par =  Column(Integer, ForeignKey("user.id"), nullable=True)
    traite_par = Column(Integer, ForeignKey("user.id"), nullable=True)
    user_compteur_id = Column(Integer, ForeignKey("user_compteur.id"), nullable=True)
    type_demande = Column(Integer,ForeignKey('type_demande.id'), nullable=True)
    commentaire = Column(String, nullable=True)
    fichier = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True),nullable=False, default=datetime.now())
    updated_at = Column(DateTime(timezone=True),nullable=False, default=datetime.now(),onupdate=datetime.now())

class SeuilTarif(Base):
    __tablename__ = 'seuil_tarif'
    id          = Column(Integer, primary_key=True, autoincrement=True)
    code_tarif  = Column(String,  nullable=False)
    id_seuil    = Column(Integer, nullable=False)
    kwh_min     = Column(Double,  nullable=False)
    kwh_max     = Column(Double,  nullable=True)
    color_hex   = Column(String,  nullable=False)
    created_at  = Column(DateTime(timezone=True), nullable=False, default=datetime.now())


Base.metadata.create_all(engine)