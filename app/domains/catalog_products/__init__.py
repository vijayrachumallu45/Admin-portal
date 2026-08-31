"""Domain package: Product Catalog."""
from app.domains.catalog_products.engine import engine
from app.domains.catalog_products.routes import bp
from app.domains.catalog_products.services import service
__all__ = ['engine', 'bp', 'service']
