# app/main.py
from fastapi import FastAPI
from app.database import engine, Base
from app import models  # Importez vos modèles pour qu'ils soient détectés

app = FastAPI(title="PaySecond App")

# Crée les tables si elles n'existent pas déjà (à n'utiliser qu'en développement)
Base.metadata.create_all(bind=engine)

@app.get("/")
def read_root():
    return {"message": "Bienvenue dans PaySecond App"}
