"""Application service for Price Books writes and operator actions."""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.domains.price_books.engine import engine
from app.domains.price_books.policies import price_books_gate_transition, price_books_policy_card, price_books_run_field_checks
from app.domains.price_books.queries import price_books_diff, price_books_export_map
from app.domains.price_books.reports import build_price_books_reporter


class PriceBooksService:
    """Coordinates validation, policy, persistence, and briefings for Price Books."""

    def list_view(self, filters: dict[str, Any] | None = None) -> dict[str, Any]:
        rows = engine.list_records(filters)
        reporter = build_price_books_reporter(rows)
        return {
            'rows': rows,
            'kpis': engine.kpi_pack(),
            'pack': reporter.pack(),
        }

    def detail_view(self, record_id: str) -> dict[str, Any] | None:
        row = engine.get(record_id)
        if row is None:
            return None
        card = price_books_policy_card(row)
        return {'record': row, 'policy': card}

    def create_from_form(self, payload: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        field_errors = price_books_run_field_checks(payload)
        if field_errors:
            return None, field_errors
        return engine.create(payload)

    def update_from_form(self, record_id: str, payload: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        current = engine.get(record_id)
        if current is None:
            return None, ['missing record']
        merged = deepcopy(current)
        merged.update(payload)
        field_errors = price_books_run_field_checks(merged)
        if field_errors:
            return None, field_errors
        row, errors = engine.update(record_id, payload)
        if row:
            row['_diff'] = price_books_diff(current, row)
        return row, errors

    def move_status(self, record_id: str, new_status: str) -> tuple[dict[str, Any] | None, list[str]]:
        current = engine.get(record_id)
        if current is None:
            return None, ['missing record']
        errors = price_books_gate_transition(str(current.get('status') or ''), new_status)
        if errors:
            return None, errors
        return engine.transition(record_id, new_status)

    def export_maps(self) -> list[dict[str, str]]:
        return [price_books_export_map(row) for row in engine.list_records()]

    def seed_if_empty(self, count: int = 10) -> int:
        return engine.seed_demo(count)


service = PriceBooksService()


def price_books_safe_payload(form: dict[str, Any]) -> dict[str, Any]:
    allowed = {name for name in ['book_code', 'region', 'currency', 'valid_from', 'status']}
    clean = {}
    for name, value in form.items():
        if name in allowed or name in {'id', 'status'}:
            clean[name] = value
    return clean


def price_books_can_delete(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    if status == 'draft':
        return True
    return int(row.get('health_score') or 0) < 20


def price_books_next_statuses(current: str) -> list[str]:
    if current not in ['draft', 'active', 'superseded']:
        return list(['draft', 'active', 'superseded'])
    index = ['draft', 'active', 'superseded'].index(current)
    options = [current]
    if index + 1 < len(['draft', 'active', 'superseded']):
        options.append(['draft', 'active', 'superseded'][index + 1])
    if index > 0:
        options.append(['draft', 'active', 'superseded'][index - 1])
    unique = []
    for item in options:
        if item not in unique:
            unique.append(item)
    return unique


def price_books_operator_actions(row: dict[str, Any]) -> list[dict[str, str]]:
    actions = [{'code': 'edit', 'label': 'Edit record'}]
    for status in price_books_next_statuses(str(row.get('status') or '')):
        actions.append({'code': 'status:' + status, 'label': 'Move to ' + status})
    if price_books_can_delete(row):
        actions.append({'code': 'delete', 'label': 'Remove record'})
    return actions


def price_books_toast(action: str, ok: bool) -> str:
    if ok:
        return f'Price Books {action} completed.'
    return f'Price Books {action} was blocked by policy.'


def price_books_dashboard_chip(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        'key': 'price_books',
        'title': 'Price Books',
        'count': len(rows),
        'hot': len([row for row in rows if int(row.get('health_score') or 0) < 45]),
    }

def price_books_form_help_book_code() -> str:
    return 'Enter Book Code for Price Books. Local validation runs on save.'


def price_books_form_help_region() -> str:
    return 'Enter Region for Price Books. Local validation runs on save.'


def price_books_form_help_currency() -> str:
    return 'Enter Currency for Price Books. Local validation runs on save.'


def price_books_form_help_valid_from() -> str:
    return 'Enter Valid From for Price Books. Local validation runs on save.'


def price_books_form_help_status() -> str:
    return 'Enter Status for Price Books. Local validation runs on save.'


FORM_HELP_PRICE_BOOKS = {
    'book_code': price_books_form_help_book_code(),
    'region': price_books_form_help_region(),
    'currency': price_books_form_help_currency(),
    'valid_from': price_books_form_help_valid_from(),
    'status': price_books_form_help_status(),
}


def price_books_form_help() -> dict[str, str]:
    return dict(FORM_HELP_PRICE_BOOKS)

