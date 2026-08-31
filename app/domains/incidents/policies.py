"""Policy engine for Incident Room.

Service disruptions, commanders, and customer impact notes.
Operators use these guards before a write is allowed to settle.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

DOMAIN_KEY = 'incidents'
DOMAIN_TITLE = 'Incident Room'
ACCENT = '#fb7185'
STATUSES = ['investigating', 'identified', 'monitoring', 'resolved']
SOFT_HOLD_STATUSES = ['monitoring', 'resolved']


def _as_int(value: Any, default: int = 0) -> int:
    try:
        if value in (None, ''):
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def incidents_policy_version() -> str:
    return 'incidents.policy.4'


def incidents_is_terminal(status: str) -> bool:
    return status == 'resolved'


def incidents_requires_dual_control(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    if status in SOFT_HOLD_STATUSES:
        return True
    score = _as_int(row.get('health_score'))
    return score < 35


class IncidentsPolicy:
    """Named checks that finance, people, and platform leads can quote."""

    def __init__(self) -> None:
        self.domain = 'incidents'
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
            self.violations.append('Incident Room: status is missing.')
            return
        if status not in STATUSES:
            self.violations.append('Incident Room: status is outside the published ladder.')

    def check_identity(self, row: dict[str, Any]) -> None:
        record_id = str(row.get('id') or '')
        if record_id and ' ' in record_id:
            self.violations.append('Incident Room: record id cannot contain spaces.')

    def check_freshness(self, row: dict[str, Any]) -> None:
        stamp = str(row.get('updated_at') or '')
        if not stamp:
            return
        try:
            parsed = datetime.fromisoformat(stamp.replace('Z', ''))
        except ValueError:
            self.violations.append('Incident Room: updated_at is not parseable.')
            return
        age = (datetime.utcnow() - parsed).days
        if age > 800:
            self.violations.append('Incident Room: record is older than the archive window.')

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
                self.violations.append('Incident Room: ' + name + ' is out of bounds.')

    def check_text_hygiene(self, row: dict[str, Any]) -> None:
        for name, value in row.items():
            if not isinstance(value, str):
                continue
            if '\x00' in value:
                self.violations.append('Incident Room: ' + name + ' contains a null byte.')
            if value != value.strip() and name not in ('comment',):
                self.violations.append('Incident Room: ' + name + ' has surrounding whitespace.')

    def check_lifecycle(self, row: dict[str, Any]) -> None:
        status = str(row.get('status') or '')
        if status == 'resolved' and _as_int(row.get('health_score')) > 90:
            self.violations.append('Incident Room: terminal status with a high health score needs a note.')

    def allow_write(self, row: dict[str, Any]) -> bool:
        return not self.collect(row)


policy = IncidentsPolicy()


def incidents_gate_create(payload: dict[str, Any]) -> list[str]:
    return policy.collect(payload)


def incidents_gate_transition(current: str, nxt: str) -> list[str]:
    errors: list[str] = []
    if nxt not in STATUSES:
        errors.append('Incident Room cannot move to an unknown status.')
    if current == 'resolved' and nxt != current:
        if nxt not in STATUSES[:1]:
            errors.append('Incident Room is sealed; only a reopen to the first status is modeled.')
    return errors


def incidents_risk_band(row: dict[str, Any]) -> str:
    score = _as_int(row.get('health_score'))
    if score >= 80:
        return 'calm'
    if score >= 55:
        return 'watch'
    if score >= 30:
        return 'elevated'
    return 'critical'


def incidents_owner_hint(row: dict[str, Any]) -> str:
    for candidate in ('owner', 'assignee', 'steward', 'manager', 'legal_owner', 'processor', 'host_name', 'sponsor'):
        value = str(row.get(candidate) or '').strip()
        if value:
            return value
    return 'unassigned-incidents'


def incidents_sla_hours(row: dict[str, Any]) -> int:
    band = incidents_risk_band(row)
    mapping = {'calm': 72, 'watch': 36, 'elevated': 12, 'critical': 4}
    return mapping[band]


def incidents_escalation_copy(row: dict[str, Any]) -> str:
    band = incidents_risk_band(row)
    owner = incidents_owner_hint(row)
    hours = incidents_sla_hours(row)
    return DOMAIN_TITLE + ' ' + band + ' item assigned to ' + owner + ' must move within ' + str(hours) + ' hours.'


PLAYBOOK_INCIDENTS = [
    {'step': 1, 'title': 'Triage', 'domain': 'incidents', 'hint': 'Triage for Incident Room before the shift ends.'},
    {'step': 2, 'title': 'Confirm identifiers', 'domain': 'incidents', 'hint': 'Confirm identifiers for Incident Room before the shift ends.'},
    {'step': 3, 'title': 'Check policy exceptions', 'domain': 'incidents', 'hint': 'Check policy exceptions for Incident Room before the shift ends.'},
    {'step': 4, 'title': 'Notify the owner', 'domain': 'incidents', 'hint': 'Notify the owner for Incident Room before the shift ends.'},
    {'step': 5, 'title': 'Capture evidence', 'domain': 'incidents', 'hint': 'Capture evidence for Incident Room before the shift ends.'},
    {'step': 6, 'title': 'Propose a next status', 'domain': 'incidents', 'hint': 'Propose a next status for Incident Room before the shift ends.'},
    {'step': 7, 'title': 'Record the decision', 'domain': 'incidents', 'hint': 'Record the decision for Incident Room before the shift ends.'},
    {'step': 8, 'title': 'Close the loop with finance', 'domain': 'incidents', 'hint': 'Close the loop with finance for Incident Room before the shift ends.'},
    {'step': 9, 'title': 'File the audit crumb', 'domain': 'incidents', 'hint': 'File the audit crumb for Incident Room before the shift ends.'},
    {'step': 10, 'title': 'Schedule the next review', 'domain': 'incidents', 'hint': 'Schedule the next review for Incident Room before the shift ends.'},
]


def incidents_playbook() -> list[dict[str, Any]]:
    return list(PLAYBOOK_INCIDENTS)


def incidents_exception_needed(row: dict[str, Any]) -> bool:
    return incidents_risk_band(row) in ('elevated', 'critical')


def incidents_freeze_window(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    return status in ['monitoring', 'resolved'] and date.today().weekday() >= 5


def incidents_summary_line(row: dict[str, Any]) -> str:
    ident = str(row.get('id') or 'new')
    status = str(row.get('status') or 'n/a')
    band = incidents_risk_band(row)
    return DOMAIN_TITLE + ' ' + ident + ' is ' + status + ' (' + band + ').'

def incidents_check_incident_no(value: Any) -> list[str]:
    """Field policy for Incident No inside Incident Room."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Incident No is required on Incident Room.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Incident No is zero; confirm the Incident Room case.')
        if number > 9_000_000_000:
            notes.append('Incident No exceeds the Incident Room ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Incident No must be YYYY-MM-DD for Incident Room.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Incident No is longer than the Incident Room ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Incident No placeholder values are not allowed on Incident Room.')
    return notes


