# alembic/env.py

from logging.config import fileConfig
import os

from sqlalchemy import engine_from_config, pool
from alembic import context

import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


# 🔧 Chargement des variables d'environnement
from dotenv import load_dotenv
load_dotenv()

# ⬇️ IMPORTATION DE VOS MODÈLES SQLALCHEMY
# Adapte ce chemin selon l'emplacement réel de tes modèles
# ⬇️ IMPORTATION DE VOS MODÈLES SQLALCHEMY
from app.database import Base    # Base vient bien de database.py
import app.models                # déclenche l’import de tous les modèles


# 🔧 RÉCUPÉRATION DE LA CONFIGURATION ALEMBIC
config = context.config

# 🛠️ MISE À JOUR DE L'URL DE CONNEXION AVEC CELLE DU .env
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL n'est pas défini. Vérifiez votre fichier .env.")

config.set_main_option("sqlalchemy.url", DATABASE_URL)

# 📂 CONFIGURATION DU LOGGING
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# 📌 DÉFINITION DU METADATA À UTILISER POUR LES MIGRATIONS
# Cela permet à Alembic de savoir quelles tables existent dans les modèles
target_metadata = Base.metadata

# 🔁 MIGRATIONS EN MODE OFFLINE
def run_migrations_offline() -> None:
    """Exécuter les migrations sans se connecter à la base."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()

# 🔁 MIGRATIONS EN MODE ONLINE
def run_migrations_online() -> None:
    """Exécuter les migrations avec une connexion à la base de données."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,  # Pour détecter les changements de types de colonnes
        )

        with context.begin_transaction():
            context.run_migrations()

# 🧠 CHOISIR ENTRE OFFLINE OU ONLINE SELON LE CONTEXTE
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
