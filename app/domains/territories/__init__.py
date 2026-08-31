"""Domain package: Sales Territories."""
from app.domains.territories.engine import engine
from app.domains.territories.routes import bp
from app.domains.territories.services import service
__all__ = ['engine', 'bp', 'service']
