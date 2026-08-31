"""Policy engine for Subscription Book.

Recurring plans, renewal dates, and expansion motions per account.
Operators use these guards before a write is allowed to settle.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

DOMAIN_KEY = 'subscriptions'
DOMAIN_TITLE = 'Subscription Book'
ACCENT = '#60a5fa'
STATUSES = ['trial', 'active', 'past_due', 'cancelled']
SOFT_HOLD_STATUSES = ['past_due', 'cancelled']


def _as_int(value: Any, default: int = 0) -> int:
    try:
        if value in (None, ''):
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def subscriptions_policy_version() -> str:
    return 'subscriptions.policy.4'


def subscriptions_is_terminal(status: str) -> bool:
    return status == 'cancelled'


def subscriptions_requires_dual_control(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    if status in SOFT_HOLD_STATUSES:
        return True
    score = _as_int(row.get('health_score'))
    return score < 35


class SubscriptionsPolicy:
    """Named checks that finance, people, and platform leads can quote."""

    def __init__(self) -> None:
        self.domain = 'subscriptions'
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
            self.violations.append('Subscription Book: status is missing.')
            return
        if status not in STATUSES:
            self.violations.append('Subscription Book: status is outside the published ladder.')

    def check_identity(self, row: dict[str, Any]) -> None:
        record_id = str(row.get('id') or '')
        if record_id and ' ' in record_id:
            self.violations.append('Subscription Book: record id cannot contain spaces.')

    def check_freshness(self, row: dict[str, Any]) -> None:
        stamp = str(row.get('updated_at') or '')
        if not stamp:
            return
        try:
            parsed = datetime.fromisoformat(stamp.replace('Z', ''))
        except ValueError:
            self.violations.append('Subscription Book: updated_at is not parseable.')
            return
        age = (datetime.utcnow() - parsed).days
        if age > 800:
            self.violations.append('Subscription Book: record is older than the archive window.')

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
                self.violations.append('Subscription Book: ' + name + ' is out of bounds.')

    def check_text_hygiene(self, row: dict[str, Any]) -> None:
        for name, value in row.items():
            if not isinstance(value, str):
                continue
            if '\x00' in value:
                self.violations.append('Subscription Book: ' + name + ' contains a null byte.')
            if value != value.strip() and name not in ('comment',):
                self.violations.append('Subscription Book: ' + name + ' has surrounding whitespace.')

    def check_lifecycle(self, row: dict[str, Any]) -> None:
        status = str(row.get('status') or '')
        if status == 'cancelled' and _as_int(row.get('health_score')) > 90:
            self.violations.append('Subscription Book: terminal status with a high health score needs a note.')

    def allow_write(self, row: dict[str, Any]) -> bool:
        return not self.collect(row)


policy = SubscriptionsPolicy()


def subscriptions_gate_create(payload: dict[str, Any]) -> list[str]:
    return policy.collect(payload)


def subscriptions_gate_transition(current: str, nxt: str) -> list[str]:
    errors: list[str] = []
    if nxt not in STATUSES:
        errors.append('Subscription Book cannot move to an unknown status.')
    if current == 'cancelled' and nxt != current:
        if nxt not in STATUSES[:1]:
            errors.append('Subscription Book is sealed; only a reopen to the first status is modeled.')
    return errors


def subscriptions_risk_band(row: dict[str, Any]) -> str:
    score = _as_int(row.get('health_score'))
    if score >= 80:
        return 'calm'
    if score >= 55:
        return 'watch'
    if score >= 30:
        return 'elevated'
    return 'critical'


def subscriptions_owner_hint(row: dict[str, Any]) -> str:
    for candidate in ('owner', 'assignee', 'steward', 'manager', 'legal_owner', 'processor', 'host_name', 'sponsor'):
        value = str(row.get(candidate) or '').strip()
        if value:
            return value
    return 'unassigned-subscriptions'


def subscriptions_sla_hours(row: dict[str, Any]) -> int:
    band = subscriptions_risk_band(row)
    mapping = {'calm': 72, 'watch': 36, 'elevated': 12, 'critical': 4}
    return mapping[band]


def subscriptions_escalation_copy(row: dict[str, Any]) -> str:
    band = subscriptions_risk_band(row)
    owner = subscriptions_owner_hint(row)
    hours = subscriptions_sla_hours(row)
    return DOMAIN_TITLE + ' ' + band + ' item assigned to ' + owner + ' must move within ' + str(hours) + ' hours.'


PLAYBOOK_SUBSCRIPTIONS = [
    {'step': 1, 'title': 'Triage', 'domain': 'subscriptions', 'hint': 'Triage for Subscription Book before the shift ends.'},
    {'step': 2, 'title': 'Confirm identifiers', 'domain': 'subscriptions', 'hint': 'Confirm identifiers for Subscription Book before the shift ends.'},
    {'step': 3, 'title': 'Check policy exceptions', 'domain': 'subscriptions', 'hint': 'Check policy exceptions for Subscription Book before the shift ends.'},
    {'step': 4, 'title': 'Notify the owner', 'domain': 'subscriptions', 'hint': 'Notify the owner for Subscription Book before the shift ends.'},
    {'step': 5, 'title': 'Capture evidence', 'domain': 'subscriptions', 'hint': 'Capture evidence for Subscription Book before the shift ends.'},
    {'step': 6, 'title': 'Propose a next status', 'domain': 'subscriptions', 'hint': 'Propose a next status for Subscription Book before the shift ends.'},
    {'step': 7, 'title': 'Record the decision', 'domain': 'subscriptions', 'hint': 'Record the decision for Subscription Book before the shift ends.'},
    {'step': 8, 'title': 'Close the loop with finance', 'domain': 'subscriptions', 'hint': 'Close the loop with finance for Subscription Book before the shift ends.'},
    {'step': 9, 'title': 'File the audit crumb', 'domain': 'subscriptions', 'hint': 'File the audit crumb for Subscription Book before the shift ends.'},
    {'step': 10, 'title': 'Schedule the next review', 'domain': 'subscriptions', 'hint': 'Schedule the next review for Subscription Book before the shift ends.'},
]


def subscriptions_playbook() -> list[dict[str, Any]]:
    return list(PLAYBOOK_SUBSCRIPTIONS)


def subscriptions_exception_needed(row: dict[str, Any]) -> bool:
    return subscriptions_risk_band(row) in ('elevated', 'critical')


def subscriptions_freeze_window(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    return status in ['past_due', 'cancelled'] and date.today().weekday() >= 5


def subscriptions_summary_line(row: dict[str, Any]) -> str:
    ident = str(row.get('id') or 'new')
    status = str(row.get('status') or 'n/a')
    band = subscriptions_risk_band(row)
    return DOMAIN_TITLE + ' ' + ident + ' is ' + status + ' (' + band + ').'

def subscriptions_check_account(value: Any) -> list[str]:
    """Field policy for Account inside Subscription Book."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Account is required on Subscription Book.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Account is zero; confirm the Subscription Book case.')
        if number > 9_000_000_000:
            notes.append('Account exceeds the Subscription Book ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Account must be YYYY-MM-DD for Subscription Book.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Account is longer than the Subscription Book ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Account placeholder values are not allowed on Subscription Book.')
    return notes


