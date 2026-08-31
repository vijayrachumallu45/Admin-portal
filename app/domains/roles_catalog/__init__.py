"""Domain package: Role Catalog."""
from app.domains.roles_catalog.engine import engine
from app.domains.roles_catalog.routes import bp
from app.domains.roles_catalog.services import service
__all__ = ['engine', 'bp', 'service']
