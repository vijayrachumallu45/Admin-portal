"""Domain package: Opportunity Board."""
from app.domains.opportunities.engine import engine
from app.domains.opportunities.routes import bp
from app.domains.opportunities.services import service
__all__ = ['engine', 'bp', 'service']
