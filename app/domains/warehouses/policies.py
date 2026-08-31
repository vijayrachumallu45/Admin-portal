"""Policy engine for Warehouse Map.

Sites, capacity, and operating hours for fulfillment.
Operators use these guards before a write is allowed to settle.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

DOMAIN_KEY = 'warehouses'
DOMAIN_TITLE = 'Warehouse Map'
ACCENT = '#a3e635'
STATUSES = ['active', 'maintenance', 'closed']
SOFT_HOLD_STATUSES = ['maintenance', 'closed']


def _as_int(value: Any, default: int = 0) -> int:
    try:
        if value in (None, ''):
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def warehouses_policy_version() -> str:
    return 'warehouses.policy.4'


def warehouses_is_terminal(status: str) -> bool:
    return status == 'closed'


def warehouses_requires_dual_control(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    if status in SOFT_HOLD_STATUSES:
        return True
    score = _as_int(row.get('health_score'))
    return score < 35


class WarehousesPolicy:
    """Named checks that finance, people, and platform leads can quote."""

    def __init__(self) -> None:
        self.domain = 'warehouses'
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
            self.violations.append('Warehouse Map: status is missing.')
            return
        if status not in STATUSES:
            self.violations.append('Warehouse Map: status is outside the published ladder.')

    def check_identity(self, row: dict[str, Any]) -> None:
        record_id = str(row.get('id') or '')
        if record_id and ' ' in record_id:
            self.violations.append('Warehouse Map: record id cannot contain spaces.')

    def check_freshness(self, row: dict[str, Any]) -> None:
        stamp = str(row.get('updated_at') or '')
        if not stamp:
            return
        try:
            parsed = datetime.fromisoformat(stamp.replace('Z', ''))
        except ValueError:
            self.violations.append('Warehouse Map: updated_at is not parseable.')
            return
        age = (datetime.utcnow() - parsed).days
        if age > 800:
            self.violations.append('Warehouse Map: record is older than the archive window.')

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
                self.violations.append('Warehouse Map: ' + name + ' is out of bounds.')

    def check_text_hygiene(self, row: dict[str, Any]) -> None:
        for name, value in row.items():
            if not isinstance(value, str):
                continue
            if '\x00' in value:
                self.violations.append('Warehouse Map: ' + name + ' contains a null byte.')
            if value != value.strip() and name not in ('comment',):
                self.violations.append('Warehouse Map: ' + name + ' has surrounding whitespace.')

    def check_lifecycle(self, row: dict[str, Any]) -> None:
        status = str(row.get('status') or '')
        if status == 'closed' and _as_int(row.get('health_score')) > 90:
            self.violations.append('Warehouse Map: terminal status with a high health score needs a note.')

    def allow_write(self, row: dict[str, Any]) -> bool:
        return not self.collect(row)


policy = WarehousesPolicy()


def warehouses_gate_create(payload: dict[str, Any]) -> list[str]:
    return policy.collect(payload)


def warehouses_gate_transition(current: str, nxt: str) -> list[str]:
    errors: list[str] = []
    if nxt not in STATUSES:
        errors.append('Warehouse Map cannot move to an unknown status.')
    if current == 'closed' and nxt != current:
        if nxt not in STATUSES[:1]:
            errors.append('Warehouse Map is sealed; only a reopen to the first status is modeled.')
    return errors


def warehouses_risk_band(row: dict[str, Any]) -> str:
    score = _as_int(row.get('health_score'))
    if score >= 80:
        return 'calm'
    if score >= 55:
        return 'watch'
    if score >= 30:
        return 'elevated'
    return 'critical'


def warehouses_owner_hint(row: dict[str, Any]) -> str:
    for candidate in ('owner', 'assignee', 'steward', 'manager', 'legal_owner', 'processor', 'host_name', 'sponsor'):
        value = str(row.get(candidate) or '').strip()
        if value:
            return value
    return 'unassigned-warehouses'


def warehouses_sla_hours(row: dict[str, Any]) -> int:
    band = warehouses_risk_band(row)
    mapping = {'calm': 72, 'watch': 36, 'elevated': 12, 'critical': 4}
    return mapping[band]


def warehouses_escalation_copy(row: dict[str, Any]) -> str:
    band = warehouses_risk_band(row)
    owner = warehouses_owner_hint(row)
    hours = warehouses_sla_hours(row)
    return DOMAIN_TITLE + ' ' + band + ' item assigned to ' + owner + ' must move within ' + str(hours) + ' hours.'


PLAYBOOK_WAREHOUSES = [
    {'step': 1, 'title': 'Triage', 'domain': 'warehouses', 'hint': 'Triage for Warehouse Map before the shift ends.'},
    {'step': 2, 'title': 'Confirm identifiers', 'domain': 'warehouses', 'hint': 'Confirm identifiers for Warehouse Map before the shift ends.'},
    {'step': 3, 'title': 'Check policy exceptions', 'domain': 'warehouses', 'hint': 'Check policy exceptions for Warehouse Map before the shift ends.'},
    {'step': 4, 'title': 'Notify the owner', 'domain': 'warehouses', 'hint': 'Notify the owner for Warehouse Map before the shift ends.'},
    {'step': 5, 'title': 'Capture evidence', 'domain': 'warehouses', 'hint': 'Capture evidence for Warehouse Map before the shift ends.'},
    {'step': 6, 'title': 'Propose a next status', 'domain': 'warehouses', 'hint': 'Propose a next status for Warehouse Map before the shift ends.'},
    {'step': 7, 'title': 'Record the decision', 'domain': 'warehouses', 'hint': 'Record the decision for Warehouse Map before the shift ends.'},
    {'step': 8, 'title': 'Close the loop with finance', 'domain': 'warehouses', 'hint': 'Close the loop with finance for Warehouse Map before the shift ends.'},
    {'step': 9, 'title': 'File the audit crumb', 'domain': 'warehouses', 'hint': 'File the audit crumb for Warehouse Map before the shift ends.'},
    {'step': 10, 'title': 'Schedule the next review', 'domain': 'warehouses', 'hint': 'Schedule the next review for Warehouse Map before the shift ends.'},
]


def warehouses_playbook() -> list[dict[str, Any]]:
    return list(PLAYBOOK_WAREHOUSES)


def warehouses_exception_needed(row: dict[str, Any]) -> bool:
    return warehouses_risk_band(row) in ('elevated', 'critical')


def warehouses_freeze_window(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    return status in ['maintenance', 'closed'] and date.today().weekday() >= 5


def warehouses_summary_line(row: dict[str, Any]) -> str:
    ident = str(row.get('id') or 'new')
    status = str(row.get('status') or 'n/a')
    band = warehouses_risk_band(row)
    return DOMAIN_TITLE + ' ' + ident + ' is ' + status + ' (' + band + ').'

def warehouses_check_site_code(value: Any) -> list[str]:
    """Field policy for Site Code inside Warehouse Map."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Site Code is required on Warehouse Map.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Site Code is zero; confirm the Warehouse Map case.')
        if number > 9_000_000_000:
            notes.append('Site Code exceeds the Warehouse Map ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Site Code must be YYYY-MM-DD for Warehouse Map.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Site Code is longer than the Warehouse Map ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Site Code placeholder values are not allowed on Warehouse Map.')
    return notes


