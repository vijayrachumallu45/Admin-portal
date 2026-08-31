"""Policy engine for Feature Flags.

Release toggles with audience percentage and owners.
Operators use these guards before a write is allowed to settle.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

DOMAIN_KEY = 'feature_flags'
DOMAIN_TITLE = 'Feature Flags'
ACCENT = '#5eead4'
STATUSES = ['off', 'ramp', 'on', 'retired']
SOFT_HOLD_STATUSES = ['on', 'retired']


def _as_int(value: Any, default: int = 0) -> int:
    try:
        if value in (None, ''):
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def feature_flags_policy_version() -> str:
    return 'feature_flags.policy.4'


def feature_flags_is_terminal(status: str) -> bool:
    return status == 'retired'


def feature_flags_requires_dual_control(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    if status in SOFT_HOLD_STATUSES:
        return True
    score = _as_int(row.get('health_score'))
    return score < 35


class FeatureFlagsPolicy:
    """Named checks that finance, people, and platform leads can quote."""

    def __init__(self) -> None:
        self.domain = 'feature_flags'
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
            self.violations.append('Feature Flags: status is missing.')
            return
        if status not in STATUSES:
            self.violations.append('Feature Flags: status is outside the published ladder.')

    def check_identity(self, row: dict[str, Any]) -> None:
        record_id = str(row.get('id') or '')
        if record_id and ' ' in record_id:
            self.violations.append('Feature Flags: record id cannot contain spaces.')

    def check_freshness(self, row: dict[str, Any]) -> None:
        stamp = str(row.get('updated_at') or '')
        if not stamp:
            return
        try:
            parsed = datetime.fromisoformat(stamp.replace('Z', ''))
        except ValueError:
            self.violations.append('Feature Flags: updated_at is not parseable.')
            return
        age = (datetime.utcnow() - parsed).days
        if age > 800:
            self.violations.append('Feature Flags: record is older than the archive window.')

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
                self.violations.append('Feature Flags: ' + name + ' is out of bounds.')

    def check_text_hygiene(self, row: dict[str, Any]) -> None:
        for name, value in row.items():
            if not isinstance(value, str):
                continue
            if '\x00' in value:
                self.violations.append('Feature Flags: ' + name + ' contains a null byte.')
            if value != value.strip() and name not in ('comment',):
                self.violations.append('Feature Flags: ' + name + ' has surrounding whitespace.')

    def check_lifecycle(self, row: dict[str, Any]) -> None:
        status = str(row.get('status') or '')
        if status == 'retired' and _as_int(row.get('health_score')) > 90:
            self.violations.append('Feature Flags: terminal status with a high health score needs a note.')

    def allow_write(self, row: dict[str, Any]) -> bool:
        return not self.collect(row)


policy = FeatureFlagsPolicy()


def feature_flags_gate_create(payload: dict[str, Any]) -> list[str]:
    return policy.collect(payload)


def feature_flags_gate_transition(current: str, nxt: str) -> list[str]:
    errors: list[str] = []
    if nxt not in STATUSES:
        errors.append('Feature Flags cannot move to an unknown status.')
    if current == 'retired' and nxt != current:
        if nxt not in STATUSES[:1]:
            errors.append('Feature Flags is sealed; only a reopen to the first status is modeled.')
    return errors


def feature_flags_risk_band(row: dict[str, Any]) -> str:
    score = _as_int(row.get('health_score'))
    if score >= 80:
        return 'calm'
    if score >= 55:
        return 'watch'
    if score >= 30:
        return 'elevated'
    return 'critical'


def feature_flags_owner_hint(row: dict[str, Any]) -> str:
    for candidate in ('owner', 'assignee', 'steward', 'manager', 'legal_owner', 'processor', 'host_name', 'sponsor'):
        value = str(row.get(candidate) or '').strip()
        if value:
            return value
    return 'unassigned-feature_flags'


def feature_flags_sla_hours(row: dict[str, Any]) -> int:
    band = feature_flags_risk_band(row)
    mapping = {'calm': 72, 'watch': 36, 'elevated': 12, 'critical': 4}
    return mapping[band]


def feature_flags_escalation_copy(row: dict[str, Any]) -> str:
    band = feature_flags_risk_band(row)
    owner = feature_flags_owner_hint(row)
    hours = feature_flags_sla_hours(row)
    return DOMAIN_TITLE + ' ' + band + ' item assigned to ' + owner + ' must move within ' + str(hours) + ' hours.'


PLAYBOOK_FEATURE_FLAGS = [
    {'step': 1, 'title': 'Triage', 'domain': 'feature_flags', 'hint': 'Triage for Feature Flags before the shift ends.'},
    {'step': 2, 'title': 'Confirm identifiers', 'domain': 'feature_flags', 'hint': 'Confirm identifiers for Feature Flags before the shift ends.'},
    {'step': 3, 'title': 'Check policy exceptions', 'domain': 'feature_flags', 'hint': 'Check policy exceptions for Feature Flags before the shift ends.'},
    {'step': 4, 'title': 'Notify the owner', 'domain': 'feature_flags', 'hint': 'Notify the owner for Feature Flags before the shift ends.'},
    {'step': 5, 'title': 'Capture evidence', 'domain': 'feature_flags', 'hint': 'Capture evidence for Feature Flags before the shift ends.'},
    {'step': 6, 'title': 'Propose a next status', 'domain': 'feature_flags', 'hint': 'Propose a next status for Feature Flags before the shift ends.'},
    {'step': 7, 'title': 'Record the decision', 'domain': 'feature_flags', 'hint': 'Record the decision for Feature Flags before the shift ends.'},
    {'step': 8, 'title': 'Close the loop with finance', 'domain': 'feature_flags', 'hint': 'Close the loop with finance for Feature Flags before the shift ends.'},
    {'step': 9, 'title': 'File the audit crumb', 'domain': 'feature_flags', 'hint': 'File the audit crumb for Feature Flags before the shift ends.'},
    {'step': 10, 'title': 'Schedule the next review', 'domain': 'feature_flags', 'hint': 'Schedule the next review for Feature Flags before the shift ends.'},
]


def feature_flags_playbook() -> list[dict[str, Any]]:
    return list(PLAYBOOK_FEATURE_FLAGS)


def feature_flags_exception_needed(row: dict[str, Any]) -> bool:
    return feature_flags_risk_band(row) in ('elevated', 'critical')


def feature_flags_freeze_window(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    return status in ['on', 'retired'] and date.today().weekday() >= 5


def feature_flags_summary_line(row: dict[str, Any]) -> str:
    ident = str(row.get('id') or 'new')
    status = str(row.get('status') or 'n/a')
    band = feature_flags_risk_band(row)
    return DOMAIN_TITLE + ' ' + ident + ' is ' + status + ' (' + band + ').'

def feature_flags_check_flag_key(value: Any) -> list[str]:
    """Field policy for Flag Key inside Feature Flags."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Flag Key is required on Feature Flags.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Flag Key is zero; confirm the Feature Flags case.')
        if number > 9_000_000_000:
            notes.append('Flag Key exceeds the Feature Flags ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Flag Key must be YYYY-MM-DD for Feature Flags.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Flag Key is longer than the Feature Flags ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Flag Key placeholder values are not allowed on Feature Flags.')
    return notes


