from sqlalchemy import (
    Column, String, DateTime, CheckConstraint, Index, DDL, event, text, func, ForeignKey
)
from sqlalchemy.dialects.postgresql import UUID, TSVECTOR
from app.database import Base

# ========================================================
# 1. Modèle SQLAlchemy pour la table "search_index"
#    (optimisation des recherches textuelles)
# ========================================================
class SearchIndex(Base):
    __tablename__ = "search_index"

    entity_type = Column(
        String(20),
        primary_key=True,
        nullable=False
    )  
    # [entity_type] : Type d'entité (user, merchant, transaction)

    entity_id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        nullable=False
    )  
    # [entity_id] : Identifiant de l'entité

    search_text = Column(
        TSVECTOR,
        nullable=False
    )  
    # [search_text] : Texte indexé pour la recherche full-text

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.current_timestamp()
    )  
    # [created_at] : Date de création de l'entrée

    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.current_timestamp()
    )  
    # [updated_at] : Date de dernière mise à jour

    __table_args__ = (
        CheckConstraint(
            "entity_type IN ('user','merchant','transaction')",
            name="chk_search_index_entity_type"
        ),  
        # Validation du type d'entité

        Index(
            "idx_search_index_text",
            "search_text",
            postgresql_using="gin"
        ),  
        # Index GIN pour la recherche full-text

        Index(
            "idx_search_index_entity_type",
            "entity_type"
        ),  
        # Index pour filtrer par type d'entité
    )

# ========================================================
# 2. DDL pour trigger de mise à jour d'`updated_at`
# ========================================================
ddl_update_search_index_ts = DDL("""
CREATE OR REPLACE FUNCTION update_search_index_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at := CURRENT_TIMESTAMP;  -- met à jour updated_at avant chaque UPDATE
    RETURN NEW;
END;
$$ LANGUAGE plpgsql STABLE;

CREATE TRIGGER trg_update_search_index
BEFORE UPDATE ON search_index
FOR EACH ROW EXECUTE FUNCTION update_search_index_timestamp();
""")  # trigger qui rafraîchit updated_at

# ========================================================
# 3. Attachement du DDL après création de la table
# ========================================================
event.listen(
    SearchIndex.__table__,
    'after_create',
    ddl_update_search_index_ts
)
