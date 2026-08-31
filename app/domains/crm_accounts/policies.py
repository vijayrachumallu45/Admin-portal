"""Policy engine for CRM Accounts.

Named companies in the revenue graph with owners and segments.
Operators use these guards before a write is allowed to settle.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

DOMAIN_KEY = 'crm_accounts'
DOMAIN_TITLE = 'CRM Accounts'
ACCENT = '#818cf8'
STATUSES = ['prospect', 'customer', 'partner', 'inactive']
SOFT_HOLD_STATUSES = ['partner', 'inactive']


def _as_int(value: Any, default: int = 0) -> int:
    try:
        if value in (None, ''):
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def crm_accounts_policy_version() -> str:
    return 'crm_accounts.policy.4'


def crm_accounts_is_terminal(status: str) -> bool:
    return status == 'inactive'


def crm_accounts_requires_dual_control(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    if status in SOFT_HOLD_STATUSES:
        return True
    score = _as_int(row.get('health_score'))
    return score < 35


class CrmAccountsPolicy:
    """Named checks that finance, people, and platform leads can quote."""

    def __init__(self) -> None:
        self.domain = 'crm_accounts'
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
            self.violations.append('CRM Accounts: status is missing.')
            return
        if status not in STATUSES:
            self.violations.append('CRM Accounts: status is outside the published ladder.')

    def check_identity(self, row: dict[str, Any]) -> None:
        record_id = str(row.get('id') or '')
        if record_id and ' ' in record_id:
            self.violations.append('CRM Accounts: record id cannot contain spaces.')

    def check_freshness(self, row: dict[str, Any]) -> None:
        stamp = str(row.get('updated_at') or '')
        if not stamp:
            return
        try:
            parsed = datetime.fromisoformat(stamp.replace('Z', ''))
        except ValueError:
            self.violations.append('CRM Accounts: updated_at is not parseable.')
            return
        age = (datetime.utcnow() - parsed).days
        if age > 800:
            self.violations.append('CRM Accounts: record is older than the archive window.')

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
                self.violations.append('CRM Accounts: ' + name + ' is out of bounds.')

    def check_text_hygiene(self, row: dict[str, Any]) -> None:
        for name, value in row.items():
            if not isinstance(value, str):
                continue
            if '\x00' in value:
                self.violations.append('CRM Accounts: ' + name + ' contains a null byte.')
            if value != value.strip() and name not in ('comment',):
                self.violations.append('CRM Accounts: ' + name + ' has surrounding whitespace.')

    def check_lifecycle(self, row: dict[str, Any]) -> None:
        status = str(row.get('status') or '')
        if status == 'inactive' and _as_int(row.get('health_score')) > 90:
            self.violations.append('CRM Accounts: terminal status with a high health score needs a note.')

    def allow_write(self, row: dict[str, Any]) -> bool:
        return not self.collect(row)


policy = CrmAccountsPolicy()


def crm_accounts_gate_create(payload: dict[str, Any]) -> list[str]:
    return policy.collect(payload)


def crm_accounts_gate_transition(current: str, nxt: str) -> list[str]:
    errors: list[str] = []
    if nxt not in STATUSES:
        errors.append('CRM Accounts cannot move to an unknown status.')
    if current == 'inactive' and nxt != current:
        if nxt not in STATUSES[:1]:
            errors.append('CRM Accounts is sealed; only a reopen to the first status is modeled.')
    return errors


def crm_accounts_risk_band(row: dict[str, Any]) -> str:
    score = _as_int(row.get('health_score'))
    if score >= 80:
        return 'calm'
    if score >= 55:
        return 'watch'
    if score >= 30:
        return 'elevated'
    return 'critical'


def crm_accounts_owner_hint(row: dict[str, Any]) -> str:
    for candidate in ('owner', 'assignee', 'steward', 'manager', 'legal_owner', 'processor', 'host_name', 'sponsor'):
        value = str(row.get(candidate) or '').strip()
        if value:
            return value
    return 'unassigned-crm_accounts'


def crm_accounts_sla_hours(row: dict[str, Any]) -> int:
    band = crm_accounts_risk_band(row)
    mapping = {'calm': 72, 'watch': 36, 'elevated': 12, 'critical': 4}
    return mapping[band]


def crm_accounts_escalation_copy(row: dict[str, Any]) -> str:
    band = crm_accounts_risk_band(row)
    owner = crm_accounts_owner_hint(row)
    hours = crm_accounts_sla_hours(row)
    return DOMAIN_TITLE + ' ' + band + ' item assigned to ' + owner + ' must move within ' + str(hours) + ' hours.'


PLAYBOOK_CRM_ACCOUNTS = [
    {'step': 1, 'title': 'Triage', 'domain': 'crm_accounts', 'hint': 'Triage for CRM Accounts before the shift ends.'},
    {'step': 2, 'title': 'Confirm identifiers', 'domain': 'crm_accounts', 'hint': 'Confirm identifiers for CRM Accounts before the shift ends.'},
    {'step': 3, 'title': 'Check policy exceptions', 'domain': 'crm_accounts', 'hint': 'Check policy exceptions for CRM Accounts before the shift ends.'},
    {'step': 4, 'title': 'Notify the owner', 'domain': 'crm_accounts', 'hint': 'Notify the owner for CRM Accounts before the shift ends.'},
    {'step': 5, 'title': 'Capture evidence', 'domain': 'crm_accounts', 'hint': 'Capture evidence for CRM Accounts before the shift ends.'},
    {'step': 6, 'title': 'Propose a next status', 'domain': 'crm_accounts', 'hint': 'Propose a next status for CRM Accounts before the shift ends.'},
    {'step': 7, 'title': 'Record the decision', 'domain': 'crm_accounts', 'hint': 'Record the decision for CRM Accounts before the shift ends.'},
    {'step': 8, 'title': 'Close the loop with finance', 'domain': 'crm_accounts', 'hint': 'Close the loop with finance for CRM Accounts before the shift ends.'},
    {'step': 9, 'title': 'File the audit crumb', 'domain': 'crm_accounts', 'hint': 'File the audit crumb for CRM Accounts before the shift ends.'},
    {'step': 10, 'title': 'Schedule the next review', 'domain': 'crm_accounts', 'hint': 'Schedule the next review for CRM Accounts before the shift ends.'},
]


def crm_accounts_playbook() -> list[dict[str, Any]]:
    return list(PLAYBOOK_CRM_ACCOUNTS)


def crm_accounts_exception_needed(row: dict[str, Any]) -> bool:
    return crm_accounts_risk_band(row) in ('elevated', 'critical')


def crm_accounts_freeze_window(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    return status in ['partner', 'inactive'] and date.today().weekday() >= 5


def crm_accounts_summary_line(row: dict[str, Any]) -> str:
    ident = str(row.get('id') or 'new')
    status = str(row.get('status') or 'n/a')
    band = crm_accounts_risk_band(row)
    return DOMAIN_TITLE + ' ' + ident + ' is ' + status + ' (' + band + ').'

def crm_accounts_check_account_name(value: Any) -> list[str]:
    """Field policy for Account Name inside CRM Accounts."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Account Name is required on CRM Accounts.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Account Name is zero; confirm the CRM Accounts case.')
        if number > 9_000_000_000:
            notes.append('Account Name exceeds the CRM Accounts ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Account Name must be YYYY-MM-DD for CRM Accounts.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Account Name is longer than the CRM Accounts ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Account Name placeholder values are not allowed on CRM Accounts.')
    return notes


