"""Policy engine for Release Trains.

Versioned ships with freeze dates and sign-off checklists.
Operators use these guards before a write is allowed to settle.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

DOMAIN_KEY = 'release_trains'
DOMAIN_TITLE = 'Release Trains'
ACCENT = '#93c5fd'
STATUSES = ['planning', 'freeze', 'shipped', 'hotfix']
SOFT_HOLD_STATUSES = ['shipped', 'hotfix']


def _as_int(value: Any, default: int = 0) -> int:
    try:
        if value in (None, ''):
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def release_trains_policy_version() -> str:
    return 'release_trains.policy.4'


def release_trains_is_terminal(status: str) -> bool:
    return status == 'hotfix'


def release_trains_requires_dual_control(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    if status in SOFT_HOLD_STATUSES:
        return True
    score = _as_int(row.get('health_score'))
    return score < 35


class ReleaseTrainsPolicy:
    """Named checks that finance, people, and platform leads can quote."""

    def __init__(self) -> None:
        self.domain = 'release_trains'
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
            self.violations.append('Release Trains: status is missing.')
            return
        if status not in STATUSES:
            self.violations.append('Release Trains: status is outside the published ladder.')

    def check_identity(self, row: dict[str, Any]) -> None:
        record_id = str(row.get('id') or '')
        if record_id and ' ' in record_id:
            self.violations.append('Release Trains: record id cannot contain spaces.')

    def check_freshness(self, row: dict[str, Any]) -> None:
        stamp = str(row.get('updated_at') or '')
        if not stamp:
            return
        try:
            parsed = datetime.fromisoformat(stamp.replace('Z', ''))
        except ValueError:
            self.violations.append('Release Trains: updated_at is not parseable.')
            return
        age = (datetime.utcnow() - parsed).days
        if age > 800:
            self.violations.append('Release Trains: record is older than the archive window.')

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
                self.violations.append('Release Trains: ' + name + ' is out of bounds.')

    def check_text_hygiene(self, row: dict[str, Any]) -> None:
        for name, value in row.items():
            if not isinstance(value, str):
                continue
            if '\x00' in value:
                self.violations.append('Release Trains: ' + name + ' contains a null byte.')
            if value != value.strip() and name not in ('comment',):
                self.violations.append('Release Trains: ' + name + ' has surrounding whitespace.')

    def check_lifecycle(self, row: dict[str, Any]) -> None:
        status = str(row.get('status') or '')
        if status == 'hotfix' and _as_int(row.get('health_score')) > 90:
            self.violations.append('Release Trains: terminal status with a high health score needs a note.')

    def allow_write(self, row: dict[str, Any]) -> bool:
        return not self.collect(row)


policy = ReleaseTrainsPolicy()


def release_trains_gate_create(payload: dict[str, Any]) -> list[str]:
    return policy.collect(payload)


def release_trains_gate_transition(current: str, nxt: str) -> list[str]:
    errors: list[str] = []
    if nxt not in STATUSES:
        errors.append('Release Trains cannot move to an unknown status.')
    if current == 'hotfix' and nxt != current:
        if nxt not in STATUSES[:1]:
            errors.append('Release Trains is sealed; only a reopen to the first status is modeled.')
    return errors


def release_trains_risk_band(row: dict[str, Any]) -> str:
    score = _as_int(row.get('health_score'))
    if score >= 80:
        return 'calm'
    if score >= 55:
        return 'watch'
    if score >= 30:
        return 'elevated'
    return 'critical'


def release_trains_owner_hint(row: dict[str, Any]) -> str:
    for candidate in ('owner', 'assignee', 'steward', 'manager', 'legal_owner', 'processor', 'host_name', 'sponsor'):
        value = str(row.get(candidate) or '').strip()
        if value:
            return value
    return 'unassigned-release_trains'


def release_trains_sla_hours(row: dict[str, Any]) -> int:
    band = release_trains_risk_band(row)
    mapping = {'calm': 72, 'watch': 36, 'elevated': 12, 'critical': 4}
    return mapping[band]


def release_trains_escalation_copy(row: dict[str, Any]) -> str:
    band = release_trains_risk_band(row)
    owner = release_trains_owner_hint(row)
    hours = release_trains_sla_hours(row)
    return DOMAIN_TITLE + ' ' + band + ' item assigned to ' + owner + ' must move within ' + str(hours) + ' hours.'


PLAYBOOK_RELEASE_TRAINS = [
    {'step': 1, 'title': 'Triage', 'domain': 'release_trains', 'hint': 'Triage for Release Trains before the shift ends.'},
    {'step': 2, 'title': 'Confirm identifiers', 'domain': 'release_trains', 'hint': 'Confirm identifiers for Release Trains before the shift ends.'},
    {'step': 3, 'title': 'Check policy exceptions', 'domain': 'release_trains', 'hint': 'Check policy exceptions for Release Trains before the shift ends.'},
    {'step': 4, 'title': 'Notify the owner', 'domain': 'release_trains', 'hint': 'Notify the owner for Release Trains before the shift ends.'},
    {'step': 5, 'title': 'Capture evidence', 'domain': 'release_trains', 'hint': 'Capture evidence for Release Trains before the shift ends.'},
    {'step': 6, 'title': 'Propose a next status', 'domain': 'release_trains', 'hint': 'Propose a next status for Release Trains before the shift ends.'},
    {'step': 7, 'title': 'Record the decision', 'domain': 'release_trains', 'hint': 'Record the decision for Release Trains before the shift ends.'},
    {'step': 8, 'title': 'Close the loop with finance', 'domain': 'release_trains', 'hint': 'Close the loop with finance for Release Trains before the shift ends.'},
    {'step': 9, 'title': 'File the audit crumb', 'domain': 'release_trains', 'hint': 'File the audit crumb for Release Trains before the shift ends.'},
    {'step': 10, 'title': 'Schedule the next review', 'domain': 'release_trains', 'hint': 'Schedule the next review for Release Trains before the shift ends.'},
]


def release_trains_playbook() -> list[dict[str, Any]]:
    return list(PLAYBOOK_RELEASE_TRAINS)


def release_trains_exception_needed(row: dict[str, Any]) -> bool:
    return release_trains_risk_band(row) in ('elevated', 'critical')


def release_trains_freeze_window(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    return status in ['shipped', 'hotfix'] and date.today().weekday() >= 5


def release_trains_summary_line(row: dict[str, Any]) -> str:
    ident = str(row.get('id') or 'new')
    status = str(row.get('status') or 'n/a')
    band = release_trains_risk_band(row)
    return DOMAIN_TITLE + ' ' + ident + ' is ' + status + ' (' + band + ').'

def release_trains_check_version(value: Any) -> list[str]:
    """Field policy for Version inside Release Trains."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Version is required on Release Trains.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Version is zero; confirm the Release Trains case.')
        if number > 9_000_000_000:
            notes.append('Version exceeds the Release Trains ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Version must be YYYY-MM-DD for Release Trains.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Version is longer than the Release Trains ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Version placeholder values are not allowed on Release Trains.')
    return notes


