import enum                                    # import du module enum pour créer des énumérations

from sqlalchemy import (                        # import des classes et fonctions SQLAlchemy
    Column, String, Text, DateTime, ForeignKey, 
    Index, DDL, event, text, func
)

from sqlalchemy.dialects.postgresql import (    # import des types PostgreSQL spécifiques
    UUID, JSONB, ENUM as PGEnum
)

from app.database import Base                   # import du Base SQLAlchemy pour déclarer les modèles

# ========================================================
# 1. Définition des énumérations Python
# ========================================================
class DocumentType(enum.Enum):                  # énumération des types de document
    id_card = "id_card"                         #   carte d’identité
    passport = "passport"                       #   passeport
    proof_of_address = "proof_of_address"       #   justificatif de domicile
    kbis = "kbis"                               #   extrait Kbis
    proof_of_income = "proof_of_income"         #   justificatif de revenus
    selfie = "selfie"                           #   photo selfie

class VerificationStatus(enum.Enum):            # énumération des statuts de vérification
    pending = "pending"                         #   en attente
    approved = "approved"                       #   approuvé
    rejected = "rejected"                       #   rejeté
    expired = "expired"                         #   expiré
    under_review = "under_review"               #   en cours de vérification
    retry = "retry"                             #   à revalider

# ========================================================
# 2. Modèle SQLAlchemy : table "document"
# ========================================================
class Document(Base):                           # déclaration de la classe Document
    __tablename__ = "document"                  # nom de la table en base

    id = Column(                                # colonne id
        UUID(as_uuid=True),                     #   type UUID PostgreSQL
        primary_key=True,                       #   clé primaire
        server_default=text("gen_random_uuid()")#   génération automatique côté serveur
    )

    user_id = Column(                           # colonne user_id
        UUID(as_uuid=True),                     #   type UUID PostgreSQL
        ForeignKey("user.id", ondelete="CASCADE"), # suppression en cascade si user supprimé
        nullable=False                          #   ne peut pas être nul
    )

    type = Column(                              # colonne type
        PGEnum(                                 #   type ENUM PostgreSQL
            DocumentType, 
            name="document_type", 
            create_type=True
        ),
        nullable=False                          #   ne peut pas être nul
    )

    file_url = Column(                          # colonne file_url
        Text,                                   #   type texte
        nullable=False                          #   ne peut pas être nul
    )

    file_hash = Column(                         # colonne file_hash
        Text,                                   #   type texte
        nullable=True,                          #   optionnel
        unique=True                             #   valeur unique
    )

    verification_status = Column(               # colonne verification_status
        PGEnum(                                 #   type ENUM PostgreSQL
            VerificationStatus, 
            name="document_verification_status", 
            create_type=True
        ),
        nullable=False,                         #   ne peut pas être nul
        server_default=VerificationStatus.pending.value  #   défaut 'pending'
    )

    rejection_reason = Column(                  # colonne rejection_reason
        Text,                                   #   type texte
        nullable=True                           #   optionnel
    )

    uploaded_at = Column(                       # colonne uploaded_at
        DateTime(timezone=True),                #   timestamp avec fuseau
        nullable=False,                         #   ne peut pas être nul
        server_default=func.current_timestamp() #   défaut CURRENT_TIMESTAMP
    )

    verified_at = Column(                       # colonne verified_at
        DateTime(timezone=True),                #   timestamp avec fuseau
        nullable=True                           #   optionnel, renseigné par trigger
    )

    updated_at = Column(                        # colonne updated_at
        DateTime(timezone=True),                #   timestamp avec fuseau
        nullable=False,                         #   ne peut pas être nul
        server_default=func.current_timestamp() #   défaut CURRENT_TIMESTAMP
    )

    verified_by = Column(                       # colonne verified_by
        UUID(as_uuid=True),                     #   type UUID PostgreSQL
        ForeignKey("user.id", ondelete="SET NULL"), # met à NULL si user supprimé
        nullable=True                           #   optionnel
    )

    expires_at = Column(                        # colonne expires_at
        DateTime(timezone=True),                #   timestamp avec fuseau
        nullable=True                           #   optionnel
    )

    encryption_key_id = Column(                 # colonne encryption_key_id
        UUID(as_uuid=True),                     #   type UUID PostgreSQL
        ForeignKey("encryption_key.id",          # clé étrangère
                   ondelete="RESTRICT"),        # empêche suppression si liée
        nullable=True                           #   optionnel
    )

    document_number = Column(                   # colonne document_number
        Text,                                   #   type texte
        nullable=True                           #   optionnel
    )

    country_issued = Column(                    # colonne country_issued
        String(2),                              #   code pays ISO 2 lettres
        nullable=True                           #   optionnel
    )

    document_metadata = Column(
        "metadata",   # nom réel de la colonne en base
        JSONB,
        nullable=True # autorise la valeur NULL
    )  # [metadata] : Métadonnées techniques (IV, tag, etc.)

    __table_args__ = (                          # index et contraintes personnalisés
        Index("idx_document_user", "user_id"),  #   index sur user_id
        Index("idx_document_status", "verification_status"), # index sur statut
        Index("idx_document_type", "type"),     #   index sur type
        Index("idx_document_uploaded_at",       #   index sur uploaded_at DESC
              text("uploaded_at DESC")),
        Index("idx_document_expires_at", "expires_at"), # index sur expires_at
        Index(                                  #   index unique partiel
            "uniq_user_doc_type_valid",         #   nom de l’index
            "user_id", "type",                  #   colonnes couvertes
            unique=True,                        #   contrainte d’unicité
            postgresql_where=text(              #   condition PostgreSQL
                "verification_status IN ("
                "'pending','under_review','approved')"
            )
        ),
    )

