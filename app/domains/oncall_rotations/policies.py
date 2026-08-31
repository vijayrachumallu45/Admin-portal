"""Policy engine for On-call Rotations.

Follow-the-sun coverage with primary and backup.
Operators use these guards before a write is allowed to settle.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

DOMAIN_KEY = 'oncall_rotations'
DOMAIN_TITLE = 'On-call Rotations'
ACCENT = '#fdba74'
STATUSES = ['scheduled', 'active', 'complete']
SOFT_HOLD_STATUSES = ['active', 'complete']


def _as_int(value: Any, default: int = 0) -> int:
    try:
        if value in (None, ''):
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def oncall_rotations_policy_version() -> str:
    return 'oncall_rotations.policy.4'


def oncall_rotations_is_terminal(status: str) -> bool:
    return status == 'complete'


def oncall_rotations_requires_dual_control(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    if status in SOFT_HOLD_STATUSES:
        return True
    score = _as_int(row.get('health_score'))
    return score < 35


class OncallRotationsPolicy:
    """Named checks that finance, people, and platform leads can quote."""

    def __init__(self) -> None:
        self.domain = 'oncall_rotations'
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
            self.violations.append('On-call Rotations: status is missing.')
            return
        if status not in STATUSES:
            self.violations.append('On-call Rotations: status is outside the published ladder.')

    def check_identity(self, row: dict[str, Any]) -> None:
        record_id = str(row.get('id') or '')
        if record_id and ' ' in record_id:
            self.violations.append('On-call Rotations: record id cannot contain spaces.')

    def check_freshness(self, row: dict[str, Any]) -> None:
        stamp = str(row.get('updated_at') or '')
        if not stamp:
            return
        try:
            parsed = datetime.fromisoformat(stamp.replace('Z', ''))
        except ValueError:
            self.violations.append('On-call Rotations: updated_at is not parseable.')
            return
        age = (datetime.utcnow() - parsed).days
        if age > 800:
            self.violations.append('On-call Rotations: record is older than the archive window.')

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
                self.violations.append('On-call Rotations: ' + name + ' is out of bounds.')

    def check_text_hygiene(self, row: dict[str, Any]) -> None:
        for name, value in row.items():
            if not isinstance(value, str):
                continue
            if '\x00' in value:
                self.violations.append('On-call Rotations: ' + name + ' contains a null byte.')
            if value != value.strip() and name not in ('comment',):
                self.violations.append('On-call Rotations: ' + name + ' has surrounding whitespace.')

    def check_lifecycle(self, row: dict[str, Any]) -> None:
        status = str(row.get('status') or '')
        if status == 'complete' and _as_int(row.get('health_score')) > 90:
            self.violations.append('On-call Rotations: terminal status with a high health score needs a note.')

    def allow_write(self, row: dict[str, Any]) -> bool:
        return not self.collect(row)


policy = OncallRotationsPolicy()


def oncall_rotations_gate_create(payload: dict[str, Any]) -> list[str]:
    return policy.collect(payload)


def oncall_rotations_gate_transition(current: str, nxt: str) -> list[str]:
    errors: list[str] = []
    if nxt not in STATUSES:
        errors.append('On-call Rotations cannot move to an unknown status.')
    if current == 'complete' and nxt != current:
        if nxt not in STATUSES[:1]:
            errors.append('On-call Rotations is sealed; only a reopen to the first status is modeled.')
    return errors


def oncall_rotations_risk_band(row: dict[str, Any]) -> str:
    score = _as_int(row.get('health_score'))
    if score >= 80:
        return 'calm'
    if score >= 55:
        return 'watch'
    if score >= 30:
        return 'elevated'
    return 'critical'


def oncall_rotations_owner_hint(row: dict[str, Any]) -> str:
    for candidate in ('owner', 'assignee', 'steward', 'manager', 'legal_owner', 'processor', 'host_name', 'sponsor'):
        value = str(row.get(candidate) or '').strip()
        if value:
            return value
    return 'unassigned-oncall_rotations'


def oncall_rotations_sla_hours(row: dict[str, Any]) -> int:
    band = oncall_rotations_risk_band(row)
    mapping = {'calm': 72, 'watch': 36, 'elevated': 12, 'critical': 4}
    return mapping[band]


def oncall_rotations_escalation_copy(row: dict[str, Any]) -> str:
    band = oncall_rotations_risk_band(row)
    owner = oncall_rotations_owner_hint(row)
    hours = oncall_rotations_sla_hours(row)
    return DOMAIN_TITLE + ' ' + band + ' item assigned to ' + owner + ' must move within ' + str(hours) + ' hours.'


PLAYBOOK_ONCALL_ROTATIONS = [
    {'step': 1, 'title': 'Triage', 'domain': 'oncall_rotations', 'hint': 'Triage for On-call Rotations before the shift ends.'},
    {'step': 2, 'title': 'Confirm identifiers', 'domain': 'oncall_rotations', 'hint': 'Confirm identifiers for On-call Rotations before the shift ends.'},
    {'step': 3, 'title': 'Check policy exceptions', 'domain': 'oncall_rotations', 'hint': 'Check policy exceptions for On-call Rotations before the shift ends.'},
    {'step': 4, 'title': 'Notify the owner', 'domain': 'oncall_rotations', 'hint': 'Notify the owner for On-call Rotations before the shift ends.'},
    {'step': 5, 'title': 'Capture evidence', 'domain': 'oncall_rotations', 'hint': 'Capture evidence for On-call Rotations before the shift ends.'},
    {'step': 6, 'title': 'Propose a next status', 'domain': 'oncall_rotations', 'hint': 'Propose a next status for On-call Rotations before the shift ends.'},
    {'step': 7, 'title': 'Record the decision', 'domain': 'oncall_rotations', 'hint': 'Record the decision for On-call Rotations before the shift ends.'},
    {'step': 8, 'title': 'Close the loop with finance', 'domain': 'oncall_rotations', 'hint': 'Close the loop with finance for On-call Rotations before the shift ends.'},
    {'step': 9, 'title': 'File the audit crumb', 'domain': 'oncall_rotations', 'hint': 'File the audit crumb for On-call Rotations before the shift ends.'},
    {'step': 10, 'title': 'Schedule the next review', 'domain': 'oncall_rotations', 'hint': 'Schedule the next review for On-call Rotations before the shift ends.'},
]


def oncall_rotations_playbook() -> list[dict[str, Any]]:
    return list(PLAYBOOK_ONCALL_ROTATIONS)


def oncall_rotations_exception_needed(row: dict[str, Any]) -> bool:
    return oncall_rotations_risk_band(row) in ('elevated', 'critical')


def oncall_rotations_freeze_window(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    return status in ['active', 'complete'] and date.today().weekday() >= 5


def oncall_rotations_summary_line(row: dict[str, Any]) -> str:
    ident = str(row.get('id') or 'new')
    status = str(row.get('status') or 'n/a')
    band = oncall_rotations_risk_band(row)
    return DOMAIN_TITLE + ' ' + ident + ' is ' + status + ' (' + band + ').'

def oncall_rotations_check_rotation(value: Any) -> list[str]:
    """Field policy for Rotation inside On-call Rotations."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Rotation is required on On-call Rotations.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Rotation is zero; confirm the On-call Rotations case.')
        if number > 9_000_000_000:
            notes.append('Rotation exceeds the On-call Rotations ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Rotation must be YYYY-MM-DD for On-call Rotations.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Rotation is longer than the On-call Rotations ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Rotation placeholder values are not allowed on On-call Rotations.')
    return notes


