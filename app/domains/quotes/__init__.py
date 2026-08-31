"""Domain package: Quote Workshop."""
from app.domains.quotes.engine import engine
from app.domains.quotes.routes import bp
from app.domains.quotes.services import service
__all__ = ['engine', 'bp', 'service']
