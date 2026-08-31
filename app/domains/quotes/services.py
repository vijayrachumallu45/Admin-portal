"""Application service for Quote Workshop writes and operator actions."""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.domains.quotes.engine import engine
from app.domains.quotes.policies import quotes_gate_transition, quotes_policy_card, quotes_run_field_checks
from app.domains.quotes.queries import quotes_diff, quotes_export_map
from app.domains.quotes.reports import build_quotes_reporter


class QuotesService:
    """Coordinates validation, policy, persistence, and briefings for Quote Workshop."""

    def list_view(self, filters: dict[str, Any] | None = None) -> dict[str, Any]:
        rows = engine.list_records(filters)
        reporter = build_quotes_reporter(rows)
        return {
            'rows': rows,
            'kpis': engine.kpi_pack(),
            'pack': reporter.pack(),
        }

    def detail_view(self, record_id: str) -> dict[str, Any] | None:
        row = engine.get(record_id)
        if row is None:
            return None
        card = quotes_policy_card(row)
        return {'record': row, 'policy': card}

    def create_from_form(self, payload: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        field_errors = quotes_run_field_checks(payload)
        if field_errors:
            return None, field_errors
        return engine.create(payload)

    def update_from_form(self, record_id: str, payload: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        current = engine.get(record_id)
        if current is None:
            return None, ['missing record']
        merged = deepcopy(current)
        merged.update(payload)
        field_errors = quotes_run_field_checks(merged)
        if field_errors:
            return None, field_errors
        row, errors = engine.update(record_id, payload)
        if row:
            row['_diff'] = quotes_diff(current, row)
        return row, errors

    def move_status(self, record_id: str, new_status: str) -> tuple[dict[str, Any] | None, list[str]]:
        current = engine.get(record_id)
        if current is None:
            return None, ['missing record']
        errors = quotes_gate_transition(str(current.get('status') or ''), new_status)
        if errors:
            return None, errors
        return engine.transition(record_id, new_status)

    def export_maps(self) -> list[dict[str, str]]:
        return [quotes_export_map(row) for row in engine.list_records()]

    def seed_if_empty(self, count: int = 10) -> int:
        return engine.seed_demo(count)


service = QuotesService()


def quotes_safe_payload(form: dict[str, Any]) -> dict[str, Any]:
    allowed = {name for name in ['quote_no', 'account_name', 'list_cents', 'discount_bps', 'owner', 'status']}
    clean = {}
    for name, value in form.items():
        if name in allowed or name in {'id', 'status'}:
            clean[name] = value
    return clean


def quotes_can_delete(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    if status == 'draft':
        return True
    return int(row.get('health_score') or 0) < 20


def quotes_next_statuses(current: str) -> list[str]:
    if current not in ['draft', 'sent', 'accepted', 'expired']:
        return list(['draft', 'sent', 'accepted', 'expired'])
    index = ['draft', 'sent', 'accepted', 'expired'].index(current)
    options = [current]
    if index + 1 < len(['draft', 'sent', 'accepted', 'expired']):
        options.append(['draft', 'sent', 'accepted', 'expired'][index + 1])
    if index > 0:
        options.append(['draft', 'sent', 'accepted', 'expired'][index - 1])
    unique = []
    for item in options:
        if item not in unique:
            unique.append(item)
    return unique


def quotes_operator_actions(row: dict[str, Any]) -> list[dict[str, str]]:
    actions = [{'code': 'edit', 'label': 'Edit record'}]
    for status in quotes_next_statuses(str(row.get('status') or '')):
        actions.append({'code': 'status:' + status, 'label': 'Move to ' + status})
    if quotes_can_delete(row):
        actions.append({'code': 'delete', 'label': 'Remove record'})
    return actions


def quotes_toast(action: str, ok: bool) -> str:
    if ok:
        return f'Quote Workshop {action} completed.'
    return f'Quote Workshop {action} was blocked by policy.'


def quotes_dashboard_chip(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        'key': 'quotes',
        'title': 'Quote Workshop',
        'count': len(rows),
        'hot': len([row for row in rows if int(row.get('health_score') or 0) < 45]),
    }

def quotes_form_help_quote_no() -> str:
    return 'Enter Quote No for Quote Workshop. Local validation runs on save.'


def quotes_form_help_account_name() -> str:
    return 'Enter Account Name for Quote Workshop. Local validation runs on save.'


def quotes_form_help_list_cents() -> str:
    return 'Enter List Cents for Quote Workshop. Local validation runs on save.'


def quotes_form_help_discount_bps() -> str:
    return 'Enter Discount Bps for Quote Workshop. Local validation runs on save.'


def quotes_form_help_owner() -> str:
    return 'Enter Owner for Quote Workshop. Local validation runs on save.'


def quotes_form_help_status() -> str:
    return 'Enter Status for Quote Workshop. Local validation runs on save.'


FORM_HELP_QUOTES = {
    'quote_no': quotes_form_help_quote_no(),
    'account_name': quotes_form_help_account_name(),
    'list_cents': quotes_form_help_list_cents(),
    'discount_bps': quotes_form_help_discount_bps(),
    'owner': quotes_form_help_owner(),
    'status': quotes_form_help_status(),
}


def quotes_form_help() -> dict[str, str]:
    return dict(FORM_HELP_QUOTES)

