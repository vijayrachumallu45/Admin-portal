"""Policy engine for Delivery Projects.

Implementation workstreams with health and budget remaining.
Operators use these guards before a write is allowed to settle.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

DOMAIN_KEY = 'projects'
DOMAIN_TITLE = 'Delivery Projects'
ACCENT = '#86efac'
STATUSES = ['planning', 'active', 'blocked', 'done']
SOFT_HOLD_STATUSES = ['blocked', 'done']


def _as_int(value: Any, default: int = 0) -> int:
    try:
        if value in (None, ''):
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def projects_policy_version() -> str:
    return 'projects.policy.4'


def projects_is_terminal(status: str) -> bool:
    return status == 'done'


def projects_requires_dual_control(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    if status in SOFT_HOLD_STATUSES:
        return True
    score = _as_int(row.get('health_score'))
    return score < 35


class ProjectsPolicy:
    """Named checks that finance, people, and platform leads can quote."""

    def __init__(self) -> None:
        self.domain = 'projects'
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
            self.violations.append('Delivery Projects: status is missing.')
            return
        if status not in STATUSES:
            self.violations.append('Delivery Projects: status is outside the published ladder.')

    def check_identity(self, row: dict[str, Any]) -> None:
        record_id = str(row.get('id') or '')
        if record_id and ' ' in record_id:
            self.violations.append('Delivery Projects: record id cannot contain spaces.')

    def check_freshness(self, row: dict[str, Any]) -> None:
        stamp = str(row.get('updated_at') or '')
        if not stamp:
            return
        try:
            parsed = datetime.fromisoformat(stamp.replace('Z', ''))
        except ValueError:
            self.violations.append('Delivery Projects: updated_at is not parseable.')
            return
        age = (datetime.utcnow() - parsed).days
        if age > 800:
            self.violations.append('Delivery Projects: record is older than the archive window.')

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
                self.violations.append('Delivery Projects: ' + name + ' is out of bounds.')

    def check_text_hygiene(self, row: dict[str, Any]) -> None:
        for name, value in row.items():
            if not isinstance(value, str):
                continue
            if '\x00' in value:
                self.violations.append('Delivery Projects: ' + name + ' contains a null byte.')
            if value != value.strip() and name not in ('comment',):
                self.violations.append('Delivery Projects: ' + name + ' has surrounding whitespace.')

    def check_lifecycle(self, row: dict[str, Any]) -> None:
        status = str(row.get('status') or '')
        if status == 'done' and _as_int(row.get('health_score')) > 90:
            self.violations.append('Delivery Projects: terminal status with a high health score needs a note.')

    def allow_write(self, row: dict[str, Any]) -> bool:
        return not self.collect(row)


policy = ProjectsPolicy()


def projects_gate_create(payload: dict[str, Any]) -> list[str]:
    return policy.collect(payload)


def projects_gate_transition(current: str, nxt: str) -> list[str]:
    errors: list[str] = []
    if nxt not in STATUSES:
        errors.append('Delivery Projects cannot move to an unknown status.')
    if current == 'done' and nxt != current:
        if nxt not in STATUSES[:1]:
            errors.append('Delivery Projects is sealed; only a reopen to the first status is modeled.')
    return errors


def projects_risk_band(row: dict[str, Any]) -> str:
    score = _as_int(row.get('health_score'))
    if score >= 80:
        return 'calm'
    if score >= 55:
        return 'watch'
    if score >= 30:
        return 'elevated'
    return 'critical'


def projects_owner_hint(row: dict[str, Any]) -> str:
    for candidate in ('owner', 'assignee', 'steward', 'manager', 'legal_owner', 'processor', 'host_name', 'sponsor'):
        value = str(row.get(candidate) or '').strip()
        if value:
            return value
    return 'unassigned-projects'


def projects_sla_hours(row: dict[str, Any]) -> int:
    band = projects_risk_band(row)
    mapping = {'calm': 72, 'watch': 36, 'elevated': 12, 'critical': 4}
    return mapping[band]


def projects_escalation_copy(row: dict[str, Any]) -> str:
    band = projects_risk_band(row)
    owner = projects_owner_hint(row)
    hours = projects_sla_hours(row)
    return DOMAIN_TITLE + ' ' + band + ' item assigned to ' + owner + ' must move within ' + str(hours) + ' hours.'


PLAYBOOK_PROJECTS = [
    {'step': 1, 'title': 'Triage', 'domain': 'projects', 'hint': 'Triage for Delivery Projects before the shift ends.'},
    {'step': 2, 'title': 'Confirm identifiers', 'domain': 'projects', 'hint': 'Confirm identifiers for Delivery Projects before the shift ends.'},
    {'step': 3, 'title': 'Check policy exceptions', 'domain': 'projects', 'hint': 'Check policy exceptions for Delivery Projects before the shift ends.'},
    {'step': 4, 'title': 'Notify the owner', 'domain': 'projects', 'hint': 'Notify the owner for Delivery Projects before the shift ends.'},
    {'step': 5, 'title': 'Capture evidence', 'domain': 'projects', 'hint': 'Capture evidence for Delivery Projects before the shift ends.'},
    {'step': 6, 'title': 'Propose a next status', 'domain': 'projects', 'hint': 'Propose a next status for Delivery Projects before the shift ends.'},
    {'step': 7, 'title': 'Record the decision', 'domain': 'projects', 'hint': 'Record the decision for Delivery Projects before the shift ends.'},
    {'step': 8, 'title': 'Close the loop with finance', 'domain': 'projects', 'hint': 'Close the loop with finance for Delivery Projects before the shift ends.'},
    {'step': 9, 'title': 'File the audit crumb', 'domain': 'projects', 'hint': 'File the audit crumb for Delivery Projects before the shift ends.'},
    {'step': 10, 'title': 'Schedule the next review', 'domain': 'projects', 'hint': 'Schedule the next review for Delivery Projects before the shift ends.'},
]


def projects_playbook() -> list[dict[str, Any]]:
    return list(PLAYBOOK_PROJECTS)


def projects_exception_needed(row: dict[str, Any]) -> bool:
    return projects_risk_band(row) in ('elevated', 'critical')


def projects_freeze_window(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    return status in ['blocked', 'done'] and date.today().weekday() >= 5


def projects_summary_line(row: dict[str, Any]) -> str:
    ident = str(row.get('id') or 'new')
    status = str(row.get('status') or 'n/a')
    band = projects_risk_band(row)
    return DOMAIN_TITLE + ' ' + ident + ' is ' + status + ' (' + band + ').'

def projects_check_project_code(value: Any) -> list[str]:
    """Field policy for Project Code inside Delivery Projects."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Project Code is required on Delivery Projects.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Project Code is zero; confirm the Delivery Projects case.')
        if number > 9_000_000_000:
            notes.append('Project Code exceeds the Delivery Projects ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Project Code must be YYYY-MM-DD for Delivery Projects.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Project Code is longer than the Delivery Projects ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Project Code placeholder values are not allowed on Delivery Projects.')
    return notes


