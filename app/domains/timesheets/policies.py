"""Policy engine for Timesheets.

Billable and internal hours against projects and cost codes.
Operators use these guards before a write is allowed to settle.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

DOMAIN_KEY = 'timesheets'
DOMAIN_TITLE = 'Timesheets'
ACCENT = '#facc15'
STATUSES = ['draft', 'submitted', 'approved', 'locked']
SOFT_HOLD_STATUSES = ['approved', 'locked']


def _as_int(value: Any, default: int = 0) -> int:
    try:
        if value in (None, ''):
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def timesheets_policy_version() -> str:
    return 'timesheets.policy.4'


def timesheets_is_terminal(status: str) -> bool:
    return status == 'locked'


def timesheets_requires_dual_control(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    if status in SOFT_HOLD_STATUSES:
        return True
    score = _as_int(row.get('health_score'))
    return score < 35


class TimesheetsPolicy:
    """Named checks that finance, people, and platform leads can quote."""

    def __init__(self) -> None:
        self.domain = 'timesheets'
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
            self.violations.append('Timesheets: status is missing.')
            return
        if status not in STATUSES:
            self.violations.append('Timesheets: status is outside the published ladder.')

    def check_identity(self, row: dict[str, Any]) -> None:
        record_id = str(row.get('id') or '')
        if record_id and ' ' in record_id:
            self.violations.append('Timesheets: record id cannot contain spaces.')

    def check_freshness(self, row: dict[str, Any]) -> None:
        stamp = str(row.get('updated_at') or '')
        if not stamp:
            return
        try:
            parsed = datetime.fromisoformat(stamp.replace('Z', ''))
        except ValueError:
            self.violations.append('Timesheets: updated_at is not parseable.')
            return
        age = (datetime.utcnow() - parsed).days
        if age > 800:
            self.violations.append('Timesheets: record is older than the archive window.')

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
                self.violations.append('Timesheets: ' + name + ' is out of bounds.')

    def check_text_hygiene(self, row: dict[str, Any]) -> None:
        for name, value in row.items():
            if not isinstance(value, str):
                continue
            if '\x00' in value:
                self.violations.append('Timesheets: ' + name + ' contains a null byte.')
            if value != value.strip() and name not in ('comment',):
                self.violations.append('Timesheets: ' + name + ' has surrounding whitespace.')

    def check_lifecycle(self, row: dict[str, Any]) -> None:
        status = str(row.get('status') or '')
        if status == 'locked' and _as_int(row.get('health_score')) > 90:
            self.violations.append('Timesheets: terminal status with a high health score needs a note.')

    def allow_write(self, row: dict[str, Any]) -> bool:
        return not self.collect(row)


policy = TimesheetsPolicy()


def timesheets_gate_create(payload: dict[str, Any]) -> list[str]:
    return policy.collect(payload)


def timesheets_gate_transition(current: str, nxt: str) -> list[str]:
    errors: list[str] = []
    if nxt not in STATUSES:
        errors.append('Timesheets cannot move to an unknown status.')
    if current == 'locked' and nxt != current:
        if nxt not in STATUSES[:1]:
            errors.append('Timesheets is sealed; only a reopen to the first status is modeled.')
    return errors


def timesheets_risk_band(row: dict[str, Any]) -> str:
    score = _as_int(row.get('health_score'))
    if score >= 80:
        return 'calm'
    if score >= 55:
        return 'watch'
    if score >= 30:
        return 'elevated'
    return 'critical'


def timesheets_owner_hint(row: dict[str, Any]) -> str:
    for candidate in ('owner', 'assignee', 'steward', 'manager', 'legal_owner', 'processor', 'host_name', 'sponsor'):
        value = str(row.get(candidate) or '').strip()
        if value:
            return value
    return 'unassigned-timesheets'


def timesheets_sla_hours(row: dict[str, Any]) -> int:
    band = timesheets_risk_band(row)
    mapping = {'calm': 72, 'watch': 36, 'elevated': 12, 'critical': 4}
    return mapping[band]


def timesheets_escalation_copy(row: dict[str, Any]) -> str:
    band = timesheets_risk_band(row)
    owner = timesheets_owner_hint(row)
    hours = timesheets_sla_hours(row)
    return DOMAIN_TITLE + ' ' + band + ' item assigned to ' + owner + ' must move within ' + str(hours) + ' hours.'


PLAYBOOK_TIMESHEETS = [
    {'step': 1, 'title': 'Triage', 'domain': 'timesheets', 'hint': 'Triage for Timesheets before the shift ends.'},
    {'step': 2, 'title': 'Confirm identifiers', 'domain': 'timesheets', 'hint': 'Confirm identifiers for Timesheets before the shift ends.'},
    {'step': 3, 'title': 'Check policy exceptions', 'domain': 'timesheets', 'hint': 'Check policy exceptions for Timesheets before the shift ends.'},
    {'step': 4, 'title': 'Notify the owner', 'domain': 'timesheets', 'hint': 'Notify the owner for Timesheets before the shift ends.'},
    {'step': 5, 'title': 'Capture evidence', 'domain': 'timesheets', 'hint': 'Capture evidence for Timesheets before the shift ends.'},
    {'step': 6, 'title': 'Propose a next status', 'domain': 'timesheets', 'hint': 'Propose a next status for Timesheets before the shift ends.'},
    {'step': 7, 'title': 'Record the decision', 'domain': 'timesheets', 'hint': 'Record the decision for Timesheets before the shift ends.'},
    {'step': 8, 'title': 'Close the loop with finance', 'domain': 'timesheets', 'hint': 'Close the loop with finance for Timesheets before the shift ends.'},
    {'step': 9, 'title': 'File the audit crumb', 'domain': 'timesheets', 'hint': 'File the audit crumb for Timesheets before the shift ends.'},
    {'step': 10, 'title': 'Schedule the next review', 'domain': 'timesheets', 'hint': 'Schedule the next review for Timesheets before the shift ends.'},
]


def timesheets_playbook() -> list[dict[str, Any]]:
    return list(PLAYBOOK_TIMESHEETS)


def timesheets_exception_needed(row: dict[str, Any]) -> bool:
    return timesheets_risk_band(row) in ('elevated', 'critical')


def timesheets_freeze_window(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    return status in ['approved', 'locked'] and date.today().weekday() >= 5


def timesheets_summary_line(row: dict[str, Any]) -> str:
    ident = str(row.get('id') or 'new')
    status = str(row.get('status') or 'n/a')
    band = timesheets_risk_band(row)
    return DOMAIN_TITLE + ' ' + ident + ' is ' + status + ' (' + band + ').'

def timesheets_check_employee_no(value: Any) -> list[str]:
    """Field policy for Employee No inside Timesheets."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Employee No is required on Timesheets.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Employee No is zero; confirm the Timesheets case.')
        if number > 9_000_000_000:
            notes.append('Employee No exceeds the Timesheets ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Employee No must be YYYY-MM-DD for Timesheets.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Employee No is longer than the Timesheets ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Employee No placeholder values are not allowed on Timesheets.')
    return notes


