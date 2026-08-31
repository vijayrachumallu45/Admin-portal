"""Domain package: Inventory Lots."""
from app.domains.inventory_lots.engine import engine
from app.domains.inventory_lots.routes import bp
from app.domains.inventory_lots.services import service
__all__ = ['engine', 'bp', 'service']