def crm_accounts_normalize_account_name(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def crm_accounts_describe_account_name() -> str:
    required = 'required' if True else 'optional'
    return 'Account Name is a ' + required + ' str field on CRM Accounts (crm_accounts).'


def crm_accounts_check_segment(value: Any) -> list[str]:
    """Field policy for Segment inside CRM Accounts."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Segment is required on CRM Accounts.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Segment is zero; confirm the CRM Accounts case.')
        if number > 9_000_000_000:
            notes.append('Segment exceeds the CRM Accounts ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Segment must be YYYY-MM-DD for CRM Accounts.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Segment is longer than the CRM Accounts ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Segment placeholder values are not allowed on CRM Accounts.')
    return notes


def crm_accounts_normalize_segment(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def crm_accounts_describe_segment() -> str:
    required = 'required' if True else 'optional'
    return 'Segment is a ' + required + ' str field on CRM Accounts (crm_accounts).'


def crm_accounts_check_owner(value: Any) -> list[str]:
    """Field policy for Owner inside CRM Accounts."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Owner is required on CRM Accounts.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Owner is zero; confirm the CRM Accounts case.')
        if number > 9_000_000_000:
            notes.append('Owner exceeds the CRM Accounts ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Owner must be YYYY-MM-DD for CRM Accounts.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Owner is longer than the CRM Accounts ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Owner placeholder values are not allowed on CRM Accounts.')
    return notes


def crm_accounts_normalize_owner(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def crm_accounts_describe_owner() -> str:
    required = 'required' if True else 'optional'
    return 'Owner is a ' + required + ' str field on CRM Accounts (crm_accounts).'


def crm_accounts_check_industry(value: Any) -> list[str]:
    """Field policy for Industry inside CRM Accounts."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Industry is required on CRM Accounts.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Industry is zero; confirm the CRM Accounts case.')
        if number > 9_000_000_000:
            notes.append('Industry exceeds the CRM Accounts ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Industry must be YYYY-MM-DD for CRM Accounts.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Industry is longer than the CRM Accounts ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Industry placeholder values are not allowed on CRM Accounts.')
    return notes


def crm_accounts_normalize_industry(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def crm_accounts_describe_industry() -> str:
    required = 'required' if True else 'optional'
    return 'Industry is a ' + required + ' str field on CRM Accounts (crm_accounts).'


def crm_accounts_check_employees(value: Any) -> list[str]:
    """Field policy for Employees inside CRM Accounts."""
    notes: list[str] = []
    if value in (None, '') and False:
        notes.append('Employees is required on CRM Accounts.')
        return notes
    if 'int' == 'int':
        number = _as_int(value, default=0)
        if False and number == 0:
            notes.append('Employees is zero; confirm the CRM Accounts case.')
        if number > 9_000_000_000:
            notes.append('Employees exceeds the CRM Accounts ceiling.')
        return notes
    if 'int' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Employees must be YYYY-MM-DD for CRM Accounts.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Employees is longer than the CRM Accounts ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and False:
        notes.append('Employees placeholder values are not allowed on CRM Accounts.')
    return notes


def crm_accounts_normalize_employees(value: Any) -> Any:
    if 'int' == 'int':
        return _as_int(value)
    if 'int' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def crm_accounts_describe_employees() -> str:
    required = 'required' if False else 'optional'
    return 'Employees is a ' + required + ' int field on CRM Accounts (crm_accounts).'


def crm_accounts_check_status(value: Any) -> list[str]:
    """Field policy for Status inside CRM Accounts."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Status is required on CRM Accounts.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Status is zero; confirm the CRM Accounts case.')
        if number > 9_000_000_000:
            notes.append('Status exceeds the CRM Accounts ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Status must be YYYY-MM-DD for CRM Accounts.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Status is longer than the CRM Accounts ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Status placeholder values are not allowed on CRM Accounts.')
    return notes


def crm_accounts_normalize_status(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def crm_accounts_describe_status() -> str:
    required = 'required' if True else 'optional'
    return 'Status is a ' + required + ' str field on CRM Accounts (crm_accounts).'


FIELD_CHECKS_CRM_ACCOUNTS = {
    'account_name': crm_accounts_check_account_name,
    'segment': crm_accounts_check_segment,
    'owner': crm_accounts_check_owner,
    'industry': crm_accounts_check_industry,
    'employees': crm_accounts_check_employees,
    'status': crm_accounts_check_status,
}


def crm_accounts_run_field_checks(row: dict[str, Any]) -> list[str]:
    found: list[str] = []
    for name, checker in FIELD_CHECKS_CRM_ACCOUNTS.items():
        found.extend(checker(row.get(name)))
    return found


def crm_accounts_policy_card(row: dict[str, Any]) -> dict[str, Any]:
    return {
        'domain': DOMAIN_KEY,
        'title': DOMAIN_TITLE,
        'band': crm_accounts_risk_band(row),
        'owner': crm_accounts_owner_hint(row),
        'sla_hours': crm_accounts_sla_hours(row),
        'exceptions': crm_accounts_exception_needed(row),
        'freeze': crm_accounts_freeze_window(row),
        'violations': policy.collect(row) + crm_accounts_run_field_checks(row),
        'summary': crm_accounts_summary_line(row),
    }

