# app/utils/security.py
import bcrypt

# Si l'attribut __about__ n'existe pas dans bcrypt, on le définit pour éviter l'erreur
if not hasattr(bcrypt, '__about__'):
    bcrypt.__about__ = {'__version__': bcrypt.__version__}


from passlib.context import CryptContext

# Création d'un contexte bcrypt pour le hashage des mots de passe
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def get_password_hash(password: str) -> str:
    """
    Retourne le hash bcrypt du mot de passe fourni.
    """
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Vérifie que le mot de passe en clair correspond au mot de passe hashé.
    """
    return pwd_context.verify(plain_password, hashed_password)
