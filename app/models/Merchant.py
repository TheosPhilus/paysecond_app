import enum
from sqlalchemy import (
    Column, String, Text, Numeric, DateTime,
    ForeignKey, UniqueConstraint, CheckConstraint,
    Index, DDL, event, func, text
)
from sqlalchemy.dialects.postgresql import UUID, JSONB, ENUM as PGEnum
from app.database import Base

# ========================================================
# 1. Python Enums pour Merchant
# ========================================================
class MerchantCategory(enum.Enum):
    retail     = "retail"
    food       = "food"
    services   = "services"
    digital    = "digital"
    health     = "health"
    education  = "education"
    tourism    = "tourism"
    transport  = "transport"

class KybStatus(enum.Enum):
    pending      = "pending"
    verified     = "verified"
    rejected     = "rejected"
    expired      = "expired"
    under_review = "under_review"
    on_hold      = "on_hold"

class RiskLevel(enum.Enum):
    low      = "low"
    medium   = "medium"
    high     = "high"
    critical = "critical"

class MerchantStatus(enum.Enum):
    active    = "active"
    suspended = "suspended"
    disabled  = "disabled"
    closed    = "closed"

# ========================================================
# 2. Modèle SQLAlchemy pour la table "merchant"
# ========================================================
class Merchant(Base):
    __tablename__ = "merchant"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()")
    )

    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("user.id", ondelete="CASCADE"),
        nullable=False,
        unique=True
    )

    siret = Column(
        String(14),
        nullable=False,
        unique=True
    )

    legal_name = Column(
        String(255),
        nullable=False
    )

    trading_name = Column(
        String(255),
        nullable=True
    )

    category = Column(
        PGEnum(MerchantCategory, name="merchant_category", create_type=True),
        nullable=False
    )

    kyb_status = Column(
        PGEnum(KybStatus, name="merchant_kyb_status", create_type=True),
        nullable=False,
        server_default=KybStatus.pending.value
    )

    monthly_volume_estimate = Column(
        Numeric(12, 2),
        nullable=True
    )

    website_url = Column(
        String(255),
        nullable=True
    )

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.current_timestamp()
    )

    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.current_timestamp()
    )

    business_description = Column(
        Text,
        nullable=True
    )

    address = Column(
        JSONB,
        nullable=True
    )

    tax_identification = Column(
        String(50),
        nullable=True
    )

    risk_level = Column(
        PGEnum(RiskLevel, name="merchant_risk_level", create_type=True),
        nullable=False,
        server_default=RiskLevel.medium.value
    )

    bank_account_id = Column(
        UUID(as_uuid=True),
        ForeignKey("bank_account.id", ondelete="SET NULL"),
        nullable=True
    )

    status = Column(
        PGEnum(MerchantStatus, name="merchant_status", create_type=True),
        nullable=False,
        server_default=MerchantStatus.active.value
    )

    __table_args__ = (
        CheckConstraint(
            "char_length(siret) = 14 AND siret ~ '^[0-9]{14}$'",
            name="chk_merchant_siret_format"
        ),
        UniqueConstraint("user_id", name="uq_merchant_user"),
        Index("idx_merchant_siret", "siret", unique=True),
        Index("idx_merchant_kyb_status", "kyb_status"),
        Index("idx_merchant_user_id", "user_id"),
        Index("idx_merchant_category", "category"),
        Index("idx_merchant_risk_level", "risk_level"),
    )

# ========================================================
# 3. DDL pour triggers et procédure stockée
# ========================================================
ddl_update_timestamp = DDL("""
CREATE OR REPLACE FUNCTION update_merchant_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at := CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_update_merchants
BEFORE UPDATE ON merchant
FOR EACH ROW EXECUTE FUNCTION update_merchant_timestamp();
""")

ddl_update_kyb_proc = DDL("""
CREATE OR REPLACE PROCEDURE update_merchant_kyb_status(
    p_merchant_id UUID,
    p_new_status VARCHAR
)
LANGUAGE plpgsql
AS $$
BEGIN
    UPDATE merchant
    SET kyb_status = p_new_status,
        updated_at = CURRENT_TIMESTAMP
    WHERE id = p_merchant_id;
END;
$$;
""")

# ========================================================
# 4. Attachement des DDL après création de la table
# ========================================================
event.listen(Merchant.__table__, 'after_create', ddl_update_timestamp)
event.listen(Merchant.__table__, 'after_create', ddl_update_kyb_proc)