def subscriptions_normalize_account(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def subscriptions_describe_account() -> str:
    required = 'required' if True else 'optional'
    return 'Account is a ' + required + ' str field on Subscription Book (subscriptions).'


def subscriptions_check_plan_code(value: Any) -> list[str]:
    """Field policy for Plan Code inside Subscription Book."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Plan Code is required on Subscription Book.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Plan Code is zero; confirm the Subscription Book case.')
        if number > 9_000_000_000:
            notes.append('Plan Code exceeds the Subscription Book ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Plan Code must be YYYY-MM-DD for Subscription Book.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Plan Code is longer than the Subscription Book ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Plan Code placeholder values are not allowed on Subscription Book.')
    return notes


def subscriptions_normalize_plan_code(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def subscriptions_describe_plan_code() -> str:
    required = 'required' if True else 'optional'
    return 'Plan Code is a ' + required + ' str field on Subscription Book (subscriptions).'


def subscriptions_check_seats(value: Any) -> list[str]:
    """Field policy for Seats inside Subscription Book."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Seats is required on Subscription Book.')
        return notes
    if 'int' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Seats is zero; confirm the Subscription Book case.')
        if number > 9_000_000_000:
            notes.append('Seats exceeds the Subscription Book ceiling.')
        return notes
    if 'int' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Seats must be YYYY-MM-DD for Subscription Book.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Seats is longer than the Subscription Book ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Seats placeholder values are not allowed on Subscription Book.')
    return notes


def subscriptions_normalize_seats(value: Any) -> Any:
    if 'int' == 'int':
        return _as_int(value)
    if 'int' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def subscriptions_describe_seats() -> str:
    required = 'required' if True else 'optional'
    return 'Seats is a ' + required + ' int field on Subscription Book (subscriptions).'


def subscriptions_check_renew_on(value: Any) -> list[str]:
    """Field policy for Renew On inside Subscription Book."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Renew On is required on Subscription Book.')
        return notes
    if 'date' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Renew On is zero; confirm the Subscription Book case.')
        if number > 9_000_000_000:
            notes.append('Renew On exceeds the Subscription Book ceiling.')
        return notes
    if 'date' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Renew On must be YYYY-MM-DD for Subscription Book.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Renew On is longer than the Subscription Book ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Renew On placeholder values are not allowed on Subscription Book.')
    return notes


def subscriptions_normalize_renew_on(value: Any) -> Any:
    if 'date' == 'int':
        return _as_int(value)
    if 'date' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def subscriptions_describe_renew_on() -> str:
    required = 'required' if True else 'optional'
    return 'Renew On is a ' + required + ' date field on Subscription Book (subscriptions).'


def subscriptions_check_term_months(value: Any) -> list[str]:
    """Field policy for Term Months inside Subscription Book."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Term Months is required on Subscription Book.')
        return notes
    if 'int' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Term Months is zero; confirm the Subscription Book case.')
        if number > 9_000_000_000:
            notes.append('Term Months exceeds the Subscription Book ceiling.')
        return notes
    if 'int' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Term Months must be YYYY-MM-DD for Subscription Book.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Term Months is longer than the Subscription Book ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Term Months placeholder values are not allowed on Subscription Book.')
    return notes


def subscriptions_normalize_term_months(value: Any) -> Any:
    if 'int' == 'int':
        return _as_int(value)
    if 'int' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def subscriptions_describe_term_months() -> str:
    required = 'required' if True else 'optional'
    return 'Term Months is a ' + required + ' int field on Subscription Book (subscriptions).'


def subscriptions_check_arr_cents(value: Any) -> list[str]:
    """Field policy for Arr Cents inside Subscription Book."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Arr Cents is required on Subscription Book.')
        return notes
    if 'int' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Arr Cents is zero; confirm the Subscription Book case.')
        if number > 9_000_000_000:
            notes.append('Arr Cents exceeds the Subscription Book ceiling.')
        return notes
    if 'int' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Arr Cents must be YYYY-MM-DD for Subscription Book.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Arr Cents is longer than the Subscription Book ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Arr Cents placeholder values are not allowed on Subscription Book.')
    return notes


def subscriptions_normalize_arr_cents(value: Any) -> Any:
    if 'int' == 'int':
        return _as_int(value)
    if 'int' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def subscriptions_describe_arr_cents() -> str:
    required = 'required' if True else 'optional'
    return 'Arr Cents is a ' + required + ' int field on Subscription Book (subscriptions).'


def subscriptions_check_status(value: Any) -> list[str]:
    """Field policy for Status inside Subscription Book."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Status is required on Subscription Book.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Status is zero; confirm the Subscription Book case.')
        if number > 9_000_000_000:
            notes.append('Status exceeds the Subscription Book ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Status must be YYYY-MM-DD for Subscription Book.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Status is longer than the Subscription Book ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Status placeholder values are not allowed on Subscription Book.')
    return notes


def subscriptions_normalize_status(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def subscriptions_describe_status() -> str:
    required = 'required' if True else 'optional'
    return 'Status is a ' + required + ' str field on Subscription Book (subscriptions).'


FIELD_CHECKS_SUBSCRIPTIONS = {
    'account': subscriptions_check_account,
    'plan_code': subscriptions_check_plan_code,
    'seats': subscriptions_check_seats,
    'renew_on': subscriptions_check_renew_on,
    'term_months': subscriptions_check_term_months,
    'arr_cents': subscriptions_check_arr_cents,
    'status': subscriptions_check_status,
}


def subscriptions_run_field_checks(row: dict[str, Any]) -> list[str]:
    found: list[str] = []
    for name, checker in FIELD_CHECKS_SUBSCRIPTIONS.items():
        found.extend(checker(row.get(name)))
    return found


def subscriptions_policy_card(row: dict[str, Any]) -> dict[str, Any]:
    return {
        'domain': DOMAIN_KEY,
        'title': DOMAIN_TITLE,
        'band': subscriptions_risk_band(row),
        'owner': subscriptions_owner_hint(row),
        'sla_hours': subscriptions_sla_hours(row),
        'exceptions': subscriptions_exception_needed(row),
        'freeze': subscriptions_freeze_window(row),
        'violations': policy.collect(row) + subscriptions_run_field_checks(row),
        'summary': subscriptions_summary_line(row),
    }

