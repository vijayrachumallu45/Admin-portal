"""Policy engine for Capacity Plans.

Headcount and infrastructure envelopes by quarter.
Operators use these guards before a write is allowed to settle.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

DOMAIN_KEY = 'capacity_plans'
DOMAIN_TITLE = 'Capacity Plans'
ACCENT = '#93c5fd'
STATUSES = ['draft', 'approved', 'tracking']
SOFT_HOLD_STATUSES = ['approved', 'tracking']


def _as_int(value: Any, default: int = 0) -> int:
    try:
        if value in (None, ''):
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def capacity_plans_policy_version() -> str:
    return 'capacity_plans.policy.4'


def capacity_plans_is_terminal(status: str) -> bool:
    return status == 'tracking'


def capacity_plans_requires_dual_control(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    if status in SOFT_HOLD_STATUSES:
        return True
    score = _as_int(row.get('health_score'))
    return score < 35


class CapacityPlansPolicy:
    """Named checks that finance, people, and platform leads can quote."""

    def __init__(self) -> None:
        self.domain = 'capacity_plans'
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
            self.violations.append('Capacity Plans: status is missing.')
            return
        if status not in STATUSES:
            self.violations.append('Capacity Plans: status is outside the published ladder.')

    def check_identity(self, row: dict[str, Any]) -> None:
        record_id = str(row.get('id') or '')
        if record_id and ' ' in record_id:
            self.violations.append('Capacity Plans: record id cannot contain spaces.')

    def check_freshness(self, row: dict[str, Any]) -> None:
        stamp = str(row.get('updated_at') or '')
        if not stamp:
            return
        try:
            parsed = datetime.fromisoformat(stamp.replace('Z', ''))
        except ValueError:
            self.violations.append('Capacity Plans: updated_at is not parseable.')
            return
        age = (datetime.utcnow() - parsed).days
        if age > 800:
            self.violations.append('Capacity Plans: record is older than the archive window.')

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
                self.violations.append('Capacity Plans: ' + name + ' is out of bounds.')

    def check_text_hygiene(self, row: dict[str, Any]) -> None:
        for name, value in row.items():
            if not isinstance(value, str):
                continue
            if '\x00' in value:
                self.violations.append('Capacity Plans: ' + name + ' contains a null byte.')
            if value != value.strip() and name not in ('comment',):
                self.violations.append('Capacity Plans: ' + name + ' has surrounding whitespace.')

    def check_lifecycle(self, row: dict[str, Any]) -> None:
        status = str(row.get('status') or '')
        if status == 'tracking' and _as_int(row.get('health_score')) > 90:
            self.violations.append('Capacity Plans: terminal status with a high health score needs a note.')

    def allow_write(self, row: dict[str, Any]) -> bool:
        return not self.collect(row)


policy = CapacityPlansPolicy()


def capacity_plans_gate_create(payload: dict[str, Any]) -> list[str]:
    return policy.collect(payload)


def capacity_plans_gate_transition(current: str, nxt: str) -> list[str]:
    errors: list[str] = []
    if nxt not in STATUSES:
        errors.append('Capacity Plans cannot move to an unknown status.')
    if current == 'tracking' and nxt != current:
        if nxt not in STATUSES[:1]:
            errors.append('Capacity Plans is sealed; only a reopen to the first status is modeled.')
    return errors


def capacity_plans_risk_band(row: dict[str, Any]) -> str:
    score = _as_int(row.get('health_score'))
    if score >= 80:
        return 'calm'
    if score >= 55:
        return 'watch'
    if score >= 30:
        return 'elevated'
    return 'critical'


def capacity_plans_owner_hint(row: dict[str, Any]) -> str:
    for candidate in ('owner', 'assignee', 'steward', 'manager', 'legal_owner', 'processor', 'host_name', 'sponsor'):
        value = str(row.get(candidate) or '').strip()
        if value:
            return value
    return 'unassigned-capacity_plans'


def capacity_plans_sla_hours(row: dict[str, Any]) -> int:
    band = capacity_plans_risk_band(row)
    mapping = {'calm': 72, 'watch': 36, 'elevated': 12, 'critical': 4}
    return mapping[band]


def capacity_plans_escalation_copy(row: dict[str, Any]) -> str:
    band = capacity_plans_risk_band(row)
    owner = capacity_plans_owner_hint(row)
    hours = capacity_plans_sla_hours(row)
    return DOMAIN_TITLE + ' ' + band + ' item assigned to ' + owner + ' must move within ' + str(hours) + ' hours.'


PLAYBOOK_CAPACITY_PLANS = [
    {'step': 1, 'title': 'Triage', 'domain': 'capacity_plans', 'hint': 'Triage for Capacity Plans before the shift ends.'},
    {'step': 2, 'title': 'Confirm identifiers', 'domain': 'capacity_plans', 'hint': 'Confirm identifiers for Capacity Plans before the shift ends.'},
    {'step': 3, 'title': 'Check policy exceptions', 'domain': 'capacity_plans', 'hint': 'Check policy exceptions for Capacity Plans before the shift ends.'},
    {'step': 4, 'title': 'Notify the owner', 'domain': 'capacity_plans', 'hint': 'Notify the owner for Capacity Plans before the shift ends.'},
    {'step': 5, 'title': 'Capture evidence', 'domain': 'capacity_plans', 'hint': 'Capture evidence for Capacity Plans before the shift ends.'},
    {'step': 6, 'title': 'Propose a next status', 'domain': 'capacity_plans', 'hint': 'Propose a next status for Capacity Plans before the shift ends.'},
    {'step': 7, 'title': 'Record the decision', 'domain': 'capacity_plans', 'hint': 'Record the decision for Capacity Plans before the shift ends.'},
    {'step': 8, 'title': 'Close the loop with finance', 'domain': 'capacity_plans', 'hint': 'Close the loop with finance for Capacity Plans before the shift ends.'},
    {'step': 9, 'title': 'File the audit crumb', 'domain': 'capacity_plans', 'hint': 'File the audit crumb for Capacity Plans before the shift ends.'},
    {'step': 10, 'title': 'Schedule the next review', 'domain': 'capacity_plans', 'hint': 'Schedule the next review for Capacity Plans before the shift ends.'},
]


def capacity_plans_playbook() -> list[dict[str, Any]]:
    return list(PLAYBOOK_CAPACITY_PLANS)


def capacity_plans_exception_needed(row: dict[str, Any]) -> bool:
    return capacity_plans_risk_band(row) in ('elevated', 'critical')


def capacity_plans_freeze_window(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    return status in ['approved', 'tracking'] and date.today().weekday() >= 5


def capacity_plans_summary_line(row: dict[str, Any]) -> str:
    ident = str(row.get('id') or 'new')
    status = str(row.get('status') or 'n/a')
    band = capacity_plans_risk_band(row)
    return DOMAIN_TITLE + ' ' + ident + ' is ' + status + ' (' + band + ').'

def capacity_plans_check_plan_code(value: Any) -> list[str]:
    """Field policy for Plan Code inside Capacity Plans."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Plan Code is required on Capacity Plans.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Plan Code is zero; confirm the Capacity Plans case.')
        if number > 9_000_000_000:
            notes.append('Plan Code exceeds the Capacity Plans ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Plan Code must be YYYY-MM-DD for Capacity Plans.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Plan Code is longer than the Capacity Plans ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Plan Code placeholder values are not allowed on Capacity Plans.')
    return notes


