import enum
from sqlalchemy import (
    Column, Text, Boolean, BigInteger, DateTime, Index, text, ForeignKey,
)
from sqlalchemy.dialects.postgresql import (
    UUID, INET, CIDR, ARRAY, ENUM as PGEnum
)
from app.database import Base

# ========================================================
# 🔑 1. Python Enum pour api_key.status
# ========================================================
class ApiKeyStatus(enum.Enum):
    active  = "active"   # clé opérationnelle
    revoked = "revoked"  # clé révoquée
    expired = "expired"  # clé expirée

# ========================================================
# 🔑 2. Modèle SQLAlchemy pour la table "api_key"
# ========================================================
class ApiKey(Base):
    __tablename__ = "api_key"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()")
    )  # [id] : Identifiant unique de la clé API, généré automatiquement

    merchant_id = Column(
        UUID(as_uuid=True),
        ForeignKey("merchant.id", ondelete="CASCADE"),
        nullable=False
    )  # [merchant_id] : Référence au commerçant (ON DELETE CASCADE)

    key_hash = Column(
        Text,
        nullable=False
    )  # [key_hash] : Hash sécurisé de la clé API

    description = Column(
        Text,
        nullable=True
    )  # [description] : Description de l’usage de la clé

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP")
    )  # [created_at] : Date de création de la clé

    last_used_at = Column(
        DateTime(timezone=True),
        nullable=True
    )  # [last_used_at] : Horodatage de la dernière utilisation

    expires_at = Column(
        DateTime(timezone=True),
        nullable=True
    )  # [expires_at] : Date d’expiration de la clé

    status = Column(
        PGEnum(ApiKeyStatus, name="api_key_status", create_type=True),
        nullable=False,
        server_default=ApiKeyStatus.active.value
    )  # [status] : Statut de la clé (active, revoked, expired)

    permissions = Column(
        ARRAY(Text),
        nullable=False,
        server_default=text("ARRAY['read']::text[]")
    )  # [permissions] : Permissions accordées (tableau de chaînes)

    ip_restrictions = Column(
        ARRAY(CIDR),
        nullable=True
    )  # [ip_restrictions] : Liste d’IP ou de sous-réseaux autorisés

    plain_key = Column(
        Text,
        nullable=True
    )  # [plain_key] : Clé en clair (affichée une seule fois à la création)

    last_ip_used = Column(
        INET,
        nullable=True
    )  # [last_ip_used] : Dernière adresse IP ayant utilisé la clé

    is_test_mode = Column(
        Boolean,
        nullable=False,
        server_default=text("FALSE")
    )  # [is_test_mode] : Indique si la clé est en mode test

    usage_count = Column(
        BigInteger,
        nullable=False,
        server_default=text("0")
    )  # [usage_count] : Nombre total d’utilisations de la clé

    __table_args__ = (
        Index("idx_api_key_merchant", "merchant_id"),             # index pour retrouver les clés d’un commerçant
        Index("idx_api_key_status", "status"),                    # index sur le statut de la clé
        Index("idx_api_key_last_used_at", text("last_used_at DESC")),  # index trié sur last_used_at
        Index("idx_api_key_expires_at", "expires_at"),            # index sur la date d’expiration
        Index("idx_api_key_usage_count", "usage_count"),          # index sur le compteur d’utilisation
    )
