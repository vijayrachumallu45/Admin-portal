"""Policy engine for Inventory Lots.

Warehouse lots, reorder points, and quarantine holds.
Operators use these guards before a write is allowed to settle.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

DOMAIN_KEY = 'inventory_lots'
DOMAIN_TITLE = 'Inventory Lots'
ACCENT = '#22d3ee'
STATUSES = ['available', 'held', 'quarantine', 'depleted']
SOFT_HOLD_STATUSES = ['quarantine', 'depleted']


def _as_int(value: Any, default: int = 0) -> int:
    try:
        if value in (None, ''):
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def inventory_lots_policy_version() -> str:
    return 'inventory_lots.policy.4'


def inventory_lots_is_terminal(status: str) -> bool:
    return status == 'depleted'


def inventory_lots_requires_dual_control(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    if status in SOFT_HOLD_STATUSES:
        return True
    score = _as_int(row.get('health_score'))
    return score < 35


class InventoryLotsPolicy:
    """Named checks that finance, people, and platform leads can quote."""

    def __init__(self) -> None:
        self.domain = 'inventory_lots'
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
            self.violations.append('Inventory Lots: status is missing.')
            return
        if status not in STATUSES:
            self.violations.append('Inventory Lots: status is outside the published ladder.')

    def check_identity(self, row: dict[str, Any]) -> None:
        record_id = str(row.get('id') or '')
        if record_id and ' ' in record_id:
            self.violations.append('Inventory Lots: record id cannot contain spaces.')

    def check_freshness(self, row: dict[str, Any]) -> None:
        stamp = str(row.get('updated_at') or '')
        if not stamp:
            return
        try:
            parsed = datetime.fromisoformat(stamp.replace('Z', ''))
        except ValueError:
            self.violations.append('Inventory Lots: updated_at is not parseable.')
            return
        age = (datetime.utcnow() - parsed).days
        if age > 800:
            self.violations.append('Inventory Lots: record is older than the archive window.')

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
                self.violations.append('Inventory Lots: ' + name + ' is out of bounds.')

    def check_text_hygiene(self, row: dict[str, Any]) -> None:
        for name, value in row.items():
            if not isinstance(value, str):
                continue
            if '\x00' in value:
                self.violations.append('Inventory Lots: ' + name + ' contains a null byte.')
            if value != value.strip() and name not in ('comment',):
                self.violations.append('Inventory Lots: ' + name + ' has surrounding whitespace.')

    def check_lifecycle(self, row: dict[str, Any]) -> None:
        status = str(row.get('status') or '')
        if status == 'depleted' and _as_int(row.get('health_score')) > 90:
            self.violations.append('Inventory Lots: terminal status with a high health score needs a note.')

    def allow_write(self, row: dict[str, Any]) -> bool:
        return not self.collect(row)


policy = InventoryLotsPolicy()


def inventory_lots_gate_create(payload: dict[str, Any]) -> list[str]:
    return policy.collect(payload)


def inventory_lots_gate_transition(current: str, nxt: str) -> list[str]:
    errors: list[str] = []
    if nxt not in STATUSES:
        errors.append('Inventory Lots cannot move to an unknown status.')
    if current == 'depleted' and nxt != current:
        if nxt not in STATUSES[:1]:
            errors.append('Inventory Lots is sealed; only a reopen to the first status is modeled.')
    return errors


def inventory_lots_risk_band(row: dict[str, Any]) -> str:
    score = _as_int(row.get('health_score'))
    if score >= 80:
        return 'calm'
    if score >= 55:
        return 'watch'
    if score >= 30:
        return 'elevated'
    return 'critical'


def inventory_lots_owner_hint(row: dict[str, Any]) -> str:
    for candidate in ('owner', 'assignee', 'steward', 'manager', 'legal_owner', 'processor', 'host_name', 'sponsor'):
        value = str(row.get(candidate) or '').strip()
        if value:
            return value
    return 'unassigned-inventory_lots'


def inventory_lots_sla_hours(row: dict[str, Any]) -> int:
    band = inventory_lots_risk_band(row)
    mapping = {'calm': 72, 'watch': 36, 'elevated': 12, 'critical': 4}
    return mapping[band]


def inventory_lots_escalation_copy(row: dict[str, Any]) -> str:
    band = inventory_lots_risk_band(row)
    owner = inventory_lots_owner_hint(row)
    hours = inventory_lots_sla_hours(row)
    return DOMAIN_TITLE + ' ' + band + ' item assigned to ' + owner + ' must move within ' + str(hours) + ' hours.'


PLAYBOOK_INVENTORY_LOTS = [
    {'step': 1, 'title': 'Triage', 'domain': 'inventory_lots', 'hint': 'Triage for Inventory Lots before the shift ends.'},
    {'step': 2, 'title': 'Confirm identifiers', 'domain': 'inventory_lots', 'hint': 'Confirm identifiers for Inventory Lots before the shift ends.'},
    {'step': 3, 'title': 'Check policy exceptions', 'domain': 'inventory_lots', 'hint': 'Check policy exceptions for Inventory Lots before the shift ends.'},
    {'step': 4, 'title': 'Notify the owner', 'domain': 'inventory_lots', 'hint': 'Notify the owner for Inventory Lots before the shift ends.'},
    {'step': 5, 'title': 'Capture evidence', 'domain': 'inventory_lots', 'hint': 'Capture evidence for Inventory Lots before the shift ends.'},
    {'step': 6, 'title': 'Propose a next status', 'domain': 'inventory_lots', 'hint': 'Propose a next status for Inventory Lots before the shift ends.'},
    {'step': 7, 'title': 'Record the decision', 'domain': 'inventory_lots', 'hint': 'Record the decision for Inventory Lots before the shift ends.'},
    {'step': 8, 'title': 'Close the loop with finance', 'domain': 'inventory_lots', 'hint': 'Close the loop with finance for Inventory Lots before the shift ends.'},
    {'step': 9, 'title': 'File the audit crumb', 'domain': 'inventory_lots', 'hint': 'File the audit crumb for Inventory Lots before the shift ends.'},
    {'step': 10, 'title': 'Schedule the next review', 'domain': 'inventory_lots', 'hint': 'Schedule the next review for Inventory Lots before the shift ends.'},
]


def inventory_lots_playbook() -> list[dict[str, Any]]:
    return list(PLAYBOOK_INVENTORY_LOTS)


def inventory_lots_exception_needed(row: dict[str, Any]) -> bool:
    return inventory_lots_risk_band(row) in ('elevated', 'critical')


def inventory_lots_freeze_window(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    return status in ['quarantine', 'depleted'] and date.today().weekday() >= 5


def inventory_lots_summary_line(row: dict[str, Any]) -> str:
    ident = str(row.get('id') or 'new')
    status = str(row.get('status') or 'n/a')
    band = inventory_lots_risk_band(row)
    return DOMAIN_TITLE + ' ' + ident + ' is ' + status + ' (' + band + ').'

def inventory_lots_check_sku(value: Any) -> list[str]:
    """Field policy for Sku inside Inventory Lots."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Sku is required on Inventory Lots.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Sku is zero; confirm the Inventory Lots case.')
        if number > 9_000_000_000:
            notes.append('Sku exceeds the Inventory Lots ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Sku must be YYYY-MM-DD for Inventory Lots.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Sku is longer than the Inventory Lots ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Sku placeholder values are not allowed on Inventory Lots.')
    return notes


