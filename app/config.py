# app/config.py
import os
from dotenv import load_dotenv

# Charge le contenu de .env dans l'environnement
load_dotenv()

# Récupère la variable d'environnement pour l'URL de la base
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL n'est pas défini dans le fichier .env")

# Autres variables de configuration si nécessaire
SECRET_KEY = os.getenv("SECRET_KEY", "votre_cle_secrete_par_defaut")
