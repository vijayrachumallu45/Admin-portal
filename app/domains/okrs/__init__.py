"""Domain package: OKR Board."""
from app.domains.okrs.engine import engine
from app.domains.okrs.routes import bp
from app.domains.okrs.services import service
__all__ = ['engine', 'bp', 'service']
