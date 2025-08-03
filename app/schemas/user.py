# app/schemas/user.py

# Importation de BaseModel et ConfigDict depuis Pydantic (nouvelle syntaxe pour la configuration en v2)
from pydantic import BaseModel, EmailStr, constr, ConfigDict
# Importation des types date et datetime pour gérer les dates et timestamps
from datetime import date, datetime
# Importation d'Optional pour les champs optionnels dans le schéma de mise à jour
from typing import Optional
# Importation du type UUID pour les identifiants uniques
from uuid import UUID

# ---------------------------------------------------------------------------
# Schéma de base utilisé lors de la création de l'utilisateur (champs immuables en production)
# ---------------------------------------------------------------------------
class UserBase(BaseModel):
    first_name: str         # Prénom (obligatoire lors de la création, puis immuable)
    last_name: str          # Nom de famille (obligatoire lors de la création, puis immuable)
    birth_date: date        # Date de naissance (obligatoire et immuable)
    birth_place: str        # Lieu de naissance (obligatoire et immuable)
    email: EmailStr         # Email de l'utilisateur (obligatoire)
    phone: str              # Numéro de téléphone (obligatoire)
    type: str               # Type de compte (ex: "client", "merchant", "admin") (obligatoire et immuable)

    # Nouvelle configuration Pydantic v2 pour autoriser la lecture par attributs des objets ORM
    model_config = ConfigDict(from_attributes=True)

# ---------------------------------------------------------------------------
# Schéma utilisé lors de la création d'un utilisateur
# ---------------------------------------------------------------------------
class UserCreate(UserBase):
    password: constr(min_length=6)  # Mot de passe en clair à fournir lors de la création (sera hashé côté serveur)

    # Hérite également de la configuration pour la conversion à partir d'objets ORM
    model_config = ConfigDict(from_attributes=True)

# ---------------------------------------------------------------------------
# Schéma pour la mise à jour d'un utilisateur en contexte bancaire
# (Les champs critiques sont exclus pour empêcher leur modification)
# ---------------------------------------------------------------------------
class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None         # Email modifiable (optionnel)
    phone: Optional[str] = None              # Téléphone modifiable (optionnel)
    language: Optional[str] = None           # Langue préférée modifiable (optionnel)
    gdpr_consent: Optional[bool] = None      # Statut de consentement RGPD, modifiable (optionnel)
    mfa_enabled: Optional[bool] = None       # Activation ou désactivation de l'authentification multi-facteurs (optionnel)

    # Configuration pour Pydantic v2
    model_config = ConfigDict(from_attributes=True)

# ---------------------------------------------------------------------------
# Schéma pour la réponse qui restitue toutes les informations de l'utilisateur
# ---------------------------------------------------------------------------
class UserOut(UserBase):
    id: UUID                             # Identifiant unique de l'utilisateur
    status: str                          # Statut du compte (ex: "active", "inactive", etc.)
    account_status: str                  # Statut de sécurité du compte (ex: "active", "blocked", etc.)
    failed_login_attempts: int           # Nombre de tentatives de connexion échouées
    last_login_at: Optional[datetime] = None  # Date/heure de la dernière connexion (optionnel)
    created_at: datetime                 # Date/heure de création du compte
    updated_at: datetime                 # Date/heure de la dernière mise à jour
    language: str                        # Langue préférée de l'utilisateur
    gdpr_consent: bool                   # Indique si le consentement RGPD a été donné
    mfa_enabled: bool                    # Indique si l’authentification multi-facteurs est activée
    last_password_change_at: Optional[datetime] = None  # Date/heure du dernier changement de mot de passe (optionnel)
    email_verified: bool                 # Statut de vérification de l'adresse email
    phone_verified: bool                 # Statut de vérification du téléphone

    # Nouvelle configuration Pydantic v2 pour la conversion à partir d'objets ORM
    model_config = ConfigDict(from_attributes=True)
