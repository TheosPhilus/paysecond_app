import enum
from sqlalchemy import (
    Column, Text, Boolean, DateTime, Integer, Float,
    CheckConstraint, Index, ForeignKey, DDL, event, text
)
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import UUID, INET, JSONB, VARCHAR
from app.database import Base

# ========================================================
# 1. Enum Python pour resolution_status
# ========================================================
class ResolutionStatus(enum.Enum):
    investigating   = "investigating"
    resolved        = "resolved"
    denied          = "denied"
    pending_review  = "pending_review"
    escalated       = "escalated"

# ========================================================
# 2. Modèle SQLAlchemy pour failed_transaction
# ========================================================
class FailedTransaction(Base):
    __tablename__ = "failed_transaction"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()")
    )

    transaction_id = Column(
        UUID(as_uuid=True),
        nullable=True
    )

    error_code = Column(
        VARCHAR(50),
        ForeignKey("transaction_error_code.code", ondelete="SET NULL"),
        nullable=True
    )

    reason = Column(
        Text,
        nullable=True
    )

    fraud_detected = Column(
        Boolean,
        nullable=False,
        server_default=text("FALSE")
    )

    resolution_status = Column(
        Text,
        nullable=False,
        server_default=ResolutionStatus.investigating.value
    )

    resolved_at = Column(
        DateTime(timezone=True),
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

    reviewed_by = Column(
        UUID(as_uuid=True),
        ForeignKey("user.id", ondelete="SET NULL"),
        nullable=True
    )

    created_by = Column(
        UUID(as_uuid=True),
        ForeignKey("user.id", ondelete="SET NULL"),
        nullable=True
    )

    updated_by = Column(
        UUID(as_uuid=True),
        ForeignKey("user.id", ondelete="SET NULL"),
        nullable=True
    )

    automatic_retry_attempt = Column(
        Integer,
        nullable=False,
        server_default=text("0")
    )

    escalation_level = Column(
        Integer,
        nullable=False,
        server_default=text("0")
    )

    ip_address = Column(
        INET,
        nullable=True
    )

    user_agent = Column(
        Text,
        nullable=True
    )

    anomaly_score = Column(
        Float,
        nullable=True
    )

    failed_metadata = Column(
        "metadata",   # nom réel de la colonne en base
        JSONB,
        nullable=True # autorise la valeur NULL
    )  # [metadata] : Métadonnées techniques (IV, tag, etc.)

    __table_args__ = (
        CheckConstraint(
            "resolution_status IN ('investigating','resolved','denied','pending_review','escalated')",
            name="chk_failed_transaction_resolution_status"
        ),
        CheckConstraint(
            "escalation_level BETWEEN 0 AND 5",
            name="chk_failed_transaction_escalation_level"
        ),
        CheckConstraint(
            "anomaly_score >= 0",
            name="chk_failed_transaction_anomaly_score"
        ),
        Index("idx_failed_transaction_status", "resolution_status"),
        Index(
            "idx_failed_transaction_fraud",
            "fraud_detected",
            postgresql_where=text("fraud_detected = TRUE")
        ),
        Index("idx_failed_transaction_error", "error_code"),
        Index("idx_failed_transaction_created", text("created_at DESC")),
        Index("idx_failed_transaction_transaction_id", "transaction_id"),
        Index("idx_failed_transaction_escalation", text("escalation_level DESC")),
        Index("idx_failed_transaction_anomaly", "anomaly_score"),
    )

# ========================================================
# 3. DDL pour triggers set_resolved_at & update updated_at
# ========================================================
ddl_resolve_update = DDL("""
CREATE OR REPLACE FUNCTION set_resolved_at_failed_transaction()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.resolution_status = 'resolved'
       AND OLD.resolution_status != 'resolved'
    THEN
        NEW.resolved_at := CURRENT_TIMESTAMP;
    END IF;
    NEW.updated_at := CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_set_resolved_at_failed_transaction
BEFORE UPDATE ON failed_transaction
FOR EACH ROW EXECUTE FUNCTION set_resolved_at_failed_transaction();
""")

# ========================================================
# 4. DDL pour trigger de validation transaction_id
# ========================================================
ddl_check_tx = DDL("""
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
AFTER INSERT OR UPDATE ON failed_transaction
DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW EXECUTE FUNCTION check_transaction_exists();
""")

# ========================================================
# 5. DDL pour procédure log_failed_transaction
# ========================================================
ddl_log_proc = DDL("""
CREATE OR REPLACE PROCEDURE log_failed_transaction(
    p_transaction_id UUID,
    p_error_code VARCHAR(50),
    p_reason TEXT,
    p_fraud_detected BOOLEAN DEFAULT FALSE,
    p_ip_address INET DEFAULT NULL,
    p_user_agent TEXT DEFAULT NULL,
    p_metadata JSONB DEFAULT NULL,
    p_created_by UUID DEFAULT NULL
)
LANGUAGE plpgsql AS $$
BEGIN
    PERFORM 1 FROM transaction WHERE id = p_transaction_id;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Transaction invalide: %', p_transaction_id;
    END IF;

    INSERT INTO failed_transaction (
        transaction_id, error_code, reason,
        fraud_detected, ip_address, user_agent,
        metadata, created_by
    ) VALUES (
        p_transaction_id, p_error_code, p_reason,
        p_fraud_detected, p_ip_address, p_user_agent,
        p_metadata, p_created_by
    );

    UPDATE transaction
    SET status          = 'failed',
        completed_at    = CURRENT_TIMESTAMP,
        fraud_flag      = p_fraud_detected,
        failure_reason  = p_reason
    WHERE id = p_transaction_id;
END;
$$;
""")

# ========================================================
# 6. Attachement des DDL après création de la table
# ========================================================
event.listen(
    FailedTransaction.__table__,
    'after_create',
    ddl_resolve_update
)
event.listen(
    FailedTransaction.__table__,
    'after_create',
    ddl_check_tx
)
event.listen(
    FailedTransaction.__table__,
    'after_create',
    ddl_log_proc
)
