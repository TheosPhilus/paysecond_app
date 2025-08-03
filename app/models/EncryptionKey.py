import enum
from sqlalchemy import (
    Column, DateTime, Boolean, Integer, Text, ForeignKey,
    CheckConstraint, Index, DDL, event, text
)
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import UUID, JSONB, CHAR, ENUM as PGEnum
from sqlalchemy.schema import Computed
from app.database import Base

# ========================================================
# 🔐 1. Python Enums pour EncryptionKey
# ========================================================
class KeyAlgorithm(enum.Enum):
    aes_256_gcm       = "aes-256-gcm"        # algorithme AES-GCM 256 bits
    rsa_4096          = "rsa-4096"           # algorithme RSA 4096 bits
    chacha20_poly1305 = "chacha20-poly1305"  # algorithme ChaCha20-Poly1305

class KeyType(enum.Enum):
    card_data           = "card_data"           # chiffrement des données de carte
    personal_data       = "personal_data"       # chiffrement des données personnelles
    documents           = "documents"           # chiffrement des documents
    transaction_details = "transaction_details" # chiffrement des détails de transaction

class KeyStorage(enum.Enum):
    database     = "database"      # stockage dans la base
    kms_external = "kms_external"  # stockage dans un KMS externe
    hsm          = "hsm"           # stockage dans un HSM

# ========================================================
# 🔐 2. Modèle SQLAlchemy pour la table "encryption_key"
# ========================================================
class EncryptionKey(Base):
    __tablename__ = "encryption_key"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()")
    )  # [id] : Identifiant unique, généré automatiquement

    key = Column(
        Text,
        nullable=False
    )  # [key] : Clé chiffrée stockée (protégée par une clé maître)

    key_algorithm = Column(
        PGEnum(KeyAlgorithm, name="encryption_key_algorithm", create_type=True),
        nullable=False,
        server_default=KeyAlgorithm.aes_256_gcm.value
    )  # [key_algorithm] : Algorithme utilisé, valeurs limitées par l’énumération

    active = Column(
        Boolean,
        nullable=False,
        server_default=text("TRUE")
    )  # [active] : Indique si la clé est active

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.current_timestamp()
    )  # [created_at] : Date de création, horodatée automatiquement

    rotated_at = Column(
        DateTime(timezone=True),
        nullable=True
    )  # [rotated_at] : Dernière date de rotation de la clé

    key_type = Column(
        PGEnum(KeyType, name="encryption_key_type", create_type=True),
        nullable=False
    )  # [key_type] : Type de données chiffrées, valeurs contrôlées

    key_version = Column(
        Integer,
        nullable=False,
        server_default=text("1")
    )  # [key_version] : Version incrémentale, strictement > 0

    created_by = Column(
        UUID(as_uuid=True),
        ForeignKey("user.id", ondelete="RESTRICT"),
        nullable=True
    )  # [created_by] : Référence à l’utilisateur créateur, suppression restreinte

    expires_at = Column(
        DateTime(timezone=True),
        nullable=False
    )  # [expires_at] : Date d’expiration, doit être postérieure à created_at

    last_used_at = Column(
        DateTime(timezone=True),
        nullable=True
    )  # [last_used_at] : Dernière utilisation pour chiffrement/déchiffrement

    key_metadata = Column(
        "metadata",   # nom réel de la colonne en base
        JSONB,
        nullable=True # autorise la valeur NULL
    )  # [metadata] : Métadonnées techniques (IV, tag, etc.)

    key_fingerprint = Column(
        CHAR(64),
        Computed("encode(sha256(key::bytea), 'hex')", persisted=True)
    )  # [key_fingerprint] : Empreinte SHA-256, calculée et stockée automatiquement

    key_storage = Column(
        PGEnum(KeyStorage, name="encryption_key_storage", create_type=True),
        nullable=False,
        server_default=KeyStorage.database.value
    )  # [key_storage] : Lieu de stockage du secret (database/kms_external/hsm)

    __table_args__ = (
        CheckConstraint(
            "key_version > 0",
            name="chk_encryption_key_version_positive"
        ),  # version strictement positive

        CheckConstraint(
            "expires_at > created_at",
            name="chk_encryption_key_expires_after_created"
        ),  # expiration après création

        Index(
            "idx_encryption_key_active_type_optimized",
            "key_type",
            unique=True,
            postgresql_where=text("active = TRUE")
        ),  # index partiel pour retrouver la clé active par type

        Index(
            "idx_encryption_key_expiry",
            "expires_at"
        ),  # index pour identifier les clés en expiration

        Index(
            "idx_encryption_key_fingerprint",
            "key_fingerprint"
        ),  # index sur l’empreinte pour garantir l’unicité/recherche rapide

        Index(
            "idx_encryption_key_type_active",
            "key_type", "active"
        ),  # index combiné type + active pour affiner les recherches
    )


# ========================================================
# 🔔 3. DDL pour triggers de rotation et de protection
# ========================================================
ddl_rotate_keys = DDL("""
CREATE OR REPLACE FUNCTION rotate_encryption_keys()
RETURNS TRIGGER AS $$
BEGIN
    -- Désactive les anciennes clés actives du même type
    UPDATE encryption_key
    SET active = FALSE,
        rotated_at = CURRENT_TIMESTAMP
    WHERE active = TRUE
      AND key_type = NEW.key_type
      AND id <> NEW.id;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_rotate_keys
AFTER INSERT ON encryption_key
FOR EACH ROW
WHEN (NEW.active = TRUE)
EXECUTE FUNCTION rotate_encryption_keys();
""")  # désactive automatiquement les anciennes clés à chaque insertion d’une nouvelle clé active

ddl_prevent_deactivation = DDL("""
CREATE OR REPLACE FUNCTION prevent_key_deactivation()
RETURNS TRIGGER AS $$
DECLARE
    cnt INT;
BEGIN
    IF OLD.active = TRUE AND NEW.active = FALSE THEN
        -- compte les clés actives restantes pour ce type
        SELECT COUNT(*) INTO cnt
        FROM encryption_key
        WHERE key_type = OLD.key_type
          AND active = TRUE
          AND id <> OLD.id;

        IF cnt = 0 THEN
            RAISE EXCEPTION
                'Impossible de désactiver la dernière clé active de type %',
                OLD.key_type
            USING HINT = 'Activez d’abord une nouvelle clé avant de désactiver l’actuelle.';
        END IF;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_prevent_key_deactivation
BEFORE UPDATE ON encryption_key
FOR EACH ROW
EXECUTE FUNCTION prevent_key_deactivation();
""")  # empêche la désactivation de la dernière clé active pour un type donné

# ========================================================
# 🚀 4. Attachement des DDL après création de la table
# ========================================================
event.listen(
    EncryptionKey.__table__,
    'after_create',
    ddl_rotate_keys
)
event.listen(
    EncryptionKey.__table__,
    'after_create',
    ddl_prevent_deactivation
)
