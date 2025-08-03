import enum
from sqlalchemy import (
    Column, String, Numeric, Date, DateTime, Boolean, Text, Integer,
    ForeignKey, CheckConstraint, Index, DDL, event, text, func
)
from sqlalchemy.dialects.postgresql import UUID, JSONB, ENUM as PGEnum
from app.database import Base

# ========================================================
# 1. Python Enums pour Subscription
# ========================================================
class Currency(enum.Enum):
    EUR = "EUR"
    USD = "USD"
    GBP = "GBP"
    XOF = "XOF"
    CAD = "CAD"
    JPY = "JPY"

class Frequency(enum.Enum):
    daily     = "daily"
    weekly    = "weekly"
    monthly   = "monthly"
    quarterly = "quarterly"
    yearly    = "yearly"
    custom    = "custom"

class SubscriptionStatus(enum.Enum):
    active    = "active"
    paused    = "paused"
    cancelled = "cancelled"
    expired   = "expired"
    failed    = "failed"
    pending   = "pending"

# ========================================================
# 2. Modèle SQLAlchemy pour la table "subscription"
# ========================================================
class Subscription(Base):
    __tablename__ = "subscription"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()")
    )  # 🆔 Identifiant unique de l'abonnement

    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("user.id", ondelete="CASCADE"),
        nullable=False
    )  # 🔗 Référence à l'utilisateur

    merchant_id = Column(
        UUID(as_uuid=True),
        ForeignKey("merchant.id", ondelete="CASCADE"),
        nullable=False
    )  # 🔗 Référence au commerçant

    amount = Column(
        Numeric(10, 2),
        nullable=False
    )  # 💶 Montant (positif)
    __table_args__ = (
        CheckConstraint("amount > 0", name="chk_subscription_amount_positive"),
    )

    currency = Column(
        PGEnum(Currency, name="subscription_currency", create_type=True),
        nullable=False,
        server_default=Currency.EUR.value
    )  # 💱 Devise de l'abonnement

    frequency = Column(
        PGEnum(Frequency, name="subscription_frequency", create_type=True),
        nullable=False
    )  # ⏱️ Fréquence des paiements

    start_date = Column(
        Date,
        nullable=False
    )  # 📅 Date de début

    end_date = Column(
        Date,
        nullable=True
    )  # 📅 Date de fin (NULL = illimité)

    status = Column(
        PGEnum(SubscriptionStatus, name="subscription_status", create_type=True),
        nullable=False,
        server_default=SubscriptionStatus.active.value
    )  # 🚦 Statut actuel

    next_payment_date = Column(
        DateTime(timezone=True),
        nullable=True
    )  # ⏭️ Prochain prélèvement prévu

    last_payment_date = Column(
        DateTime(timezone=True),
        nullable=True
    )  # ⏮️ Dernier paiement effectué

    payment_method_id = Column(
        UUID(as_uuid=True),
        ForeignKey("card.id", ondelete="SET NULL"),
        nullable=True
    )  # 💳 Méthode de paiement utilisée

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.current_timestamp()
    )  # 🕓 Création

    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.current_timestamp()
    )  # 🔄 Dernière mise à jour

    description = Column(
        Text,
        nullable=True
    )  # 📝 Description de l'abonnement

    trial_period_days = Column(
        Integer,
        nullable=False,
        server_default=text("0")
    )  # 🆓 Durée de la période d'essai
    __table_args__ += (
        CheckConstraint("trial_period_days >= 0", name="chk_subscription_trial_days_nonneg"),
    )

    subcription_metadata = Column(
        "metadata",   # nom réel de la colonne en base
        JSONB,
        nullable=True # autorise la valeur NULL
    )  # [metadata] : Métadonnées techniques (IV, tag, etc.)

    cancellation_reason = Column(
        Text,
        nullable=True
    )  # 🚫 Raison de l'annulation

    is_auto_renew = Column(
        Boolean,
        nullable=False,
        server_default=text("TRUE")
    )  # 🔄 Renouvellement automatique

    created_by = Column(
        UUID(as_uuid=True),
        ForeignKey("user.id", ondelete="SET NULL"),
        nullable=True
    )  # 👤 Créé par

    updated_by = Column(
        UUID(as_uuid=True),
        ForeignKey("user.id", ondelete="SET NULL"),
        nullable=True
    )  # ✏️ Modifié par

    retry_count = Column(
        Integer,
        nullable=False,
        server_default=text("0")
    )  # 🔁 Tentatives de paiement échouées
    max_retry = Column(
        Integer,
        nullable=False,
        server_default=text("3")
    )  # 🚫 Nombre max de relances
    __table_args__ += (
        CheckConstraint("retry_count >= 0", name="chk_subscription_retry_nonneg"),
        CheckConstraint("max_retry >= 0", name="chk_subscription_max_retry_nonneg"),
    )

    failure_reason = Column(
        Text,
        nullable=True
    )  # ❌ Dernière raison d'échec

    # Indexes pour optimiser les requêtes
    __table_args__ += (
        Index("idx_subscription_next_payment", "next_payment_date"),
        Index("idx_subscription_status", "status"),
        Index("idx_subscription_user", "user_id"),
        Index("idx_subscription_merchant", "merchant_id"),
        Index("idx_subscription_start_date", "start_date"),
        Index("idx_subscription_retry", "status", "retry_count"),
        Index("idx_subscription_end_date", "end_date"),
    )

# ========================================================
# 3. DDL pour Trigger et Procédure stockée
# ========================================================
ddl_update_subscription_ts = DDL("""
CREATE OR REPLACE FUNCTION update_subscription_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_update_subscription
BEFORE UPDATE ON subscription
FOR EACH ROW EXECUTE FUNCTION update_subscription_timestamp();
""")

ddl_cancel_subscription_proc = DDL("""
CREATE OR REPLACE PROCEDURE cancel_subscription(
    p_subscription_id UUID,
    p_reason TEXT DEFAULT NULL,
    p_canceller_id UUID DEFAULT NULL
)
LANGUAGE plpgsql
AS $$
BEGIN
    UPDATE subscription
    SET
        status = 'cancelled',
        end_date = CURRENT_DATE,
        cancellation_reason = p_reason,
        updated_at = CURRENT_TIMESTAMP,
        updated_by = p_canceller_id
    WHERE id = p_subscription_id
      AND status != 'cancelled';
END;
$$;
""")

# ========================================================
# 4. Attachement des DDL après création de la table
# ========================================================
event.listen(Subscription.__table__, 'after_create', ddl_update_subscription_ts)
event.listen(Subscription.__table__, 'after_create', ddl_cancel_subscription_proc)
