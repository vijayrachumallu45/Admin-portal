"""Domain package: Compensation Bands."""
from app.domains.compensation_bands.engine import engine
from app.domains.compensation_bands.routes import bp
from app.domains.compensation_bands.services import service
__all__ = ['engine', 'bp', 'service']
