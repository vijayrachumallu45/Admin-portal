"""Policy engine for HR Employees.

Employment records, cost centers, and work patterns.
Operators use these guards before a write is allowed to settle.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

DOMAIN_KEY = 'employees'
DOMAIN_TITLE = 'HR Employees'
ACCENT = '#c084fc'
STATUSES = ['active', 'leave', 'terminated']
SOFT_HOLD_STATUSES = ['leave', 'terminated']


def _as_int(value: Any, default: int = 0) -> int:
    try:
        if value in (None, ''):
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def employees_policy_version() -> str:
    return 'employees.policy.4'


def employees_is_terminal(status: str) -> bool:
    return status == 'terminated'


def employees_requires_dual_control(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    if status in SOFT_HOLD_STATUSES:
        return True
    score = _as_int(row.get('health_score'))
    return score < 35


class EmployeesPolicy:
    """Named checks that finance, people, and platform leads can quote."""

    def __init__(self) -> None:
        self.domain = 'employees'
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
            self.violations.append('HR Employees: status is missing.')
            return
        if status not in STATUSES:
            self.violations.append('HR Employees: status is outside the published ladder.')

    def check_identity(self, row: dict[str, Any]) -> None:
        record_id = str(row.get('id') or '')
        if record_id and ' ' in record_id:
            self.violations.append('HR Employees: record id cannot contain spaces.')

    def check_freshness(self, row: dict[str, Any]) -> None:
        stamp = str(row.get('updated_at') or '')
        if not stamp:
            return
        try:
            parsed = datetime.fromisoformat(stamp.replace('Z', ''))
        except ValueError:
            self.violations.append('HR Employees: updated_at is not parseable.')
            return
        age = (datetime.utcnow() - parsed).days
        if age > 800:
            self.violations.append('HR Employees: record is older than the archive window.')

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
                self.violations.append('HR Employees: ' + name + ' is out of bounds.')

    def check_text_hygiene(self, row: dict[str, Any]) -> None:
        for name, value in row.items():
            if not isinstance(value, str):
                continue
            if '\x00' in value:
                self.violations.append('HR Employees: ' + name + ' contains a null byte.')
            if value != value.strip() and name not in ('comment',):
                self.violations.append('HR Employees: ' + name + ' has surrounding whitespace.')

    def check_lifecycle(self, row: dict[str, Any]) -> None:
        status = str(row.get('status') or '')
        if status == 'terminated' and _as_int(row.get('health_score')) > 90:
            self.violations.append('HR Employees: terminal status with a high health score needs a note.')

    def allow_write(self, row: dict[str, Any]) -> bool:
        return not self.collect(row)


policy = EmployeesPolicy()


def employees_gate_create(payload: dict[str, Any]) -> list[str]:
    return policy.collect(payload)


def employees_gate_transition(current: str, nxt: str) -> list[str]:
    errors: list[str] = []
    if nxt not in STATUSES:
        errors.append('HR Employees cannot move to an unknown status.')
    if current == 'terminated' and nxt != current:
        if nxt not in STATUSES[:1]:
            errors.append('HR Employees is sealed; only a reopen to the first status is modeled.')
    return errors


def employees_risk_band(row: dict[str, Any]) -> str:
    score = _as_int(row.get('health_score'))
    if score >= 80:
        return 'calm'
    if score >= 55:
        return 'watch'
    if score >= 30:
        return 'elevated'
    return 'critical'


def employees_owner_hint(row: dict[str, Any]) -> str:
    for candidate in ('owner', 'assignee', 'steward', 'manager', 'legal_owner', 'processor', 'host_name', 'sponsor'):
        value = str(row.get(candidate) or '').strip()
        if value:
            return value
    return 'unassigned-employees'


def employees_sla_hours(row: dict[str, Any]) -> int:
    band = employees_risk_band(row)
    mapping = {'calm': 72, 'watch': 36, 'elevated': 12, 'critical': 4}
    return mapping[band]


def employees_escalation_copy(row: dict[str, Any]) -> str:
    band = employees_risk_band(row)
    owner = employees_owner_hint(row)
    hours = employees_sla_hours(row)
    return DOMAIN_TITLE + ' ' + band + ' item assigned to ' + owner + ' must move within ' + str(hours) + ' hours.'


PLAYBOOK_EMPLOYEES = [
    {'step': 1, 'title': 'Triage', 'domain': 'employees', 'hint': 'Triage for HR Employees before the shift ends.'},
    {'step': 2, 'title': 'Confirm identifiers', 'domain': 'employees', 'hint': 'Confirm identifiers for HR Employees before the shift ends.'},
    {'step': 3, 'title': 'Check policy exceptions', 'domain': 'employees', 'hint': 'Check policy exceptions for HR Employees before the shift ends.'},
    {'step': 4, 'title': 'Notify the owner', 'domain': 'employees', 'hint': 'Notify the owner for HR Employees before the shift ends.'},
    {'step': 5, 'title': 'Capture evidence', 'domain': 'employees', 'hint': 'Capture evidence for HR Employees before the shift ends.'},
    {'step': 6, 'title': 'Propose a next status', 'domain': 'employees', 'hint': 'Propose a next status for HR Employees before the shift ends.'},
    {'step': 7, 'title': 'Record the decision', 'domain': 'employees', 'hint': 'Record the decision for HR Employees before the shift ends.'},
    {'step': 8, 'title': 'Close the loop with finance', 'domain': 'employees', 'hint': 'Close the loop with finance for HR Employees before the shift ends.'},
    {'step': 9, 'title': 'File the audit crumb', 'domain': 'employees', 'hint': 'File the audit crumb for HR Employees before the shift ends.'},
    {'step': 10, 'title': 'Schedule the next review', 'domain': 'employees', 'hint': 'Schedule the next review for HR Employees before the shift ends.'},
]


def employees_playbook() -> list[dict[str, Any]]:
    return list(PLAYBOOK_EMPLOYEES)


def employees_exception_needed(row: dict[str, Any]) -> bool:
    return employees_risk_band(row) in ('elevated', 'critical')


def employees_freeze_window(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    return status in ['leave', 'terminated'] and date.today().weekday() >= 5


def employees_summary_line(row: dict[str, Any]) -> str:
    ident = str(row.get('id') or 'new')
    status = str(row.get('status') or 'n/a')
    band = employees_risk_band(row)
    return DOMAIN_TITLE + ' ' + ident + ' is ' + status + ' (' + band + ').'

def employees_check_employee_no(value: Any) -> list[str]:
    """Field policy for Employee No inside HR Employees."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Employee No is required on HR Employees.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Employee No is zero; confirm the HR Employees case.')
        if number > 9_000_000_000:
            notes.append('Employee No exceeds the HR Employees ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Employee No must be YYYY-MM-DD for HR Employees.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Employee No is longer than the HR Employees ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Employee No placeholder values are not allowed on HR Employees.')
    return notes


