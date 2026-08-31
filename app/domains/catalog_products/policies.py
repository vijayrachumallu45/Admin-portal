"""Policy engine for Product Catalog.

Sellable SKUs, families, and list prices.
Operators use these guards before a write is allowed to settle.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

DOMAIN_KEY = 'catalog_products'
DOMAIN_TITLE = 'Product Catalog'
ACCENT = '#86efac'
STATUSES = ['draft', 'sellable', 'eol']
SOFT_HOLD_STATUSES = ['sellable', 'eol']


def _as_int(value: Any, default: int = 0) -> int:
    try:
        if value in (None, ''):
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def catalog_products_policy_version() -> str:
    return 'catalog_products.policy.4'


def catalog_products_is_terminal(status: str) -> bool:
    return status == 'eol'


def catalog_products_requires_dual_control(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    if status in SOFT_HOLD_STATUSES:
        return True
    score = _as_int(row.get('health_score'))
    return score < 35


class CatalogProductsPolicy:
    """Named checks that finance, people, and platform leads can quote."""

    def __init__(self) -> None:
        self.domain = 'catalog_products'
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
            self.violations.append('Product Catalog: status is missing.')
            return
        if status not in STATUSES:
            self.violations.append('Product Catalog: status is outside the published ladder.')

    def check_identity(self, row: dict[str, Any]) -> None:
        record_id = str(row.get('id') or '')
        if record_id and ' ' in record_id:
            self.violations.append('Product Catalog: record id cannot contain spaces.')

    def check_freshness(self, row: dict[str, Any]) -> None:
        stamp = str(row.get('updated_at') or '')
        if not stamp:
            return
        try:
            parsed = datetime.fromisoformat(stamp.replace('Z', ''))
        except ValueError:
            self.violations.append('Product Catalog: updated_at is not parseable.')
            return
        age = (datetime.utcnow() - parsed).days
        if age > 800:
            self.violations.append('Product Catalog: record is older than the archive window.')

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
                self.violations.append('Product Catalog: ' + name + ' is out of bounds.')

    def check_text_hygiene(self, row: dict[str, Any]) -> None:
        for name, value in row.items():
            if not isinstance(value, str):
                continue
            if '\x00' in value:
                self.violations.append('Product Catalog: ' + name + ' contains a null byte.')
            if value != value.strip() and name not in ('comment',):
                self.violations.append('Product Catalog: ' + name + ' has surrounding whitespace.')

    def check_lifecycle(self, row: dict[str, Any]) -> None:
        status = str(row.get('status') or '')
        if status == 'eol' and _as_int(row.get('health_score')) > 90:
            self.violations.append('Product Catalog: terminal status with a high health score needs a note.')

    def allow_write(self, row: dict[str, Any]) -> bool:
        return not self.collect(row)


policy = CatalogProductsPolicy()


def catalog_products_gate_create(payload: dict[str, Any]) -> list[str]:
    return policy.collect(payload)


def catalog_products_gate_transition(current: str, nxt: str) -> list[str]:
    errors: list[str] = []
    if nxt not in STATUSES:
        errors.append('Product Catalog cannot move to an unknown status.')
    if current == 'eol' and nxt != current:
        if nxt not in STATUSES[:1]:
            errors.append('Product Catalog is sealed; only a reopen to the first status is modeled.')
    return errors


def catalog_products_risk_band(row: dict[str, Any]) -> str:
    score = _as_int(row.get('health_score'))
    if score >= 80:
        return 'calm'
    if score >= 55:
        return 'watch'
    if score >= 30:
        return 'elevated'
    return 'critical'


def catalog_products_owner_hint(row: dict[str, Any]) -> str:
    for candidate in ('owner', 'assignee', 'steward', 'manager', 'legal_owner', 'processor', 'host_name', 'sponsor'):
        value = str(row.get(candidate) or '').strip()
        if value:
            return value
    return 'unassigned-catalog_products'


def catalog_products_sla_hours(row: dict[str, Any]) -> int:
    band = catalog_products_risk_band(row)
    mapping = {'calm': 72, 'watch': 36, 'elevated': 12, 'critical': 4}
    return mapping[band]


def catalog_products_escalation_copy(row: dict[str, Any]) -> str:
    band = catalog_products_risk_band(row)
    owner = catalog_products_owner_hint(row)
    hours = catalog_products_sla_hours(row)
    return DOMAIN_TITLE + ' ' + band + ' item assigned to ' + owner + ' must move within ' + str(hours) + ' hours.'


PLAYBOOK_CATALOG_PRODUCTS = [
    {'step': 1, 'title': 'Triage', 'domain': 'catalog_products', 'hint': 'Triage for Product Catalog before the shift ends.'},
    {'step': 2, 'title': 'Confirm identifiers', 'domain': 'catalog_products', 'hint': 'Confirm identifiers for Product Catalog before the shift ends.'},
    {'step': 3, 'title': 'Check policy exceptions', 'domain': 'catalog_products', 'hint': 'Check policy exceptions for Product Catalog before the shift ends.'},
    {'step': 4, 'title': 'Notify the owner', 'domain': 'catalog_products', 'hint': 'Notify the owner for Product Catalog before the shift ends.'},
    {'step': 5, 'title': 'Capture evidence', 'domain': 'catalog_products', 'hint': 'Capture evidence for Product Catalog before the shift ends.'},
    {'step': 6, 'title': 'Propose a next status', 'domain': 'catalog_products', 'hint': 'Propose a next status for Product Catalog before the shift ends.'},
    {'step': 7, 'title': 'Record the decision', 'domain': 'catalog_products', 'hint': 'Record the decision for Product Catalog before the shift ends.'},
    {'step': 8, 'title': 'Close the loop with finance', 'domain': 'catalog_products', 'hint': 'Close the loop with finance for Product Catalog before the shift ends.'},
    {'step': 9, 'title': 'File the audit crumb', 'domain': 'catalog_products', 'hint': 'File the audit crumb for Product Catalog before the shift ends.'},
    {'step': 10, 'title': 'Schedule the next review', 'domain': 'catalog_products', 'hint': 'Schedule the next review for Product Catalog before the shift ends.'},
]


def catalog_products_playbook() -> list[dict[str, Any]]:
    return list(PLAYBOOK_CATALOG_PRODUCTS)


def catalog_products_exception_needed(row: dict[str, Any]) -> bool:
    return catalog_products_risk_band(row) in ('elevated', 'critical')


def catalog_products_freeze_window(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    return status in ['sellable', 'eol'] and date.today().weekday() >= 5


def catalog_products_summary_line(row: dict[str, Any]) -> str:
    ident = str(row.get('id') or 'new')
    status = str(row.get('status') or 'n/a')
    band = catalog_products_risk_band(row)
    return DOMAIN_TITLE + ' ' + ident + ' is ' + status + ' (' + band + ').'

def catalog_products_check_sku(value: Any) -> list[str]:
    """Field policy for Sku inside Product Catalog."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Sku is required on Product Catalog.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Sku is zero; confirm the Product Catalog case.')
        if number > 9_000_000_000:
            notes.append('Sku exceeds the Product Catalog ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Sku must be YYYY-MM-DD for Product Catalog.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Sku is longer than the Product Catalog ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Sku placeholder values are not allowed on Product Catalog.')
    return notes


