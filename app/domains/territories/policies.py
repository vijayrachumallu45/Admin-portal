"""Policy engine for Sales Territories.

Named patches with quota and coverage owners.
Operators use these guards before a write is allowed to settle.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

DOMAIN_KEY = 'territories'
DOMAIN_TITLE = 'Sales Territories'
ACCENT = '#6ee7b7'
STATUSES = ['open', 'covered', 'split']
SOFT_HOLD_STATUSES = ['covered', 'split']


def _as_int(value: Any, default: int = 0) -> int:
    try:
        if value in (None, ''):
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def territories_policy_version() -> str:
    return 'territories.policy.4'


def territories_is_terminal(status: str) -> bool:
    return status == 'split'


def territories_requires_dual_control(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    if status in SOFT_HOLD_STATUSES:
        return True
    score = _as_int(row.get('health_score'))
    return score < 35


class TerritoriesPolicy:
    """Named checks that finance, people, and platform leads can quote."""

    def __init__(self) -> None:
        self.domain = 'territories'
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
            self.violations.append('Sales Territories: status is missing.')
            return
        if status not in STATUSES:
            self.violations.append('Sales Territories: status is outside the published ladder.')

    def check_identity(self, row: dict[str, Any]) -> None:
        record_id = str(row.get('id') or '')
        if record_id and ' ' in record_id:
            self.violations.append('Sales Territories: record id cannot contain spaces.')

    def check_freshness(self, row: dict[str, Any]) -> None:
        stamp = str(row.get('updated_at') or '')
        if not stamp:
            return
        try:
            parsed = datetime.fromisoformat(stamp.replace('Z', ''))
        except ValueError:
            self.violations.append('Sales Territories: updated_at is not parseable.')
            return
        age = (datetime.utcnow() - parsed).days
        if age > 800:
            self.violations.append('Sales Territories: record is older than the archive window.')

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
                self.violations.append('Sales Territories: ' + name + ' is out of bounds.')

    def check_text_hygiene(self, row: dict[str, Any]) -> None:
        for name, value in row.items():
            if not isinstance(value, str):
                continue
            if '\x00' in value:
                self.violations.append('Sales Territories: ' + name + ' contains a null byte.')
            if value != value.strip() and name not in ('comment',):
                self.violations.append('Sales Territories: ' + name + ' has surrounding whitespace.')

    def check_lifecycle(self, row: dict[str, Any]) -> None:
        status = str(row.get('status') or '')
        if status == 'split' and _as_int(row.get('health_score')) > 90:
            self.violations.append('Sales Territories: terminal status with a high health score needs a note.')

    def allow_write(self, row: dict[str, Any]) -> bool:
        return not self.collect(row)


policy = TerritoriesPolicy()


def territories_gate_create(payload: dict[str, Any]) -> list[str]:
    return policy.collect(payload)


def territories_gate_transition(current: str, nxt: str) -> list[str]:
    errors: list[str] = []
    if nxt not in STATUSES:
        errors.append('Sales Territories cannot move to an unknown status.')
    if current == 'split' and nxt != current:
        if nxt not in STATUSES[:1]:
            errors.append('Sales Territories is sealed; only a reopen to the first status is modeled.')
    return errors


def territories_risk_band(row: dict[str, Any]) -> str:
    score = _as_int(row.get('health_score'))
    if score >= 80:
        return 'calm'
    if score >= 55:
        return 'watch'
    if score >= 30:
        return 'elevated'
    return 'critical'


def territories_owner_hint(row: dict[str, Any]) -> str:
    for candidate in ('owner', 'assignee', 'steward', 'manager', 'legal_owner', 'processor', 'host_name', 'sponsor'):
        value = str(row.get(candidate) or '').strip()
        if value:
            return value
    return 'unassigned-territories'


def territories_sla_hours(row: dict[str, Any]) -> int:
    band = territories_risk_band(row)
    mapping = {'calm': 72, 'watch': 36, 'elevated': 12, 'critical': 4}
    return mapping[band]


def territories_escalation_copy(row: dict[str, Any]) -> str:
    band = territories_risk_band(row)
    owner = territories_owner_hint(row)
    hours = territories_sla_hours(row)
    return DOMAIN_TITLE + ' ' + band + ' item assigned to ' + owner + ' must move within ' + str(hours) + ' hours.'


PLAYBOOK_TERRITORIES = [
    {'step': 1, 'title': 'Triage', 'domain': 'territories', 'hint': 'Triage for Sales Territories before the shift ends.'},
    {'step': 2, 'title': 'Confirm identifiers', 'domain': 'territories', 'hint': 'Confirm identifiers for Sales Territories before the shift ends.'},
    {'step': 3, 'title': 'Check policy exceptions', 'domain': 'territories', 'hint': 'Check policy exceptions for Sales Territories before the shift ends.'},
    {'step': 4, 'title': 'Notify the owner', 'domain': 'territories', 'hint': 'Notify the owner for Sales Territories before the shift ends.'},
    {'step': 5, 'title': 'Capture evidence', 'domain': 'territories', 'hint': 'Capture evidence for Sales Territories before the shift ends.'},
    {'step': 6, 'title': 'Propose a next status', 'domain': 'territories', 'hint': 'Propose a next status for Sales Territories before the shift ends.'},
    {'step': 7, 'title': 'Record the decision', 'domain': 'territories', 'hint': 'Record the decision for Sales Territories before the shift ends.'},
    {'step': 8, 'title': 'Close the loop with finance', 'domain': 'territories', 'hint': 'Close the loop with finance for Sales Territories before the shift ends.'},
    {'step': 9, 'title': 'File the audit crumb', 'domain': 'territories', 'hint': 'File the audit crumb for Sales Territories before the shift ends.'},
    {'step': 10, 'title': 'Schedule the next review', 'domain': 'territories', 'hint': 'Schedule the next review for Sales Territories before the shift ends.'},
]


def territories_playbook() -> list[dict[str, Any]]:
    return list(PLAYBOOK_TERRITORIES)


def territories_exception_needed(row: dict[str, Any]) -> bool:
    return territories_risk_band(row) in ('elevated', 'critical')


def territories_freeze_window(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    return status in ['covered', 'split'] and date.today().weekday() >= 5


def territories_summary_line(row: dict[str, Any]) -> str:
    ident = str(row.get('id') or 'new')
    status = str(row.get('status') or 'n/a')
    band = territories_risk_band(row)
    return DOMAIN_TITLE + ' ' + ident + ' is ' + status + ' (' + band + ').'

def territories_check_territory_code(value: Any) -> list[str]:
    """Field policy for Territory Code inside Sales Territories."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Territory Code is required on Sales Territories.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Territory Code is zero; confirm the Sales Territories case.')
        if number > 9_000_000_000:
            notes.append('Territory Code exceeds the Sales Territories ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Territory Code must be YYYY-MM-DD for Sales Territories.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Territory Code is longer than the Sales Territories ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Territory Code placeholder values are not allowed on Sales Territories.')
    return notes


