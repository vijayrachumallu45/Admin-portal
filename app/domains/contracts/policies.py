"""Policy engine for Contract Vault.

Commercial paper with renewal clauses and legal owners.
Operators use these guards before a write is allowed to settle.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

DOMAIN_KEY = 'contracts'
DOMAIN_TITLE = 'Contract Vault'
ACCENT = '#d4d4d8'
STATUSES = ['negotiation', 'signed', 'renewing', 'expired']
SOFT_HOLD_STATUSES = ['renewing', 'expired']


def _as_int(value: Any, default: int = 0) -> int:
    try:
        if value in (None, ''):
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def contracts_policy_version() -> str:
    return 'contracts.policy.4'


def contracts_is_terminal(status: str) -> bool:
    return status == 'expired'


def contracts_requires_dual_control(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    if status in SOFT_HOLD_STATUSES:
        return True
    score = _as_int(row.get('health_score'))
    return score < 35


class ContractsPolicy:
    """Named checks that finance, people, and platform leads can quote."""

    def __init__(self) -> None:
        self.domain = 'contracts'
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
            self.violations.append('Contract Vault: status is missing.')
            return
        if status not in STATUSES:
            self.violations.append('Contract Vault: status is outside the published ladder.')

    def check_identity(self, row: dict[str, Any]) -> None:
        record_id = str(row.get('id') or '')
        if record_id and ' ' in record_id:
            self.violations.append('Contract Vault: record id cannot contain spaces.')

    def check_freshness(self, row: dict[str, Any]) -> None:
        stamp = str(row.get('updated_at') or '')
        if not stamp:
            return
        try:
            parsed = datetime.fromisoformat(stamp.replace('Z', ''))
        except ValueError:
            self.violations.append('Contract Vault: updated_at is not parseable.')
            return
        age = (datetime.utcnow() - parsed).days
        if age > 800:
            self.violations.append('Contract Vault: record is older than the archive window.')

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
                self.violations.append('Contract Vault: ' + name + ' is out of bounds.')

    def check_text_hygiene(self, row: dict[str, Any]) -> None:
        for name, value in row.items():
            if not isinstance(value, str):
                continue
            if '\x00' in value:
                self.violations.append('Contract Vault: ' + name + ' contains a null byte.')
            if value != value.strip() and name not in ('comment',):
                self.violations.append('Contract Vault: ' + name + ' has surrounding whitespace.')

    def check_lifecycle(self, row: dict[str, Any]) -> None:
        status = str(row.get('status') or '')
        if status == 'expired' and _as_int(row.get('health_score')) > 90:
            self.violations.append('Contract Vault: terminal status with a high health score needs a note.')

    def allow_write(self, row: dict[str, Any]) -> bool:
        return not self.collect(row)


policy = ContractsPolicy()


def contracts_gate_create(payload: dict[str, Any]) -> list[str]:
    return policy.collect(payload)


def contracts_gate_transition(current: str, nxt: str) -> list[str]:
    errors: list[str] = []
    if nxt not in STATUSES:
        errors.append('Contract Vault cannot move to an unknown status.')
    if current == 'expired' and nxt != current:
        if nxt not in STATUSES[:1]:
            errors.append('Contract Vault is sealed; only a reopen to the first status is modeled.')
    return errors


def contracts_risk_band(row: dict[str, Any]) -> str:
    score = _as_int(row.get('health_score'))
    if score >= 80:
        return 'calm'
    if score >= 55:
        return 'watch'
    if score >= 30:
        return 'elevated'
    return 'critical'


def contracts_owner_hint(row: dict[str, Any]) -> str:
    for candidate in ('owner', 'assignee', 'steward', 'manager', 'legal_owner', 'processor', 'host_name', 'sponsor'):
        value = str(row.get(candidate) or '').strip()
        if value:
            return value
    return 'unassigned-contracts'


def contracts_sla_hours(row: dict[str, Any]) -> int:
    band = contracts_risk_band(row)
    mapping = {'calm': 72, 'watch': 36, 'elevated': 12, 'critical': 4}
    return mapping[band]


def contracts_escalation_copy(row: dict[str, Any]) -> str:
    band = contracts_risk_band(row)
    owner = contracts_owner_hint(row)
    hours = contracts_sla_hours(row)
    return DOMAIN_TITLE + ' ' + band + ' item assigned to ' + owner + ' must move within ' + str(hours) + ' hours.'


PLAYBOOK_CONTRACTS = [
    {'step': 1, 'title': 'Triage', 'domain': 'contracts', 'hint': 'Triage for Contract Vault before the shift ends.'},
    {'step': 2, 'title': 'Confirm identifiers', 'domain': 'contracts', 'hint': 'Confirm identifiers for Contract Vault before the shift ends.'},
    {'step': 3, 'title': 'Check policy exceptions', 'domain': 'contracts', 'hint': 'Check policy exceptions for Contract Vault before the shift ends.'},
    {'step': 4, 'title': 'Notify the owner', 'domain': 'contracts', 'hint': 'Notify the owner for Contract Vault before the shift ends.'},
    {'step': 5, 'title': 'Capture evidence', 'domain': 'contracts', 'hint': 'Capture evidence for Contract Vault before the shift ends.'},
    {'step': 6, 'title': 'Propose a next status', 'domain': 'contracts', 'hint': 'Propose a next status for Contract Vault before the shift ends.'},
    {'step': 7, 'title': 'Record the decision', 'domain': 'contracts', 'hint': 'Record the decision for Contract Vault before the shift ends.'},
    {'step': 8, 'title': 'Close the loop with finance', 'domain': 'contracts', 'hint': 'Close the loop with finance for Contract Vault before the shift ends.'},
    {'step': 9, 'title': 'File the audit crumb', 'domain': 'contracts', 'hint': 'File the audit crumb for Contract Vault before the shift ends.'},
    {'step': 10, 'title': 'Schedule the next review', 'domain': 'contracts', 'hint': 'Schedule the next review for Contract Vault before the shift ends.'},
]


def contracts_playbook() -> list[dict[str, Any]]:
    return list(PLAYBOOK_CONTRACTS)


def contracts_exception_needed(row: dict[str, Any]) -> bool:
    return contracts_risk_band(row) in ('elevated', 'critical')


def contracts_freeze_window(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    return status in ['renewing', 'expired'] and date.today().weekday() >= 5


def contracts_summary_line(row: dict[str, Any]) -> str:
    ident = str(row.get('id') or 'new')
    status = str(row.get('status') or 'n/a')
    band = contracts_risk_band(row)
    return DOMAIN_TITLE + ' ' + ident + ' is ' + status + ' (' + band + ').'

def contracts_check_contract_no(value: Any) -> list[str]:
    """Field policy for Contract No inside Contract Vault."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Contract No is required on Contract Vault.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Contract No is zero; confirm the Contract Vault case.')
        if number > 9_000_000_000:
            notes.append('Contract No exceeds the Contract Vault ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Contract No must be YYYY-MM-DD for Contract Vault.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Contract No is longer than the Contract Vault ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Contract No placeholder values are not allowed on Contract Vault.')
    return notes