def projects_normalize_project_code(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def projects_describe_project_code() -> str:
    required = 'required' if True else 'optional'
    return 'Project Code is a ' + required + ' str field on Delivery Projects (projects).'


def projects_check_name(value: Any) -> list[str]:
    """Field policy for Name inside Delivery Projects."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Name is required on Delivery Projects.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Name is zero; confirm the Delivery Projects case.')
        if number > 9_000_000_000:
            notes.append('Name exceeds the Delivery Projects ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Name must be YYYY-MM-DD for Delivery Projects.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Name is longer than the Delivery Projects ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Name placeholder values are not allowed on Delivery Projects.')
    return notes


def projects_normalize_name(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def projects_describe_name() -> str:
    required = 'required' if True else 'optional'
    return 'Name is a ' + required + ' str field on Delivery Projects (projects).'


def projects_check_sponsor(value: Any) -> list[str]:
    """Field policy for Sponsor inside Delivery Projects."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Sponsor is required on Delivery Projects.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Sponsor is zero; confirm the Delivery Projects case.')
        if number > 9_000_000_000:
            notes.append('Sponsor exceeds the Delivery Projects ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Sponsor must be YYYY-MM-DD for Delivery Projects.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Sponsor is longer than the Delivery Projects ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Sponsor placeholder values are not allowed on Delivery Projects.')
    return notes


def projects_normalize_sponsor(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def projects_describe_sponsor() -> str:
    required = 'required' if True else 'optional'
    return 'Sponsor is a ' + required + ' str field on Delivery Projects (projects).'


def projects_check_budget_cents(value: Any) -> list[str]:
    """Field policy for Budget Cents inside Delivery Projects."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Budget Cents is required on Delivery Projects.')
        return notes
    if 'int' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Budget Cents is zero; confirm the Delivery Projects case.')
        if number > 9_000_000_000:
            notes.append('Budget Cents exceeds the Delivery Projects ceiling.')
        return notes
    if 'int' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Budget Cents must be YYYY-MM-DD for Delivery Projects.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Budget Cents is longer than the Delivery Projects ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Budget Cents placeholder values are not allowed on Delivery Projects.')
    return notes


def projects_normalize_budget_cents(value: Any) -> Any:
    if 'int' == 'int':
        return _as_int(value)
    if 'int' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def projects_describe_budget_cents() -> str:
    required = 'required' if True else 'optional'
    return 'Budget Cents is a ' + required + ' int field on Delivery Projects (projects).'


def projects_check_health(value: Any) -> list[str]:
    """Field policy for Health inside Delivery Projects."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Health is required on Delivery Projects.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Health is zero; confirm the Delivery Projects case.')
        if number > 9_000_000_000:
            notes.append('Health exceeds the Delivery Projects ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Health must be YYYY-MM-DD for Delivery Projects.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Health is longer than the Delivery Projects ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Health placeholder values are not allowed on Delivery Projects.')
    return notes


def projects_normalize_health(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def projects_describe_health() -> str:
    required = 'required' if True else 'optional'
    return 'Health is a ' + required + ' str field on Delivery Projects (projects).'


def projects_check_status(value: Any) -> list[str]:
    """Field policy for Status inside Delivery Projects."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Status is required on Delivery Projects.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Status is zero; confirm the Delivery Projects case.')
        if number > 9_000_000_000:
            notes.append('Status exceeds the Delivery Projects ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Status must be YYYY-MM-DD for Delivery Projects.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Status is longer than the Delivery Projects ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Status placeholder values are not allowed on Delivery Projects.')
    return notes


def projects_normalize_status(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def projects_describe_status() -> str:
    required = 'required' if True else 'optional'
    return 'Status is a ' + required + ' str field on Delivery Projects (projects).'


FIELD_CHECKS_PROJECTS = {
    'project_code': projects_check_project_code,
    'name': projects_check_name,
    'sponsor': projects_check_sponsor,
    'budget_cents': projects_check_budget_cents,
    'health': projects_check_health,
    'status': projects_check_status,
}


def projects_run_field_checks(row: dict[str, Any]) -> list[str]:
    found: list[str] = []
    for name, checker in FIELD_CHECKS_PROJECTS.items():
        found.extend(checker(row.get(name)))
    return found


def projects_policy_card(row: dict[str, Any]) -> dict[str, Any]:
    return {
        'domain': DOMAIN_KEY,
        'title': DOMAIN_TITLE,
        'band': projects_risk_band(row),
        'owner': projects_owner_hint(row),
        'sla_hours': projects_sla_hours(row),
        'exceptions': projects_exception_needed(row),
        'freeze': projects_freeze_window(row),
        'violations': policy.collect(row) + projects_run_field_checks(row),
        'summary': projects_summary_line(row),
    }

