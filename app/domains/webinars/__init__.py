"""Domain package: Webinar Desk."""
from app.domains.webinars.engine import engine
from app.domains.webinars.routes import bp
from app.domains.webinars.services import service
__all__ = ['engine', 'bp', 'service']
