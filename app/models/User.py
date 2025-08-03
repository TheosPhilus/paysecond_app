import enum                                            # import Python enum base
from sqlalchemy import (                               # import core SQLAlchemy constructs
    Column, String, DateTime, Boolean, Integer, Text,
    Index, DDL, event, text, ForeignKey
)
from sqlalchemy.sql import func                         # import SQL functions (e.g. now())
from sqlalchemy.dialects.postgresql import UUID, INET, ENUM as PGEnum  # import Postgres types
from app.database import Base                          # Base declarative from your project

# ========================================================
# 🔐 1. Python Enums pour User (synchronisés en Postgres)
# ========================================================
class UserType(enum.Enum):
    client   = "client"     # client user
    merchant = "merchant"   # merchant user
    admin    = "admin"      # admin user

class UserStatus(enum.Enum):
    active               = "active"               # account is active
    inactive             = "inactive"             # account is inactive
    pending_verification = "pending_verification" # awaiting verification
    suspended            = "suspended"            # account suspended
    closed               = "closed"               # account closed

class AccountStatus(enum.Enum):
    active    = "active"    # security active
    suspended = "suspended" # security suspended
    blocked   = "blocked"   # account blocked
    on_hold   = "on_hold"   # account on hold

class Language(enum.Enum):
    fr = "fr"  # French
    en = "en"  # English
    es = "es"  # Spanish
    de = "de"  # German

# ========================================================
# 🔐 2. Modèle SQLAlchemy pour la table "user"
# ========================================================
class User(Base):
    __tablename__ = "user" 

    id = Column(                                       # [id] : UUID primary key
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()")
    )

    username = Column(                                 # [username] : unique public identifier
        String(50),
        unique=True
    )

    deleted_at = Column(                               # [deleted_at] : soft delete timestamp
        DateTime(timezone=True),
        nullable=True
    )

    last_login_ip = Column(                            # [last_login_ip] : last login IP address
        INET,
        nullable=True
    )

    email = Column(                                    # [email] : unique, required email
        String(255),
        nullable=False,
        unique=True
    )

    phone = Column(                                    # [phone] : unique, required phone number
        String(20),
        nullable=False,
        unique=True
    )

    password_hash = Column(                            # [password_hash] : hashed password
        Text,
        nullable=False
    )

    full_name = Column(                                # [full_name] : optional full name
        String(100),
        nullable=False
    )

    date_of_birth = Column(                            # [date_of_birth] : required birth date
        DateTime,                                      # use DateTime or Date per project
        nullable=False
    )

    birth_place = Column(                              # [birth_place] : required birth place
        String(255),
        nullable=False
    )

    type = Column(                                     # [type] : user role enum
        PGEnum(UserType, name="user_type", create_type=True),
        nullable=False
    )

    status = Column(                                   # [status] : general account status enum
        PGEnum(UserStatus, name="user_status", create_type=True),
        nullable=False,
        server_default=UserStatus.active.value
    )

    account_status = Column(                           # [account_status] : security status enum
        PGEnum(AccountStatus, name="user_account_status", create_type=True),
        nullable=False,
        server_default=AccountStatus.active.value
    )

    failed_login_attempts = Column(                    # [failed_login_attempts] : count of failed logins
        Integer,
        nullable=False,
        server_default=text("0")
    )

    last_login_at = Column(                            # [last_login_at] : last successful login timestamp
        DateTime(timezone=True),
        nullable=True
    )

    created_at = Column(                               # [created_at] : record creation timestamp
        DateTime(timezone=True),
        nullable=False,
        server_default=func.current_timestamp()
    )

    updated_at = Column(                               # [updated_at] : record update timestamp
        DateTime(timezone=True),
        nullable=False,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp()
    )

    language = Column(                                 # [language] : preferred language enum
        PGEnum(Language, name="user_language", create_type=True),
        nullable=False,
        server_default=Language.fr.value
    )

    gdpr_consent = Column(                             # [gdpr_consent] : GDPR consent flag
        Boolean,
        nullable=False,
        server_default=text("FALSE")
    )

    mfa_enabled = Column(                              # [mfa_enabled] : multi-factor auth enabled flag
        Boolean,
        nullable=False,
        server_default=text("FALSE")
    )

    last_password_change_at = Column(                  # [last_password_change_at] : timestamp of last password change
        DateTime(timezone=True),
        nullable=True
    )

    email_verified = Column(                           # [email_verified] : email verification flag
        Boolean,
        nullable=False,
        server_default=text("FALSE")
    )

    phone_verified = Column(                           # [phone_verified] : phone verification flag
        Boolean,
        nullable=False,
        server_default=text("FALSE")
    )

    __table_args__ = (
        Index("idx_user_email_lower", func.lower(email), unique=True),  # unique index on lower(email)
        Index("idx_user_phone", phone, unique=True),                    # unique index on phone
        Index("idx_user_status", status),                               # index on status
        Index("idx_user_type", type),                                   # index on type
        Index("idx_user_created_at", created_at),                       # index on creation timestamp
        Index("idx_user_account_status", account_status),               # index on account_status
        Index("idx_user_email_verified", email_verified),               # index on email_verified flag
    )

# ========================================================
# 🔔 3. DDL pour triggers et procédure stockée
# ========================================================
ddl_update_ts = DDL("""
CREATE OR REPLACE FUNCTION update_user_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;  -- update 'updated_at' on modify
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_update_user
BEFORE UPDATE ON "user"
FOR EACH ROW EXECUTE FUNCTION update_user_timestamp();
""")

ddl_lock_proc = DDL("""
CREATE OR REPLACE PROCEDURE lock_user_account(p_user_id UUID)
LANGUAGE plpgsql AS $$
BEGIN
    UPDATE "user"
      SET account_status = 'blocked',
          failed_login_attempts = 0
    WHERE id = p_user_id;
END;
$$;
""")

# ========================================================
# 🚀 4. Attachement des DDL après création de la table
# ========================================================
event.listen(User.__table__, 'after_create', ddl_update_ts)
event.listen(User.__table__, 'after_create', ddl_lock_proc)
