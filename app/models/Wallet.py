import enum
from sqlalchemy import (
    Column, DateTime, Boolean, Numeric, ForeignKey, CheckConstraint,
    Index, DDL, event, text
)
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import UUID, ENUM as PGEnum
from app.database import Base

# ========================================================
# 1. Python Enums pour Wallet
# ========================================================
class Currency(enum.Enum):
    EUR = "EUR"  # euro (devise de base)
    USD = "USD"  # dollar américain
    GBP = "GBP"  # livre sterling
    XOF = "XOF"  # franc CFA
    CAD = "CAD"  # dollar canadien
    JPY = "JPY"  # yen japonais

class WalletStatus(enum.Enum):
    active   = "active"   # portefeuille actif
    inactive = "inactive" # portefeuille inactif
    frozen   = "frozen"   # portefeuille gelé

# ========================================================
# 2. Modèle SQLAlchemy pour la table "wallet"
# ========================================================
class Wallet(Base):
    __tablename__ = "wallet"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()")
    )  # [id] : Identifiant unique du portefeuille, généré automatiquement

    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("user.id", ondelete="CASCADE"),
        nullable=False
    )  # [user_id] : Référence vers l'utilisateur propriétaire (ON DELETE CASCADE)

    balance = Column(
        Numeric(12, 2),
        nullable=False,
        server_default=text("0.00")
    )  # [balance] : Solde actuel, précision 2 décimales, non négatif

    currency = Column(
        PGEnum(Currency, name="wallet_currency", create_type=True),
        nullable=False,
        server_default=Currency.EUR.value
    )  # [currency] : Devise ISO 4217, valeurs limitées par l'énumération

    last_updated = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.current_timestamp()
    )  # [last_updated] : Date et heure de la dernière mise à jour

    max_balance = Column(
        Numeric(12, 2),
        nullable=False,
        server_default=text("1000000.00")
    )  # [max_balance] : Limite maximale du solde, bornée entre 0 et 10 000 000

    is_primary = Column(
        Boolean,
        nullable=False,
        server_default=text("TRUE")
    )  # [is_primary] : Indique si c'est le portefeuille principal

    status = Column(
        PGEnum(WalletStatus, name="wallet_status", create_type=True),
        nullable=False,
        server_default=WalletStatus.active.value
    )  # [status] : Statut du portefeuille (active/inactive/frozen)

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.current_timestamp()
    )  # [created_at] : Horodatage de création

    deleted_at = Column(
        DateTime(timezone=True),
        nullable=True
    )  # [deleted_at] : Suppression logique (soft delete)

    __table_args__ = (
        CheckConstraint("balance >= 0", name="chk_wallet_balance_non_negative"),  # solde non négatif
        CheckConstraint(
            "max_balance >= 0 AND max_balance <= 10000000.00",
            name="chk_wallet_max_balance_range"
        ),  # bornes du solde maximal
        Index("idx_wallet_user_currency", "user_id", "currency", unique=True),     # un portefeuille par devise/utilisateur
        Index("idx_wallet_user_id", "user_id"),                                   # index pour rechercher par utilisateur
        Index("idx_wallet_currency", "currency"),                                 # index pour filtrer par devise
        Index(
            "idx_wallet_status",
            "status",
            postgresql_where=text("status != 'active'")
        ),  # index partiel pour portefeuilles non actifs
    )

# ========================================================
# 3. DDL pour triggers
# ========================================================
ddl_update_wallet_ts = DDL("""
CREATE OR REPLACE FUNCTION update_wallet_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.last_updated = CURRENT_TIMESTAMP;  -- met à jour last_updated avant chaque UPDATE
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_update_wallet
BEFORE UPDATE ON wallet
FOR EACH ROW EXECUTE FUNCTION update_wallet_timestamp();
""")  # trigger automatique sur last_updated

ddl_check_wallet_balance = DDL("""
CREATE OR REPLACE FUNCTION check_wallet_balance()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.balance < 0 THEN
        RAISE EXCEPTION 'Le solde du portefeuille ne peut pas être négatif.';  -- empêche solde négatif
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE CONSTRAINT TRIGGER trg_check_wallet_balance
AFTER INSERT OR UPDATE OF balance ON wallet
FOR EACH ROW EXECUTE FUNCTION check_wallet_balance();
""")  # trigger complémentaire pour garantir balance >= 0

# ========================================================
# 4. Attachement des DDL après création de la table
# ========================================================
event.listen(Wallet.__table__, 'after_create', ddl_update_wallet_ts)
event.listen(Wallet.__table__, 'after_create', ddl_check_wallet_balance)
