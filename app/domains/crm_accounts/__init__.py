"""Domain package: CRM Accounts."""
from app.domains.crm_accounts.engine import engine
from app.domains.crm_accounts.routes import bp
from app.domains.crm_accounts.services import service
__all__ = ['engine', 'bp', 'service']