def employees_normalize_employee_no(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def employees_describe_employee_no() -> str:
    required = 'required' if True else 'optional'
    return 'Employee No is a ' + required + ' str field on HR Employees (employees).'


def employees_check_full_name(value: Any) -> list[str]:
    """Field policy for Full Name inside HR Employees."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Full Name is required on HR Employees.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Full Name is zero; confirm the HR Employees case.')
        if number > 9_000_000_000:
            notes.append('Full Name exceeds the HR Employees ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Full Name must be YYYY-MM-DD for HR Employees.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Full Name is longer than the HR Employees ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Full Name placeholder values are not allowed on HR Employees.')
    return notes


def employees_normalize_full_name(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def employees_describe_full_name() -> str:
    required = 'required' if True else 'optional'
    return 'Full Name is a ' + required + ' str field on HR Employees (employees).'


def employees_check_cost_center(value: Any) -> list[str]:
    """Field policy for Cost Center inside HR Employees."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Cost Center is required on HR Employees.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Cost Center is zero; confirm the HR Employees case.')
        if number > 9_000_000_000:
            notes.append('Cost Center exceeds the HR Employees ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Cost Center must be YYYY-MM-DD for HR Employees.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Cost Center is longer than the HR Employees ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Cost Center placeholder values are not allowed on HR Employees.')
    return notes


def employees_normalize_cost_center(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def employees_describe_cost_center() -> str:
    required = 'required' if True else 'optional'
    return 'Cost Center is a ' + required + ' str field on HR Employees (employees).'


def employees_check_hire_on(value: Any) -> list[str]:
    """Field policy for Hire On inside HR Employees."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Hire On is required on HR Employees.')
        return notes
    if 'date' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Hire On is zero; confirm the HR Employees case.')
        if number > 9_000_000_000:
            notes.append('Hire On exceeds the HR Employees ceiling.')
        return notes
    if 'date' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Hire On must be YYYY-MM-DD for HR Employees.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Hire On is longer than the HR Employees ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Hire On placeholder values are not allowed on HR Employees.')
    return notes


def employees_normalize_hire_on(value: Any) -> Any:
    if 'date' == 'int':
        return _as_int(value)
    if 'date' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def employees_describe_hire_on() -> str:
    required = 'required' if True else 'optional'
    return 'Hire On is a ' + required + ' date field on HR Employees (employees).'


def employees_check_fte_bps(value: Any) -> list[str]:
    """Field policy for Fte Bps inside HR Employees."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Fte Bps is required on HR Employees.')
        return notes
    if 'int' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Fte Bps is zero; confirm the HR Employees case.')
        if number > 9_000_000_000:
            notes.append('Fte Bps exceeds the HR Employees ceiling.')
        return notes
    if 'int' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Fte Bps must be YYYY-MM-DD for HR Employees.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Fte Bps is longer than the HR Employees ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Fte Bps placeholder values are not allowed on HR Employees.')
    return notes


def employees_normalize_fte_bps(value: Any) -> Any:
    if 'int' == 'int':
        return _as_int(value)
    if 'int' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def employees_describe_fte_bps() -> str:
    required = 'required' if True else 'optional'
    return 'Fte Bps is a ' + required + ' int field on HR Employees (employees).'


def employees_check_status(value: Any) -> list[str]:
    """Field policy for Status inside HR Employees."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Status is required on HR Employees.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Status is zero; confirm the HR Employees case.')
        if number > 9_000_000_000:
            notes.append('Status exceeds the HR Employees ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Status must be YYYY-MM-DD for HR Employees.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Status is longer than the HR Employees ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Status placeholder values are not allowed on HR Employees.')
    return notes


def employees_normalize_status(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def employees_describe_status() -> str:
    required = 'required' if True else 'optional'
    return 'Status is a ' + required + ' str field on HR Employees (employees).'


FIELD_CHECKS_EMPLOYEES = {
    'employee_no': employees_check_employee_no,
    'full_name': employees_check_full_name,
    'cost_center': employees_check_cost_center,
    'hire_on': employees_check_hire_on,
    'fte_bps': employees_check_fte_bps,
    'status': employees_check_status,
}


def employees_run_field_checks(row: dict[str, Any]) -> list[str]:
    found: list[str] = []
    for name, checker in FIELD_CHECKS_EMPLOYEES.items():
        found.extend(checker(row.get(name)))
    return found


def employees_policy_card(row: dict[str, Any]) -> dict[str, Any]:
    return {
        'domain': DOMAIN_KEY,
        'title': DOMAIN_TITLE,
        'band': employees_risk_band(row),
        'owner': employees_owner_hint(row),
        'sla_hours': employees_sla_hours(row),
        'exceptions': employees_exception_needed(row),
        'freeze': employees_freeze_window(row),
        'violations': policy.collect(row) + employees_run_field_checks(row),
        'summary': employees_summary_line(row),
    }

