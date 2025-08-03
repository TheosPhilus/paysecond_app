from sqlalchemy import (
    Column, Integer, Text, Boolean, CheckConstraint, 
    PrimaryKeyConstraint, Index, ForeignKey, DDL, event, 
    TIMESTAMP, func, text
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from app.database import Base

# ========================================================
# 1. Modèle SQLAlchemy pour la table "webhook_log"
#    partitionnée par RANGE(created_at)
# ========================================================
class WebhookLog(Base):
    __tablename__ = "webhook_log"
    __table_args__ = (
        # Clé primaire composite pour le partitionnement
        PrimaryKeyConstraint("id", "created_at", name="pk_webhook_log"),
        # Plage raisonnable de tentatives max
        CheckConstraint("retry_max BETWEEN 0 AND 10", name="chk_webhook_log_retry_max"),
        # Indexes pour les requêtes fréquentes
        Index("idx_webhook_log_webhook_id", "webhook_id"),
        Index("idx_webhook_log_created_at", "created_at"),
        Index("idx_webhook_log_success", "success"),
        Index("idx_webhook_log_event_type", "event_type"),
        Index("idx_webhook_log_next_retry", "next_retry_at"),
        Index("idx_webhook_log_retry_attempt", "retry_attempt"),
    )

    id = Column(
        UUID(as_uuid=True),
        nullable=False,
        server_default=text("gen_random_uuid()")
    )
    webhook_id = Column(
        UUID(as_uuid=True),
        ForeignKey("webhook.id", ondelete="CASCADE"),
        nullable=False
    )
    event_id = Column(
        UUID(as_uuid=True),
        nullable=False
    )
    payload = Column(
        JSONB,
        nullable=False
    )
    response_code = Column(
        Integer,
        nullable=True
    )
    response_body = Column(
        Text,
        nullable=True
    )
    delivery_time_ms = Column(
        Integer,
        nullable=True
    )
    success = Column(
        Boolean,
        nullable=False
    )
    created_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.current_timestamp()
    )
    retry_attempt = Column(
        Integer,
        nullable=False,
        server_default=text("0")
    )
    error_message = Column(
        Text,
        nullable=True
    )
    event_type = Column(
        Text,
        nullable=False
    )
    retry_max = Column(
        Integer,
        nullable=False,
        server_default=text("5")
    )
    next_retry_at = Column(
        TIMESTAMP(timezone=True),
        nullable=True
    )
    manual_triggered = Column(
        Boolean,
        nullable=False,
        server_default=text("FALSE")
    )

# ========================================================
# 2. DDL pour partitionnement et création de partitions
# ========================================================
# Définit la table comme partitionnée par RANGE(created_at)
ddl_partition_by = DDL("""
ALTER TABLE webhook_log
PARTITION BY RANGE (created_at);
""")

# Partitions statiques pour 2023, 2024, 2025
ddl_partitions = DDL("""
CREATE TABLE IF NOT EXISTS webhook_log_y2023 PARTITION OF webhook_log
    FOR VALUES FROM ('2023-01-01 00:00:00+00') TO ('2024-01-01 00:00:00+00');
CREATE TABLE IF NOT EXISTS webhook_log_y2024 PARTITION OF webhook_log
    FOR VALUES FROM ('2024-01-01 00:00:00+00') TO ('2025-01-01 00:00:00+00');
CREATE TABLE IF NOT EXISTS webhook_log_y2025 PARTITION OF webhook_log
    FOR VALUES FROM ('2025-01-01 00:00:00+00') TO ('2026-01-01 00:00:00+00');
""")

# Fonction dynamique de création de partition pour une date donnée
ddl_ensure_partition_fn = DDL("""
CREATE OR REPLACE FUNCTION public.ensure_webhook_partition_for_date(p_date TIMESTAMPTZ)
RETURNS void AS $$
DECLARE
    y TEXT := TO_CHAR(p_date, 'YYYY');
    next_y TEXT := TO_CHAR(p_date + INTERVAL '1 year', 'YYYY');
    partition_name TEXT := 'webhook_log_y' || y;
BEGIN
    IF NOT EXISTS (
        SELECT 1
          FROM pg_class c
          JOIN pg_namespace n ON n.oid = c.relnamespace
         WHERE c.relkind = 'r'
           AND c.relname = partition_name
    ) THEN
        EXECUTE format(
            'CREATE TABLE %I PARTITION OF webhook_log FOR VALUES FROM (%L) TO (%L)',
            partition_name,
            y || '-01-01 00:00:00+00',
            next_y || '-01-01 00:00:00+00'
        );
    END IF;
END;
$$ LANGUAGE plpgsql;
""")

# ========================================================
# 3. Attachement des DDLs après création de la table
# ========================================================
event.listen(WebhookLog.__table__, 'after_create', ddl_partition_by)
event.listen(WebhookLog.__table__, 'after_create', ddl_partitions)
event.listen(WebhookLog.__table__, 'after_create', ddl_ensure_partition_fn)
