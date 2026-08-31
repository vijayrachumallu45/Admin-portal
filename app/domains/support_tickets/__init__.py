"""Domain package: Support Queue."""
from app.domains.support_tickets.engine import engine
from app.domains.support_tickets.routes import bp
from app.domains.support_tickets.services import service
__all__ = ['engine', 'bp', 'service']
