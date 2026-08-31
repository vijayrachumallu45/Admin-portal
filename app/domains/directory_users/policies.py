"""Policy engine for People Directory.

Workforce identities mapped to tenants, managers, and access bands.
Operators use these guards before a write is allowed to settle.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

DOMAIN_KEY = 'directory_users'
DOMAIN_TITLE = 'People Directory'
ACCENT = '#7aa2ff'
STATUSES = ['invited', 'active', 'leave', 'offboarded']
SOFT_HOLD_STATUSES = ['leave', 'offboarded']


def _as_int(value: Any, default: int = 0) -> int:
    try:
        if value in (None, ''):
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def directory_users_policy_version() -> str:
    return 'directory_users.policy.4'


def directory_users_is_terminal(status: str) -> bool:
    return status == 'offboarded'


def directory_users_requires_dual_control(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    if status in SOFT_HOLD_STATUSES:
        return True
    score = _as_int(row.get('health_score'))
    return score < 35


class DirectoryUsersPolicy:
    """Named checks that finance, people, and platform leads can quote."""

    def __init__(self) -> None:
        self.domain = 'directory_users'
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
            self.violations.append('People Directory: status is missing.')
            return
        if status not in STATUSES:
            self.violations.append('People Directory: status is outside the published ladder.')

    def check_identity(self, row: dict[str, Any]) -> None:
        record_id = str(row.get('id') or '')
        if record_id and ' ' in record_id:
            self.violations.append('People Directory: record id cannot contain spaces.')

    def check_freshness(self, row: dict[str, Any]) -> None:
        stamp = str(row.get('updated_at') or '')
        if not stamp:
            return
        try:
            parsed = datetime.fromisoformat(stamp.replace('Z', ''))
        except ValueError:
            self.violations.append('People Directory: updated_at is not parseable.')
            return
        age = (datetime.utcnow() - parsed).days
        if age > 800:
            self.violations.append('People Directory: record is older than the archive window.')

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
                self.violations.append('People Directory: ' + name + ' is out of bounds.')

    def check_text_hygiene(self, row: dict[str, Any]) -> None:
        for name, value in row.items():
            if not isinstance(value, str):
                continue
            if '\x00' in value:
                self.violations.append('People Directory: ' + name + ' contains a null byte.')
            if value != value.strip() and name not in ('comment',):
                self.violations.append('People Directory: ' + name + ' has surrounding whitespace.')

    def check_lifecycle(self, row: dict[str, Any]) -> None:
        status = str(row.get('status') or '')
        if status == 'offboarded' and _as_int(row.get('health_score')) > 90:
            self.violations.append('People Directory: terminal status with a high health score needs a note.')

    def allow_write(self, row: dict[str, Any]) -> bool:
        return not self.collect(row)


policy = DirectoryUsersPolicy()


def directory_users_gate_create(payload: dict[str, Any]) -> list[str]:
    return policy.collect(payload)


def directory_users_gate_transition(current: str, nxt: str) -> list[str]:
    errors: list[str] = []
    if nxt not in STATUSES:
        errors.append('People Directory cannot move to an unknown status.')
    if current == 'offboarded' and nxt != current:
        if nxt not in STATUSES[:1]:
            errors.append('People Directory is sealed; only a reopen to the first status is modeled.')
    return errors


def directory_users_risk_band(row: dict[str, Any]) -> str:
    score = _as_int(row.get('health_score'))
    if score >= 80:
        return 'calm'
    if score >= 55:
        return 'watch'
    if score >= 30:
        return 'elevated'
    return 'critical'


def directory_users_owner_hint(row: dict[str, Any]) -> str:
    for candidate in ('owner', 'assignee', 'steward', 'manager', 'legal_owner', 'processor', 'host_name', 'sponsor'):
        value = str(row.get(candidate) or '').strip()
        if value:
            return value
    return 'unassigned-directory_users'


def directory_users_sla_hours(row: dict[str, Any]) -> int:
    band = directory_users_risk_band(row)
    mapping = {'calm': 72, 'watch': 36, 'elevated': 12, 'critical': 4}
    return mapping[band]


def directory_users_escalation_copy(row: dict[str, Any]) -> str:
    band = directory_users_risk_band(row)
    owner = directory_users_owner_hint(row)
    hours = directory_users_sla_hours(row)
    return DOMAIN_TITLE + ' ' + band + ' item assigned to ' + owner + ' must move within ' + str(hours) + ' hours.'


PLAYBOOK_DIRECTORY_USERS = [
    {'step': 1, 'title': 'Triage', 'domain': 'directory_users', 'hint': 'Triage for People Directory before the shift ends.'},
    {'step': 2, 'title': 'Confirm identifiers', 'domain': 'directory_users', 'hint': 'Confirm identifiers for People Directory before the shift ends.'},
    {'step': 3, 'title': 'Check policy exceptions', 'domain': 'directory_users', 'hint': 'Check policy exceptions for People Directory before the shift ends.'},
    {'step': 4, 'title': 'Notify the owner', 'domain': 'directory_users', 'hint': 'Notify the owner for People Directory before the shift ends.'},
    {'step': 5, 'title': 'Capture evidence', 'domain': 'directory_users', 'hint': 'Capture evidence for People Directory before the shift ends.'},
    {'step': 6, 'title': 'Propose a next status', 'domain': 'directory_users', 'hint': 'Propose a next status for People Directory before the shift ends.'},
    {'step': 7, 'title': 'Record the decision', 'domain': 'directory_users', 'hint': 'Record the decision for People Directory before the shift ends.'},
    {'step': 8, 'title': 'Close the loop with finance', 'domain': 'directory_users', 'hint': 'Close the loop with finance for People Directory before the shift ends.'},
    {'step': 9, 'title': 'File the audit crumb', 'domain': 'directory_users', 'hint': 'File the audit crumb for People Directory before the shift ends.'},
    {'step': 10, 'title': 'Schedule the next review', 'domain': 'directory_users', 'hint': 'Schedule the next review for People Directory before the shift ends.'},
]


def directory_users_playbook() -> list[dict[str, Any]]:
    return list(PLAYBOOK_DIRECTORY_USERS)


def directory_users_exception_needed(row: dict[str, Any]) -> bool:
    return directory_users_risk_band(row) in ('elevated', 'critical')


def directory_users_freeze_window(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    return status in ['leave', 'offboarded'] and date.today().weekday() >= 5


def directory_users_summary_line(row: dict[str, Any]) -> str:
    ident = str(row.get('id') or 'new')
    status = str(row.get('status') or 'n/a')
    band = directory_users_risk_band(row)
    return DOMAIN_TITLE + ' ' + ident + ' is ' + status + ' (' + band + ').'

def directory_users_check_email(value: Any) -> list[str]:
    """Field policy for Email inside People Directory."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Email is required on People Directory.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Email is zero; confirm the People Directory case.')
        if number > 9_000_000_000:
            notes.append('Email exceeds the People Directory ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Email must be YYYY-MM-DD for People Directory.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Email is longer than the People Directory ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Email placeholder values are not allowed on People Directory.')
    return notes