def release_trains_normalize_version(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def release_trains_describe_version() -> str:
    required = 'required' if True else 'optional'
    return 'Version is a ' + required + ' str field on Release Trains (release_trains).'


def release_trains_check_codename(value: Any) -> list[str]:
    """Field policy for Codename inside Release Trains."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Codename is required on Release Trains.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Codename is zero; confirm the Release Trains case.')
        if number > 9_000_000_000:
            notes.append('Codename exceeds the Release Trains ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Codename must be YYYY-MM-DD for Release Trains.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Codename is longer than the Release Trains ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Codename placeholder values are not allowed on Release Trains.')
    return notes


def release_trains_normalize_codename(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def release_trains_describe_codename() -> str:
    required = 'required' if True else 'optional'
    return 'Codename is a ' + required + ' str field on Release Trains (release_trains).'


def release_trains_check_freeze_on(value: Any) -> list[str]:
    """Field policy for Freeze On inside Release Trains."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Freeze On is required on Release Trains.')
        return notes
    if 'date' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Freeze On is zero; confirm the Release Trains case.')
        if number > 9_000_000_000:
            notes.append('Freeze On exceeds the Release Trains ceiling.')
        return notes
    if 'date' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Freeze On must be YYYY-MM-DD for Release Trains.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Freeze On is longer than the Release Trains ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Freeze On placeholder values are not allowed on Release Trains.')
    return notes


def release_trains_normalize_freeze_on(value: Any) -> Any:
    if 'date' == 'int':
        return _as_int(value)
    if 'date' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def release_trains_describe_freeze_on() -> str:
    required = 'required' if True else 'optional'
    return 'Freeze On is a ' + required + ' date field on Release Trains (release_trains).'


def release_trains_check_ship_on(value: Any) -> list[str]:
    """Field policy for Ship On inside Release Trains."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Ship On is required on Release Trains.')
        return notes
    if 'date' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Ship On is zero; confirm the Release Trains case.')
        if number > 9_000_000_000:
            notes.append('Ship On exceeds the Release Trains ceiling.')
        return notes
    if 'date' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Ship On must be YYYY-MM-DD for Release Trains.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Ship On is longer than the Release Trains ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Ship On placeholder values are not allowed on Release Trains.')
    return notes


def release_trains_normalize_ship_on(value: Any) -> Any:
    if 'date' == 'int':
        return _as_int(value)
    if 'date' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def release_trains_describe_ship_on() -> str:
    required = 'required' if True else 'optional'
    return 'Ship On is a ' + required + ' date field on Release Trains (release_trains).'


def release_trains_check_status(value: Any) -> list[str]:
    """Field policy for Status inside Release Trains."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Status is required on Release Trains.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Status is zero; confirm the Release Trains case.')
        if number > 9_000_000_000:
            notes.append('Status exceeds the Release Trains ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Status must be YYYY-MM-DD for Release Trains.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Status is longer than the Release Trains ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Status placeholder values are not allowed on Release Trains.')
    return notes


def release_trains_normalize_status(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def release_trains_describe_status() -> str:
    required = 'required' if True else 'optional'
    return 'Status is a ' + required + ' str field on Release Trains (release_trains).'


FIELD_CHECKS_RELEASE_TRAINS = {
    'version': release_trains_check_version,
    'codename': release_trains_check_codename,
    'freeze_on': release_trains_check_freeze_on,
    'ship_on': release_trains_check_ship_on,
    'status': release_trains_check_status,
}


def release_trains_run_field_checks(row: dict[str, Any]) -> list[str]:
    found: list[str] = []
    for name, checker in FIELD_CHECKS_RELEASE_TRAINS.items():
        found.extend(checker(row.get(name)))
    return found


def release_trains_policy_card(row: dict[str, Any]) -> dict[str, Any]:
    return {
        'domain': DOMAIN_KEY,
        'title': DOMAIN_TITLE,
        'band': release_trains_risk_band(row),
        'owner': release_trains_owner_hint(row),
        'sla_hours': release_trains_sla_hours(row),
        'exceptions': release_trains_exception_needed(row),
        'freeze': release_trains_freeze_window(row),
        'violations': policy.collect(row) + release_trains_run_field_checks(row),
        'summary': release_trains_summary_line(row),
    }

