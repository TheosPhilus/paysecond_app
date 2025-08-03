import enum
from sqlalchemy import (
    Column, String, Text, Boolean, DateTime, ForeignKey,
    UniqueConstraint, Index, DDL, event, text, func
)
from sqlalchemy.dialects.postgresql import UUID, ENUM as PGEnum
from app.database import Base

# ========================================================
# 1. Python Enums pour BankAccount
# ========================================================
class BankAccountStatus(enum.Enum):
    pending   = "pending"   # en attente
    verified  = "verified"  # validé
    rejected  = "rejected"  # refusé
    suspended = "suspended" # suspendu

class VerificationMethod(enum.Enum):
    manual = "manual"  # vérification manuelle
    auto   = "auto"    # vérification automatique

# ========================================================
# 2. Modèle SQLAlchemy pour la table "bank_account"
# ========================================================
class BankAccount(Base):
    __tablename__ = "bank_account"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()")
    )  # Identifiant unique du compte

    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("user.id", ondelete="CASCADE"),
        nullable=False
    )  # Référence à l’utilisateur (ON DELETE CASCADE)

    iban = Column(
        String(34),
        nullable=False
    )  # Numéro IBAN

    bic = Column(
        String(11),
        nullable=False
    )  # Code BIC/SWIFT

    account_holder_name = Column(
        Text,
        nullable=False
    )  # Nom complet du titulaire

    bank_name = Column(
        String(100),
        nullable=True
    )  # Nom de la banque

    currency = Column(
        String(3),
        nullable=False,
        server_default=text("'EUR'")
    )  # Devise ISO (ex. EUR)

    is_primary = Column(
        Boolean,
        nullable=False,
        server_default=text("FALSE")
    )  # Indique si c’est le compte principal

    status = Column(
        PGEnum(BankAccountStatus, name="bank_account_status", create_type=True),
        nullable=False,
        server_default=BankAccountStatus.pending.value
    )  # Statut du compte

    verification_method = Column(
        PGEnum(VerificationMethod, name="bank_account_verification_method", create_type=True),
        nullable=False,
        server_default=VerificationMethod.manual.value
    )  # Méthode de vérification

    rejected_reason = Column(
        Text,
        nullable=True
    )  # Raison du rejet (le cas échéant)

    verified_at = Column(
        DateTime(timezone=True),
        nullable=True
    )  # Timestamp de vérification

    rejected_at = Column(
        DateTime(timezone=True),
        nullable=True
    )  # Timestamp de rejet

    last_used_at = Column(
        DateTime(timezone=True),
        nullable=True
    )  # Dernière utilisation

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.current_timestamp()
    )  # Date de création

    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.current_timestamp()
    )  # Date de dernière mise à jour

    created_by = Column(
        UUID(as_uuid=True),
        ForeignKey("user.id", ondelete="SET NULL"),
        nullable=True
    )  # Qui a créé le compte

    verified_by = Column(
        UUID(as_uuid=True),
        ForeignKey("user.id", ondelete="SET NULL"),
        nullable=True
    )  # Qui a validé le compte

    __table_args__ = (
        UniqueConstraint("iban", "user_id", name="unique_iban_user"),
        Index("idx_bank_account_user", "user_id"),
        Index("idx_bank_account_status", "status"),
        Index("idx_bank_account_iban", "iban"),
    )

# ========================================================
# 3. DDL pour triggers et procédure stockée
# ========================================================
ddl_timestamps = DDL("""
CREATE OR REPLACE FUNCTION trg_set_bank_account_timestamps()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at := CURRENT_TIMESTAMP;

    IF NEW.status = 'verified' AND OLD.status <> 'verified' THEN
        NEW.verified_at := CURRENT_TIMESTAMP;
    ELSIF NEW.status = 'rejected' AND OLD.status <> 'rejected' THEN
        NEW.rejected_at := CURRENT_TIMESTAMP;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_update_bank_account_timestamps
BEFORE UPDATE ON bank_account
FOR EACH ROW EXECUTE FUNCTION trg_set_bank_account_timestamps();
""")

ddl_primary = DDL("""
CREATE OR REPLACE FUNCTION ensure_single_primary_account()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.is_primary THEN
        UPDATE bank_account
        SET is_primary = FALSE
        WHERE user_id = NEW.user_id
          AND id <> NEW.id;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_ensure_primary_account
BEFORE INSERT OR UPDATE ON bank_account
FOR EACH ROW EXECUTE FUNCTION ensure_single_primary_account();
""")

ddl_verify_proc = DDL("""
CREATE OR REPLACE PROCEDURE verify_bank_account(
    p_account_id UUID,
    p_verifier_user_id UUID,
    p_method VARCHAR DEFAULT 'manual'
)
LANGUAGE plpgsql AS $$
BEGIN
    UPDATE bank_account
    SET status = 'verified',
        verified_at = CURRENT_TIMESTAMP,
        verified_by = p_verifier_user_id,
        verification_method = p_method
    WHERE id = p_account_id AND status = 'pending';
END;
$$;
""")

# ========================================================
# 4. Attachement des DDL après création de la table
# ========================================================
event.listen(BankAccount.__table__, 'after_create', ddl_timestamps)
event.listen(BankAccount.__table__, 'after_create', ddl_primary)
event.listen(BankAccount.__table__, 'after_create', ddl_verify_proc)