# ========================================================
# 3. DDL pour triggers et procédure stockée
# ========================================================
ddl_set_verified_at = DDL(                    # DDL pour trigger set_document_verified_at
    """
    CREATE OR REPLACE FUNCTION set_document_verified_at()
    RETURNS TRIGGER AS $$
    BEGIN
        IF NEW.verification_status = 'approved'
           AND OLD.verification_status <> 'approved'
        THEN
            NEW.verified_at := CURRENT_TIMESTAMP;
        END IF;
        RETURN NEW;
    END;
    $$ LANGUAGE plpgsql STABLE;

    CREATE TRIGGER trg_set_document_verified_at
    BEFORE UPDATE ON document
    FOR EACH ROW EXECUTE FUNCTION set_document_verified_at();
    """
)

ddl_set_updated_at = DDL(                     # DDL pour trigger set_document_updated_at
    """
    CREATE OR REPLACE FUNCTION set_document_updated_at()
    RETURNS TRIGGER AS $$
    BEGIN
        NEW.updated_at := CURRENT_TIMESTAMP;
        RETURN NEW;
    END;
    $$ LANGUAGE plpgsql STABLE;

    CREATE TRIGGER trg_document_updated_at
    BEFORE UPDATE ON document
    FOR EACH ROW EXECUTE FUNCTION set_document_updated_at();
    """
)

ddl_update_verification = DDL(                # DDL pour procédure update_document_verification_status
    """
    CREATE OR REPLACE PROCEDURE update_document_verification_status(
        p_document_id UUID,
        p_new_status VARCHAR,
        p_rejection_reason TEXT DEFAULT NULL,
        p_verifier_user_id UUID DEFAULT NULL
    )
    LANGUAGE plpgsql
    AS $$
    BEGIN
        UPDATE document
        SET
            verification_status = p_new_status,
            rejection_reason = CASE
                WHEN p_new_status = 'rejected' THEN p_rejection_reason
                ELSE rejection_reason
            END,
            verified_at = CASE
                WHEN p_new_status = 'approved' THEN CURRENT_TIMESTAMP
                ELSE verified_at
            END,
            verified_by = CASE
                WHEN p_new_status IN ('approved','rejected') THEN p_verifier_user_id
                ELSE verified_by
            END,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = p_document_id;
    END;
    $$;
    """
)

# ========================================================
# 4. Attachement des DDL après création de la table
# ========================================================
event.listen(                                # attache ddl_set_verified_at
    Document.__table__, 'after_create', ddl_set_verified_at
)
event.listen(                                # attache ddl_set_updated_at
    Document.__table__, 'after_create', ddl_set_updated_at
)
event.listen(                                # attache ddl_update_verification
    Document.__table__, 'after_create', ddl_update_verification
)
