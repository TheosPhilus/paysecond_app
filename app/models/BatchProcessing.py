import enum
from sqlalchemy import (
    Column, Integer, String, DateTime, Boolean, CheckConstraint, ForeignKey,
    Index, DDL, event, text, func, Text
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from app.database import Base

# ========================================================
# 1. Python Enum pour batch_processing.job_type et status
# ========================================================
class JobType(enum.Enum):
    interest_calculation = "interest_calculation"
    fraud_scan           = "fraud_scan"
    kyc_renewal          = "kyc_renewal"
    report_generation    = "report_generation"

class JobStatus(enum.Enum):
    pending    = "pending"
    running    = "running"
    completed  = "completed"
    failed     = "failed"
    retrying   = "retrying"
    cancelled  = "cancelled"

# ========================================================
# 2. Modèle SQLAlchemy pour la table "batch_processing"
# ========================================================
class BatchProcessing(Base):
    __tablename__ = "batch_processing"
    __table_args__ = (
        CheckConstraint(
            "job_type IN ('interest_calculation','fraud_scan','kyc_renewal','report_generation')",
            name="chk_batch_job_type"
        ),
        CheckConstraint(
            "status IN ('pending','running','completed','failed','retrying','cancelled')",
            name="chk_batch_status"
        ),
        CheckConstraint(
            "progress_percentage BETWEEN 0 AND 100",
            name="chk_batch_progress_percentage"
        ),
        CheckConstraint(
            "priority BETWEEN 1 AND 5",
            name="chk_batch_priority"
        ),
        CheckConstraint(
            "max_retry >= 0",
            name="chk_batch_max_retry_nonneg"
        ),
        Index("idx_batch_job_type", "job_type"),
        Index("idx_batch_status", "status"),
        Index("idx_batch_scheduled", "scheduled_at"),
        Index("idx_batch_retry", "next_retry_at", postgresql_where=text("status = 'retrying'")),
        Index("idx_batch_priority", "priority"),
        Index("idx_batch_next_retry", "next_retry_at"),
        Index("idx_batch_parent_job", "parent_job_id"),
    )

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()")
    )

    job_type = Column(String(50), nullable=False)

    status = Column(
        String(20),
        nullable=False,
        server_default=text(f"'{JobStatus.pending.value}'")
    )

    scheduled_at = Column(DateTime(timezone=True), nullable=False)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    retry_count = Column(
        Integer,
        nullable=False,
        server_default=text("0")
    )

    last_error = Column(Text, nullable=True)

    progress_percentage = Column(
        Integer,
        nullable=False,
        server_default=text("0")
    )

    parameters = Column(JSONB, nullable=True)

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.current_timestamp()
    )

    next_retry_at = Column(DateTime(timezone=True), nullable=True)

    total_items = Column(Integer, nullable=True)

    processed_items = Column(
        Integer,
        nullable=False,
        server_default=text("0")
    )

    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.current_timestamp()
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

    priority = Column(
        Integer,
        nullable=False,
        server_default=text("1")
    )

    max_retry = Column(
        Integer,
        nullable=False,
        server_default=text("3")
    )

    parent_job_id = Column(
        UUID(as_uuid=True),
        ForeignKey("batch_processing.id", ondelete="CASCADE"),
        nullable=True
    )

# ========================================================
# 3. DDL pour triggers
# ========================================================
ddl_update_progress = DDL("""
CREATE OR REPLACE FUNCTION update_batch_progress()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.total_items > 0 AND NEW.processed_items IS NOT NULL THEN
        NEW.progress_percentage := (NEW.processed_items * 100) / NEW.total_items;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql STABLE;

CREATE TRIGGER trg_update_batch_progress
BEFORE INSERT OR UPDATE ON batch_processing
FOR EACH ROW EXECUTE FUNCTION update_batch_progress();
""")

ddl_update_timestamp = DDL("""
CREATE OR REPLACE FUNCTION trg_set_batch_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at := CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql STABLE;

CREATE TRIGGER trg_update_batch_timestamp
BEFORE UPDATE ON batch_processing
FOR EACH ROW EXECUTE FUNCTION trg_set_batch_updated_at();
""")

# ========================================================
# 4. Attachement des DDL après création de la table
# ========================================================
event.listen(BatchProcessing.__table__, 'after_create', ddl_update_progress)
event.listen(BatchProcessing.__table__, 'after_create', ddl_update_timestamp)