def timesheets_normalize_employee_no(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def timesheets_describe_employee_no() -> str:
    required = 'required' if True else 'optional'
    return 'Employee No is a ' + required + ' str field on Timesheets (timesheets).'


def timesheets_check_week_start(value: Any) -> list[str]:
    """Field policy for Week Start inside Timesheets."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Week Start is required on Timesheets.')
        return notes
    if 'date' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Week Start is zero; confirm the Timesheets case.')
        if number > 9_000_000_000:
            notes.append('Week Start exceeds the Timesheets ceiling.')
        return notes
    if 'date' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Week Start must be YYYY-MM-DD for Timesheets.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Week Start is longer than the Timesheets ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Week Start placeholder values are not allowed on Timesheets.')
    return notes


def timesheets_normalize_week_start(value: Any) -> Any:
    if 'date' == 'int':
        return _as_int(value)
    if 'date' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def timesheets_describe_week_start() -> str:
    required = 'required' if True else 'optional'
    return 'Week Start is a ' + required + ' date field on Timesheets (timesheets).'


def timesheets_check_project_code(value: Any) -> list[str]:
    """Field policy for Project Code inside Timesheets."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Project Code is required on Timesheets.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Project Code is zero; confirm the Timesheets case.')
        if number > 9_000_000_000:
            notes.append('Project Code exceeds the Timesheets ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Project Code must be YYYY-MM-DD for Timesheets.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Project Code is longer than the Timesheets ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Project Code placeholder values are not allowed on Timesheets.')
    return notes


def timesheets_normalize_project_code(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def timesheets_describe_project_code() -> str:
    required = 'required' if True else 'optional'
    return 'Project Code is a ' + required + ' str field on Timesheets (timesheets).'


def timesheets_check_minutes(value: Any) -> list[str]:
    """Field policy for Minutes inside Timesheets."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Minutes is required on Timesheets.')
        return notes
    if 'int' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Minutes is zero; confirm the Timesheets case.')
        if number > 9_000_000_000:
            notes.append('Minutes exceeds the Timesheets ceiling.')
        return notes
    if 'int' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Minutes must be YYYY-MM-DD for Timesheets.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Minutes is longer than the Timesheets ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Minutes placeholder values are not allowed on Timesheets.')
    return notes


def timesheets_normalize_minutes(value: Any) -> Any:
    if 'int' == 'int':
        return _as_int(value)
    if 'int' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def timesheets_describe_minutes() -> str:
    required = 'required' if True else 'optional'
    return 'Minutes is a ' + required + ' int field on Timesheets (timesheets).'


def timesheets_check_billable(value: Any) -> list[str]:
    """Field policy for Billable inside Timesheets."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Billable is required on Timesheets.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Billable is zero; confirm the Timesheets case.')
        if number > 9_000_000_000:
            notes.append('Billable exceeds the Timesheets ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Billable must be YYYY-MM-DD for Timesheets.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Billable is longer than the Timesheets ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Billable placeholder values are not allowed on Timesheets.')
    return notes


def timesheets_normalize_billable(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def timesheets_describe_billable() -> str:
    required = 'required' if True else 'optional'
    return 'Billable is a ' + required + ' str field on Timesheets (timesheets).'


def timesheets_check_status(value: Any) -> list[str]:
    """Field policy for Status inside Timesheets."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Status is required on Timesheets.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Status is zero; confirm the Timesheets case.')
        if number > 9_000_000_000:
            notes.append('Status exceeds the Timesheets ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Status must be YYYY-MM-DD for Timesheets.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Status is longer than the Timesheets ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Status placeholder values are not allowed on Timesheets.')
    return notes


def timesheets_normalize_status(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def timesheets_describe_status() -> str:
    required = 'required' if True else 'optional'
    return 'Status is a ' + required + ' str field on Timesheets (timesheets).'


FIELD_CHECKS_TIMESHEETS = {
    'employee_no': timesheets_check_employee_no,
    'week_start': timesheets_check_week_start,
    'project_code': timesheets_check_project_code,
    'minutes': timesheets_check_minutes,
    'billable': timesheets_check_billable,
    'status': timesheets_check_status,
}


def timesheets_run_field_checks(row: dict[str, Any]) -> list[str]:
    found: list[str] = []
    for name, checker in FIELD_CHECKS_TIMESHEETS.items():
        found.extend(checker(row.get(name)))
    return found


def timesheets_policy_card(row: dict[str, Any]) -> dict[str, Any]:
    return {
        'domain': DOMAIN_KEY,
        'title': DOMAIN_TITLE,
        'band': timesheets_risk_band(row),
        'owner': timesheets_owner_hint(row),
        'sla_hours': timesheets_sla_hours(row),
        'exceptions': timesheets_exception_needed(row),
        'freeze': timesheets_freeze_window(row),
        'violations': policy.collect(row) + timesheets_run_field_checks(row),
        'summary': timesheets_summary_line(row),
    }

