"""Policy engine for Training Catalog.

Required learning paths and completion windows.
Operators use these guards before a write is allowed to settle.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

DOMAIN_KEY = 'training_courses'
DOMAIN_TITLE = 'Training Catalog'
ACCENT = '#f0abfc'
STATUSES = ['draft', 'required', 'optional', 'retired']
SOFT_HOLD_STATUSES = ['optional', 'retired']


def _as_int(value: Any, default: int = 0) -> int:
    try:
        if value in (None, ''):
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def training_courses_policy_version() -> str:
    return 'training_courses.policy.4'


def training_courses_is_terminal(status: str) -> bool:
    return status == 'retired'


def training_courses_requires_dual_control(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    if status in SOFT_HOLD_STATUSES:
        return True
    score = _as_int(row.get('health_score'))
    return score < 35


class TrainingCoursesPolicy:
    """Named checks that finance, people, and platform leads can quote."""

    def __init__(self) -> None:
        self.domain = 'training_courses'
        self.violations: list[str] = []

    def reset(self) -> None:
        self.violations = []

    def collect(self, row: dict[str, Any]) -> list[str]:
        self.reset()
        self.check_status(row)
        self.check_identity(row)
        self.check_freshness(row)
        self.check_numeric_bounds(row)
        self.check_text_hygiene(row)
        self.check_lifecycle(row)
        return list(self.violations)

    def check_status(self, row: dict[str, Any]) -> None:
        status = str(row.get('status') or '')
        if not status:
            self.violations.append('Training Catalog: status is missing.')
            return
        if status not in STATUSES:
            self.violations.append('Training Catalog: status is outside the published ladder.')

    def check_identity(self, row: dict[str, Any]) -> None:
        record_id = str(row.get('id') or '')
        if record_id and ' ' in record_id:
            self.violations.append('Training Catalog: record id cannot contain spaces.')

    def check_freshness(self, row: dict[str, Any]) -> None:
        stamp = str(row.get('updated_at') or '')
        if not stamp:
            return
        try:
            parsed = datetime.fromisoformat(stamp.replace('Z', ''))
        except ValueError:
            self.violations.append('Training Catalog: updated_at is not parseable.')
            return
        age = (datetime.utcnow() - parsed).days
        if age > 800:
            self.violations.append('Training Catalog: record is older than the archive window.')

    def check_numeric_bounds(self, row: dict[str, Any]) -> None:
        for name, value in row.items():
            if not name.endswith('_cents') and name not in (
                'health_score',
                'seats',
                'minutes',
                'days',
                'percent',
                'score',
                'cap',
                'headcount',
            ):
                continue
            number = _as_int(value, default=-1)
            if number < 0:
                self.violations.append('Training Catalog: ' + name + ' is out of bounds.')

    def check_text_hygiene(self, row: dict[str, Any]) -> None:
        for name, value in row.items():
            if not isinstance(value, str):
                continue
            if '\x00' in value:
                self.violations.append('Training Catalog: ' + name + ' contains a null byte.')
            if value != value.strip() and name not in ('comment',):
                self.violations.append('Training Catalog: ' + name + ' has surrounding whitespace.')

    def check_lifecycle(self, row: dict[str, Any]) -> None:
        status = str(row.get('status') or '')
        if status == 'retired' and _as_int(row.get('health_score')) > 90:
            self.violations.append('Training Catalog: terminal status with a high health score needs a note.')

    def allow_write(self, row: dict[str, Any]) -> bool:
        return not self.collect(row)


policy = TrainingCoursesPolicy()


def training_courses_gate_create(payload: dict[str, Any]) -> list[str]:
    return policy.collect(payload)


def training_courses_gate_transition(current: str, nxt: str) -> list[str]:
    errors: list[str] = []
    if nxt not in STATUSES:
        errors.append('Training Catalog cannot move to an unknown status.')
    if current == 'retired' and nxt != current:
        if nxt not in STATUSES[:1]:
            errors.append('Training Catalog is sealed; only a reopen to the first status is modeled.')
    return errors


def training_courses_risk_band(row: dict[str, Any]) -> str:
    score = _as_int(row.get('health_score'))
    if score >= 80:
        return 'calm'
    if score >= 55:
        return 'watch'
    if score >= 30:
        return 'elevated'
    return 'critical'


def training_courses_owner_hint(row: dict[str, Any]) -> str:
    for candidate in ('owner', 'assignee', 'steward', 'manager', 'legal_owner', 'processor', 'host_name', 'sponsor'):
        value = str(row.get(candidate) or '').strip()
        if value:
            return value
    return 'unassigned-training_courses'


def training_courses_sla_hours(row: dict[str, Any]) -> int:
    band = training_courses_risk_band(row)
    mapping = {'calm': 72, 'watch': 36, 'elevated': 12, 'critical': 4}
    return mapping[band]


def training_courses_escalation_copy(row: dict[str, Any]) -> str:
    band = training_courses_risk_band(row)
    owner = training_courses_owner_hint(row)
    hours = training_courses_sla_hours(row)
    return DOMAIN_TITLE + ' ' + band + ' item assigned to ' + owner + ' must move within ' + str(hours) + ' hours.'


PLAYBOOK_TRAINING_COURSES = [
    {'step': 1, 'title': 'Triage', 'domain': 'training_courses', 'hint': 'Triage for Training Catalog before the shift ends.'},
    {'step': 2, 'title': 'Confirm identifiers', 'domain': 'training_courses', 'hint': 'Confirm identifiers for Training Catalog before the shift ends.'},
    {'step': 3, 'title': 'Check policy exceptions', 'domain': 'training_courses', 'hint': 'Check policy exceptions for Training Catalog before the shift ends.'},
    {'step': 4, 'title': 'Notify the owner', 'domain': 'training_courses', 'hint': 'Notify the owner for Training Catalog before the shift ends.'},
    {'step': 5, 'title': 'Capture evidence', 'domain': 'training_courses', 'hint': 'Capture evidence for Training Catalog before the shift ends.'},
    {'step': 6, 'title': 'Propose a next status', 'domain': 'training_courses', 'hint': 'Propose a next status for Training Catalog before the shift ends.'},
    {'step': 7, 'title': 'Record the decision', 'domain': 'training_courses', 'hint': 'Record the decision for Training Catalog before the shift ends.'},
    {'step': 8, 'title': 'Close the loop with finance', 'domain': 'training_courses', 'hint': 'Close the loop with finance for Training Catalog before the shift ends.'},
    {'step': 9, 'title': 'File the audit crumb', 'domain': 'training_courses', 'hint': 'File the audit crumb for Training Catalog before the shift ends.'},
    {'step': 10, 'title': 'Schedule the next review', 'domain': 'training_courses', 'hint': 'Schedule the next review for Training Catalog before the shift ends.'},
]


def training_courses_playbook() -> list[dict[str, Any]]:
    return list(PLAYBOOK_TRAINING_COURSES)


def training_courses_exception_needed(row: dict[str, Any]) -> bool:
    return training_courses_risk_band(row) in ('elevated', 'critical')


def training_courses_freeze_window(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    return status in ['optional', 'retired'] and date.today().weekday() >= 5


def training_courses_summary_line(row: dict[str, Any]) -> str:
    ident = str(row.get('id') or 'new')
    status = str(row.get('status') or 'n/a')
    band = training_courses_risk_band(row)
    return DOMAIN_TITLE + ' ' + ident + ' is ' + status + ' (' + band + ').'

def training_courses_check_course_code(value: Any) -> list[str]:
    """Field policy for Course Code inside Training Catalog."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Course Code is required on Training Catalog.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Course Code is zero; confirm the Training Catalog case.')
        if number > 9_000_000_000:
            notes.append('Course Code exceeds the Training Catalog ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Course Code must be YYYY-MM-DD for Training Catalog.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Course Code is longer than the Training Catalog ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Course Code placeholder values are not allowed on Training Catalog.')
    return notes


