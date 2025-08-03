import enum
from sqlalchemy import (
    Column, DateTime, Boolean, Numeric, String, Text, ForeignKey,
    Index, DDL, event, text
)
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import (
    UUID, INET, CIDR, JSONB, ENUM as PGEnum
)
from sqlalchemy.schema import Computed
from app.database import Base

# ========================================================
# 📜 1. Python Enums pour WalletAuditLog
# ========================================================
class OperationType(enum.Enum):
    deposit     = "deposit"     # dépôt
    withdrawal  = "withdrawal"  # retrait
    transfer    = "transfer"    # virement interne
    adjustment  = "adjustment"  # ajustement de solde
    fee         = "fee"         # collecte de frais
    reversal    = "reversal"    # annulation
    chargeback  = "chargeback"  # rétrofacturation

class AuditCurrency(enum.Enum):
    EUR = "EUR"  # euro
    USD = "USD"  # dollar US
    GBP = "GBP"  # livre sterling
    XOF = "XOF"  # franc CFA
    CAD = "CAD"  # dollar canadien
    JPY = "JPY"  # yen japonais

# ========================================================
# 📜 2. Modèle SQLAlchemy pour la table "wallet_audit_log"
# ========================================================
class WalletAuditLog(Base):
    __tablename__ = "wallet_audit_log"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()")
    )  
    # [id] : Identifiant unique généré automatiquement

    wallet_id = Column(
        UUID(as_uuid=True),
        ForeignKey("wallet.id", ondelete="CASCADE"),
        nullable=False
    )  
    # [wallet_id] : Référence au portefeuille concerné (ON DELETE CASCADE)

    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("user.id", ondelete="SET NULL"),
        nullable=True
    )  
    # [user_id] : Référence à l'utilisateur (ON DELETE SET NULL)

    old_balance = Column(
        Numeric(12, 2),
        nullable=False
    )  
    # [old_balance] : Solde avant l'opération

    new_balance = Column(
        Numeric(12, 2),
        nullable=False
    )  
    # [new_balance] : Solde après l'opération

    change_amount = Column(
        Numeric(12, 2),
        Computed("new_balance - old_balance", persisted=True),
        nullable=False
    )  
    # [change_amount] : Différence calculée (new_balance - old_balance)

    operation_type = Column(
        PGEnum(OperationType, name="wallet_audit_log_operation_type", create_type=True),
        nullable=False
    )  
    # [operation_type] : Type d'opération, contrôlé par l'Enum

    transaction_id = Column(
        UUID(as_uuid=True),
        nullable=True
    )  
    # [transaction_id] : Référence facultative à une transaction

    audit_batch_id = Column(
        UUID(as_uuid=True),
        nullable=True
    )  
    # [audit_batch_id] : Regroupe plusieurs opérations d'audit

    notes = Column(
        Text,
        nullable=True
    )  
    # [notes] : Commentaires additionnels

    changed_by = Column(
        UUID(as_uuid=True),
        ForeignKey("user.id", ondelete="SET NULL"),
        nullable=True
    )  
    # [changed_by] : Utilisateur ayant initié l'opération

    changed_at = Column(
        DateTime(timezone=True),
        primary_key=True,
        server_default=func.current_timestamp(),
        nullable=False
    )  
    # [changed_at] : Horodatage de l'opération (partition key)

    ip_address = Column(
        INET,
        nullable=True
    )  
    # [ip_address] : Adresse IP d'origine

    ip_truncated = Column(
        CIDR,
        nullable=True
    )  
    # [ip_truncated] : IP anonymisée (masquée en /24 ou /64)

    source_system = Column(
        String(30),
        nullable=True
    )  
    # [source_system] : Origine de la requête (web, mobile, etc.)

    entry_hash = Column(
        Text,
        nullable=True
    )  
    # [entry_hash] : Hash d'intégrité basé sur wallet_id, new_balance, changed_at

    currency = Column(
        PGEnum(AuditCurrency, name="wallet_audit_log_currency", create_type=True),
        nullable=False
    )  
    # [currency] : Devise ISO 4217 utilisée

    __table_args__ = (
        Index("idx_wallet_audit_wallet", "wallet_id"),                                      # index wallet_id
        Index("idx_wallet_audit_changed_at", "changed_at"),                                 # index changed_at
        Index("idx_wallet_audit_operation", "operation_type"),                             # index operation_type
        Index("idx_wallet_audit_wallet_date", "wallet_id", text("changed_at DESC")),        # index composite wallet_id + changed_at DESC
        Index("idx_wallet_audit_transaction", "transaction_id"),                           # index transaction_id
    )

# ========================================================
# 📜 3. DDL pour triggers
# ========================================================
ddl_set_user_id = DDL("""
CREATE OR REPLACE FUNCTION set_audit_user_id()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.user_id IS NULL THEN
        SELECT user_id INTO NEW.user_id FROM wallet WHERE id = NEW.wallet_id;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql STABLE;

CREATE TRIGGER trg_set_audit_user_id
BEFORE INSERT ON wallet_audit_log
FOR EACH ROW EXECUTE FUNCTION set_audit_user_id();
""")  
# Trigger 1 : remplit user_id depuis wallet si absent

ddl_calc_audit_fields = DDL("""
CREATE OR REPLACE FUNCTION calculate_audit_fields()
RETURNS TRIGGER AS $$
BEGIN
    NEW.ip_truncated := CASE
        WHEN NEW.ip_address IS NULL THEN NULL
        WHEN family(NEW.ip_address) = 4 THEN set_masklen(NEW.ip_address, 24)
        ELSE set_masklen(NEW.ip_address, 64)
    END;
    NEW.entry_hash := encode(
        digest(NEW.wallet_id::TEXT || NEW.new_balance::TEXT || NEW.changed_at::TEXT, 'sha256'),
        'hex'
    );
    RETURN NEW;
END;
$$ LANGUAGE plpgsql STABLE;

CREATE TRIGGER trg_calculate_audit_fields
BEFORE INSERT ON wallet_audit_log
FOR EACH ROW EXECUTE FUNCTION calculate_audit_fields();
""")  
# Trigger 2 : calcule ip_truncated et entry_hash

ddl_check_tx_exists = DDL("""
CREATE OR REPLACE FUNCTION check_transaction_exists()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.transaction_id IS NOT NULL THEN
        PERFORM 1 FROM transaction WHERE id = NEW.transaction_id;
        IF NOT FOUND THEN
            RAISE EXCEPTION 'Transaction invalide: %', NEW.transaction_id;
        END IF;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE CONSTRAINT TRIGGER trg_check_transaction_exists
AFTER INSERT OR UPDATE ON wallet_audit_log
DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW EXECUTE FUNCTION check_transaction_exists();
""")  
# Trigger 3 : vérifie l’existence de la transaction référencée

# ========================================================
# 🚀 4. Attachement des DDL après création de la table
# ========================================================
event.listen(WalletAuditLog.__table__, 'after_create', ddl_set_user_id)
event.listen(WalletAuditLog.__table__, 'after_create', ddl_calc_audit_fields)
event.listen(WalletAuditLog.__table__, 'after_create', ddl_check_tx_exists)
