# app/main.py

from fastapi import FastAPI              # Importation de FastAPI pour créer l'application web
from app.database import engine, Base    # Importation de l'engine et de Base pour gérer la création des tables en base
from app.routers import user, auth, protected             # Importation du module user (router) depuis le dossier app/routers

# Création de l'application FastAPI avec un titre identifiable
app = FastAPI(title="Application Bancaire paysecond_app")


from fastapi.openapi.utils import get_openapi

def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    openapi_schema = get_openapi(
        title="Application Bancaire",
        version="1.0.0",
        description="API pour l'application bancaire",
        routes=app.routes,
    )
    # Utiliser un schéma de sécurité HTTP de type Bearer JWT
    openapi_schema["components"]["securitySchemes"] = {
        "BearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
        }
    }
    # Appliquer ce schéma à tous les endpoints (si vous le souhaitez)
    openapi_schema["security"] = [{"BearerAuth": []}]
    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi



# Création automatique des tables en base de données à partir des modèles SQLAlchemy.
# En développement, cela vous évite de gérer manuellement les migrations.
# En production, il est conseillé d'utiliser Alembic pour les migrations.
Base.metadata.create_all(bind=engine)

# Inclusion du routeur user dans l'application.
app.include_router(auth.router)       # Endpoints d'authentification (register, login)
app.include_router(protected.router)  # Endpoints protégés nécessitant un token
app.include_router(user.router)       # Endpoints relatifs aux utilisateurs (CRUD)


# Endpoint racine pour tester que l'application fonctionne
@app.get("/")
def root():
    return {"message": "Bienvenue dans l'application bancaire paysecond_app"}
