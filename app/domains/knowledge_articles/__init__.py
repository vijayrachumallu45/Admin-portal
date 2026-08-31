"""Domain package: Knowledge Base."""
from app.domains.knowledge_articles.engine import engine
from app.domains.knowledge_articles.routes import bp
from app.domains.knowledge_articles.services import service
__all__ = ['engine', 'bp', 'service']
