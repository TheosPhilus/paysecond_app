# app/routers/user.py

import hashlib  # Pour le hashage du mot de passe
import uuid     # Pour manipuler l'identifiant utilisateur (UUID)
from datetime import datetime  # Pour gérer les timestamps (date et heure)
from typing import List      # Pour annoter des listes (ex: liste d'utilisateurs)

from fastapi import APIRouter, Depends, HTTPException, status  # Importation des outils FastAPI pour définir les endpoints et gérer les erreurs
from sqlalchemy.orm import Session  # Pour interagir avec la base de données via SQLAlchemy

from app.models.User import User  # Importation du modèle User (défini en SQLAlchemy)
from app.schemas.user import UserCreate, UserUpdate, UserOut  # Importation des schémas Pydantic pour la validation et la transformation des données
from app.database import SessionLocal  # Importation de la session de base de données configurée

# Création d'un routeur dédié aux opérations sur les utilisateurs.
router = APIRouter(
    prefix="/users",   # Tous les endpoints de ce routeur commenceront par /users
    tags=["users"]     # Tag utilisé pour grouper dans la documentation
)

def get_db():
    """
    Fonction de dépendance pour fournir une session de base de données à chaque endpoint.
    Cette fonction crée une session, la renvoie et s'assure qu'elle est fermée après utilisation.
    """
    db = SessionLocal()  # Création d'une session de base de données
    try:
        yield db  # Fourniture de la session pour l'endpoint qui en a besoin
    finally:
        db.close()  # Fermeture de la session après utilisation pour éviter les fuites de connexion

@router.get("/", response_model=List[UserOut])
def get_users(db: Session = Depends(get_db)):
    """
    Endpoint GET pour récupérer la liste de tous les utilisateurs.
    La réponse est formatée selon le schéma UserOut.
    """
    users = db.query(User).all()  # Récupère la liste de tous les utilisateurs de la base de données
    return users  # Retourne la liste des utilisateurs (convertie automatiquement par FastAPI)

@router.get("/{user_id}", response_model=UserOut)
def get_user(user_id: uuid.UUID, db: Session = Depends(get_db)):
    """
    Endpoint GET pour récupérer un utilisateur par son identifiant.
    Si l'utilisateur n'est pas trouvé, une exception HTTP 404 est renvoyée.
    """
    user = db.query(User).filter(User.id == user_id).first()  # Recherche de l'utilisateur dans la base de données par son UUID
    if not user:
        # Si aucun utilisateur n'est trouvé, renvoie une erreur 404
        raise HTTPException(status_code=404, detail="User not found")
    return user  # Retourne l'utilisateur trouvé

@router.post("/", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(user_in: UserCreate, db: Session = Depends(get_db)):
    """
    Endpoint POST pour créer un nouvel utilisateur.
    - Vérifie que l'email et le numéro de téléphone ne sont pas déjà utilisés.
    - Hash le mot de passe fourni (ici avec SHA-256; en production, privilégiez bcrypt ou argon2).
    - Crée et stocke le nouvel utilisateur dans la base de données.
    La réponse est formatée selon le schéma UserOut.
    """
    # Vérification de l'unicité de l'email
    if db.query(User).filter(User.email == user_in.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")
    # Vérification de l'unicité du numéro de téléphone
    if db.query(User).filter(User.phone == user_in.phone).first():
        raise HTTPException(status_code=400, detail="Phone already registered")
    
    # Hashage du mot de passe utilisant SHA-256.
    # En production, il est recommandé d'utiliser une solution de hashage plus sécurisée.
    password_hash = hashlib.sha256(user_in.password.encode("utf-8")).hexdigest()

    # Création de l'instance de l'utilisateur avec les informations fournies.
    # Notez que les champs sensibles (first_name, last_name, birth_date, birth_place, type) sont définis lors de la création.
    user = User(
        first_name=user_in.first_name,         # Affecte le prénom
        last_name=user_in.last_name,           # Affecte le nom de famille
        birth_date=user_in.birth_date,         # Affecte la date de naissance
        birth_place=user_in.birth_place,       # Affecte le lieu de naissance
        email=user_in.email,                   # Affecte l'email
        phone=user_in.phone,                   # Affecte le numéro de téléphone
        password_hash=password_hash,           # Stocke le mot de passe hashé
        type=user_in.type                      # Affecte le type de compte
    )
    db.add(user)         # Ajoute l'instance utilisateur à la session en cours
    db.commit()          # Valide l'insertion dans la base de données
    db.refresh(user)     # Recharge l'objet utilisateur pour récupérer les valeurs générées (ex: id, timestamps)
    return user          # Retourne l'utilisateur créé, formaté selon UserOut

@router.put("/{user_id}", response_model=UserOut)
def update_user(user_id: uuid.UUID, user_update: UserUpdate, db: Session = Depends(get_db)):
    """
    Endpoint PUT pour mettre à jour un utilisateur existant.
    Seuls les champs modifiables (par exemple, email, téléphone, langue, etc.) peuvent être mis à jour.
    Les champs sensibles (prénom, nom, date/lieu de naissance, mot de passe, type) ne sont pas inclus pour des raisons de sécurité.
    """
    # Recherche de l'utilisateur à mettre à jour
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        # Retourne une erreur 404 si l'utilisateur n'existe pas
        raise HTTPException(status_code=404, detail="User not found")
    
    # Extrait les données de la requête qui ont été effectivement fournies
    update_data = user_update.dict(exclude_unset=True)
    if "password" in update_data:
        # Le cas du mot de passe est à gérer avec une méthode dédiée : ici, on hash le nouveau mot de passe
        update_data["password_hash"] = hashlib.sha256(
            update_data.pop("password").encode("utf-8")
        ).hexdigest()
    
    # Mise à jour des attributs de l'utilisateur avec les champs fournis dans la requête
    for field, value in update_data.items():
        setattr(user, field, value)
    
    db.commit()  # Confirme la mise à jour dans la base de données
    db.refresh(user)  # Recharge l'objet mis à jour
    return user  # Retourne l'utilisateur mis à jour, formaté selon UserOut



@router.patch("/{user_id}/deactivate", response_model=UserOut)
def deactivate_user(user_id: uuid.UUID, db: Session = Depends(get_db)):
    """
    Endpoint PATCH pour désactiver (clôturer) un compte utilisateur.
    Dans une application bancaire, on ne supprime jamais un utilisateur, mais on clôture son compte.
    Cette opération modifie le statut du compte en "closed" et le status de sécurité en "blocked".
    """
    # Recherche de l'utilisateur dans la base de données par son identifiant (UUID)
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        # Si aucun utilisateur n'est trouvé, on renvoie une erreur 404
        raise HTTPException(status_code=404, detail="User not found")
    
    # Vérifie si le compte est déjà clôturé; si oui, on renvoie une erreur 400 pour éviter une redondance
    if user.status == "closed":
        raise HTTPException(status_code=400, detail="User account is already closed")
    
    # Met à jour le statut de l'utilisateur pour indiquer que le compte est clôturé
    user.status = "closed"            # Modifie le statut général du compte à "closed"
    user.account_status = "blocked"     # Change également le statut de sécurité à "blocked" pour empêcher toute utilisation

    # Valide les modifications dans la base de données
    db.commit()
    # Recharge l'objet utilisateur pour avoir les dernières valeurs mises à jour (notamment, les timestamps éventuels)
    db.refresh(user)
    
    # Retourne l'utilisateur mis à jour, formaté selon le schéma UserOut
    return user
