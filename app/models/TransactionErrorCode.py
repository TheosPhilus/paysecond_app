import enum
from sqlalchemy import (
    UUID, Column, Text, Boolean, DateTime, Enum as SAEnum, ARRAY,
    Index, DDL, event, ForeignKey, text
)
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import VARCHAR, JSONB
from app.database import Base

# ========================================================
# 1. Python Enums pour severity et category
# ========================================================
class ErrorSeverity(enum.Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"

class ErrorCategory(enum.Enum):
    authentication = "authentication"
    funds          = "funds"
    system         = "system"
    fraud          = "fraud"
    network        = "network"
    technical      = "technical"
    compliance     = "compliance"
    user_input     = "user_input"

# ========================================================
# 2. Modèle SQLAlchemy pour transaction_error_code
# ========================================================
class TransactionErrorCode(Base):
    __tablename__ = "transaction_error_code"

    code = Column(
        VARCHAR(50),
        primary_key=True
    )  # code : Identifiant unique de l'erreur

    description = Column(
        Text,
        nullable=False
    )  # description : Texte explicatif de l'erreur

    severity = Column(
        SAEnum(ErrorSeverity, name="error_severity_enum", create_type=True),
        nullable=False
    )  # severity : Gravité (low, medium, high, critical)

    resolution_guide = Column(
        Text,
        nullable=True
    )  # resolution_guide : Guide de résolution

    retry_possible = Column(
        Boolean,
        nullable=False,
        server_default=text("TRUE")
    )  # retry_possible : Réessayer possible

    category = Column(
        SAEnum(ErrorCategory, name="error_category_enum", create_type=True),
        nullable=False
    )  # category : Catégorie de l'erreur

    tags = Column(
        ARRAY(Text),
        nullable=False,
        server_default="{}"
    )  # tags : Tableau de labels

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.current_timestamp()
    )  # created_at : Date de création

    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.current_timestamp()
    )  # updated_at : Date de dernière mise à jour

    archived_at = Column(
        DateTime(timezone=True),
        nullable=True
    )  # archived_at : Date d'archivage

    created_by = Column(
        UUID(as_uuid=True),
        ForeignKey("user.id", ondelete="SET NULL"),
        nullable=True
    )  # created_by : Créateur de l'enregistrement

    updated_by = Column(
        UUID(as_uuid=True),
        ForeignKey("user.id", ondelete="SET NULL"),
        nullable=True
    )  # updated_by : Dernier modificateur

    __table_args__ = (
        Index("idx_error_codes_severity", "severity"),
        Index("idx_error_codes_category", "category"),
        Index("idx_error_codes_retry", "retry_possible"),
        Index("idx_error_codes_tags", "tags", postgresql_using="gin"),
    )

# ========================================================
# 3. DDL pour trigger updated_at
# ========================================================
ddl_update_timestamp = DDL("""
CREATE OR REPLACE FUNCTION update_error_code_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at := CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_update_error_codes
BEFORE UPDATE ON transaction_error_code
FOR EACH ROW EXECUTE FUNCTION update_error_code_timestamp();
""")

# ========================================================
# 4. Attachement du DDL après création de la table
# ========================================================
event.listen(
    TransactionErrorCode.__table__,
    'after_create',
    ddl_update_timestamp
)
