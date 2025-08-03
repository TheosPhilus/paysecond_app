# app/routers/auth.py

from fastapi import APIRouter, Depends, HTTPException, status   # Outils FastAPI pour la gestion des endpoints et des exceptions HTTP
from sqlalchemy.orm import Session                           # Pour interagir avec la base de données
import os

# Importation des schémas d'authentification et d'utilisateur
from app.schemas.auth import LoginRequest, Token
from app.schemas.user import UserCreate, UserOut
# Importation du modèle User (défini en SQLAlchemy)
from app.models.User import User
# Importation de la session de base de données
from app.database import SessionLocal

# Importation des fonctions des modules services et utils
from app.services.auth_service import create_access_token, authenticate_user
from app.utils.security import get_password_hash

# Création du routeur pour gérer l'authentification
router = APIRouter(
    prefix="",     # Pas de préfixe spécifique, les endpoints seront accessibles directement (ex. /register, /login)
    tags=["auth"]  # Tag utilisé dans la documentation Swagger pour regrouper ces endpoints
)

def get_db():
    """
    Dépendance FastAPI pour fournir une session de base de données à chaque endpoint.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post("/register", response_model=UserOut)
def register(user_in: UserCreate, db: Session = Depends(get_db)):
    """
    Endpoint d'inscription (register) :
    - Vérifie que l'email et le téléphone n'existent pas déjà.
    - Hash le mot de passe avec get_password_hash().
    - Crée et sauvegarde l'utilisateur dans la base de données.
    """
    # Vérification de l'unicité de l'email
    if db.query(User).filter(User.email == user_in.email).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    # Vérification de l'unicité du téléphone
    if db.query(User).filter(User.phone == user_in.phone).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Phone already registered"
        )
    
    # Hashage sécurisé du mot de passe
    hashed_password = get_password_hash(user_in.password)
    
    # Création de la nouvelle instance utilisateur
    new_user = User(
        first_name=user_in.first_name,
        last_name=user_in.last_name,
        birth_date=user_in.birth_date,
        birth_place=user_in.birth_place,
        email=user_in.email,
        phone=user_in.phone,
        password_hash=hashed_password,
        type=user_in.type
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user

@router.post("/login", response_model=Token)
def login(login_data: LoginRequest, db: Session = Depends(get_db)):
    """
    Endpoint de connexion (login) :
    - Récupère l'utilisateur par email.
    - Vérifie que le mot de passe fourni est correct.
    - Génère et renvoie un token JWT si l'authentification est réussie.
    """
    user = db.query(User).filter(User.email == login_data.email).first()
    if not user or not authenticate_user(user, login_data.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )
    access_token = create_access_token(data={"sub": str(user.id), "email": user.email})
    return {"access_token": access_token, "token_type": "bearer"}
