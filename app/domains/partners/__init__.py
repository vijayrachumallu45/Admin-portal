"""Domain package: Partner Desk."""
from app.domains.partners.engine import engine
from app.domains.partners.routes import bp
from app.domains.partners.services import service
__all__ = ['engine', 'bp', 'service']
