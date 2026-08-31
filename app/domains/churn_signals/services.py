"""Application service for Churn Signals writes and operator actions."""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.domains.churn_signals.engine import engine
from app.domains.churn_signals.policies import churn_signals_gate_transition, churn_signals_policy_card, churn_signals_run_field_checks
from app.domains.churn_signals.queries import churn_signals_diff, churn_signals_export_map
from app.domains.churn_signals.reports import build_churn_signals_reporter


class ChurnSignalsService:
    """Coordinates validation, policy, persistence, and briefings for Churn Signals."""

    def list_view(self, filters: dict[str, Any] | None = None) -> dict[str, Any]:
        rows = engine.list_records(filters)
        reporter = build_churn_signals_reporter(rows)
        return {
            'rows': rows,
            'kpis': engine.kpi_pack(),
            'pack': reporter.pack(),
        }

    def detail_view(self, record_id: str) -> dict[str, Any] | None:
        row = engine.get(record_id)
        if row is None:
            return None
        card = churn_signals_policy_card(row)
        return {'record': row, 'policy': card}

    def create_from_form(self, payload: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        field_errors = churn_signals_run_field_checks(payload)
        if field_errors:
            return None, field_errors
        return engine.create(payload)

    def update_from_form(self, record_id: str, payload: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        current = engine.get(record_id)
        if current is None:
            return None, ['missing record']
        merged = deepcopy(current)
        merged.update(payload)
        field_errors = churn_signals_run_field_checks(merged)
        if field_errors:
            return None, field_errors
        row, errors = engine.update(record_id, payload)
        if row:
            row['_diff'] = churn_signals_diff(current, row)
        return row, errors

    def move_status(self, record_id: str, new_status: str) -> tuple[dict[str, Any] | None, list[str]]:
        current = engine.get(record_id)
        if current is None:
            return None, ['missing record']
        errors = churn_signals_gate_transition(str(current.get('status') or ''), new_status)
        if errors:
            return None, errors
        return engine.transition(record_id, new_status)

    def export_maps(self) -> list[dict[str, str]]:
        return [churn_signals_export_map(row) for row in engine.list_records()]

    def seed_if_empty(self, count: int = 10) -> int:
        return engine.seed_demo(count)


service = ChurnSignalsService()


def churn_signals_safe_payload(form: dict[str, Any]) -> dict[str, Any]:
    allowed = {name for name in ['account_name', 'signal', 'severity', 'owner', 'status']}
    clean = {}
    for name, value in form.items():
        if name in allowed or name in {'id', 'status'}:
            clean[name] = value
    return clean


def churn_signals_can_delete(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    if status == 'open':
        return True
    return int(row.get('health_score') or 0) < 20


def churn_signals_next_statuses(current: str) -> list[str]:
    if current not in ['open', 'working', 'saved', 'lost']:
        return list(['open', 'working', 'saved', 'lost'])
    index = ['open', 'working', 'saved', 'lost'].index(current)
    options = [current]
    if index + 1 < len(['open', 'working', 'saved', 'lost']):
        options.append(['open', 'working', 'saved', 'lost'][index + 1])
    if index > 0:
        options.append(['open', 'working', 'saved', 'lost'][index - 1])
    unique = []
    for item in options:
        if item not in unique:
            unique.append(item)
    return unique


def churn_signals_operator_actions(row: dict[str, Any]) -> list[dict[str, str]]:
    actions = [{'code': 'edit', 'label': 'Edit record'}]
    for status in churn_signals_next_statuses(str(row.get('status') or '')):
        actions.append({'code': 'status:' + status, 'label': 'Move to ' + status})
    if churn_signals_can_delete(row):
        actions.append({'code': 'delete', 'label': 'Remove record'})
    return actions


def churn_signals_toast(action: str, ok: bool) -> str:
    if ok:
        return f'Churn Signals {action} completed.'
    return f'Churn Signals {action} was blocked by policy.'


def churn_signals_dashboard_chip(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        'key': 'churn_signals',
        'title': 'Churn Signals',
        'count': len(rows),
        'hot': len([row for row in rows if int(row.get('health_score') or 0) < 45]),
    }

def churn_signals_form_help_account_name() -> str:
    return 'Enter Account Name for Churn Signals. Local validation runs on save.'


def churn_signals_form_help_signal() -> str:
    return 'Enter Signal for Churn Signals. Local validation runs on save.'


def churn_signals_form_help_severity() -> str:
    return 'Enter Severity for Churn Signals. Local validation runs on save.'


def churn_signals_form_help_owner() -> str:
    return 'Enter Owner for Churn Signals. Local validation runs on save.'


def churn_signals_form_help_status() -> str:
    return 'Enter Status for Churn Signals. Local validation runs on save.'


FORM_HELP_CHURN_SIGNALS = {
    'account_name': churn_signals_form_help_account_name(),
    'signal': churn_signals_form_help_signal(),
    'severity': churn_signals_form_help_severity(),
    'owner': churn_signals_form_help_owner(),
    'status': churn_signals_form_help_status(),
}


def churn_signals_form_help() -> dict[str, str]:
    return dict(FORM_HELP_CHURN_SIGNALS)

