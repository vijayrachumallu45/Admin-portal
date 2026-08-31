"""Domain package: Revenue Forecast."""
from app.domains.forecasts.engine import engine
from app.domains.forecasts.routes import bp
from app.domains.forecasts.services import service
__all__ = ['engine', 'bp', 'service']
