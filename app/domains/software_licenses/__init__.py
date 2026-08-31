"""Domain package: Software Licenses."""
from app.domains.software_licenses.engine import engine
from app.domains.software_licenses.routes import bp
from app.domains.software_licenses.services import service
__all__ = ['engine', 'bp', 'service']
