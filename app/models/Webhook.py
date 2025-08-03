import enum                                      # import du module enum pour définir des énumérations

from sqlalchemy import (                          # import des classes et fonctions SQLAlchemy
    Column, Text, Boolean, Integer, DateTime,     #   types de colonne de base
    CheckConstraint, Index, DDL, event, text,     #   contraintes, index, DDL, écoute d’événements, SQL brut
    ARRAY, ForeignKey                              #   type ARRAY et clé étrangère
)
from sqlalchemy.sql import func                    # import de func pour les fonctions SQL (CURRENT_TIMESTAMP)
from sqlalchemy.dialects.postgresql import (      # import des types PostgreSQL spécifiques
    UUID,                                          #   UUID natif
    ENUM as PGEnum                                 #   ENUM PostgreSQL
)
from app.database import Base                     # import du Base déclaratif SQLAlchemy

# ========================================================
# 1. Python Enum pour le statut du webhook
# ========================================================
class WebhookStatus(enum.Enum):                   # déclaration de l’énumération WebhookStatus
    active = "active"                             #   statut opérationnel
    inactive = "inactive"                         #   statut désactivé
    failed = "failed"                             #   statut en échec

# ========================================================
# 2. Modèle SQLAlchemy pour la table "webhook"
# ========================================================
class Webhook(Base):                              # définition de la classe Webhook héritant de Base
    __tablename__ = "webhook"                     # nom de la table en base

    id = Column(                                  # colonne id
        UUID(as_uuid=True),                       #   type UUID PostgreSQL
        primary_key=True,                         #   clé primaire
        server_default=text("gen_random_uuid()")  #   valeur par défaut générée par la fonction gen_random_uuid()
    )

    merchant_id = Column(                         # colonne merchant_id
        UUID(as_uuid=True),                       #   type UUID PostgreSQL
        ForeignKey("merchant.id", ondelete="CASCADE"),  # clé étrangère vers merchant.id, suppression en cascade
        nullable=False                            #   ne peut pas être nul
    )

    url = Column(                                 # colonne url
        Text,                                     #   type texte
        nullable=False                            #   ne peut pas être nul
    )

    secret_key = Column(                          # colonne secret_key
        Text,                                     #   type texte
        nullable=False                            #   ne peut pas être nul
    )

    events = Column(                              # colonne events
        ARRAY(Text),                              #   tableau de textes
        nullable=False,                           #   ne peut pas être nul
        server_default=text("ARRAY['payment.success','payment.failed']")  # valeur par défaut
    )

    status = Column(                              # colonne status
        PGEnum(WebhookStatus,                     #   type ENUM PostgreSQL basé sur WebhookStatus
               name="webhook_status", create_type=True),
        nullable=False,                           #   ne peut pas être nul
        server_default=text(f"'{WebhookStatus.active.value}'")  # valeur par défaut "'active'"
    )

    last_response_code = Column(                  # colonne last_response_code
        Integer,                                  #   type entier
        nullable=True                             #   optionnel
    )

    last_delivery_attempt = Column(               # colonne last_delivery_attempt
        DateTime(timezone=True),                  #   type timestamp avec fuseau
        nullable=True                             #   optionnel
    )

    retry_count = Column(                         # colonne retry_count
        Integer,                                  #   type entier
        nullable=False,                           #   ne peut pas être nul
        server_default=text("0")                  #   valeur par défaut 0
    )

    created_at = Column(                          # colonne created_at
        DateTime(timezone=True),                  #   type timestamp avec fuseau
        nullable=False,                           #   ne peut pas être nul
        server_default=func.current_timestamp()   #   valeur par défaut CURRENT_TIMESTAMP
    )

    updated_at = Column(                          # colonne updated_at
        DateTime(timezone=True),                  #   type timestamp avec fuseau
        nullable=False,                           #   ne peut pas être nul
        server_default=func.current_timestamp()   #   valeur par défaut CURRENT_TIMESTAMP
    )

    description = Column(                         # colonne description
        Text,                                     #   type texte
        nullable=True                             #   optionnel
    )

    timeout_ms = Column(                          # colonne timeout_ms
        Integer,                                  #   type entier
        nullable=False,                           #   ne peut pas être nul
        server_default=text("5000")               #   valeur par défaut 5000 ms
    )

    is_test_mode = Column(                        # colonne is_test_mode
        Boolean,                                  #   type booléen
        nullable=False,                           #   ne peut pas être nul
        server_default=text("FALSE")              #   valeur par défaut FALSE
    )

    created_by = Column(                          # colonne created_by
        UUID(as_uuid=True),                       #   type UUID PostgreSQL
        ForeignKey("user.id", ondelete="SET NULL"),  # FK vers user.id, met NULL si user supprimé
        nullable=True                             #   optionnel
    )

    updated_by = Column(                          # colonne updated_by
        UUID(as_uuid=True),                       #   type UUID PostgreSQL
        ForeignKey("user.id", ondelete="SET NULL"),  # FK vers user.id, met NULL si user supprimé
        nullable=True                             #   optionnel
    )

    failure_reason = Column(                      # colonne failure_reason
        Text,                                     #   type texte
        nullable=True                             #   optionnel
    )

    max_retry = Column(                           # colonne max_retry
        Integer,                                  #   type entier
        nullable=False,                           #   ne peut pas être nul
        server_default=text("5")                  #   valeur par défaut 5
    )

    is_verified = Column(                         # colonne is_verified
        Boolean,                                  #   type booléen
        nullable=False,                           #   ne peut pas être nul
        server_default=text("FALSE")              #   valeur par défaut FALSE
    )

    __table_args__ = (                            # définition des contraintes et index
        CheckConstraint(                          # contrainte de timeout
            "timeout_ms BETWEEN 1000 AND 30000",
            name="chk_webhook_timeout_range"
        ),
        CheckConstraint(                          # contrainte de max_retry
            "max_retry BETWEEN 0 AND 10",
            name="chk_webhook_max_retry_range"
        ),
        Index("idx_webhook_merchant", "merchant_id"),          # index sur merchant_id
        Index("idx_webhook_status", "status"),                # index sur status
        Index("idx_webhook_last_delivery",                      # index sur last_delivery_attempt DESC
              text("last_delivery_attempt DESC")),
        Index("idx_webhook_retry", "retry_count"),            # index sur retry_count
        Index("idx_webhook_event", "events",                  # index GIN sur events
              postgresql_using="gin"),
    )

# ========================================================
# 3. DDL pour trigger `updated_at`
# ========================================================
ddl_update_ts = DDL("""                              # DDL pour mise à jour du timestamp
CREATE OR REPLACE FUNCTION update_webhook_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;               # mise à jour de updated_at
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_update_webhook
BEFORE UPDATE ON webhook
FOR EACH ROW EXECUTE FUNCTION update_webhook_timestamp();
""")

# ========================================================
# 4. DDL pour procédure `verify_webhook`
# ========================================================
ddl_verify_proc = DDL("""                           # DDL pour procédure de vérification
CREATE OR REPLACE PROCEDURE verify_webhook(p_webhook_id UUID)
LANGUAGE plpgsql AS $$
BEGIN
    UPDATE webhook
    SET is_verified = TRUE,                          # passe is_verified à TRUE
        updated_at = CURRENT_TIMESTAMP               # met à jour updated_at
    WHERE id = p_webhook_id;
END;
$$;
""")

# ========================================================
# 5. Attachement des DDL après création de la table
# ========================================================
event.listen(Webhook.__table__, 'after_create', ddl_update_ts)     # attache ddl_update_ts
event.listen(Webhook.__table__, 'after_create', ddl_verify_proc)  # attache ddl_verify_proc
