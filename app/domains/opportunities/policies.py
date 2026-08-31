"""Policy engine for Opportunity Board.

Pipeline stages, amounts, and close dates for forecast.
Operators use these guards before a write is allowed to settle.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

DOMAIN_KEY = 'opportunities'
DOMAIN_TITLE = 'Opportunity Board'
ACCENT = '#2dd4bf'
STATUSES = ['open', 'won', 'lost']
SOFT_HOLD_STATUSES = ['won', 'lost']


def _as_int(value: Any, default: int = 0) -> int:
    try:
        if value in (None, ''):
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def opportunities_policy_version() -> str:
    return 'opportunities.policy.4'


def opportunities_is_terminal(status: str) -> bool:
    return status == 'lost'


def opportunities_requires_dual_control(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    if status in SOFT_HOLD_STATUSES:
        return True
    score = _as_int(row.get('health_score'))
    return score < 35


class OpportunitiesPolicy:
    """Named checks that finance, people, and platform leads can quote."""

    def __init__(self) -> None:
        self.domain = 'opportunities'
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
            self.violations.append('Opportunity Board: status is missing.')
            return
        if status not in STATUSES:
            self.violations.append('Opportunity Board: status is outside the published ladder.')

    def check_identity(self, row: dict[str, Any]) -> None:
        record_id = str(row.get('id') or '')
        if record_id and ' ' in record_id:
            self.violations.append('Opportunity Board: record id cannot contain spaces.')

    def check_freshness(self, row: dict[str, Any]) -> None:
        stamp = str(row.get('updated_at') or '')
        if not stamp:
            return
        try:
            parsed = datetime.fromisoformat(stamp.replace('Z', ''))
        except ValueError:
            self.violations.append('Opportunity Board: updated_at is not parseable.')
            return
        age = (datetime.utcnow() - parsed).days
        if age > 800:
            self.violations.append('Opportunity Board: record is older than the archive window.')

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
                self.violations.append('Opportunity Board: ' + name + ' is out of bounds.')

    def check_text_hygiene(self, row: dict[str, Any]) -> None:
        for name, value in row.items():
            if not isinstance(value, str):
                continue
            if '\x00' in value:
                self.violations.append('Opportunity Board: ' + name + ' contains a null byte.')
            if value != value.strip() and name not in ('comment',):
                self.violations.append('Opportunity Board: ' + name + ' has surrounding whitespace.')

    def check_lifecycle(self, row: dict[str, Any]) -> None:
        status = str(row.get('status') or '')
        if status == 'lost' and _as_int(row.get('health_score')) > 90:
            self.violations.append('Opportunity Board: terminal status with a high health score needs a note.')

    def allow_write(self, row: dict[str, Any]) -> bool:
        return not self.collect(row)


policy = OpportunitiesPolicy()


def opportunities_gate_create(payload: dict[str, Any]) -> list[str]:
    return policy.collect(payload)


def opportunities_gate_transition(current: str, nxt: str) -> list[str]:
    errors: list[str] = []
    if nxt not in STATUSES:
        errors.append('Opportunity Board cannot move to an unknown status.')
    if current == 'lost' and nxt != current:
        if nxt not in STATUSES[:1]:
            errors.append('Opportunity Board is sealed; only a reopen to the first status is modeled.')
    return errors


def opportunities_risk_band(row: dict[str, Any]) -> str:
    score = _as_int(row.get('health_score'))
    if score >= 80:
        return 'calm'
    if score >= 55:
        return 'watch'
    if score >= 30:
        return 'elevated'
    return 'critical'


def opportunities_owner_hint(row: dict[str, Any]) -> str:
    for candidate in ('owner', 'assignee', 'steward', 'manager', 'legal_owner', 'processor', 'host_name', 'sponsor'):
        value = str(row.get(candidate) or '').strip()
        if value:
            return value
    return 'unassigned-opportunities'


def opportunities_sla_hours(row: dict[str, Any]) -> int:
    band = opportunities_risk_band(row)
    mapping = {'calm': 72, 'watch': 36, 'elevated': 12, 'critical': 4}
    return mapping[band]


def opportunities_escalation_copy(row: dict[str, Any]) -> str:
    band = opportunities_risk_band(row)
    owner = opportunities_owner_hint(row)
    hours = opportunities_sla_hours(row)
    return DOMAIN_TITLE + ' ' + band + ' item assigned to ' + owner + ' must move within ' + str(hours) + ' hours.'


PLAYBOOK_OPPORTUNITIES = [
    {'step': 1, 'title': 'Triage', 'domain': 'opportunities', 'hint': 'Triage for Opportunity Board before the shift ends.'},
    {'step': 2, 'title': 'Confirm identifiers', 'domain': 'opportunities', 'hint': 'Confirm identifiers for Opportunity Board before the shift ends.'},
    {'step': 3, 'title': 'Check policy exceptions', 'domain': 'opportunities', 'hint': 'Check policy exceptions for Opportunity Board before the shift ends.'},
    {'step': 4, 'title': 'Notify the owner', 'domain': 'opportunities', 'hint': 'Notify the owner for Opportunity Board before the shift ends.'},
    {'step': 5, 'title': 'Capture evidence', 'domain': 'opportunities', 'hint': 'Capture evidence for Opportunity Board before the shift ends.'},
    {'step': 6, 'title': 'Propose a next status', 'domain': 'opportunities', 'hint': 'Propose a next status for Opportunity Board before the shift ends.'},
    {'step': 7, 'title': 'Record the decision', 'domain': 'opportunities', 'hint': 'Record the decision for Opportunity Board before the shift ends.'},
    {'step': 8, 'title': 'Close the loop with finance', 'domain': 'opportunities', 'hint': 'Close the loop with finance for Opportunity Board before the shift ends.'},
    {'step': 9, 'title': 'File the audit crumb', 'domain': 'opportunities', 'hint': 'File the audit crumb for Opportunity Board before the shift ends.'},
    {'step': 10, 'title': 'Schedule the next review', 'domain': 'opportunities', 'hint': 'Schedule the next review for Opportunity Board before the shift ends.'},
]


def opportunities_playbook() -> list[dict[str, Any]]:
    return list(PLAYBOOK_OPPORTUNITIES)


def opportunities_exception_needed(row: dict[str, Any]) -> bool:
    return opportunities_risk_band(row) in ('elevated', 'critical')


def opportunities_freeze_window(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    return status in ['won', 'lost'] and date.today().weekday() >= 5


def opportunities_summary_line(row: dict[str, Any]) -> str:
    ident = str(row.get('id') or 'new')
    status = str(row.get('status') or 'n/a')
    band = opportunities_risk_band(row)
    return DOMAIN_TITLE + ' ' + ident + ' is ' + status + ' (' + band + ').'

def opportunities_check_deal_name(value: Any) -> list[str]:
    """Field policy for Deal Name inside Opportunity Board."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Deal Name is required on Opportunity Board.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Deal Name is zero; confirm the Opportunity Board case.')
        if number > 9_000_000_000:
            notes.append('Deal Name exceeds the Opportunity Board ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Deal Name must be YYYY-MM-DD for Opportunity Board.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Deal Name is longer than the Opportunity Board ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Deal Name placeholder values are not allowed on Opportunity Board.')
    return notes