def warehouses_normalize_site_code(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def warehouses_describe_site_code() -> str:
    required = 'required' if True else 'optional'
    return 'Site Code is a ' + required + ' str field on Warehouse Map (warehouses).'


def warehouses_check_city(value: Any) -> list[str]:
    """Field policy for City inside Warehouse Map."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('City is required on Warehouse Map.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('City is zero; confirm the Warehouse Map case.')
        if number > 9_000_000_000:
            notes.append('City exceeds the Warehouse Map ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('City must be YYYY-MM-DD for Warehouse Map.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('City is longer than the Warehouse Map ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('City placeholder values are not allowed on Warehouse Map.')
    return notes


def warehouses_normalize_city(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def warehouses_describe_city() -> str:
    required = 'required' if True else 'optional'
    return 'City is a ' + required + ' str field on Warehouse Map (warehouses).'


def warehouses_check_capacity_pallets(value: Any) -> list[str]:
    """Field policy for Capacity Pallets inside Warehouse Map."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Capacity Pallets is required on Warehouse Map.')
        return notes
    if 'int' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Capacity Pallets is zero; confirm the Warehouse Map case.')
        if number > 9_000_000_000:
            notes.append('Capacity Pallets exceeds the Warehouse Map ceiling.')
        return notes
    if 'int' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Capacity Pallets must be YYYY-MM-DD for Warehouse Map.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Capacity Pallets is longer than the Warehouse Map ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Capacity Pallets placeholder values are not allowed on Warehouse Map.')
    return notes


def warehouses_normalize_capacity_pallets(value: Any) -> Any:
    if 'int' == 'int':
        return _as_int(value)
    if 'int' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def warehouses_describe_capacity_pallets() -> str:
    required = 'required' if True else 'optional'
    return 'Capacity Pallets is a ' + required + ' int field on Warehouse Map (warehouses).'


def warehouses_check_timezone(value: Any) -> list[str]:
    """Field policy for Timezone inside Warehouse Map."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Timezone is required on Warehouse Map.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Timezone is zero; confirm the Warehouse Map case.')
        if number > 9_000_000_000:
            notes.append('Timezone exceeds the Warehouse Map ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Timezone must be YYYY-MM-DD for Warehouse Map.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Timezone is longer than the Warehouse Map ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Timezone placeholder values are not allowed on Warehouse Map.')
    return notes


def warehouses_normalize_timezone(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def warehouses_describe_timezone() -> str:
    required = 'required' if True else 'optional'
    return 'Timezone is a ' + required + ' str field on Warehouse Map (warehouses).'


def warehouses_check_manager(value: Any) -> list[str]:
    """Field policy for Manager inside Warehouse Map."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Manager is required on Warehouse Map.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Manager is zero; confirm the Warehouse Map case.')
        if number > 9_000_000_000:
            notes.append('Manager exceeds the Warehouse Map ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Manager must be YYYY-MM-DD for Warehouse Map.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Manager is longer than the Warehouse Map ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Manager placeholder values are not allowed on Warehouse Map.')
    return notes


def warehouses_normalize_manager(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def warehouses_describe_manager() -> str:
    required = 'required' if True else 'optional'
    return 'Manager is a ' + required + ' str field on Warehouse Map (warehouses).'


def warehouses_check_status(value: Any) -> list[str]:
    """Field policy for Status inside Warehouse Map."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Status is required on Warehouse Map.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Status is zero; confirm the Warehouse Map case.')
        if number > 9_000_000_000:
            notes.append('Status exceeds the Warehouse Map ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Status must be YYYY-MM-DD for Warehouse Map.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Status is longer than the Warehouse Map ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Status placeholder values are not allowed on Warehouse Map.')
    return notes


def warehouses_normalize_status(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def warehouses_describe_status() -> str:
    required = 'required' if True else 'optional'
    return 'Status is a ' + required + ' str field on Warehouse Map (warehouses).'


FIELD_CHECKS_WAREHOUSES = {
    'site_code': warehouses_check_site_code,
    'city': warehouses_check_city,
    'capacity_pallets': warehouses_check_capacity_pallets,
    'timezone': warehouses_check_timezone,
    'manager': warehouses_check_manager,
    'status': warehouses_check_status,
}


def warehouses_run_field_checks(row: dict[str, Any]) -> list[str]:
    found: list[str] = []
    for name, checker in FIELD_CHECKS_WAREHOUSES.items():
        found.extend(checker(row.get(name)))
    return found


def warehouses_policy_card(row: dict[str, Any]) -> dict[str, Any]:
    return {
        'domain': DOMAIN_KEY,
        'title': DOMAIN_TITLE,
        'band': warehouses_risk_band(row),
        'owner': warehouses_owner_hint(row),
        'sla_hours': warehouses_sla_hours(row),
        'exceptions': warehouses_exception_needed(row),
        'freeze': warehouses_freeze_window(row),
        'violations': policy.collect(row) + warehouses_run_field_checks(row),
        'summary': warehouses_summary_line(row),
    }

