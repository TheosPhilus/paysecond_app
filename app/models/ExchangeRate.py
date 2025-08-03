import enum
from sqlalchemy import (
    Column, Numeric, DateTime, String, Index,
    DDL, event, text, ForeignKey
)
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import UUID, ENUM as PGEnum
from app.database import Base

# ========================================================
# 1. Python Enum pour les devises
# ========================================================
class Currency(enum.Enum):
    EUR = "EUR"  # euro
    USD = "USD"  # dollar américain
    GBP = "GBP"  # livre sterling
    XOF = "XOF"  # franc CFA

# ========================================================
# 2. Modèle SQLAlchemy pour la table "exchange_rate"
# ========================================================
class ExchangeRate(Base):
    __tablename__ = "exchange_rate"

    base_currency = Column(
        PGEnum(Currency, name="exchange_rate_currency", create_type=True),
        primary_key=True,
        nullable=False
    )  # [base_currency] : Devise de base (clé primaire composite)

    target_currency = Column(
        PGEnum(Currency, name="exchange_rate_currency", create_type=True),
        primary_key=True,
        nullable=False
    )  # [target_currency] : Devise cible (clé primaire composite)

    valid_from = Column(
        DateTime(timezone=True),
        primary_key=True,
        nullable=False
    )  # [valid_from] : Date de prise d'effet (clé primaire composite)

    rate = Column(
        Numeric(10, 6),
        nullable=False
    )  # [rate] : Taux de change (précision 6 décimales)

    valid_to = Column(
        DateTime(timezone=True),
        nullable=True
    )  # [valid_to] : Date de fin de validité

    source = Column(
        String(20),
        nullable=False
    )  # [source] : Source du taux de change

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.current_timestamp()
    )  # [created_at] : Date de création de l'enregistrement

    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.current_timestamp()
    )  # [updated_at] : Date de dernière modification (mise à jour via trigger)

    __table_args__ = (
        Index(
            "idx_exchange_rate_pair",
            "base_currency", "target_currency"
        ),  # index sur la paire de devises

        Index(
            "idx_exchange_rate_validity",
            text("valid_from DESC")
        ),  # index pour trier par date de prise d'effet descendant
    )

# ========================================================
# 3. DDL pour trigger de mise à jour d'updated_at
# ========================================================
ddl_update_exchange_rate_ts = DDL("""
CREATE OR REPLACE FUNCTION update_exchange_rate_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at := CURRENT_TIMESTAMP;  -- met à jour updated_at avant chaque UPDATE
    RETURN NEW;
END;
$$ LANGUAGE plpgsql STABLE;

CREATE TRIGGER trg_update_exchange_rate
BEFORE UPDATE ON exchange_rate
FOR EACH ROW EXECUTE FUNCTION update_exchange_rate_timestamp();
""")  # trigger qui rafraîchit updated_at

# ========================================================
# 4. Attachement du DDL après création de la table
# ========================================================
event.listen(
    ExchangeRate.__table__,
    'after_create',
    ddl_update_exchange_rate_ts
)
