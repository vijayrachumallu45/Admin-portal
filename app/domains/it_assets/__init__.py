"""Domain package: IT Asset Register."""
from app.domains.it_assets.engine import engine
from app.domains.it_assets.routes import bp
from app.domains.it_assets.services import service
__all__ = ['engine', 'bp', 'service']