def feature_flags_normalize_flag_key(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def feature_flags_describe_flag_key() -> str:
    required = 'required' if True else 'optional'
    return 'Flag Key is a ' + required + ' str field on Feature Flags (feature_flags).'


def feature_flags_check_description(value: Any) -> list[str]:
    """Field policy for Description inside Feature Flags."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Description is required on Feature Flags.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Description is zero; confirm the Feature Flags case.')
        if number > 9_000_000_000:
            notes.append('Description exceeds the Feature Flags ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Description must be YYYY-MM-DD for Feature Flags.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Description is longer than the Feature Flags ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Description placeholder values are not allowed on Feature Flags.')
    return notes


def feature_flags_normalize_description(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def feature_flags_describe_description() -> str:
    required = 'required' if True else 'optional'
    return 'Description is a ' + required + ' str field on Feature Flags (feature_flags).'


def feature_flags_check_percent(value: Any) -> list[str]:
    """Field policy for Percent inside Feature Flags."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Percent is required on Feature Flags.')
        return notes
    if 'int' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Percent is zero; confirm the Feature Flags case.')
        if number > 9_000_000_000:
            notes.append('Percent exceeds the Feature Flags ceiling.')
        return notes
    if 'int' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Percent must be YYYY-MM-DD for Feature Flags.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Percent is longer than the Feature Flags ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Percent placeholder values are not allowed on Feature Flags.')
    return notes


def feature_flags_normalize_percent(value: Any) -> Any:
    if 'int' == 'int':
        return _as_int(value)
    if 'int' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def feature_flags_describe_percent() -> str:
    required = 'required' if True else 'optional'
    return 'Percent is a ' + required + ' int field on Feature Flags (feature_flags).'


def feature_flags_check_owner(value: Any) -> list[str]:
    """Field policy for Owner inside Feature Flags."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Owner is required on Feature Flags.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Owner is zero; confirm the Feature Flags case.')
        if number > 9_000_000_000:
            notes.append('Owner exceeds the Feature Flags ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Owner must be YYYY-MM-DD for Feature Flags.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Owner is longer than the Feature Flags ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Owner placeholder values are not allowed on Feature Flags.')
    return notes


def feature_flags_normalize_owner(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def feature_flags_describe_owner() -> str:
    required = 'required' if True else 'optional'
    return 'Owner is a ' + required + ' str field on Feature Flags (feature_flags).'


def feature_flags_check_status(value: Any) -> list[str]:
    """Field policy for Status inside Feature Flags."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Status is required on Feature Flags.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Status is zero; confirm the Feature Flags case.')
        if number > 9_000_000_000:
            notes.append('Status exceeds the Feature Flags ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Status must be YYYY-MM-DD for Feature Flags.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Status is longer than the Feature Flags ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Status placeholder values are not allowed on Feature Flags.')
    return notes


def feature_flags_normalize_status(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def feature_flags_describe_status() -> str:
    required = 'required' if True else 'optional'
    return 'Status is a ' + required + ' str field on Feature Flags (feature_flags).'


FIELD_CHECKS_FEATURE_FLAGS = {
    'flag_key': feature_flags_check_flag_key,
    'description': feature_flags_check_description,
    'percent': feature_flags_check_percent,
    'owner': feature_flags_check_owner,
    'status': feature_flags_check_status,
}


def feature_flags_run_field_checks(row: dict[str, Any]) -> list[str]:
    found: list[str] = []
    for name, checker in FIELD_CHECKS_FEATURE_FLAGS.items():
        found.extend(checker(row.get(name)))
    return found


def feature_flags_policy_card(row: dict[str, Any]) -> dict[str, Any]:
    return {
        'domain': DOMAIN_KEY,
        'title': DOMAIN_TITLE,
        'band': feature_flags_risk_band(row),
        'owner': feature_flags_owner_hint(row),
        'sla_hours': feature_flags_sla_hours(row),
        'exceptions': feature_flags_exception_needed(row),
        'freeze': feature_flags_freeze_window(row),
        'violations': policy.collect(row) + feature_flags_run_field_checks(row),
        'summary': feature_flags_summary_line(row),
    }

