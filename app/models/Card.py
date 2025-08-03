import enum
from sqlalchemy import (
    Column, String, DateTime, Boolean, Integer, Text, Date, Numeric,
    ForeignKey, CheckConstraint, Index, DDL, event, text
)
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import UUID, ENUM as PGEnum
from app.database import Base

# ========================================================
# 1. Python Enums pour Card
# ========================================================
class CardType(enum.Enum):
    virtual  = "virtual"   # carte virtuelle
    physical = "physical"  # carte physique
    credit   = "credit"    # carte de crédit
    debit    = "debit"     # carte de débit

class CardStatus(enum.Enum):
    active             = "active"             # carte active
    blocked            = "blocked"            # carte bloquée
    expired            = "expired"            # carte expirée
    lost               = "lost"               # carte déclarée perdue
    stolen             = "stolen"             # carte déclarée volée
    pending_activation = "pending_activation" # en attente d’activation

# ========================================================
# 2. Modèle SQLAlchemy pour la table "card"
# ========================================================
class Card(Base):
    __tablename__ = "card"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()")
    )  # [id] : Identifiant unique de la carte, généré automatiquement.

    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("user.id", ondelete="CASCADE"),
        nullable=False
    )  # [user_id] : Référence à l’utilisateur propriétaire (ON DELETE CASCADE).

    wallet_id = Column(
        UUID(as_uuid=True),
        ForeignKey("wallet.id", ondelete="CASCADE"),
        nullable=False
    )  # [wallet_id] : Référence au portefeuille associé (ON DELETE CASCADE).

    card_number_encrypted = Column(
        Text,
        nullable=False
    )  # [card_number_encrypted] : Numéro de carte chiffré (PCI DSS).

    card_number_last_four = Column(
        String(4),
        nullable=False
    )  # [card_number_last_four] : 4 derniers chiffres de la carte.

    card_fingerprint = Column(
        Text,
        nullable=False,
        unique=True
    )  # [card_fingerprint] : Empreinte unique de la carte.

    expiry_date = Column(
        Date,
        nullable=False
    )  # [expiry_date] : Date d’expiration (entre maintenant et +10 ans).

    type = Column(
        PGEnum(CardType, name="card_type", create_type=True),
        nullable=False
    )  # [type] : Type de carte (virtual, physical, credit, debit).

    status = Column(
        PGEnum(CardStatus, name="card_status", create_type=True),
        nullable=False,
        server_default=CardStatus.active.value
    )  # [status] : Statut de la carte (active, blocked, etc.).

    reported_lost = Column(
        Boolean,
        nullable=False,
        server_default=text("FALSE")
    )  # [reported_lost] : Carte signalée perdue.

    failed_attempts = Column(
        Integer,
        nullable=False,
        server_default=text("0")
    )  # [failed_attempts] : Tentatives PIN échouées (0–3).

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.current_timestamp()
    )  # [created_at] : Date de création de l’enregistrement.

    data_retention_days = Column(
        Integer,
        nullable=False,
        server_default=text("730")
    )  # [data_retention_days] : Durée de rétention (30–1095 jours).

    purge_after = Column(
        DateTime(timezone=True),
        nullable=False
    )  # [purge_after] : Date à partir de laquelle purger la carte.

    cardholder_name = Column(
        Text,
        nullable=True
    )  # [cardholder_name] : Nom du titulaire de la carte.

    issuer = Column(
        String(50),
        nullable=True
    )  # [issuer] : Émetteur de la carte (banque).

    encryption_key_id = Column(
        UUID(as_uuid=True),
        ForeignKey("encryption_key.id", ondelete="RESTRICT"),
        nullable=False
    )  # [encryption_key_id] : Clé utilisée pour chiffrer le numéro (ON DELETE RESTRICT).

    __table_args__ = (
        CheckConstraint(
            "char_length(card_number_last_four) = 4",
            name="chk_card_last_four_length"
        ),  # [check_card_number_last_four] : exactement 4 caractères.

        CheckConstraint(
            "expiry_date > CURRENT_DATE AND expiry_date < CURRENT_DATE + INTERVAL '10 years'",
            name="chk_card_expiry_range"
        ),  # [expiry_date CHECK] : date valide.

        CheckConstraint(
            "failed_attempts BETWEEN 0 AND 3",
            name="chk_card_failed_attempts"
        ),  # [failed_attempts CHECK] : 0–3 tentatives.

        CheckConstraint(
            "data_retention_days BETWEEN 30 AND 1095",
            name="chk_card_data_retention"
        ),  # [data_retention_days CHECK] : 30–1095 jours.

        Index("idx_card_user_id", "user_id"),  # [idx_card_user_id] : accélère recherches par utilisateur.
        Index("idx_card_wallet_id", "wallet_id"),  # [idx_card_wallet_id] : index wallet_id.
        Index(
            "idx_card_status", "status",
            postgresql_where=text("status != 'active'")
        ),  # [idx_card_status] : index partiel pour cartes non actives.
        Index("idx_card_expiry", "expiry_date"),  # [idx_card_expiry] : index date d’expiration.
        Index("idx_card_purge", "purge_after"),  # [idx_card_purge] : index date de purge.
        Index("idx_card_encryption_key_id", "encryption_key_id"),  # [idx_card_encryption_key_id] : index clé de chiffrement.
    )

