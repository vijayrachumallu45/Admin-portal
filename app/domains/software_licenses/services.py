"""Application service for Software Licenses writes and operator actions."""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.domains.software_licenses.engine import engine
from app.domains.software_licenses.policies import software_licenses_gate_transition, software_licenses_policy_card, software_licenses_run_field_checks
from app.domains.software_licenses.queries import software_licenses_diff, software_licenses_export_map
from app.domains.software_licenses.reports import build_software_licenses_reporter


class SoftwareLicensesService:
    """Coordinates validation, policy, persistence, and briefings for Software Licenses."""

    def list_view(self, filters: dict[str, Any] | None = None) -> dict[str, Any]:
        rows = engine.list_records(filters)
        reporter = build_software_licenses_reporter(rows)
        return {
            'rows': rows,
            'kpis': engine.kpi_pack(),
            'pack': reporter.pack(),
        }

    def detail_view(self, record_id: str) -> dict[str, Any] | None:
        row = engine.get(record_id)
        if row is None:
            return None
        card = software_licenses_policy_card(row)
        return {'record': row, 'policy': card}

    def create_from_form(self, payload: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        field_errors = software_licenses_run_field_checks(payload)
        if field_errors:
            return None, field_errors
        return engine.create(payload)

    def update_from_form(self, record_id: str, payload: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        current = engine.get(record_id)
        if current is None:
            return None, ['missing record']
        merged = deepcopy(current)
        merged.update(payload)
        field_errors = software_licenses_run_field_checks(merged)
        if field_errors:
            return None, field_errors
        row, errors = engine.update(record_id, payload)
        if row:
            row['_diff'] = software_licenses_diff(current, row)
        return row, errors

    def move_status(self, record_id: str, new_status: str) -> tuple[dict[str, Any] | None, list[str]]:
        current = engine.get(record_id)
        if current is None:
            return None, ['missing record']
        errors = software_licenses_gate_transition(str(current.get('status') or ''), new_status)
        if errors:
            return None, errors
        return engine.transition(record_id, new_status)

    def export_maps(self) -> list[dict[str, str]]:
        return [software_licenses_export_map(row) for row in engine.list_records()]

    def seed_if_empty(self, count: int = 10) -> int:
        return engine.seed_demo(count)


service = SoftwareLicensesService()


def software_licenses_safe_payload(form: dict[str, Any]) -> dict[str, Any]:
    allowed = {name for name in ['product_name', 'publisher', 'seats', 'renew_on', 'status']}
    clean = {}
    for name, value in form.items():
        if name in allowed or name in {'id', 'status'}:
            clean[name] = value
    return clean


def software_licenses_can_delete(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    if status == 'active':
        return True
    return int(row.get('health_score') or 0) < 20


def software_licenses_next_statuses(current: str) -> list[str]:
    if current not in ['active', 'unused', 'expiring', 'expired']:
        return list(['active', 'unused', 'expiring', 'expired'])
    index = ['active', 'unused', 'expiring', 'expired'].index(current)
    options = [current]
    if index + 1 < len(['active', 'unused', 'expiring', 'expired']):
        options.append(['active', 'unused', 'expiring', 'expired'][index + 1])
    if index > 0:
        options.append(['active', 'unused', 'expiring', 'expired'][index - 1])
    unique = []
    for item in options:
        if item not in unique:
            unique.append(item)
    return unique


def software_licenses_operator_actions(row: dict[str, Any]) -> list[dict[str, str]]:
    actions = [{'code': 'edit', 'label': 'Edit record'}]
    for status in software_licenses_next_statuses(str(row.get('status') or '')):
        actions.append({'code': 'status:' + status, 'label': 'Move to ' + status})
    if software_licenses_can_delete(row):
        actions.append({'code': 'delete', 'label': 'Remove record'})
    return actions


def software_licenses_toast(action: str, ok: bool) -> str:
    if ok:
        return f'Software Licenses {action} completed.'
    return f'Software Licenses {action} was blocked by policy.'


def software_licenses_dashboard_chip(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        'key': 'software_licenses',
        'title': 'Software Licenses',
        'count': len(rows),
        'hot': len([row for row in rows if int(row.get('health_score') or 0) < 45]),
    }

def software_licenses_form_help_product_name() -> str:
    return 'Enter Product Name for Software Licenses. Local validation runs on save.'


def software_licenses_form_help_publisher() -> str:
    return 'Enter Publisher for Software Licenses. Local validation runs on save.'


def software_licenses_form_help_seats() -> str:
    return 'Enter Seats for Software Licenses. Local validation runs on save.'


def software_licenses_form_help_renew_on() -> str:
    return 'Enter Renew On for Software Licenses. Local validation runs on save.'


def software_licenses_form_help_status() -> str:
    return 'Enter Status for Software Licenses. Local validation runs on save.'


FORM_HELP_SOFTWARE_LICENSES = {
    'product_name': software_licenses_form_help_product_name(),
    'publisher': software_licenses_form_help_publisher(),
    'seats': software_licenses_form_help_seats(),
    'renew_on': software_licenses_form_help_renew_on(),
    'status': software_licenses_form_help_status(),
}


def software_licenses_form_help() -> dict[str, str]:
    return dict(FORM_HELP_SOFTWARE_LICENSES)