def inventory_lots_normalize_sku(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def inventory_lots_describe_sku() -> str:
    required = 'required' if True else 'optional'
    return 'Sku is a ' + required + ' str field on Inventory Lots (inventory_lots).'


def inventory_lots_check_warehouse(value: Any) -> list[str]:
    """Field policy for Warehouse inside Inventory Lots."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Warehouse is required on Inventory Lots.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Warehouse is zero; confirm the Inventory Lots case.')
        if number > 9_000_000_000:
            notes.append('Warehouse exceeds the Inventory Lots ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Warehouse must be YYYY-MM-DD for Inventory Lots.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Warehouse is longer than the Inventory Lots ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Warehouse placeholder values are not allowed on Inventory Lots.')
    return notes


def inventory_lots_normalize_warehouse(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def inventory_lots_describe_warehouse() -> str:
    required = 'required' if True else 'optional'
    return 'Warehouse is a ' + required + ' str field on Inventory Lots (inventory_lots).'


def inventory_lots_check_on_hand(value: Any) -> list[str]:
    """Field policy for On Hand inside Inventory Lots."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('On Hand is required on Inventory Lots.')
        return notes
    if 'int' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('On Hand is zero; confirm the Inventory Lots case.')
        if number > 9_000_000_000:
            notes.append('On Hand exceeds the Inventory Lots ceiling.')
        return notes
    if 'int' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('On Hand must be YYYY-MM-DD for Inventory Lots.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('On Hand is longer than the Inventory Lots ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('On Hand placeholder values are not allowed on Inventory Lots.')
    return notes


def inventory_lots_normalize_on_hand(value: Any) -> Any:
    if 'int' == 'int':
        return _as_int(value)
    if 'int' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def inventory_lots_describe_on_hand() -> str:
    required = 'required' if True else 'optional'
    return 'On Hand is a ' + required + ' int field on Inventory Lots (inventory_lots).'


def inventory_lots_check_reserved(value: Any) -> list[str]:
    """Field policy for Reserved inside Inventory Lots."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Reserved is required on Inventory Lots.')
        return notes
    if 'int' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Reserved is zero; confirm the Inventory Lots case.')
        if number > 9_000_000_000:
            notes.append('Reserved exceeds the Inventory Lots ceiling.')
        return notes
    if 'int' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Reserved must be YYYY-MM-DD for Inventory Lots.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Reserved is longer than the Inventory Lots ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Reserved placeholder values are not allowed on Inventory Lots.')
    return notes


def inventory_lots_normalize_reserved(value: Any) -> Any:
    if 'int' == 'int':
        return _as_int(value)
    if 'int' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def inventory_lots_describe_reserved() -> str:
    required = 'required' if True else 'optional'
    return 'Reserved is a ' + required + ' int field on Inventory Lots (inventory_lots).'


def inventory_lots_check_reorder_at(value: Any) -> list[str]:
    """Field policy for Reorder At inside Inventory Lots."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Reorder At is required on Inventory Lots.')
        return notes
    if 'int' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Reorder At is zero; confirm the Inventory Lots case.')
        if number > 9_000_000_000:
            notes.append('Reorder At exceeds the Inventory Lots ceiling.')
        return notes
    if 'int' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Reorder At must be YYYY-MM-DD for Inventory Lots.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Reorder At is longer than the Inventory Lots ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Reorder At placeholder values are not allowed on Inventory Lots.')
    return notes


def inventory_lots_normalize_reorder_at(value: Any) -> Any:
    if 'int' == 'int':
        return _as_int(value)
    if 'int' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def inventory_lots_describe_reorder_at() -> str:
    required = 'required' if True else 'optional'
    return 'Reorder At is a ' + required + ' int field on Inventory Lots (inventory_lots).'


def inventory_lots_check_status(value: Any) -> list[str]:
    """Field policy for Status inside Inventory Lots."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Status is required on Inventory Lots.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Status is zero; confirm the Inventory Lots case.')
        if number > 9_000_000_000:
            notes.append('Status exceeds the Inventory Lots ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Status must be YYYY-MM-DD for Inventory Lots.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Status is longer than the Inventory Lots ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Status placeholder values are not allowed on Inventory Lots.')
    return notes


def inventory_lots_normalize_status(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def inventory_lots_describe_status() -> str:
    required = 'required' if True else 'optional'
    return 'Status is a ' + required + ' str field on Inventory Lots (inventory_lots).'


FIELD_CHECKS_INVENTORY_LOTS = {
    'sku': inventory_lots_check_sku,
    'warehouse': inventory_lots_check_warehouse,
    'on_hand': inventory_lots_check_on_hand,
    'reserved': inventory_lots_check_reserved,
    'reorder_at': inventory_lots_check_reorder_at,
    'status': inventory_lots_check_status,
}


def inventory_lots_run_field_checks(row: dict[str, Any]) -> list[str]:
    found: list[str] = []
    for name, checker in FIELD_CHECKS_INVENTORY_LOTS.items():
        found.extend(checker(row.get(name)))
    return found


def inventory_lots_policy_card(row: dict[str, Any]) -> dict[str, Any]:
    return {
        'domain': DOMAIN_KEY,
        'title': DOMAIN_TITLE,
        'band': inventory_lots_risk_band(row),
        'owner': inventory_lots_owner_hint(row),
        'sla_hours': inventory_lots_sla_hours(row),
        'exceptions': inventory_lots_exception_needed(row),
        'freeze': inventory_lots_freeze_window(row),
        'violations': policy.collect(row) + inventory_lots_run_field_checks(row),
        'summary': inventory_lots_summary_line(row),
    }

