# app/database.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from app.config import DATABASE_URL

# Création de l'engine SQLAlchemy
engine = create_engine(DATABASE_URL, pool_pre_ping=True)

# Création d'une session locale pour interagir avec la BDD
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base sur laquelle seront basés tous les modèles SQLAlchemy
Base = declarative_base()
