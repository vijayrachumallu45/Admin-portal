"""Domain package: HR Employees."""
from app.domains.employees.engine import engine
from app.domains.employees.routes import bp
from app.domains.employees.services import service
__all__ = ['engine', 'bp', 'service']
