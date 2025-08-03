import enum
from sqlalchemy import (
    Column, DateTime, Boolean, Integer, String, Text, Numeric,
    ForeignKey, CheckConstraint, Index, DDL, event, text
)
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import UUID, INET, JSONB, ENUM as PGEnum
from app.database import Base

# ========================================================
# 1. Python Enums pour Transaction
# ========================================================
class TransactionType(enum.Enum):
    payment         = "payment"
    refund          = "refund"
    chargeback      = "chargeback"
    withdrawal      = "withdrawal"
    deposit         = "deposit"
    transfer        = "transfer"
    fee_collection  = "fee_collection"
    adjustment      = "adjustment"

class TransactionMethod(enum.Enum):
    card            = "card"
    wallet          = "wallet"
    bank_transfer   = "bank_transfer"
    subscription    = "subscription"
    crypto          = "crypto"

class Currency(enum.Enum):
    EUR = "EUR"
    USD = "USD"
    GBP = "GBP"
    XOF = "XOF"
    CAD = "CAD"
    JPY = "JPY"

class TransactionStatus(enum.Enum):
    pending     = "pending"
    completed   = "completed"
    failed      = "failed"
    cancelled   = "cancelled"
    refunded    = "refunded"
    disputed    = "disputed"
    authorized  = "authorized"
    captured    = "captured"

# ========================================================
# 2. Modèle SQLAlchemy pour la table "transaction"
# ========================================================
class Transaction(Base):
    __tablename__ = "transaction"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()")
    )  # [id] : Identifiant unique, généré automatiquement.

    created_at = Column(
        DateTime(timezone=True),
        primary_key=True,
        server_default=func.current_timestamp(),
        nullable=False
    )  # [created_at] : Horodatage de la création, partition clé.

    transaction_type = Column(
        PGEnum(TransactionType, name="transaction_type", create_type=True),
        nullable=False
    )  # [transaction_type] : Type d’opération, contrôlé par Enum.

    transaction_method = Column(
        PGEnum(TransactionMethod, name="transaction_method", create_type=True),
        nullable=False
    )  # [transaction_method] : Mode d’opération, contrôlé par Enum.

    card_id = Column(
        UUID(as_uuid=True),
        ForeignKey("card.id", ondelete="SET NULL"),
        nullable=True
    )  # [card_id] : Carte utilisée (le cas échéant).

    sender_wallet_id = Column(
        UUID(as_uuid=True),
        ForeignKey("wallet.id", ondelete="SET NULL"),
        nullable=True
    )  # [sender_wallet_id] : Portefeuille émetteur.

    recipient_wallet_id = Column(
        UUID(as_uuid=True),
        ForeignKey("wallet.id", ondelete="SET NULL"),
        nullable=True
    )  # [recipient_wallet_id] : Portefeuille destinataire.

    amount = Column(
        Numeric(12, 2),
        nullable=False
    )  # [amount] : Montant, positif ≤ 10 000 000.

    currency = Column(
        PGEnum(Currency, name="transaction_currency", create_type=True),
        nullable=False,
        server_default=Currency.EUR.value
    )  # [currency] : Devise ISO 4217.

    status = Column(
        PGEnum(TransactionStatus, name="transaction_status", create_type=True),
        nullable=False
    )  # [status] : Statut de la transaction.

    fraud_flag = Column(
        Boolean,
        nullable=False,
        server_default=text("FALSE")
    )  # [fraud_flag] : Indique une suspicion de fraude.

    completed_at = Column(
        DateTime(timezone=True),
        nullable=True
    )  # [completed_at] : Horodatage de complétion.

    archived = Column(
        Boolean,
        nullable=False,
        server_default=text("FALSE")
    )  # [archived] : Marque les transactions archivées.

    merchant_id = Column(
        UUID(as_uuid=True),
        ForeignKey("merchant.id", ondelete="SET NULL"),
        nullable=True
    )  # [merchant_id] : Commerçant impliqué (le cas échéant).

    fee_amount = Column(
        Numeric(10, 2),
        nullable=False,
        server_default=text("0.00")
    )  # [fee_amount] : Montant des frais associés.

    description = Column(
        Text,
        nullable=True
    )  # [description] : Commentaire libre.

    transaction_metadata = Column(
        "metadata",   # nom réel de la colonne en base
        JSONB,
        nullable=True # autorise la valeur NULL
    )  # [metadata] : Métadonnées techniques (IV, tag, etc.)

    processor_transaction_id = Column(
        String(255),
        nullable=True
    )  # [processor_transaction_id] : Référence externe.

    failure_reason = Column(
        Text,
        nullable=True
    )  # [failure_reason] : Raison d’échec éventuel.

    ip_address = Column(
        INET,
        nullable=True
    )  # [ip_address] : Adresse IP d’origine.

    source_system = Column(
        String(30),
        nullable=True
    )  # [source_system] : Système émetteur de l’opération.

    audit_batch_id = Column(
        UUID(as_uuid=True),
        nullable=True
    )  # [audit_batch_id] : Regroupe plusieurs opérations.

    deleted_at = Column(
        DateTime(timezone=True),
        nullable=True
    )  # [deleted_at] : Suppression logique.

    __table_args__ = (
        CheckConstraint(
            "sender_wallet_id IS DISTINCT FROM recipient_wallet_id",
            name="chk_no_self_transfer"
        ),  # empêche un portefeuille de s’envoyer à lui-même

        CheckConstraint(
            "(transaction_type IN ('payment','transfer','withdrawal','chargeback') AND sender_wallet_id IS NOT NULL) OR "
            "(transaction_type IN ('deposit','payment','transfer','refund') AND recipient_wallet_id IS NOT NULL) OR "
            "(transaction_type IN ('fee_collection','adjustment') AND "
            "(sender_wallet_id IS NOT NULL OR recipient_wallet_id IS NOT NULL))",
            name="chk_wallet_ids_for_type"
        ),  # cohérence wallets ↔ type de transaction

        CheckConstraint(
            "amount > 0 AND amount <= 10000000",
            name="chk_transaction_amount_range"
        ),  # montant valide

        Index("idx_transaction_type_status", "transaction_type", "status"),
        Index("idx_transaction_sender", "sender_wallet_id"),
        Index("idx_transaction_recipient", "recipient_wallet_id"),
        Index("idx_transaction_created", "created_at"),
        Index("idx_transaction_status", "status"),
        Index("idx_transaction_merchant", "merchant_id"),
        Index("idx_transaction_card_id", "card_id"),
        Index(
            "idx_transaction_fraud",
            "fraud_flag",
            postgresql_where=text("fraud_flag = TRUE")
        ),
    )