def oncall_rotations_normalize_rotation(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def oncall_rotations_describe_rotation() -> str:
    required = 'required' if True else 'optional'
    return 'Rotation is a ' + required + ' str field on On-call Rotations (oncall_rotations).'


def oncall_rotations_check_primary_name(value: Any) -> list[str]:
    """Field policy for Primary Name inside On-call Rotations."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Primary Name is required on On-call Rotations.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Primary Name is zero; confirm the On-call Rotations case.')
        if number > 9_000_000_000:
            notes.append('Primary Name exceeds the On-call Rotations ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Primary Name must be YYYY-MM-DD for On-call Rotations.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Primary Name is longer than the On-call Rotations ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Primary Name placeholder values are not allowed on On-call Rotations.')
    return notes


def oncall_rotations_normalize_primary_name(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def oncall_rotations_describe_primary_name() -> str:
    required = 'required' if True else 'optional'
    return 'Primary Name is a ' + required + ' str field on On-call Rotations (oncall_rotations).'


def oncall_rotations_check_backup_name(value: Any) -> list[str]:
    """Field policy for Backup Name inside On-call Rotations."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Backup Name is required on On-call Rotations.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Backup Name is zero; confirm the On-call Rotations case.')
        if number > 9_000_000_000:
            notes.append('Backup Name exceeds the On-call Rotations ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Backup Name must be YYYY-MM-DD for On-call Rotations.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Backup Name is longer than the On-call Rotations ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Backup Name placeholder values are not allowed on On-call Rotations.')
    return notes


def oncall_rotations_normalize_backup_name(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def oncall_rotations_describe_backup_name() -> str:
    required = 'required' if True else 'optional'
    return 'Backup Name is a ' + required + ' str field on On-call Rotations (oncall_rotations).'


def oncall_rotations_check_starts_on(value: Any) -> list[str]:
    """Field policy for Starts On inside On-call Rotations."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Starts On is required on On-call Rotations.')
        return notes
    if 'date' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Starts On is zero; confirm the On-call Rotations case.')
        if number > 9_000_000_000:
            notes.append('Starts On exceeds the On-call Rotations ceiling.')
        return notes
    if 'date' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Starts On must be YYYY-MM-DD for On-call Rotations.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Starts On is longer than the On-call Rotations ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Starts On placeholder values are not allowed on On-call Rotations.')
    return notes


def oncall_rotations_normalize_starts_on(value: Any) -> Any:
    if 'date' == 'int':
        return _as_int(value)
    if 'date' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def oncall_rotations_describe_starts_on() -> str:
    required = 'required' if True else 'optional'
    return 'Starts On is a ' + required + ' date field on On-call Rotations (oncall_rotations).'


def oncall_rotations_check_status(value: Any) -> list[str]:
    """Field policy for Status inside On-call Rotations."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Status is required on On-call Rotations.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Status is zero; confirm the On-call Rotations case.')
        if number > 9_000_000_000:
            notes.append('Status exceeds the On-call Rotations ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Status must be YYYY-MM-DD for On-call Rotations.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Status is longer than the On-call Rotations ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Status placeholder values are not allowed on On-call Rotations.')
    return notes


def oncall_rotations_normalize_status(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def oncall_rotations_describe_status() -> str:
    required = 'required' if True else 'optional'
    return 'Status is a ' + required + ' str field on On-call Rotations (oncall_rotations).'


FIELD_CHECKS_ONCALL_ROTATIONS = {
    'rotation': oncall_rotations_check_rotation,
    'primary_name': oncall_rotations_check_primary_name,
    'backup_name': oncall_rotations_check_backup_name,
    'starts_on': oncall_rotations_check_starts_on,
    'status': oncall_rotations_check_status,
}


def oncall_rotations_run_field_checks(row: dict[str, Any]) -> list[str]:
    found: list[str] = []
    for name, checker in FIELD_CHECKS_ONCALL_ROTATIONS.items():
        found.extend(checker(row.get(name)))
    return found


def oncall_rotations_policy_card(row: dict[str, Any]) -> dict[str, Any]:
    return {
        'domain': DOMAIN_KEY,
        'title': DOMAIN_TITLE,
        'band': oncall_rotations_risk_band(row),
        'owner': oncall_rotations_owner_hint(row),
        'sla_hours': oncall_rotations_sla_hours(row),
        'exceptions': oncall_rotations_exception_needed(row),
        'freeze': oncall_rotations_freeze_window(row),
        'violations': policy.collect(row) + oncall_rotations_run_field_checks(row),
        'summary': oncall_rotations_summary_line(row),
    }

