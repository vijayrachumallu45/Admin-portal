"""Domain package: Facilities."""
from app.domains.facilities.engine import engine
from app.domains.facilities.routes import bp
from app.domains.facilities.services import service
__all__ = ['engine', 'bp', 'service']
