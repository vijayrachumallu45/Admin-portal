"""Domain package: Invoice Desk."""
from app.domains.invoices.engine import engine
from app.domains.invoices.routes import bp
from app.domains.invoices.services import service
__all__ = ['engine', 'bp', 'service']
