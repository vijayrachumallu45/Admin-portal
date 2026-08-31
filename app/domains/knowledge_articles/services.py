"""Application service for Knowledge Base writes and operator actions."""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.domains.knowledge_articles.engine import engine
from app.domains.knowledge_articles.policies import knowledge_articles_gate_transition, knowledge_articles_policy_card, knowledge_articles_run_field_checks
from app.domains.knowledge_articles.queries import knowledge_articles_diff, knowledge_articles_export_map
from app.domains.knowledge_articles.reports import build_knowledge_articles_reporter


class KnowledgeArticlesService:
    """Coordinates validation, policy, persistence, and briefings for Knowledge Base."""

    def list_view(self, filters: dict[str, Any] | None = None) -> dict[str, Any]:
        rows = engine.list_records(filters)
        reporter = build_knowledge_articles_reporter(rows)
        return {
            'rows': rows,
            'kpis': engine.kpi_pack(),
            'pack': reporter.pack(),
        }

    def detail_view(self, record_id: str) -> dict[str, Any] | None:
        row = engine.get(record_id)
        if row is None:
            return None
        card = knowledge_articles_policy_card(row)
        return {'record': row, 'policy': card}

    def create_from_form(self, payload: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        field_errors = knowledge_articles_run_field_checks(payload)
        if field_errors:
            return None, field_errors
        return engine.create(payload)

    def update_from_form(self, record_id: str, payload: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        current = engine.get(record_id)
        if current is None:
            return None, ['missing record']
        merged = deepcopy(current)
        merged.update(payload)
        field_errors = knowledge_articles_run_field_checks(merged)
        if field_errors:
            return None, field_errors
        row, errors = engine.update(record_id, payload)
        if row:
            row['_diff'] = knowledge_articles_diff(current, row)
        return row, errors

    def move_status(self, record_id: str, new_status: str) -> tuple[dict[str, Any] | None, list[str]]:
        current = engine.get(record_id)
        if current is None:
            return None, ['missing record']
        errors = knowledge_articles_gate_transition(str(current.get('status') or ''), new_status)
        if errors:
            return None, errors
        return engine.transition(record_id, new_status)

    def export_maps(self) -> list[dict[str, str]]:
        return [knowledge_articles_export_map(row) for row in engine.list_records()]

    def seed_if_empty(self, count: int = 10) -> int:
        return engine.seed_demo(count)


service = KnowledgeArticlesService()


def knowledge_articles_safe_payload(form: dict[str, Any]) -> dict[str, Any]:
    allowed = {name for name in ['slug_key', 'title', 'audience', 'owner', 'status']}
    clean = {}
    for name, value in form.items():
        if name in allowed or name in {'id', 'status'}:
            clean[name] = value
    return clean


def knowledge_articles_can_delete(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    if status == 'draft':
        return True
    return int(row.get('health_score') or 0) < 20


def knowledge_articles_next_statuses(current: str) -> list[str]:
    if current not in ['draft', 'review', 'published', 'retired']:
        return list(['draft', 'review', 'published', 'retired'])
    index = ['draft', 'review', 'published', 'retired'].index(current)
    options = [current]
    if index + 1 < len(['draft', 'review', 'published', 'retired']):
        options.append(['draft', 'review', 'published', 'retired'][index + 1])
    if index > 0:
        options.append(['draft', 'review', 'published', 'retired'][index - 1])
    unique = []
    for item in options:
        if item not in unique:
            unique.append(item)
    return unique


def knowledge_articles_operator_actions(row: dict[str, Any]) -> list[dict[str, str]]:
    actions = [{'code': 'edit', 'label': 'Edit record'}]
    for status in knowledge_articles_next_statuses(str(row.get('status') or '')):
        actions.append({'code': 'status:' + status, 'label': 'Move to ' + status})
    if knowledge_articles_can_delete(row):
        actions.append({'code': 'delete', 'label': 'Remove record'})
    return actions


def knowledge_articles_toast(action: str, ok: bool) -> str:
    if ok:
        return f'Knowledge Base {action} completed.'
    return f'Knowledge Base {action} was blocked by policy.'


def knowledge_articles_dashboard_chip(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        'key': 'knowledge_articles',
        'title': 'Knowledge Base',
        'count': len(rows),
        'hot': len([row for row in rows if int(row.get('health_score') or 0) < 45]),
    }

def knowledge_articles_form_help_slug_key() -> str:
    return 'Enter Slug Key for Knowledge Base. Local validation runs on save.'


def knowledge_articles_form_help_title() -> str:
    return 'Enter Title for Knowledge Base. Local validation runs on save.'


def knowledge_articles_form_help_audience() -> str:
    return 'Enter Audience for Knowledge Base. Local validation runs on save.'


def knowledge_articles_form_help_owner() -> str:
    return 'Enter Owner for Knowledge Base. Local validation runs on save.'


def knowledge_articles_form_help_status() -> str:
    return 'Enter Status for Knowledge Base. Local validation runs on save.'


FORM_HELP_KNOWLEDGE_ARTICLES = {
    'slug_key': knowledge_articles_form_help_slug_key(),
    'title': knowledge_articles_form_help_title(),
    'audience': knowledge_articles_form_help_audience(),
    'owner': knowledge_articles_form_help_owner(),
    'status': knowledge_articles_form_help_status(),
}


def knowledge_articles_form_help() -> dict[str, str]:
    return dict(FORM_HELP_KNOWLEDGE_ARTICLES)

