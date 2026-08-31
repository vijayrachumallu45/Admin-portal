"""Domain package: Training Catalog."""
from app.domains.training_courses.engine import engine
from app.domains.training_courses.routes import bp
from app.domains.training_courses.services import service
__all__ = ['engine', 'bp', 'service']