def training_courses_normalize_course_code(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def training_courses_describe_course_code() -> str:
    required = 'required' if True else 'optional'
    return 'Course Code is a ' + required + ' str field on Training Catalog (training_courses).'


def training_courses_check_title(value: Any) -> list[str]:
    """Field policy for Title inside Training Catalog."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Title is required on Training Catalog.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Title is zero; confirm the Training Catalog case.')
        if number > 9_000_000_000:
            notes.append('Title exceeds the Training Catalog ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Title must be YYYY-MM-DD for Training Catalog.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Title is longer than the Training Catalog ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Title placeholder values are not allowed on Training Catalog.')
    return notes


def training_courses_normalize_title(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def training_courses_describe_title() -> str:
    required = 'required' if True else 'optional'
    return 'Title is a ' + required + ' str field on Training Catalog (training_courses).'


def training_courses_check_hours(value: Any) -> list[str]:
    """Field policy for Hours inside Training Catalog."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Hours is required on Training Catalog.')
        return notes
    if 'int' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Hours is zero; confirm the Training Catalog case.')
        if number > 9_000_000_000:
            notes.append('Hours exceeds the Training Catalog ceiling.')
        return notes
    if 'int' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Hours must be YYYY-MM-DD for Training Catalog.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Hours is longer than the Training Catalog ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Hours placeholder values are not allowed on Training Catalog.')
    return notes


def training_courses_normalize_hours(value: Any) -> Any:
    if 'int' == 'int':
        return _as_int(value)
    if 'int' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def training_courses_describe_hours() -> str:
    required = 'required' if True else 'optional'
    return 'Hours is a ' + required + ' int field on Training Catalog (training_courses).'


def training_courses_check_audience(value: Any) -> list[str]:
    """Field policy for Audience inside Training Catalog."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Audience is required on Training Catalog.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Audience is zero; confirm the Training Catalog case.')
        if number > 9_000_000_000:
            notes.append('Audience exceeds the Training Catalog ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Audience must be YYYY-MM-DD for Training Catalog.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Audience is longer than the Training Catalog ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Audience placeholder values are not allowed on Training Catalog.')
    return notes


def training_courses_normalize_audience(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def training_courses_describe_audience() -> str:
    required = 'required' if True else 'optional'
    return 'Audience is a ' + required + ' str field on Training Catalog (training_courses).'


def training_courses_check_status(value: Any) -> list[str]:
    """Field policy for Status inside Training Catalog."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Status is required on Training Catalog.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Status is zero; confirm the Training Catalog case.')
        if number > 9_000_000_000:
            notes.append('Status exceeds the Training Catalog ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Status must be YYYY-MM-DD for Training Catalog.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Status is longer than the Training Catalog ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Status placeholder values are not allowed on Training Catalog.')
    return notes


def training_courses_normalize_status(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def training_courses_describe_status() -> str:
    required = 'required' if True else 'optional'
    return 'Status is a ' + required + ' str field on Training Catalog (training_courses).'


FIELD_CHECKS_TRAINING_COURSES = {
    'course_code': training_courses_check_course_code,
    'title': training_courses_check_title,
    'hours': training_courses_check_hours,
    'audience': training_courses_check_audience,
    'status': training_courses_check_status,
}


def training_courses_run_field_checks(row: dict[str, Any]) -> list[str]:
    found: list[str] = []
    for name, checker in FIELD_CHECKS_TRAINING_COURSES.items():
        found.extend(checker(row.get(name)))
    return found


def training_courses_policy_card(row: dict[str, Any]) -> dict[str, Any]:
    return {
        'domain': DOMAIN_KEY,
        'title': DOMAIN_TITLE,
        'band': training_courses_risk_band(row),
        'owner': training_courses_owner_hint(row),
        'sla_hours': training_courses_sla_hours(row),
        'exceptions': training_courses_exception_needed(row),
        'freeze': training_courses_freeze_window(row),
        'violations': policy.collect(row) + training_courses_run_field_checks(row),
        'summary': training_courses_summary_line(row),
    }

