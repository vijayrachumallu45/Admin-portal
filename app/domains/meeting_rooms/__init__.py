"""Domain package: Meeting Rooms."""
from app.domains.meeting_rooms.engine import engine
from app.domains.meeting_rooms.routes import bp
from app.domains.meeting_rooms.services import service
__all__ = ['engine', 'bp', 'service']
