"""Domain package: Vendor Register."""
from app.domains.vendors.engine import engine
from app.domains.vendors.routes import bp
from app.domains.vendors.services import service
__all__ = ['engine', 'bp', 'service']
