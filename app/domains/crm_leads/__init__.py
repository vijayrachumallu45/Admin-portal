"""Domain package: Lead Inbox."""
from app.domains.crm_leads.engine import engine
from app.domains.crm_leads.routes import bp
from app.domains.crm_leads.services import service
__all__ = ['engine', 'bp', 'service']
