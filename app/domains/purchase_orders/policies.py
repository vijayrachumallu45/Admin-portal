"""Policy engine for Purchase Orders.

Committed spend with receiving status and budget codes.
Operators use these guards before a write is allowed to settle.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

DOMAIN_KEY = 'purchase_orders'
DOMAIN_TITLE = 'Purchase Orders'
ACCENT = '#34d399'
STATUSES = ['open', 'partial', 'received', 'closed', 'cancelled']
SOFT_HOLD_STATUSES = ['closed', 'cancelled']


def _as_int(value: Any, default: int = 0) -> int:
    try:
        if value in (None, ''):
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def purchase_orders_policy_version() -> str:
    return 'purchase_orders.policy.4'


def purchase_orders_is_terminal(status: str) -> bool:
    return status == 'cancelled'


def purchase_orders_requires_dual_control(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    if status in SOFT_HOLD_STATUSES:
        return True
    score = _as_int(row.get('health_score'))
    return score < 35


class PurchaseOrdersPolicy:
    """Named checks that finance, people, and platform leads can quote."""

    def __init__(self) -> None:
        self.domain = 'purchase_orders'
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
            self.violations.append('Purchase Orders: status is missing.')
            return
        if status not in STATUSES:
            self.violations.append('Purchase Orders: status is outside the published ladder.')

    def check_identity(self, row: dict[str, Any]) -> None:
        record_id = str(row.get('id') or '')
        if record_id and ' ' in record_id:
            self.violations.append('Purchase Orders: record id cannot contain spaces.')

    def check_freshness(self, row: dict[str, Any]) -> None:
        stamp = str(row.get('updated_at') or '')
        if not stamp:
            return
        try:
            parsed = datetime.fromisoformat(stamp.replace('Z', ''))
        except ValueError:
            self.violations.append('Purchase Orders: updated_at is not parseable.')
            return
        age = (datetime.utcnow() - parsed).days
        if age > 800:
            self.violations.append('Purchase Orders: record is older than the archive window.')

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
                self.violations.append('Purchase Orders: ' + name + ' is out of bounds.')

    def check_text_hygiene(self, row: dict[str, Any]) -> None:
        for name, value in row.items():
            if not isinstance(value, str):
                continue
            if '\x00' in value:
                self.violations.append('Purchase Orders: ' + name + ' contains a null byte.')
            if value != value.strip() and name not in ('comment',):
                self.violations.append('Purchase Orders: ' + name + ' has surrounding whitespace.')

    def check_lifecycle(self, row: dict[str, Any]) -> None:
        status = str(row.get('status') or '')
        if status == 'cancelled' and _as_int(row.get('health_score')) > 90:
            self.violations.append('Purchase Orders: terminal status with a high health score needs a note.')

    def allow_write(self, row: dict[str, Any]) -> bool:
        return not self.collect(row)


policy = PurchaseOrdersPolicy()


def purchase_orders_gate_create(payload: dict[str, Any]) -> list[str]:
    return policy.collect(payload)


def purchase_orders_gate_transition(current: str, nxt: str) -> list[str]:
    errors: list[str] = []
    if nxt not in STATUSES:
        errors.append('Purchase Orders cannot move to an unknown status.')
    if current == 'cancelled' and nxt != current:
        if nxt not in STATUSES[:1]:
            errors.append('Purchase Orders is sealed; only a reopen to the first status is modeled.')
    return errors


def purchase_orders_risk_band(row: dict[str, Any]) -> str:
    score = _as_int(row.get('health_score'))
    if score >= 80:
        return 'calm'
    if score >= 55:
        return 'watch'
    if score >= 30:
        return 'elevated'
    return 'critical'


def purchase_orders_owner_hint(row: dict[str, Any]) -> str:
    for candidate in ('owner', 'assignee', 'steward', 'manager', 'legal_owner', 'processor', 'host_name', 'sponsor'):
        value = str(row.get(candidate) or '').strip()
        if value:
            return value
    return 'unassigned-purchase_orders'


def purchase_orders_sla_hours(row: dict[str, Any]) -> int:
    band = purchase_orders_risk_band(row)
    mapping = {'calm': 72, 'watch': 36, 'elevated': 12, 'critical': 4}
    return mapping[band]


def purchase_orders_escalation_copy(row: dict[str, Any]) -> str:
    band = purchase_orders_risk_band(row)
    owner = purchase_orders_owner_hint(row)
    hours = purchase_orders_sla_hours(row)
    return DOMAIN_TITLE + ' ' + band + ' item assigned to ' + owner + ' must move within ' + str(hours) + ' hours.'


PLAYBOOK_PURCHASE_ORDERS = [
    {'step': 1, 'title': 'Triage', 'domain': 'purchase_orders', 'hint': 'Triage for Purchase Orders before the shift ends.'},
    {'step': 2, 'title': 'Confirm identifiers', 'domain': 'purchase_orders', 'hint': 'Confirm identifiers for Purchase Orders before the shift ends.'},
    {'step': 3, 'title': 'Check policy exceptions', 'domain': 'purchase_orders', 'hint': 'Check policy exceptions for Purchase Orders before the shift ends.'},
    {'step': 4, 'title': 'Notify the owner', 'domain': 'purchase_orders', 'hint': 'Notify the owner for Purchase Orders before the shift ends.'},
    {'step': 5, 'title': 'Capture evidence', 'domain': 'purchase_orders', 'hint': 'Capture evidence for Purchase Orders before the shift ends.'},
    {'step': 6, 'title': 'Propose a next status', 'domain': 'purchase_orders', 'hint': 'Propose a next status for Purchase Orders before the shift ends.'},
    {'step': 7, 'title': 'Record the decision', 'domain': 'purchase_orders', 'hint': 'Record the decision for Purchase Orders before the shift ends.'},
    {'step': 8, 'title': 'Close the loop with finance', 'domain': 'purchase_orders', 'hint': 'Close the loop with finance for Purchase Orders before the shift ends.'},
    {'step': 9, 'title': 'File the audit crumb', 'domain': 'purchase_orders', 'hint': 'File the audit crumb for Purchase Orders before the shift ends.'},
    {'step': 10, 'title': 'Schedule the next review', 'domain': 'purchase_orders', 'hint': 'Schedule the next review for Purchase Orders before the shift ends.'},
]


def purchase_orders_playbook() -> list[dict[str, Any]]:
    return list(PLAYBOOK_PURCHASE_ORDERS)


def purchase_orders_exception_needed(row: dict[str, Any]) -> bool:
    return purchase_orders_risk_band(row) in ('elevated', 'critical')


def purchase_orders_freeze_window(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    return status in ['closed', 'cancelled'] and date.today().weekday() >= 5


def purchase_orders_summary_line(row: dict[str, Any]) -> str:
    ident = str(row.get('id') or 'new')
    status = str(row.get('status') or 'n/a')
    band = purchase_orders_risk_band(row)
    return DOMAIN_TITLE + ' ' + ident + ' is ' + status + ' (' + band + ').'

def purchase_orders_check_po_number(value: Any) -> list[str]:
    """Field policy for Po Number inside Purchase Orders."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Po Number is required on Purchase Orders.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Po Number is zero; confirm the Purchase Orders case.')
        if number > 9_000_000_000:
            notes.append('Po Number exceeds the Purchase Orders ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Po Number must be YYYY-MM-DD for Purchase Orders.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Po Number is longer than the Purchase Orders ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Po Number placeholder values are not allowed on Purchase Orders.')
    return notes


