"""Policy engine for Churn Signals.

Early-warning usage and sentiment flags for success managers.
Operators use these guards before a write is allowed to settle.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

DOMAIN_KEY = 'churn_signals'
DOMAIN_TITLE = 'Churn Signals'
ACCENT = '#f87171'
STATUSES = ['open', 'working', 'saved', 'lost']
SOFT_HOLD_STATUSES = ['saved', 'lost']


def _as_int(value: Any, default: int = 0) -> int:
    try:
        if value in (None, ''):
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def churn_signals_policy_version() -> str:
    return 'churn_signals.policy.4'


def churn_signals_is_terminal(status: str) -> bool:
    return status == 'lost'


def churn_signals_requires_dual_control(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    if status in SOFT_HOLD_STATUSES:
        return True
    score = _as_int(row.get('health_score'))
    return score < 35


class ChurnSignalsPolicy:
    """Named checks that finance, people, and platform leads can quote."""

    def __init__(self) -> None:
        self.domain = 'churn_signals'
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
            self.violations.append('Churn Signals: status is missing.')
            return
        if status not in STATUSES:
            self.violations.append('Churn Signals: status is outside the published ladder.')

    def check_identity(self, row: dict[str, Any]) -> None:
        record_id = str(row.get('id') or '')
        if record_id and ' ' in record_id:
            self.violations.append('Churn Signals: record id cannot contain spaces.')

    def check_freshness(self, row: dict[str, Any]) -> None:
        stamp = str(row.get('updated_at') or '')
        if not stamp:
            return
        try:
            parsed = datetime.fromisoformat(stamp.replace('Z', ''))
        except ValueError:
            self.violations.append('Churn Signals: updated_at is not parseable.')
            return
        age = (datetime.utcnow() - parsed).days
        if age > 800:
            self.violations.append('Churn Signals: record is older than the archive window.')

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
                self.violations.append('Churn Signals: ' + name + ' is out of bounds.')

    def check_text_hygiene(self, row: dict[str, Any]) -> None:
        for name, value in row.items():
            if not isinstance(value, str):
                continue
            if '\x00' in value:
                self.violations.append('Churn Signals: ' + name + ' contains a null byte.')
            if value != value.strip() and name not in ('comment',):
                self.violations.append('Churn Signals: ' + name + ' has surrounding whitespace.')

    def check_lifecycle(self, row: dict[str, Any]) -> None:
        status = str(row.get('status') or '')
        if status == 'lost' and _as_int(row.get('health_score')) > 90:
            self.violations.append('Churn Signals: terminal status with a high health score needs a note.')

    def allow_write(self, row: dict[str, Any]) -> bool:
        return not self.collect(row)


policy = ChurnSignalsPolicy()


def churn_signals_gate_create(payload: dict[str, Any]) -> list[str]:
    return policy.collect(payload)


def churn_signals_gate_transition(current: str, nxt: str) -> list[str]:
    errors: list[str] = []
    if nxt not in STATUSES:
        errors.append('Churn Signals cannot move to an unknown status.')
    if current == 'lost' and nxt != current:
        if nxt not in STATUSES[:1]:
            errors.append('Churn Signals is sealed; only a reopen to the first status is modeled.')
    return errors


def churn_signals_risk_band(row: dict[str, Any]) -> str:
    score = _as_int(row.get('health_score'))
    if score >= 80:
        return 'calm'
    if score >= 55:
        return 'watch'
    if score >= 30:
        return 'elevated'
    return 'critical'


def churn_signals_owner_hint(row: dict[str, Any]) -> str:
    for candidate in ('owner', 'assignee', 'steward', 'manager', 'legal_owner', 'processor', 'host_name', 'sponsor'):
        value = str(row.get(candidate) or '').strip()
        if value:
            return value
    return 'unassigned-churn_signals'


def churn_signals_sla_hours(row: dict[str, Any]) -> int:
    band = churn_signals_risk_band(row)
    mapping = {'calm': 72, 'watch': 36, 'elevated': 12, 'critical': 4}
    return mapping[band]


def churn_signals_escalation_copy(row: dict[str, Any]) -> str:
    band = churn_signals_risk_band(row)
    owner = churn_signals_owner_hint(row)
    hours = churn_signals_sla_hours(row)
    return DOMAIN_TITLE + ' ' + band + ' item assigned to ' + owner + ' must move within ' + str(hours) + ' hours.'


PLAYBOOK_CHURN_SIGNALS = [
    {'step': 1, 'title': 'Triage', 'domain': 'churn_signals', 'hint': 'Triage for Churn Signals before the shift ends.'},
    {'step': 2, 'title': 'Confirm identifiers', 'domain': 'churn_signals', 'hint': 'Confirm identifiers for Churn Signals before the shift ends.'},
    {'step': 3, 'title': 'Check policy exceptions', 'domain': 'churn_signals', 'hint': 'Check policy exceptions for Churn Signals before the shift ends.'},
    {'step': 4, 'title': 'Notify the owner', 'domain': 'churn_signals', 'hint': 'Notify the owner for Churn Signals before the shift ends.'},
    {'step': 5, 'title': 'Capture evidence', 'domain': 'churn_signals', 'hint': 'Capture evidence for Churn Signals before the shift ends.'},
    {'step': 6, 'title': 'Propose a next status', 'domain': 'churn_signals', 'hint': 'Propose a next status for Churn Signals before the shift ends.'},
    {'step': 7, 'title': 'Record the decision', 'domain': 'churn_signals', 'hint': 'Record the decision for Churn Signals before the shift ends.'},
    {'step': 8, 'title': 'Close the loop with finance', 'domain': 'churn_signals', 'hint': 'Close the loop with finance for Churn Signals before the shift ends.'},
    {'step': 9, 'title': 'File the audit crumb', 'domain': 'churn_signals', 'hint': 'File the audit crumb for Churn Signals before the shift ends.'},
    {'step': 10, 'title': 'Schedule the next review', 'domain': 'churn_signals', 'hint': 'Schedule the next review for Churn Signals before the shift ends.'},
]


def churn_signals_playbook() -> list[dict[str, Any]]:
    return list(PLAYBOOK_CHURN_SIGNALS)


def churn_signals_exception_needed(row: dict[str, Any]) -> bool:
    return churn_signals_risk_band(row) in ('elevated', 'critical')


def churn_signals_freeze_window(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    return status in ['saved', 'lost'] and date.today().weekday() >= 5


def churn_signals_summary_line(row: dict[str, Any]) -> str:
    ident = str(row.get('id') or 'new')
    status = str(row.get('status') or 'n/a')
    band = churn_signals_risk_band(row)
    return DOMAIN_TITLE + ' ' + ident + ' is ' + status + ' (' + band + ').'

def churn_signals_check_account_name(value: Any) -> list[str]:
    """Field policy for Account Name inside Churn Signals."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Account Name is required on Churn Signals.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Account Name is zero; confirm the Churn Signals case.')
        if number > 9_000_000_000:
            notes.append('Account Name exceeds the Churn Signals ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Account Name must be YYYY-MM-DD for Churn Signals.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Account Name is longer than the Churn Signals ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Account Name placeholder values are not allowed on Churn Signals.')
    return notes