# ========================================================
# 3. DDL pour le trigger de complétion automatique
# ========================================================
ddl_set_completed_at = DDL("""
CREATE OR REPLACE FUNCTION set_transaction_completed_at()
RETURNS TRIGGER AS $$
BEGIN
  IF NEW.status IN ('completed','failed','refunded','cancelled')
     AND (OLD.status IS NULL OR OLD.status NOT IN ('completed','failed','refunded','cancelled')) THEN
    NEW.completed_at := CURRENT_TIMESTAMP;
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_set_transaction_completed_at
BEFORE UPDATE ON transaction
FOR EACH ROW EXECUTE FUNCTION set_transaction_completed_at();
""")  # met à jour completed_at dès que le statut passe en état final

# ========================================================
# 4. DDL pour la procédure stockée de paiement
# ========================================================
ddl_process_payment = DDL("""
CREATE OR REPLACE PROCEDURE process_payment(
  p_sender_wallet_id UUID,
  p_recipient_wallet_id UUID,
  p_amount NUMERIC(12,2),
  p_currency VARCHAR(3),
  p_description TEXT,
  p_merchant_id UUID DEFAULT NULL
)
LANGUAGE plpgsql AS $$
DECLARE
  v_transaction_id UUID;
  v_sender_balance NUMERIC(12,2);
BEGIN
  SELECT balance INTO v_sender_balance FROM wallet WHERE id = p_sender_wallet_id;
  IF v_sender_balance IS NULL OR v_sender_balance < p_amount THEN
    RAISE EXCEPTION 'Solde insuffisant ou portefeuille introuvable.';
  END IF;

  BEGIN
    INSERT INTO transaction (
      transaction_type, transaction_method, sender_wallet_id,
      recipient_wallet_id, amount, currency, status,
      description, merchant_id, created_at
    ) VALUES (
      'payment','wallet',p_sender_wallet_id,
      p_recipient_wallet_id,p_amount,p_currency,
      'pending',p_description,p_merchant_id,CURRENT_TIMESTAMP
    ) RETURNING id INTO v_transaction_id;

    UPDATE wallet
      SET balance = balance - p_amount, last_updated = CURRENT_TIMESTAMP
      WHERE id = p_sender_wallet_id;

    UPDATE wallet
      SET balance = balance + p_amount, last_updated = CURRENT_TIMESTAMP
      WHERE id = p_recipient_wallet_id;

    UPDATE transaction
      SET status = 'completed'
      WHERE id = v_transaction_id;
  EXCEPTION
    WHEN OTHERS THEN
      UPDATE transaction
        SET status = 'failed', completed_at = CURRENT_TIMESTAMP,
            failure_reason = SQLERRM
      WHERE id = v_transaction_id;
      RAISE;
  END;
END;
$$;
""")  # procédure pour traiter un paiement atomiquement

# ========================================================
# 5. Attachement des DDL après création de la table
# ========================================================
event.listen(Transaction.__table__, 'after_create', ddl_set_completed_at)
event.listen(Transaction.__table__, 'after_create', ddl_process_payment)
