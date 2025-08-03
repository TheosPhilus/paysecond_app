# app/routers/protected.py

from fastapi import APIRouter, Depends
from app.dependencies import get_current_user
from app.schemas.user import UserOut  # Schéma de réponse pour afficher les données utilisateur

router = APIRouter(
    prefix="/protected",   # Tous les endpoints de ce routeur seront préfixés par /protected
    tags=["protected"]     # Pour la documentation Swagger
)

@router.get("/profile", response_model=UserOut)
def read_user_profile(current_user = Depends(get_current_user)):
    """
    Cet endpoint protégé retourne le profil de l'utilisateur actuellement connecté.
    Le token JWT doit être fourni dans l'en-tête Authorization sous la forme "Bearer <token>".
    """
    return current_user