def directory_users_normalize_email(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def directory_users_describe_email() -> str:
    required = 'required' if True else 'optional'
    return 'Email is a ' + required + ' str field on People Directory (directory_users).'


def directory_users_check_full_name(value: Any) -> list[str]:
    """Field policy for Full Name inside People Directory."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Full Name is required on People Directory.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Full Name is zero; confirm the People Directory case.')
        if number > 9_000_000_000:
            notes.append('Full Name exceeds the People Directory ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Full Name must be YYYY-MM-DD for People Directory.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Full Name is longer than the People Directory ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Full Name placeholder values are not allowed on People Directory.')
    return notes


def directory_users_normalize_full_name(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def directory_users_describe_full_name() -> str:
    required = 'required' if True else 'optional'
    return 'Full Name is a ' + required + ' str field on People Directory (directory_users).'


def directory_users_check_job_title(value: Any) -> list[str]:
    """Field policy for Job Title inside People Directory."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Job Title is required on People Directory.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Job Title is zero; confirm the People Directory case.')
        if number > 9_000_000_000:
            notes.append('Job Title exceeds the People Directory ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Job Title must be YYYY-MM-DD for People Directory.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Job Title is longer than the People Directory ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Job Title placeholder values are not allowed on People Directory.')
    return notes


def directory_users_normalize_job_title(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def directory_users_describe_job_title() -> str:
    required = 'required' if True else 'optional'
    return 'Job Title is a ' + required + ' str field on People Directory (directory_users).'


def directory_users_check_department(value: Any) -> list[str]:
    """Field policy for Department inside People Directory."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Department is required on People Directory.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Department is zero; confirm the People Directory case.')
        if number > 9_000_000_000:
            notes.append('Department exceeds the People Directory ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Department must be YYYY-MM-DD for People Directory.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Department is longer than the People Directory ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Department placeholder values are not allowed on People Directory.')
    return notes


def directory_users_normalize_department(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def directory_users_describe_department() -> str:
    required = 'required' if True else 'optional'
    return 'Department is a ' + required + ' str field on People Directory (directory_users).'


def directory_users_check_manager_email(value: Any) -> list[str]:
    """Field policy for Manager Email inside People Directory."""
    notes: list[str] = []
    if value in (None, '') and False:
        notes.append('Manager Email is required on People Directory.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if False and number == 0:
            notes.append('Manager Email is zero; confirm the People Directory case.')
        if number > 9_000_000_000:
            notes.append('Manager Email exceeds the People Directory ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Manager Email must be YYYY-MM-DD for People Directory.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Manager Email is longer than the People Directory ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and False:
        notes.append('Manager Email placeholder values are not allowed on People Directory.')
    return notes


def directory_users_normalize_manager_email(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def directory_users_describe_manager_email() -> str:
    required = 'required' if False else 'optional'
    return 'Manager Email is a ' + required + ' str field on People Directory (directory_users).'


def directory_users_check_location(value: Any) -> list[str]:
    """Field policy for Location inside People Directory."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Location is required on People Directory.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Location is zero; confirm the People Directory case.')
        if number > 9_000_000_000:
            notes.append('Location exceeds the People Directory ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Location must be YYYY-MM-DD for People Directory.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Location is longer than the People Directory ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Location placeholder values are not allowed on People Directory.')
    return notes


def directory_users_normalize_location(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def directory_users_describe_location() -> str:
    required = 'required' if True else 'optional'
    return 'Location is a ' + required + ' str field on People Directory (directory_users).'


def directory_users_check_band(value: Any) -> list[str]:
    """Field policy for Band inside People Directory."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Band is required on People Directory.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Band is zero; confirm the People Directory case.')
        if number > 9_000_000_000:
            notes.append('Band exceeds the People Directory ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Band must be YYYY-MM-DD for People Directory.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Band is longer than the People Directory ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Band placeholder values are not allowed on People Directory.')
    return notes


def directory_users_normalize_band(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def directory_users_describe_band() -> str:
    required = 'required' if True else 'optional'
    return 'Band is a ' + required + ' str field on People Directory (directory_users).'


def directory_users_check_status(value: Any) -> list[str]:
    """Field policy for Status inside People Directory."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Status is required on People Directory.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Status is zero; confirm the People Directory case.')
        if number > 9_000_000_000:
            notes.append('Status exceeds the People Directory ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Status must be YYYY-MM-DD for People Directory.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Status is longer than the People Directory ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Status placeholder values are not allowed on People Directory.')
    return notes


def directory_users_normalize_status(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def directory_users_describe_status() -> str:
    required = 'required' if True else 'optional'
    return 'Status is a ' + required + ' str field on People Directory (directory_users).'


FIELD_CHECKS_DIRECTORY_USERS = {
    'email': directory_users_check_email,
    'full_name': directory_users_check_full_name,
    'job_title': directory_users_check_job_title,
    'department': directory_users_check_department,
    'manager_email': directory_users_check_manager_email,
    'location': directory_users_check_location,
    'band': directory_users_check_band,
    'status': directory_users_check_status,
}


def directory_users_run_field_checks(row: dict[str, Any]) -> list[str]:
    found: list[str] = []
    for name, checker in FIELD_CHECKS_DIRECTORY_USERS.items():
        found.extend(checker(row.get(name)))
    return found


def directory_users_policy_card(row: dict[str, Any]) -> dict[str, Any]:
    return {
        'domain': DOMAIN_KEY,
        'title': DOMAIN_TITLE,
        'band': directory_users_risk_band(row),
        'owner': directory_users_owner_hint(row),
        'sla_hours': directory_users_sla_hours(row),
        'exceptions': directory_users_exception_needed(row),
        'freeze': directory_users_freeze_window(row),
        'violations': policy.collect(row) + directory_users_run_field_checks(row),
        'summary': directory_users_summary_line(row),
    }

