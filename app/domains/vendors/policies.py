"""Policy engine for Vendor Register.

Procurement counterparties, categories, and onboarding completeness.
Operators use these guards before a write is allowed to settle.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

DOMAIN_KEY = 'vendors'
DOMAIN_TITLE = 'Vendor Register'
ACCENT = '#fbbf24'
STATUSES = ['screening', 'approved', 'watchlist', 'exited']
SOFT_HOLD_STATUSES = ['watchlist', 'exited']


def _as_int(value: Any, default: int = 0) -> int:
    try:
        if value in (None, ''):
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def vendors_policy_version() -> str:
    return 'vendors.policy.4'


def vendors_is_terminal(status: str) -> bool:
    return status == 'exited'


def vendors_requires_dual_control(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    if status in SOFT_HOLD_STATUSES:
        return True
    score = _as_int(row.get('health_score'))
    return score < 35


class VendorsPolicy:
    """Named checks that finance, people, and platform leads can quote."""

    def __init__(self) -> None:
        self.domain = 'vendors'
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
            self.violations.append('Vendor Register: status is missing.')
            return
        if status not in STATUSES:
            self.violations.append('Vendor Register: status is outside the published ladder.')

    def check_identity(self, row: dict[str, Any]) -> None:
        record_id = str(row.get('id') or '')
        if record_id and ' ' in record_id:
            self.violations.append('Vendor Register: record id cannot contain spaces.')

    def check_freshness(self, row: dict[str, Any]) -> None:
        stamp = str(row.get('updated_at') or '')
        if not stamp:
            return
        try:
            parsed = datetime.fromisoformat(stamp.replace('Z', ''))
        except ValueError:
            self.violations.append('Vendor Register: updated_at is not parseable.')
            return
        age = (datetime.utcnow() - parsed).days
        if age > 800:
            self.violations.append('Vendor Register: record is older than the archive window.')

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
                self.violations.append('Vendor Register: ' + name + ' is out of bounds.')

    def check_text_hygiene(self, row: dict[str, Any]) -> None:
        for name, value in row.items():
            if not isinstance(value, str):
                continue
            if '\x00' in value:
                self.violations.append('Vendor Register: ' + name + ' contains a null byte.')
            if value != value.strip() and name not in ('comment',):
                self.violations.append('Vendor Register: ' + name + ' has surrounding whitespace.')

    def check_lifecycle(self, row: dict[str, Any]) -> None:
        status = str(row.get('status') or '')
        if status == 'exited' and _as_int(row.get('health_score')) > 90:
            self.violations.append('Vendor Register: terminal status with a high health score needs a note.')

    def allow_write(self, row: dict[str, Any]) -> bool:
        return not self.collect(row)


policy = VendorsPolicy()


def vendors_gate_create(payload: dict[str, Any]) -> list[str]:
    return policy.collect(payload)


def vendors_gate_transition(current: str, nxt: str) -> list[str]:
    errors: list[str] = []
    if nxt not in STATUSES:
        errors.append('Vendor Register cannot move to an unknown status.')
    if current == 'exited' and nxt != current:
        if nxt not in STATUSES[:1]:
            errors.append('Vendor Register is sealed; only a reopen to the first status is modeled.')
    return errors


def vendors_risk_band(row: dict[str, Any]) -> str:
    score = _as_int(row.get('health_score'))
    if score >= 80:
        return 'calm'
    if score >= 55:
        return 'watch'
    if score >= 30:
        return 'elevated'
    return 'critical'


def vendors_owner_hint(row: dict[str, Any]) -> str:
    for candidate in ('owner', 'assignee', 'steward', 'manager', 'legal_owner', 'processor', 'host_name', 'sponsor'):
        value = str(row.get(candidate) or '').strip()
        if value:
            return value
    return 'unassigned-vendors'


def vendors_sla_hours(row: dict[str, Any]) -> int:
    band = vendors_risk_band(row)
    mapping = {'calm': 72, 'watch': 36, 'elevated': 12, 'critical': 4}
    return mapping[band]


def vendors_escalation_copy(row: dict[str, Any]) -> str:
    band = vendors_risk_band(row)
    owner = vendors_owner_hint(row)
    hours = vendors_sla_hours(row)
    return DOMAIN_TITLE + ' ' + band + ' item assigned to ' + owner + ' must move within ' + str(hours) + ' hours.'


PLAYBOOK_VENDORS = [
    {'step': 1, 'title': 'Triage', 'domain': 'vendors', 'hint': 'Triage for Vendor Register before the shift ends.'},
    {'step': 2, 'title': 'Confirm identifiers', 'domain': 'vendors', 'hint': 'Confirm identifiers for Vendor Register before the shift ends.'},
    {'step': 3, 'title': 'Check policy exceptions', 'domain': 'vendors', 'hint': 'Check policy exceptions for Vendor Register before the shift ends.'},
    {'step': 4, 'title': 'Notify the owner', 'domain': 'vendors', 'hint': 'Notify the owner for Vendor Register before the shift ends.'},
    {'step': 5, 'title': 'Capture evidence', 'domain': 'vendors', 'hint': 'Capture evidence for Vendor Register before the shift ends.'},
    {'step': 6, 'title': 'Propose a next status', 'domain': 'vendors', 'hint': 'Propose a next status for Vendor Register before the shift ends.'},
    {'step': 7, 'title': 'Record the decision', 'domain': 'vendors', 'hint': 'Record the decision for Vendor Register before the shift ends.'},
    {'step': 8, 'title': 'Close the loop with finance', 'domain': 'vendors', 'hint': 'Close the loop with finance for Vendor Register before the shift ends.'},
    {'step': 9, 'title': 'File the audit crumb', 'domain': 'vendors', 'hint': 'File the audit crumb for Vendor Register before the shift ends.'},
    {'step': 10, 'title': 'Schedule the next review', 'domain': 'vendors', 'hint': 'Schedule the next review for Vendor Register before the shift ends.'},
]


def vendors_playbook() -> list[dict[str, Any]]:
    return list(PLAYBOOK_VENDORS)


def vendors_exception_needed(row: dict[str, Any]) -> bool:
    return vendors_risk_band(row) in ('elevated', 'critical')


def vendors_freeze_window(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    return status in ['watchlist', 'exited'] and date.today().weekday() >= 5


def vendors_summary_line(row: dict[str, Any]) -> str:
    ident = str(row.get('id') or 'new')
    status = str(row.get('status') or 'n/a')
    band = vendors_risk_band(row)
    return DOMAIN_TITLE + ' ' + ident + ' is ' + status + ' (' + band + ').'

def vendors_check_vendor_code(value: Any) -> list[str]:
    """Field policy for Vendor Code inside Vendor Register."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Vendor Code is required on Vendor Register.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Vendor Code is zero; confirm the Vendor Register case.')
        if number > 9_000_000_000:
            notes.append('Vendor Code exceeds the Vendor Register ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Vendor Code must be YYYY-MM-DD for Vendor Register.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Vendor Code is longer than the Vendor Register ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Vendor Code placeholder values are not allowed on Vendor Register.')
    return notes