def opportunities_normalize_deal_name(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def opportunities_describe_deal_name() -> str:
    required = 'required' if True else 'optional'
    return 'Deal Name is a ' + required + ' str field on Opportunity Board (opportunities).'


def opportunities_check_account_name(value: Any) -> list[str]:
    """Field policy for Account Name inside Opportunity Board."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Account Name is required on Opportunity Board.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Account Name is zero; confirm the Opportunity Board case.')
        if number > 9_000_000_000:
            notes.append('Account Name exceeds the Opportunity Board ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Account Name must be YYYY-MM-DD for Opportunity Board.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Account Name is longer than the Opportunity Board ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Account Name placeholder values are not allowed on Opportunity Board.')
    return notes


def opportunities_normalize_account_name(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def opportunities_describe_account_name() -> str:
    required = 'required' if True else 'optional'
    return 'Account Name is a ' + required + ' str field on Opportunity Board (opportunities).'


def opportunities_check_amount_cents(value: Any) -> list[str]:
    """Field policy for Amount Cents inside Opportunity Board."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Amount Cents is required on Opportunity Board.')
        return notes
    if 'int' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Amount Cents is zero; confirm the Opportunity Board case.')
        if number > 9_000_000_000:
            notes.append('Amount Cents exceeds the Opportunity Board ceiling.')
        return notes
    if 'int' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Amount Cents must be YYYY-MM-DD for Opportunity Board.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Amount Cents is longer than the Opportunity Board ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Amount Cents placeholder values are not allowed on Opportunity Board.')
    return notes


def opportunities_normalize_amount_cents(value: Any) -> Any:
    if 'int' == 'int':
        return _as_int(value)
    if 'int' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def opportunities_describe_amount_cents() -> str:
    required = 'required' if True else 'optional'
    return 'Amount Cents is a ' + required + ' int field on Opportunity Board (opportunities).'


def opportunities_check_stage(value: Any) -> list[str]:
    """Field policy for Stage inside Opportunity Board."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Stage is required on Opportunity Board.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Stage is zero; confirm the Opportunity Board case.')
        if number > 9_000_000_000:
            notes.append('Stage exceeds the Opportunity Board ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Stage must be YYYY-MM-DD for Opportunity Board.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Stage is longer than the Opportunity Board ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Stage placeholder values are not allowed on Opportunity Board.')
    return notes


def opportunities_normalize_stage(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def opportunities_describe_stage() -> str:
    required = 'required' if True else 'optional'
    return 'Stage is a ' + required + ' str field on Opportunity Board (opportunities).'


def opportunities_check_close_on(value: Any) -> list[str]:
    """Field policy for Close On inside Opportunity Board."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Close On is required on Opportunity Board.')
        return notes
    if 'date' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Close On is zero; confirm the Opportunity Board case.')
        if number > 9_000_000_000:
            notes.append('Close On exceeds the Opportunity Board ceiling.')
        return notes
    if 'date' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Close On must be YYYY-MM-DD for Opportunity Board.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Close On is longer than the Opportunity Board ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Close On placeholder values are not allowed on Opportunity Board.')
    return notes


def opportunities_normalize_close_on(value: Any) -> Any:
    if 'date' == 'int':
        return _as_int(value)
    if 'date' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def opportunities_describe_close_on() -> str:
    required = 'required' if True else 'optional'
    return 'Close On is a ' + required + ' date field on Opportunity Board (opportunities).'


def opportunities_check_status(value: Any) -> list[str]:
    """Field policy for Status inside Opportunity Board."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Status is required on Opportunity Board.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Status is zero; confirm the Opportunity Board case.')
        if number > 9_000_000_000:
            notes.append('Status exceeds the Opportunity Board ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Status must be YYYY-MM-DD for Opportunity Board.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Status is longer than the Opportunity Board ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Status placeholder values are not allowed on Opportunity Board.')
    return notes


def opportunities_normalize_status(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def opportunities_describe_status() -> str:
    required = 'required' if True else 'optional'
    return 'Status is a ' + required + ' str field on Opportunity Board (opportunities).'


FIELD_CHECKS_OPPORTUNITIES = {
    'deal_name': opportunities_check_deal_name,
    'account_name': opportunities_check_account_name,
    'amount_cents': opportunities_check_amount_cents,
    'stage': opportunities_check_stage,
    'close_on': opportunities_check_close_on,
    'status': opportunities_check_status,
}


def opportunities_run_field_checks(row: dict[str, Any]) -> list[str]:
    found: list[str] = []
    for name, checker in FIELD_CHECKS_OPPORTUNITIES.items():
        found.extend(checker(row.get(name)))
    return found


def opportunities_policy_card(row: dict[str, Any]) -> dict[str, Any]:
    return {
        'domain': DOMAIN_KEY,
        'title': DOMAIN_TITLE,
        'band': opportunities_risk_band(row),
        'owner': opportunities_owner_hint(row),
        'sla_hours': opportunities_sla_hours(row),
        'exceptions': opportunities_exception_needed(row),
        'freeze': opportunities_freeze_window(row),
        'violations': policy.collect(row) + opportunities_run_field_checks(row),
        'summary': opportunities_summary_line(row),
    }

