"""Domain package: Fleet Assets."""
from app.domains.fleet_assets.engine import engine
from app.domains.fleet_assets.routes import bp
from app.domains.fleet_assets.services import service
__all__ = ['engine', 'bp', 'service']
