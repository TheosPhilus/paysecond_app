# app/schemas/auth.py

# Importation de BaseModel (pour créer des schémas Pydantic)
from pydantic import BaseModel

# Schéma pour la requête de connexion (login)
class LoginRequest(BaseModel):
    email: str        # L'email de l'utilisateur
    password: str     # Le mot de passe en clair

# Schéma pour le retour d'un token après une connexion réussie
class Token(BaseModel):
    access_token: str  # Le token JWT généré
    token_type: str    # Type de token (généralement "bearer")