# ========================================================
# 3. DDL pour triggers et procédure stockée
# ========================================================
ddl_reset_failed_attempts = DDL("""
CREATE OR REPLACE FUNCTION reset_card_failed_attempts()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.status = 'active' AND OLD.status <> 'active' THEN
        NEW.failed_attempts := 0;  -- réinitialise quand carte repasse active
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_reset_card_failed_attempts
BEFORE UPDATE ON card
FOR EACH ROW EXECUTE FUNCTION reset_card_failed_attempts();
""")  # Trigger 1 : reset du compteur failed_attempts

ddl_set_purge_after = DDL("""
CREATE OR REPLACE FUNCTION set_purge_after()
RETURNS TRIGGER AS $$
BEGIN
    NEW.purge_after := NEW.created_at + (NEW.data_retention_days * INTERVAL '1 day');
    RETURN NEW;  -- calcule automatiquement purge_after
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_set_purge_after
BEFORE INSERT OR UPDATE ON card
FOR EACH ROW EXECUTE FUNCTION set_purge_after();
""")  # Trigger 2 : calcul de la date de purge

ddl_check_wallet_belongs = DDL("""
CREATE OR REPLACE FUNCTION check_wallet_belongs_to_user()
RETURNS TRIGGER AS $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM wallet
        WHERE id = NEW.wallet_id AND user_id = NEW.user_id
    ) THEN
        RAISE EXCEPTION 'Wallet % does not belong to user %', NEW.wallet_id, NEW.user_id;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE CONSTRAINT TRIGGER trg_check_wallet_belongs_to_user
AFTER INSERT OR UPDATE ON card
DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW EXECUTE FUNCTION check_wallet_belongs_to_user();
""")  # Trigger 3 : cohérence wallet↔user

ddl_block_proc = DDL("""
CREATE OR REPLACE PROCEDURE block_card_on_failed_attempts(p_card_id UUID)
LANGUAGE plpgsql AS $$
BEGIN
    UPDATE card
    SET status = 'blocked'
    WHERE id = p_card_id AND failed_attempts >= 3;
END;
$$;
""")  # Procédure : bloquer la carte après 3 échecs

# ========================================================
# 4. Attachement des DDL après création de la table
# ========================================================
event.listen(Card.__table__, 'after_create', ddl_reset_failed_attempts)
event.listen(Card.__table__, 'after_create', ddl_set_purge_after)
event.listen(Card.__table__, 'after_create', ddl_check_wallet_belongs)
event.listen(Card.__table__, 'after_create', ddl_block_proc)
