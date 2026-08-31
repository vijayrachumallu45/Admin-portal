"""Application service for Training Catalog writes and operator actions."""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.domains.training_courses.engine import engine
from app.domains.training_courses.policies import training_courses_gate_transition, training_courses_policy_card, training_courses_run_field_checks
from app.domains.training_courses.queries import training_courses_diff, training_courses_export_map
from app.domains.training_courses.reports import build_training_courses_reporter


class TrainingCoursesService:
    """Coordinates validation, policy, persistence, and briefings for Training Catalog."""

    def list_view(self, filters: dict[str, Any] | None = None) -> dict[str, Any]:
        rows = engine.list_records(filters)
        reporter = build_training_courses_reporter(rows)
        return {
            'rows': rows,
            'kpis': engine.kpi_pack(),
            'pack': reporter.pack(),
        }

    def detail_view(self, record_id: str) -> dict[str, Any] | None:
        row = engine.get(record_id)
        if row is None:
            return None
        card = training_courses_policy_card(row)
        return {'record': row, 'policy': card}

    def create_from_form(self, payload: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        field_errors = training_courses_run_field_checks(payload)
        if field_errors:
            return None, field_errors
        return engine.create(payload)

    def update_from_form(self, record_id: str, payload: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        current = engine.get(record_id)
        if current is None:
            return None, ['missing record']
        merged = deepcopy(current)
        merged.update(payload)
        field_errors = training_courses_run_field_checks(merged)
        if field_errors:
            return None, field_errors
        row, errors = engine.update(record_id, payload)
        if row:
            row['_diff'] = training_courses_diff(current, row)
        return row, errors

    def move_status(self, record_id: str, new_status: str) -> tuple[dict[str, Any] | None, list[str]]:
        current = engine.get(record_id)
        if current is None:
            return None, ['missing record']
        errors = training_courses_gate_transition(str(current.get('status') or ''), new_status)
        if errors:
            return None, errors
        return engine.transition(record_id, new_status)

    def export_maps(self) -> list[dict[str, str]]:
        return [training_courses_export_map(row) for row in engine.list_records()]

    def seed_if_empty(self, count: int = 10) -> int:
        return engine.seed_demo(count)


service = TrainingCoursesService()


def training_courses_safe_payload(form: dict[str, Any]) -> dict[str, Any]:
    allowed = {name for name in ['course_code', 'title', 'hours', 'audience', 'status']}
    clean = {}
    for name, value in form.items():
        if name in allowed or name in {'id', 'status'}:
            clean[name] = value
    return clean


def training_courses_can_delete(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    if status == 'draft':
        return True
    return int(row.get('health_score') or 0) < 20


def training_courses_next_statuses(current: str) -> list[str]:
    if current not in ['draft', 'required', 'optional', 'retired']:
        return list(['draft', 'required', 'optional', 'retired'])
    index = ['draft', 'required', 'optional', 'retired'].index(current)
    options = [current]
    if index + 1 < len(['draft', 'required', 'optional', 'retired']):
        options.append(['draft', 'required', 'optional', 'retired'][index + 1])
    if index > 0:
        options.append(['draft', 'required', 'optional', 'retired'][index - 1])
    unique = []
    for item in options:
        if item not in unique:
            unique.append(item)
    return unique


def training_courses_operator_actions(row: dict[str, Any]) -> list[dict[str, str]]:
    actions = [{'code': 'edit', 'label': 'Edit record'}]
    for status in training_courses_next_statuses(str(row.get('status') or '')):
        actions.append({'code': 'status:' + status, 'label': 'Move to ' + status})
    if training_courses_can_delete(row):
        actions.append({'code': 'delete', 'label': 'Remove record'})
    return actions


def training_courses_toast(action: str, ok: bool) -> str:
    if ok:
        return f'Training Catalog {action} completed.'
    return f'Training Catalog {action} was blocked by policy.'


def training_courses_dashboard_chip(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        'key': 'training_courses',
        'title': 'Training Catalog',
        'count': len(rows),
        'hot': len([row for row in rows if int(row.get('health_score') or 0) < 45]),
    }

def training_courses_form_help_course_code() -> str:
    return 'Enter Course Code for Training Catalog. Local validation runs on save.'


def training_courses_form_help_title() -> str:
    return 'Enter Title for Training Catalog. Local validation runs on save.'


def training_courses_form_help_hours() -> str:
    return 'Enter Hours for Training Catalog. Local validation runs on save.'


def training_courses_form_help_audience() -> str:
    return 'Enter Audience for Training Catalog. Local validation runs on save.'


def training_courses_form_help_status() -> str:
    return 'Enter Status for Training Catalog. Local validation runs on save.'


FORM_HELP_TRAINING_COURSES = {
    'course_code': training_courses_form_help_course_code(),
    'title': training_courses_form_help_title(),
    'hours': training_courses_form_help_hours(),
    'audience': training_courses_form_help_audience(),
    'status': training_courses_form_help_status(),
}


def training_courses_form_help() -> dict[str, str]:
    return dict(FORM_HELP_TRAINING_COURSES)