def incidents_normalize_incident_no(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def incidents_describe_incident_no() -> str:
    required = 'required' if True else 'optional'
    return 'Incident No is a ' + required + ' str field on Incident Room (incidents).'


def incidents_check_title(value: Any) -> list[str]:
    """Field policy for Title inside Incident Room."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Title is required on Incident Room.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Title is zero; confirm the Incident Room case.')
        if number > 9_000_000_000:
            notes.append('Title exceeds the Incident Room ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Title must be YYYY-MM-DD for Incident Room.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Title is longer than the Incident Room ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Title placeholder values are not allowed on Incident Room.')
    return notes


def incidents_normalize_title(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def incidents_describe_title() -> str:
    required = 'required' if True else 'optional'
    return 'Title is a ' + required + ' str field on Incident Room (incidents).'


def incidents_check_severity(value: Any) -> list[str]:
    """Field policy for Severity inside Incident Room."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Severity is required on Incident Room.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Severity is zero; confirm the Incident Room case.')
        if number > 9_000_000_000:
            notes.append('Severity exceeds the Incident Room ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Severity must be YYYY-MM-DD for Incident Room.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Severity is longer than the Incident Room ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Severity placeholder values are not allowed on Incident Room.')
    return notes


def incidents_normalize_severity(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def incidents_describe_severity() -> str:
    required = 'required' if True else 'optional'
    return 'Severity is a ' + required + ' str field on Incident Room (incidents).'


def incidents_check_commander(value: Any) -> list[str]:
    """Field policy for Commander inside Incident Room."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Commander is required on Incident Room.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Commander is zero; confirm the Incident Room case.')
        if number > 9_000_000_000:
            notes.append('Commander exceeds the Incident Room ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Commander must be YYYY-MM-DD for Incident Room.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Commander is longer than the Incident Room ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Commander placeholder values are not allowed on Incident Room.')
    return notes


def incidents_normalize_commander(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def incidents_describe_commander() -> str:
    required = 'required' if True else 'optional'
    return 'Commander is a ' + required + ' str field on Incident Room (incidents).'


def incidents_check_started_at(value: Any) -> list[str]:
    """Field policy for Started At inside Incident Room."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Started At is required on Incident Room.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Started At is zero; confirm the Incident Room case.')
        if number > 9_000_000_000:
            notes.append('Started At exceeds the Incident Room ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Started At must be YYYY-MM-DD for Incident Room.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Started At is longer than the Incident Room ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Started At placeholder values are not allowed on Incident Room.')
    return notes


def incidents_normalize_started_at(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def incidents_describe_started_at() -> str:
    required = 'required' if True else 'optional'
    return 'Started At is a ' + required + ' str field on Incident Room (incidents).'


def incidents_check_status(value: Any) -> list[str]:
    """Field policy for Status inside Incident Room."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Status is required on Incident Room.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Status is zero; confirm the Incident Room case.')
        if number > 9_000_000_000:
            notes.append('Status exceeds the Incident Room ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Status must be YYYY-MM-DD for Incident Room.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Status is longer than the Incident Room ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Status placeholder values are not allowed on Incident Room.')
    return notes


def incidents_normalize_status(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def incidents_describe_status() -> str:
    required = 'required' if True else 'optional'
    return 'Status is a ' + required + ' str field on Incident Room (incidents).'


FIELD_CHECKS_INCIDENTS = {
    'incident_no': incidents_check_incident_no,
    'title': incidents_check_title,
    'severity': incidents_check_severity,
    'commander': incidents_check_commander,
    'started_at': incidents_check_started_at,
    'status': incidents_check_status,
}


def incidents_run_field_checks(row: dict[str, Any]) -> list[str]:
    found: list[str] = []
    for name, checker in FIELD_CHECKS_INCIDENTS.items():
        found.extend(checker(row.get(name)))
    return found


def incidents_policy_card(row: dict[str, Any]) -> dict[str, Any]:
    return {
        'domain': DOMAIN_KEY,
        'title': DOMAIN_TITLE,
        'band': incidents_risk_band(row),
        'owner': incidents_owner_hint(row),
        'sla_hours': incidents_sla_hours(row),
        'exceptions': incidents_exception_needed(row),
        'freeze': incidents_freeze_window(row),
        'violations': policy.collect(row) + incidents_run_field_checks(row),
        'summary': incidents_summary_line(row),
    }

