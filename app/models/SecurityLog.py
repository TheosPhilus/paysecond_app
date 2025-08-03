from sqlalchemy import (
    Column, String, DateTime, CheckConstraint, Index,
    DDL, event, Boolean, Float, Text, ForeignKey, func, text
)
from sqlalchemy.dialects.postgresql import UUID, INET, JSONB
from app.database import Base

# ========================================================
# 1. Modèle SQLAlchemy pour la table "security_log"
#    (partitionnée par année sur created_at)
# ========================================================
class SecurityLog(Base):
    __tablename__ = "security_log"
    __table_args__ = (
        CheckConstraint(
            "severity IN ('low','medium','high','critical')",
            name="chk_security_log_severity"
        ),  
        # Validation de la gravité

        CheckConstraint(
            "((latitude IS NULL AND longitude IS NULL) OR "
            "(latitude BETWEEN -90 AND 90 AND longitude BETWEEN -180 AND 180))",
            name="valid_coordinates"
        ),  
        # Validation conditionnelle des coordonnées

        Index("idx_security_log_user", "user_id"),  
        # Index sur l’utilisateur

        Index("idx_security_log_event_type", "event_type"),  
        # Index sur le type d’événement

        Index("idx_security_log_created", "created_at"),  
        # Index sur la date de création pour partition scan

        Index("idx_security_log_severity", "severity"),  
        # Index sur la gravité

        Index("idx_security_log_coords", "latitude", "longitude"),  
        # Index multidimensionnel sur coordonnées

        {"postgresql_partition_by": "RANGE (created_at)"}
        # Partitionnement par plage sur created_at
    )

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()")
    )  
    # Identifiant unique du log

    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("user.id", ondelete="SET NULL")
    )  
    # Référence à l’utilisateur (nullable si supprimé)

    event_type = Column(
        String(50),
        nullable=False
    )  
    # Type d’événement (login, fraud, ban, etc.)

    ip_address = Column(
        INET
    )  
    # Adresse IP d’origine

    user_agent = Column(
        Text
    )  
    # Informations navigateur / device

    device_id = Column(
        Text
    )  
    # Identifiant de l’appareil

    latitude = Column(
        Float
    )  
    # Latitude géographique (nullable)

    longitude = Column(
        Float
    )  
    # Longitude géographique (nullable)

    severity = Column(
        String(10),
        nullable=False,
        server_default="medium"
    )  
    # Gravité (low, medium, high, critical)

    details = Column(
        JSONB,
        nullable=False
    )  
    # Détails supplémentaires en JSON

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.current_timestamp()
    )  
    # Date/heure de création

    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.current_timestamp()
    )  
    # Date/heure de dernière mise à jour

    resolved = Column(
        Boolean,
        nullable=False,
        server_default=text("FALSE")
    )  
    # Statut de résolution

    resolution_notes = Column(
        Text
    )  
    # Notes de résolution (nullable)

    related_transaction = Column(
        UUID(as_uuid=True)
    )  
    # Transaction liée (facultatif)


# ========================================================
# 2. DDL : création des partitions annuelles 2023–2026
# ========================================================
ddl_initial_partitions = DDL("""
CREATE TABLE IF NOT EXISTS security_log_y2023
  PARTITION OF security_log
  FOR VALUES FROM ('2023-01-01 00:00:00+00') TO ('2024-01-01 00:00:00+00');

CREATE TABLE IF NOT EXISTS security_log_y2024
  PARTITION OF security_log
  FOR VALUES FROM ('2024-01-01 00:00:00+00') TO ('2025-01-01 00:00:00+00');

CREATE TABLE IF NOT EXISTS security_log_y2025
  PARTITION OF security_log
  FOR VALUES FROM ('2025-01-01 00:00:00+00') TO ('2026-01-01 00:00:00+00');

CREATE TABLE IF NOT EXISTS security_log_y2026
  PARTITION OF security_log
  FOR VALUES FROM ('2026-01-01 00:00:00+00') TO ('2027-01-01 00:00:00+00');
""")

# ========================================================
# 3. DDL : fonction et appel pour créer automatiquement
#          la partition de l’année suivante
# ========================================================
ddl_future_partitions = DDL("""
DROP FUNCTION IF EXISTS create_future_security_log_partitions CASCADE;

CREATE OR REPLACE FUNCTION create_future_security_log_partitions()
RETURNS void AS $$
DECLARE
  next_year TEXT := TO_CHAR(CURRENT_DATE + INTERVAL '1 year', 'YYYY');
  year_start TIMESTAMPTZ := DATE_TRUNC('year', CURRENT_DATE + INTERVAL '1 year');
  year_end   TIMESTAMPTZ := DATE_TRUNC('year', CURRENT_DATE + INTERVAL '2 years');
  partition_name TEXT := 'security_log_y' || next_year;
BEGIN
  IF NOT EXISTS (
    SELECT FROM pg_class WHERE relname = partition_name
  ) THEN
    EXECUTE format(
      'CREATE TABLE %I PARTITION OF security_log FOR VALUES FROM (%L) TO (%L);',
      partition_name,
      year_start,
      year_end
    );
  END IF;
END;
$$ LANGUAGE plpgsql;

-- Appel immédiat pour s’assurer de la partition prochaine
SELECT create_future_security_log_partitions();
""")

# ========================================================
# 4. DDL : trigger pour mise à jour automatique de updated_at
# ========================================================
ddl_update_ts = DDL("""
CREATE OR REPLACE FUNCTION update_security_log_timestamp()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at := CURRENT_TIMESTAMP;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_update_security_log
BEFORE UPDATE ON security_log
FOR EACH ROW EXECUTE FUNCTION update_security_log_timestamp();
""")

# ========================================================
# 5. Attacher tous les DDL au moment de la création de la table
# ========================================================
event.listen(
    SecurityLog.__table__,
    "after_create",
    ddl_initial_partitions
)
event.listen(
    SecurityLog.__table__,
    "after_create",
    ddl_future_partitions
)
event.listen(
    SecurityLog.__table__,
    "after_create",
    ddl_update_ts
)
