"""Domain package: People Directory."""
from app.domains.directory_users.engine import engine
from app.domains.directory_users.routes import bp
from app.domains.directory_users.services import service
__all__ = ['engine', 'bp', 'service']
