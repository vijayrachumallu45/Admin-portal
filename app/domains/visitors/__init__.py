"""Domain package: Visitor Desk."""
from app.domains.visitors.engine import engine
from app.domains.visitors.routes import bp
from app.domains.visitors.services import service
__all__ = ['engine', 'bp', 'service']