def churn_signals_normalize_account_name(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def churn_signals_describe_account_name() -> str:
    required = 'required' if True else 'optional'
    return 'Account Name is a ' + required + ' str field on Churn Signals (churn_signals).'


def churn_signals_check_signal(value: Any) -> list[str]:
    """Field policy for Signal inside Churn Signals."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Signal is required on Churn Signals.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Signal is zero; confirm the Churn Signals case.')
        if number > 9_000_000_000:
            notes.append('Signal exceeds the Churn Signals ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Signal must be YYYY-MM-DD for Churn Signals.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Signal is longer than the Churn Signals ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Signal placeholder values are not allowed on Churn Signals.')
    return notes


def churn_signals_normalize_signal(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def churn_signals_describe_signal() -> str:
    required = 'required' if True else 'optional'
    return 'Signal is a ' + required + ' str field on Churn Signals (churn_signals).'


def churn_signals_check_severity(value: Any) -> list[str]:
    """Field policy for Severity inside Churn Signals."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Severity is required on Churn Signals.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Severity is zero; confirm the Churn Signals case.')
        if number > 9_000_000_000:
            notes.append('Severity exceeds the Churn Signals ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Severity must be YYYY-MM-DD for Churn Signals.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Severity is longer than the Churn Signals ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Severity placeholder values are not allowed on Churn Signals.')
    return notes


def churn_signals_normalize_severity(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def churn_signals_describe_severity() -> str:
    required = 'required' if True else 'optional'
    return 'Severity is a ' + required + ' str field on Churn Signals (churn_signals).'


def churn_signals_check_owner(value: Any) -> list[str]:
    """Field policy for Owner inside Churn Signals."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Owner is required on Churn Signals.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Owner is zero; confirm the Churn Signals case.')
        if number > 9_000_000_000:
            notes.append('Owner exceeds the Churn Signals ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Owner must be YYYY-MM-DD for Churn Signals.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Owner is longer than the Churn Signals ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Owner placeholder values are not allowed on Churn Signals.')
    return notes


def churn_signals_normalize_owner(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def churn_signals_describe_owner() -> str:
    required = 'required' if True else 'optional'
    return 'Owner is a ' + required + ' str field on Churn Signals (churn_signals).'


def churn_signals_check_status(value: Any) -> list[str]:
    """Field policy for Status inside Churn Signals."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Status is required on Churn Signals.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Status is zero; confirm the Churn Signals case.')
        if number > 9_000_000_000:
            notes.append('Status exceeds the Churn Signals ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Status must be YYYY-MM-DD for Churn Signals.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Status is longer than the Churn Signals ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Status placeholder values are not allowed on Churn Signals.')
    return notes


def churn_signals_normalize_status(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def churn_signals_describe_status() -> str:
    required = 'required' if True else 'optional'
    return 'Status is a ' + required + ' str field on Churn Signals (churn_signals).'


FIELD_CHECKS_CHURN_SIGNALS = {
    'account_name': churn_signals_check_account_name,
    'signal': churn_signals_check_signal,
    'severity': churn_signals_check_severity,
    'owner': churn_signals_check_owner,
    'status': churn_signals_check_status,
}


def churn_signals_run_field_checks(row: dict[str, Any]) -> list[str]:
    found: list[str] = []
    for name, checker in FIELD_CHECKS_CHURN_SIGNALS.items():
        found.extend(checker(row.get(name)))
    return found


def churn_signals_policy_card(row: dict[str, Any]) -> dict[str, Any]:
    return {
        'domain': DOMAIN_KEY,
        'title': DOMAIN_TITLE,
        'band': churn_signals_risk_band(row),
        'owner': churn_signals_owner_hint(row),
        'sla_hours': churn_signals_sla_hours(row),
        'exceptions': churn_signals_exception_needed(row),
        'freeze': churn_signals_freeze_window(row),
        'violations': policy.collect(row) + churn_signals_run_field_checks(row),
        'summary': churn_signals_summary_line(row),
    }

