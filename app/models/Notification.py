import enum
from sqlalchemy import (
    Column, Text, Boolean, DateTime, Integer, JSON, ForeignKey,
    Index, DDL, event, text
)
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import UUID, INET, JSONB, ENUM as PGEnum
from app.database import Base

# ========================================================
# 🔔 1. Python Enums pour Notification
# ========================================================
class NotificationType(enum.Enum):
    transaction = "transaction"  # type transactionnel
    security    = "security"     # type sécurité
    marketing   = "marketing"    # type marketing
    system      = "system"       # type système
    account     = "account"      # type compte
    promotion   = "promotion"    # type promotionnel
    kyc_update  = "kyc_update"   # mise à jour KYB/KYC

class NotificationLanguage(enum.Enum):
    fr = "fr"  # français
    en = "en"  # anglais
    es = "es"  # espagnol
    de = "de"  # allemand

class Channel(enum.Enum):
    in_app = "in-app"  # canal in-app
    email  = "email"   # canal email
    sms    = "sms"     # canal SMS
    push   = "push"    # canal push

# ========================================================
# 🔔 2. Modèle SQLAlchemy pour la table "notification"
# ========================================================
class Notification(Base):
    __tablename__ = "notification"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()")
    )  # [id] : Identifiant unique de la notification

    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("user.id", ondelete="CASCADE"),
        nullable=False
    )  # [user_id] : Utilisateur destinataire (ON DELETE CASCADE)

    title = Column(
        Text,
        nullable=False
    )  # [title] : Titre bref de la notification

    message = Column(
        Text,
        nullable=False
    )  # [message] : Contenu complet de la notification

    is_read = Column(
        Boolean,
        nullable=False,
        server_default=text("FALSE")
    )  # [is_read] : Statut de lecture

    notification_type = Column(
        PGEnum(NotificationType,
               name="notification_type_enum", create_type=True),
        nullable=True
    )  # [notification_type] : Catégorie de la notification

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.current_timestamp()
    )  # [created_at] : Date de création

    read_at = Column(
        DateTime(timezone=True),
        nullable=True
    )  # [read_at] : Date de lecture (définie par trigger)

    expires_at = Column(
        DateTime(timezone=True),
        nullable=True
    )  # [expires_at] : Date d’expiration de la notification

    language = Column(
        PGEnum(NotificationLanguage,
               name="notification_language_enum", create_type=True),
        nullable=False,
        server_default=NotificationLanguage.fr.value
    )  # [language] : Langue de la notification

    action_url = Column(
        Text,
        nullable=True
    )  # [action_url] : URL actionnable liée

    priority = Column(
        Integer,
        nullable=False,
        server_default=text("1")
    )  # [priority] : Niveau de priorité (1–3)

    channel = Column(
        PGEnum(Channel, name="notification_channel_enum", create_type=True),
        nullable=False,
        server_default=Channel.in_app.value
    )  # [channel] : Canal de diffusion

    sender_id = Column(
        UUID(as_uuid=True),
        ForeignKey("user.id", ondelete="SET NULL"),
        nullable=True
    )  # [sender_id] : Expéditeur (ON DELETE SET NULL)

    ip_address = Column(
        INET,
        nullable=True
    )  # [ip_address] : Adresse IP d’origine

    source_system = Column(
        Text,
        nullable=True
    )  # [source_system] : Système émetteur

    payload = Column(
        JSONB,
        nullable=True
    )  # [payload] : Données dynamiques complémentaires

    __table_args__ = (
        Index("idx_notification_user", "user_id"),                                    # index user_id
        Index("idx_notification_read", "is_read", postgresql_where=text("NOT is_read")),  # index notifications non lues
        Index("idx_notification_created", text("created_at DESC")),                   # index tri par date création
        Index("idx_notification_priority", text("priority DESC")),                    # index tri par priorité
        Index("idx_notification_type", "notification_type"),                          # index par type
        Index("idx_notification_channel", "channel"),                                # index par canal
    )

# ========================================================
# 🔔 3. DDL pour trigger de lecture
# ========================================================
ddl_set_read_at = DDL("""
CREATE OR REPLACE FUNCTION set_notification_read_at()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.is_read = TRUE AND OLD.is_read = FALSE THEN
        NEW.read_at := CURRENT_TIMESTAMP;  -- définit read_at lors du passage à lu
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_set_notification_read_at
BEFORE UPDATE ON notification
FOR EACH ROW EXECUTE FUNCTION set_notification_read_at();
""")  # trigger qui remplit read_at

# ========================================================
# 🔔 4. DDL pour procédure create_notification
# ========================================================
ddl_create_notification = DDL("""
CREATE OR REPLACE PROCEDURE create_notification(
    p_user_id UUID,
    p_title TEXT,
    p_message TEXT,
    p_notification_type VARCHAR(30) DEFAULT 'system',
    p_action_url TEXT DEFAULT NULL,
    p_priority INT DEFAULT 1,
    p_language VARCHAR(10) DEFAULT 'fr',
    p_channel VARCHAR(20) DEFAULT 'in-app',
    p_sender_id UUID DEFAULT NULL,
    p_payload JSONB DEFAULT NULL,
    p_expires_at TIMESTAMP WITH TIME ZONE DEFAULT NULL,
    p_source_system VARCHAR(30) DEFAULT NULL,
    p_ip_address INET DEFAULT NULL
)
LANGUAGE plpgsql AS $$
BEGIN
    INSERT INTO notification (
        user_id, title, message, notification_type, action_url,
        priority, language, channel, sender_id,
        payload, expires_at, source_system, ip_address
    ) VALUES (
        p_user_id, p_title, p_message, p_notification_type, p_action_url,
        p_priority, p_language, p_channel, p_sender_id,
        p_payload, p_expires_at, p_source_system, p_ip_address
    );
END;
$$;
""")  # procédure stockée pour créer une notification

# ========================================================
# 🚀 5. Attachement des DDL après création de la table
# ========================================================
event.listen(Notification.__table__, 'after_create', ddl_set_read_at)
event.listen(Notification.__table__, 'after_create', ddl_create_notification)
