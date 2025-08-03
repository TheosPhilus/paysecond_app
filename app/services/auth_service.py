# app/services/auth_service.py

from datetime import datetime, timedelta
from jose import jwt  # Pour encoder et générer le token JWT
import os             # Pour accéder à la variable d'environnement

# Import du module utilitaire pour la vérification du mot de passe
from app.utils.security import verify_password

# Paramètres pour le JWT
SECRET_KEY = os.getenv("SECRET_KEY", "supersecretkey")  # Clé secrète extraite de l'environnement
ALGORITHM = "HS256"                                     # Algorithme de chiffrement du token
ACCESS_TOKEN_EXPIRE_MINUTES = 30                        # Durée de validité du token en minutes

def create_access_token(data: dict, expires_delta: timedelta = None) -> str:
    """
    Génère et retourne un token d'accès (JWT) avec une date d'expiration.
    """
    to_encode = data.copy()  # Copie des données à inclure dans le token
    expire = datetime.utcnow() + (expires_delta if expires_delta else timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})  # Ajout de la date d'expiration dans la charge utile
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def authenticate_user(user, plain_password: str) -> bool:
    """
    Vérifie si l'utilisateur est authentique en comparant le mot de passe fourni 
    avec le mot de passe hashé stocké.
    """
    return verify_password(plain_password, user.password_hash)