def vendors_normalize_vendor_code(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def vendors_describe_vendor_code() -> str:
    required = 'required' if True else 'optional'
    return 'Vendor Code is a ' + required + ' str field on Vendor Register (vendors).'


def vendors_check_name(value: Any) -> list[str]:
    """Field policy for Name inside Vendor Register."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Name is required on Vendor Register.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Name is zero; confirm the Vendor Register case.')
        if number > 9_000_000_000:
            notes.append('Name exceeds the Vendor Register ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Name must be YYYY-MM-DD for Vendor Register.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Name is longer than the Vendor Register ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Name placeholder values are not allowed on Vendor Register.')
    return notes


def vendors_normalize_name(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def vendors_describe_name() -> str:
    required = 'required' if True else 'optional'
    return 'Name is a ' + required + ' str field on Vendor Register (vendors).'


def vendors_check_category(value: Any) -> list[str]:
    """Field policy for Category inside Vendor Register."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Category is required on Vendor Register.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Category is zero; confirm the Vendor Register case.')
        if number > 9_000_000_000:
            notes.append('Category exceeds the Vendor Register ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Category must be YYYY-MM-DD for Vendor Register.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Category is longer than the Vendor Register ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Category placeholder values are not allowed on Vendor Register.')
    return notes


def vendors_normalize_category(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def vendors_describe_category() -> str:
    required = 'required' if True else 'optional'
    return 'Category is a ' + required + ' str field on Vendor Register (vendors).'


def vendors_check_country(value: Any) -> list[str]:
    """Field policy for Country inside Vendor Register."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Country is required on Vendor Register.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Country is zero; confirm the Vendor Register case.')
        if number > 9_000_000_000:
            notes.append('Country exceeds the Vendor Register ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Country must be YYYY-MM-DD for Vendor Register.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Country is longer than the Vendor Register ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Country placeholder values are not allowed on Vendor Register.')
    return notes


def vendors_normalize_country(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def vendors_describe_country() -> str:
    required = 'required' if True else 'optional'
    return 'Country is a ' + required + ' str field on Vendor Register (vendors).'


def vendors_check_risk_score(value: Any) -> list[str]:
    """Field policy for Risk Score inside Vendor Register."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Risk Score is required on Vendor Register.')
        return notes
    if 'int' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Risk Score is zero; confirm the Vendor Register case.')
        if number > 9_000_000_000:
            notes.append('Risk Score exceeds the Vendor Register ceiling.')
        return notes
    if 'int' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Risk Score must be YYYY-MM-DD for Vendor Register.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Risk Score is longer than the Vendor Register ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Risk Score placeholder values are not allowed on Vendor Register.')
    return notes


def vendors_normalize_risk_score(value: Any) -> Any:
    if 'int' == 'int':
        return _as_int(value)
    if 'int' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def vendors_describe_risk_score() -> str:
    required = 'required' if True else 'optional'
    return 'Risk Score is a ' + required + ' int field on Vendor Register (vendors).'


def vendors_check_status(value: Any) -> list[str]:
    """Field policy for Status inside Vendor Register."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Status is required on Vendor Register.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Status is zero; confirm the Vendor Register case.')
        if number > 9_000_000_000:
            notes.append('Status exceeds the Vendor Register ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Status must be YYYY-MM-DD for Vendor Register.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Status is longer than the Vendor Register ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Status placeholder values are not allowed on Vendor Register.')
    return notes


def vendors_normalize_status(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def vendors_describe_status() -> str:
    required = 'required' if True else 'optional'
    return 'Status is a ' + required + ' str field on Vendor Register (vendors).'


FIELD_CHECKS_VENDORS = {
    'vendor_code': vendors_check_vendor_code,
    'name': vendors_check_name,
    'category': vendors_check_category,
    'country': vendors_check_country,
    'risk_score': vendors_check_risk_score,
    'status': vendors_check_status,
}


def vendors_run_field_checks(row: dict[str, Any]) -> list[str]:
    found: list[str] = []
    for name, checker in FIELD_CHECKS_VENDORS.items():
        found.extend(checker(row.get(name)))
    return found


def vendors_policy_card(row: dict[str, Any]) -> dict[str, Any]:
    return {
        'domain': DOMAIN_KEY,
        'title': DOMAIN_TITLE,
        'band': vendors_risk_band(row),
        'owner': vendors_owner_hint(row),
        'sla_hours': vendors_sla_hours(row),
        'exceptions': vendors_exception_needed(row),
        'freeze': vendors_freeze_window(row),
        'violations': policy.collect(row) + vendors_run_field_checks(row),
        'summary': vendors_summary_line(row),
    }