def contracts_normalize_contract_no(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def contracts_describe_contract_no() -> str:
    required = 'required' if True else 'optional'
    return 'Contract No is a ' + required + ' str field on Contract Vault (contracts).'


def contracts_check_counterparty(value: Any) -> list[str]:
    """Field policy for Counterparty inside Contract Vault."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Counterparty is required on Contract Vault.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Counterparty is zero; confirm the Contract Vault case.')
        if number > 9_000_000_000:
            notes.append('Counterparty exceeds the Contract Vault ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Counterparty must be YYYY-MM-DD for Contract Vault.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Counterparty is longer than the Contract Vault ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Counterparty placeholder values are not allowed on Contract Vault.')
    return notes


def contracts_normalize_counterparty(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def contracts_describe_counterparty() -> str:
    required = 'required' if True else 'optional'
    return 'Counterparty is a ' + required + ' str field on Contract Vault (contracts).'


def contracts_check_value_cents(value: Any) -> list[str]:
    """Field policy for Value Cents inside Contract Vault."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Value Cents is required on Contract Vault.')
        return notes
    if 'int' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Value Cents is zero; confirm the Contract Vault case.')
        if number > 9_000_000_000:
            notes.append('Value Cents exceeds the Contract Vault ceiling.')
        return notes
    if 'int' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Value Cents must be YYYY-MM-DD for Contract Vault.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Value Cents is longer than the Contract Vault ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Value Cents placeholder values are not allowed on Contract Vault.')
    return notes


def contracts_normalize_value_cents(value: Any) -> Any:
    if 'int' == 'int':
        return _as_int(value)
    if 'int' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def contracts_describe_value_cents() -> str:
    required = 'required' if True else 'optional'
    return 'Value Cents is a ' + required + ' int field on Contract Vault (contracts).'


def contracts_check_renew_on(value: Any) -> list[str]:
    """Field policy for Renew On inside Contract Vault."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Renew On is required on Contract Vault.')
        return notes
    if 'date' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Renew On is zero; confirm the Contract Vault case.')
        if number > 9_000_000_000:
            notes.append('Renew On exceeds the Contract Vault ceiling.')
        return notes
    if 'date' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Renew On must be YYYY-MM-DD for Contract Vault.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Renew On is longer than the Contract Vault ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Renew On placeholder values are not allowed on Contract Vault.')
    return notes


def contracts_normalize_renew_on(value: Any) -> Any:
    if 'date' == 'int':
        return _as_int(value)
    if 'date' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def contracts_describe_renew_on() -> str:
    required = 'required' if True else 'optional'
    return 'Renew On is a ' + required + ' date field on Contract Vault (contracts).'


def contracts_check_legal_owner(value: Any) -> list[str]:
    """Field policy for Legal Owner inside Contract Vault."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Legal Owner is required on Contract Vault.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Legal Owner is zero; confirm the Contract Vault case.')
        if number > 9_000_000_000:
            notes.append('Legal Owner exceeds the Contract Vault ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Legal Owner must be YYYY-MM-DD for Contract Vault.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Legal Owner is longer than the Contract Vault ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Legal Owner placeholder values are not allowed on Contract Vault.')
    return notes


def contracts_normalize_legal_owner(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def contracts_describe_legal_owner() -> str:
    required = 'required' if True else 'optional'
    return 'Legal Owner is a ' + required + ' str field on Contract Vault (contracts).'


def contracts_check_status(value: Any) -> list[str]:
    """Field policy for Status inside Contract Vault."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Status is required on Contract Vault.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Status is zero; confirm the Contract Vault case.')
        if number > 9_000_000_000:
            notes.append('Status exceeds the Contract Vault ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Status must be YYYY-MM-DD for Contract Vault.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Status is longer than the Contract Vault ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Status placeholder values are not allowed on Contract Vault.')
    return notes


def contracts_normalize_status(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def contracts_describe_status() -> str:
    required = 'required' if True else 'optional'
    return 'Status is a ' + required + ' str field on Contract Vault (contracts).'


FIELD_CHECKS_CONTRACTS = {
    'contract_no': contracts_check_contract_no,
    'counterparty': contracts_check_counterparty,
    'value_cents': contracts_check_value_cents,
    'renew_on': contracts_check_renew_on,
    'legal_owner': contracts_check_legal_owner,
    'status': contracts_check_status,
}


def contracts_run_field_checks(row: dict[str, Any]) -> list[str]:
    found: list[str] = []
    for name, checker in FIELD_CHECKS_CONTRACTS.items():
        found.extend(checker(row.get(name)))
    return found


def contracts_policy_card(row: dict[str, Any]) -> dict[str, Any]:
    return {
        'domain': DOMAIN_KEY,
        'title': DOMAIN_TITLE,
        'band': contracts_risk_band(row),
        'owner': contracts_owner_hint(row),
        'sla_hours': contracts_sla_hours(row),
        'exceptions': contracts_exception_needed(row),
        'freeze': contracts_freeze_window(row),
        'violations': policy.collect(row) + contracts_run_field_checks(row),
        'summary': contracts_summary_line(row),
    }