def capacity_plans_normalize_plan_code(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def capacity_plans_describe_plan_code() -> str:
    required = 'required' if True else 'optional'
    return 'Plan Code is a ' + required + ' str field on Capacity Plans (capacity_plans).'


def capacity_plans_check_quarter(value: Any) -> list[str]:
    """Field policy for Quarter inside Capacity Plans."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Quarter is required on Capacity Plans.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Quarter is zero; confirm the Capacity Plans case.')
        if number > 9_000_000_000:
            notes.append('Quarter exceeds the Capacity Plans ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Quarter must be YYYY-MM-DD for Capacity Plans.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Quarter is longer than the Capacity Plans ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Quarter placeholder values are not allowed on Capacity Plans.')
    return notes


def capacity_plans_normalize_quarter(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def capacity_plans_describe_quarter() -> str:
    required = 'required' if True else 'optional'
    return 'Quarter is a ' + required + ' str field on Capacity Plans (capacity_plans).'


def capacity_plans_check_seats(value: Any) -> list[str]:
    """Field policy for Seats inside Capacity Plans."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Seats is required on Capacity Plans.')
        return notes
    if 'int' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Seats is zero; confirm the Capacity Plans case.')
        if number > 9_000_000_000:
            notes.append('Seats exceeds the Capacity Plans ceiling.')
        return notes
    if 'int' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Seats must be YYYY-MM-DD for Capacity Plans.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Seats is longer than the Capacity Plans ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Seats placeholder values are not allowed on Capacity Plans.')
    return notes


def capacity_plans_normalize_seats(value: Any) -> Any:
    if 'int' == 'int':
        return _as_int(value)
    if 'int' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def capacity_plans_describe_seats() -> str:
    required = 'required' if True else 'optional'
    return 'Seats is a ' + required + ' int field on Capacity Plans (capacity_plans).'


def capacity_plans_check_owner(value: Any) -> list[str]:
    """Field policy for Owner inside Capacity Plans."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Owner is required on Capacity Plans.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Owner is zero; confirm the Capacity Plans case.')
        if number > 9_000_000_000:
            notes.append('Owner exceeds the Capacity Plans ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Owner must be YYYY-MM-DD for Capacity Plans.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Owner is longer than the Capacity Plans ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Owner placeholder values are not allowed on Capacity Plans.')
    return notes


def capacity_plans_normalize_owner(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def capacity_plans_describe_owner() -> str:
    required = 'required' if True else 'optional'
    return 'Owner is a ' + required + ' str field on Capacity Plans (capacity_plans).'


def capacity_plans_check_status(value: Any) -> list[str]:
    """Field policy for Status inside Capacity Plans."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Status is required on Capacity Plans.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Status is zero; confirm the Capacity Plans case.')
        if number > 9_000_000_000:
            notes.append('Status exceeds the Capacity Plans ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Status must be YYYY-MM-DD for Capacity Plans.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Status is longer than the Capacity Plans ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Status placeholder values are not allowed on Capacity Plans.')
    return notes


def capacity_plans_normalize_status(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def capacity_plans_describe_status() -> str:
    required = 'required' if True else 'optional'
    return 'Status is a ' + required + ' str field on Capacity Plans (capacity_plans).'


FIELD_CHECKS_CAPACITY_PLANS = {
    'plan_code': capacity_plans_check_plan_code,
    'quarter': capacity_plans_check_quarter,
    'seats': capacity_plans_check_seats,
    'owner': capacity_plans_check_owner,
    'status': capacity_plans_check_status,
}


def capacity_plans_run_field_checks(row: dict[str, Any]) -> list[str]:
    found: list[str] = []
    for name, checker in FIELD_CHECKS_CAPACITY_PLANS.items():
        found.extend(checker(row.get(name)))
    return found


def capacity_plans_policy_card(row: dict[str, Any]) -> dict[str, Any]:
    return {
        'domain': DOMAIN_KEY,
        'title': DOMAIN_TITLE,
        'band': capacity_plans_risk_band(row),
        'owner': capacity_plans_owner_hint(row),
        'sla_hours': capacity_plans_sla_hours(row),
        'exceptions': capacity_plans_exception_needed(row),
        'freeze': capacity_plans_freeze_window(row),
        'violations': policy.collect(row) + capacity_plans_run_field_checks(row),
        'summary': capacity_plans_summary_line(row),
    }