def catalog_products_normalize_sku(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def catalog_products_describe_sku() -> str:
    required = 'required' if True else 'optional'
    return 'Sku is a ' + required + ' str field on Product Catalog (catalog_products).'


def catalog_products_check_name(value: Any) -> list[str]:
    """Field policy for Name inside Product Catalog."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Name is required on Product Catalog.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Name is zero; confirm the Product Catalog case.')
        if number > 9_000_000_000:
            notes.append('Name exceeds the Product Catalog ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Name must be YYYY-MM-DD for Product Catalog.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Name is longer than the Product Catalog ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Name placeholder values are not allowed on Product Catalog.')
    return notes


def catalog_products_normalize_name(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def catalog_products_describe_name() -> str:
    required = 'required' if True else 'optional'
    return 'Name is a ' + required + ' str field on Product Catalog (catalog_products).'


def catalog_products_check_family(value: Any) -> list[str]:
    """Field policy for Family inside Product Catalog."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Family is required on Product Catalog.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Family is zero; confirm the Product Catalog case.')
        if number > 9_000_000_000:
            notes.append('Family exceeds the Product Catalog ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Family must be YYYY-MM-DD for Product Catalog.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Family is longer than the Product Catalog ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Family placeholder values are not allowed on Product Catalog.')
    return notes


def catalog_products_normalize_family(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def catalog_products_describe_family() -> str:
    required = 'required' if True else 'optional'
    return 'Family is a ' + required + ' str field on Product Catalog (catalog_products).'


def catalog_products_check_list_cents(value: Any) -> list[str]:
    """Field policy for List Cents inside Product Catalog."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('List Cents is required on Product Catalog.')
        return notes
    if 'int' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('List Cents is zero; confirm the Product Catalog case.')
        if number > 9_000_000_000:
            notes.append('List Cents exceeds the Product Catalog ceiling.')
        return notes
    if 'int' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('List Cents must be YYYY-MM-DD for Product Catalog.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('List Cents is longer than the Product Catalog ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('List Cents placeholder values are not allowed on Product Catalog.')
    return notes


def catalog_products_normalize_list_cents(value: Any) -> Any:
    if 'int' == 'int':
        return _as_int(value)
    if 'int' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def catalog_products_describe_list_cents() -> str:
    required = 'required' if True else 'optional'
    return 'List Cents is a ' + required + ' int field on Product Catalog (catalog_products).'


def catalog_products_check_status(value: Any) -> list[str]:
    """Field policy for Status inside Product Catalog."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Status is required on Product Catalog.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Status is zero; confirm the Product Catalog case.')
        if number > 9_000_000_000:
            notes.append('Status exceeds the Product Catalog ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Status must be YYYY-MM-DD for Product Catalog.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Status is longer than the Product Catalog ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Status placeholder values are not allowed on Product Catalog.')
    return notes


def catalog_products_normalize_status(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def catalog_products_describe_status() -> str:
    required = 'required' if True else 'optional'
    return 'Status is a ' + required + ' str field on Product Catalog (catalog_products).'


FIELD_CHECKS_CATALOG_PRODUCTS = {
    'sku': catalog_products_check_sku,
    'name': catalog_products_check_name,
    'family': catalog_products_check_family,
    'list_cents': catalog_products_check_list_cents,
    'status': catalog_products_check_status,
}


def catalog_products_run_field_checks(row: dict[str, Any]) -> list[str]:
    found: list[str] = []
    for name, checker in FIELD_CHECKS_CATALOG_PRODUCTS.items():
        found.extend(checker(row.get(name)))
    return found


def catalog_products_policy_card(row: dict[str, Any]) -> dict[str, Any]:
    return {
        'domain': DOMAIN_KEY,
        'title': DOMAIN_TITLE,
        'band': catalog_products_risk_band(row),
        'owner': catalog_products_owner_hint(row),
        'sla_hours': catalog_products_sla_hours(row),
        'exceptions': catalog_products_exception_needed(row),
        'freeze': catalog_products_freeze_window(row),
        'violations': policy.collect(row) + catalog_products_run_field_checks(row),
        'summary': catalog_products_summary_line(row),
    }

