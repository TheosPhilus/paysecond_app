# app/models/__init__.py

# On importe la base déclarative depuis le fichier database.py
from app.database import Base

# On importe tous les modèles pour qu'Alembic puisse les détecter
from .ApiKey import ApiKey
from .BankAccount import BankAccount
from .BatchProcessing import BatchProcessing
from .Card import Card
from .Document import Document
from .EncryptionKey import EncryptionKey
from .ExchangeRate import ExchangeRate
from .FailedTransaction import FailedTransaction
from .Merchant import Merchant
from .Notification import Notification
from .SearchIndex import SearchIndex
from .SecurityLog import SecurityLog
from .Subscription import Subscription
from .Transaction import Transaction
from .TransactionErrorCode import TransactionErrorCode
from .User import User
from .Wallet import Wallet
from .WalletAuditLog import WalletAuditLog
from .Webhook import Webhook
from .WebhookLog import WebhookLog


# Ajoute ici d'autres modèles au fur et à mesure (Wallet, Transaction, etc.)
# from .wallet import Wallet
# from .card import Card
# etc.
