"""Domain package: On-call Rotations."""
from app.domains.oncall_rotations.engine import engine
from app.domains.oncall_rotations.routes import bp
from app.domains.oncall_rotations.services import service
__all__ = ['engine', 'bp', 'service']
