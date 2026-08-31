"""Application service for Journal Entries writes and operator actions."""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.domains.journal_entries.engine import engine
from app.domains.journal_entries.policies import journal_entries_gate_transition, journal_entries_policy_card, journal_entries_run_field_checks
from app.domains.journal_entries.queries import journal_entries_diff, journal_entries_export_map
from app.domains.journal_entries.reports import build_journal_entries_reporter


class JournalEntriesService:
    """Coordinates validation, policy, persistence, and briefings for Journal Entries."""

    def list_view(self, filters: dict[str, Any] | None = None) -> dict[str, Any]:
        rows = engine.list_records(filters)
        reporter = build_journal_entries_reporter(rows)
        return {
            'rows': rows,
            'kpis': engine.kpi_pack(),
            'pack': reporter.pack(),
        }

    def detail_view(self, record_id: str) -> dict[str, Any] | None:
        row = engine.get(record_id)
        if row is None:
            return None
        card = journal_entries_policy_card(row)
        return {'record': row, 'policy': card}

    def create_from_form(self, payload: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        field_errors = journal_entries_run_field_checks(payload)
        if field_errors:
            return None, field_errors
        return engine.create(payload)

    def update_from_form(self, record_id: str, payload: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        current = engine.get(record_id)
        if current is None:
            return None, ['missing record']
        merged = deepcopy(current)
        merged.update(payload)
        field_errors = journal_entries_run_field_checks(merged)
        if field_errors:
            return None, field_errors
        row, errors = engine.update(record_id, payload)
        if row:
            row['_diff'] = journal_entries_diff(current, row)
        return row, errors

    def move_status(self, record_id: str, new_status: str) -> tuple[dict[str, Any] | None, list[str]]:
        current = engine.get(record_id)
        if current is None:
            return None, ['missing record']
        errors = journal_entries_gate_transition(str(current.get('status') or ''), new_status)
        if errors:
            return None, errors
        return engine.transition(record_id, new_status)

    def export_maps(self) -> list[dict[str, str]]:
        return [journal_entries_export_map(row) for row in engine.list_records()]

    def seed_if_empty(self, count: int = 10) -> int:
        return engine.seed_demo(count)


service = JournalEntriesService()


def journal_entries_safe_payload(form: dict[str, Any]) -> dict[str, Any]:
    allowed = {name for name in ['entry_no', 'memo', 'amount_cents', 'posted_on', 'status']}
    clean = {}
    for name, value in form.items():
        if name in allowed or name in {'id', 'status'}:
            clean[name] = value
    return clean


def journal_entries_can_delete(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    if status == 'draft':
        return True
    return int(row.get('health_score') or 0) < 20


def journal_entries_next_statuses(current: str) -> list[str]:
    if current not in ['draft', 'posted', 'reversed']:
        return list(['draft', 'posted', 'reversed'])
    index = ['draft', 'posted', 'reversed'].index(current)
    options = [current]
    if index + 1 < len(['draft', 'posted', 'reversed']):
        options.append(['draft', 'posted', 'reversed'][index + 1])
    if index > 0:
        options.append(['draft', 'posted', 'reversed'][index - 1])
    unique = []
    for item in options:
        if item not in unique:
            unique.append(item)
    return unique


def journal_entries_operator_actions(row: dict[str, Any]) -> list[dict[str, str]]:
    actions = [{'code': 'edit', 'label': 'Edit record'}]
    for status in journal_entries_next_statuses(str(row.get('status') or '')):
        actions.append({'code': 'status:' + status, 'label': 'Move to ' + status})
    if journal_entries_can_delete(row):
        actions.append({'code': 'delete', 'label': 'Remove record'})
    return actions


def journal_entries_toast(action: str, ok: bool) -> str:
    if ok:
        return f'Journal Entries {action} completed.'
    return f'Journal Entries {action} was blocked by policy.'


def journal_entries_dashboard_chip(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        'key': 'journal_entries',
        'title': 'Journal Entries',
        'count': len(rows),
        'hot': len([row for row in rows if int(row.get('health_score') or 0) < 45]),
    }

def journal_entries_form_help_entry_no() -> str:
    return 'Enter Entry No for Journal Entries. Local validation runs on save.'


def journal_entries_form_help_memo() -> str:
    return 'Enter Memo for Journal Entries. Local validation runs on save.'


def journal_entries_form_help_amount_cents() -> str:
    return 'Enter Amount Cents for Journal Entries. Local validation runs on save.'


def journal_entries_form_help_posted_on() -> str:
    return 'Enter Posted On for Journal Entries. Local validation runs on save.'


def journal_entries_form_help_status() -> str:
    return 'Enter Status for Journal Entries. Local validation runs on save.'


FORM_HELP_JOURNAL_ENTRIES = {
    'entry_no': journal_entries_form_help_entry_no(),
    'memo': journal_entries_form_help_memo(),
    'amount_cents': journal_entries_form_help_amount_cents(),
    'posted_on': journal_entries_form_help_posted_on(),
    'status': journal_entries_form_help_status(),
}


def journal_entries_form_help() -> dict[str, str]:
    return dict(FORM_HELP_JOURNAL_ENTRIES)