def territories_normalize_territory_code(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def territories_describe_territory_code() -> str:
    required = 'required' if True else 'optional'
    return 'Territory Code is a ' + required + ' str field on Sales Territories (territories).'


def territories_check_name(value: Any) -> list[str]:
    """Field policy for Name inside Sales Territories."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Name is required on Sales Territories.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Name is zero; confirm the Sales Territories case.')
        if number > 9_000_000_000:
            notes.append('Name exceeds the Sales Territories ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Name must be YYYY-MM-DD for Sales Territories.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Name is longer than the Sales Territories ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Name placeholder values are not allowed on Sales Territories.')
    return notes


def territories_normalize_name(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def territories_describe_name() -> str:
    required = 'required' if True else 'optional'
    return 'Name is a ' + required + ' str field on Sales Territories (territories).'


def territories_check_owner(value: Any) -> list[str]:
    """Field policy for Owner inside Sales Territories."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Owner is required on Sales Territories.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Owner is zero; confirm the Sales Territories case.')
        if number > 9_000_000_000:
            notes.append('Owner exceeds the Sales Territories ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Owner must be YYYY-MM-DD for Sales Territories.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Owner is longer than the Sales Territories ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Owner placeholder values are not allowed on Sales Territories.')
    return notes


def territories_normalize_owner(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def territories_describe_owner() -> str:
    required = 'required' if True else 'optional'
    return 'Owner is a ' + required + ' str field on Sales Territories (territories).'


def territories_check_quota_cents(value: Any) -> list[str]:
    """Field policy for Quota Cents inside Sales Territories."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Quota Cents is required on Sales Territories.')
        return notes
    if 'int' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Quota Cents is zero; confirm the Sales Territories case.')
        if number > 9_000_000_000:
            notes.append('Quota Cents exceeds the Sales Territories ceiling.')
        return notes
    if 'int' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Quota Cents must be YYYY-MM-DD for Sales Territories.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Quota Cents is longer than the Sales Territories ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Quota Cents placeholder values are not allowed on Sales Territories.')
    return notes


def territories_normalize_quota_cents(value: Any) -> Any:
    if 'int' == 'int':
        return _as_int(value)
    if 'int' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def territories_describe_quota_cents() -> str:
    required = 'required' if True else 'optional'
    return 'Quota Cents is a ' + required + ' int field on Sales Territories (territories).'


def territories_check_status(value: Any) -> list[str]:
    """Field policy for Status inside Sales Territories."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Status is required on Sales Territories.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Status is zero; confirm the Sales Territories case.')
        if number > 9_000_000_000:
            notes.append('Status exceeds the Sales Territories ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Status must be YYYY-MM-DD for Sales Territories.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Status is longer than the Sales Territories ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Status placeholder values are not allowed on Sales Territories.')
    return notes


def territories_normalize_status(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def territories_describe_status() -> str:
    required = 'required' if True else 'optional'
    return 'Status is a ' + required + ' str field on Sales Territories (territories).'


FIELD_CHECKS_TERRITORIES = {
    'territory_code': territories_check_territory_code,
    'name': territories_check_name,
    'owner': territories_check_owner,
    'quota_cents': territories_check_quota_cents,
    'status': territories_check_status,
}


def territories_run_field_checks(row: dict[str, Any]) -> list[str]:
    found: list[str] = []
    for name, checker in FIELD_CHECKS_TERRITORIES.items():
        found.extend(checker(row.get(name)))
    return found


def territories_policy_card(row: dict[str, Any]) -> dict[str, Any]:
    return {
        'domain': DOMAIN_KEY,
        'title': DOMAIN_TITLE,
        'band': territories_risk_band(row),
        'owner': territories_owner_hint(row),
        'sla_hours': territories_sla_hours(row),
        'exceptions': territories_exception_needed(row),
        'freeze': territories_freeze_window(row),
        'violations': policy.collect(row) + territories_run_field_checks(row),
        'summary': territories_summary_line(row),
    }