def purchase_orders_normalize_po_number(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def purchase_orders_describe_po_number() -> str:
    required = 'required' if True else 'optional'
    return 'Po Number is a ' + required + ' str field on Purchase Orders (purchase_orders).'


def purchase_orders_check_vendor_code(value: Any) -> list[str]:
    """Field policy for Vendor Code inside Purchase Orders."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Vendor Code is required on Purchase Orders.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Vendor Code is zero; confirm the Purchase Orders case.')
        if number > 9_000_000_000:
            notes.append('Vendor Code exceeds the Purchase Orders ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Vendor Code must be YYYY-MM-DD for Purchase Orders.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Vendor Code is longer than the Purchase Orders ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Vendor Code placeholder values are not allowed on Purchase Orders.')
    return notes


def purchase_orders_normalize_vendor_code(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def purchase_orders_describe_vendor_code() -> str:
    required = 'required' if True else 'optional'
    return 'Vendor Code is a ' + required + ' str field on Purchase Orders (purchase_orders).'


def purchase_orders_check_budget_code(value: Any) -> list[str]:
    """Field policy for Budget Code inside Purchase Orders."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Budget Code is required on Purchase Orders.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Budget Code is zero; confirm the Purchase Orders case.')
        if number > 9_000_000_000:
            notes.append('Budget Code exceeds the Purchase Orders ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Budget Code must be YYYY-MM-DD for Purchase Orders.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Budget Code is longer than the Purchase Orders ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Budget Code placeholder values are not allowed on Purchase Orders.')
    return notes


def purchase_orders_normalize_budget_code(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def purchase_orders_describe_budget_code() -> str:
    required = 'required' if True else 'optional'
    return 'Budget Code is a ' + required + ' str field on Purchase Orders (purchase_orders).'


def purchase_orders_check_amount_cents(value: Any) -> list[str]:
    """Field policy for Amount Cents inside Purchase Orders."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Amount Cents is required on Purchase Orders.')
        return notes
    if 'int' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Amount Cents is zero; confirm the Purchase Orders case.')
        if number > 9_000_000_000:
            notes.append('Amount Cents exceeds the Purchase Orders ceiling.')
        return notes
    if 'int' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Amount Cents must be YYYY-MM-DD for Purchase Orders.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Amount Cents is longer than the Purchase Orders ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Amount Cents placeholder values are not allowed on Purchase Orders.')
    return notes


def purchase_orders_normalize_amount_cents(value: Any) -> Any:
    if 'int' == 'int':
        return _as_int(value)
    if 'int' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def purchase_orders_describe_amount_cents() -> str:
    required = 'required' if True else 'optional'
    return 'Amount Cents is a ' + required + ' int field on Purchase Orders (purchase_orders).'


def purchase_orders_check_needed_by(value: Any) -> list[str]:
    """Field policy for Needed By inside Purchase Orders."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Needed By is required on Purchase Orders.')
        return notes
    if 'date' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Needed By is zero; confirm the Purchase Orders case.')
        if number > 9_000_000_000:
            notes.append('Needed By exceeds the Purchase Orders ceiling.')
        return notes
    if 'date' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Needed By must be YYYY-MM-DD for Purchase Orders.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Needed By is longer than the Purchase Orders ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Needed By placeholder values are not allowed on Purchase Orders.')
    return notes


def purchase_orders_normalize_needed_by(value: Any) -> Any:
    if 'date' == 'int':
        return _as_int(value)
    if 'date' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def purchase_orders_describe_needed_by() -> str:
    required = 'required' if True else 'optional'
    return 'Needed By is a ' + required + ' date field on Purchase Orders (purchase_orders).'


def purchase_orders_check_status(value: Any) -> list[str]:
    """Field policy for Status inside Purchase Orders."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Status is required on Purchase Orders.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Status is zero; confirm the Purchase Orders case.')
        if number > 9_000_000_000:
            notes.append('Status exceeds the Purchase Orders ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Status must be YYYY-MM-DD for Purchase Orders.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Status is longer than the Purchase Orders ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Status placeholder values are not allowed on Purchase Orders.')
    return notes


def purchase_orders_normalize_status(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def purchase_orders_describe_status() -> str:
    required = 'required' if True else 'optional'
    return 'Status is a ' + required + ' str field on Purchase Orders (purchase_orders).'


FIELD_CHECKS_PURCHASE_ORDERS = {
    'po_number': purchase_orders_check_po_number,
    'vendor_code': purchase_orders_check_vendor_code,
    'budget_code': purchase_orders_check_budget_code,
    'amount_cents': purchase_orders_check_amount_cents,
    'needed_by': purchase_orders_check_needed_by,
    'status': purchase_orders_check_status,
}


def purchase_orders_run_field_checks(row: dict[str, Any]) -> list[str]:
    found: list[str] = []
    for name, checker in FIELD_CHECKS_PURCHASE_ORDERS.items():
        found.extend(checker(row.get(name)))
    return found


def purchase_orders_policy_card(row: dict[str, Any]) -> dict[str, Any]:
    return {
        'domain': DOMAIN_KEY,
        'title': DOMAIN_TITLE,
        'band': purchase_orders_risk_band(row),
        'owner': purchase_orders_owner_hint(row),
        'sla_hours': purchase_orders_sla_hours(row),
        'exceptions': purchase_orders_exception_needed(row),
        'freeze': purchase_orders_freeze_window(row),
        'violations': policy.collect(row) + purchase_orders_run_field_checks(row),
        'summary': purchase_orders_summary_line(row),
    }

