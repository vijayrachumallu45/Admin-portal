"""Policy engine for Contractor Bench.

External workers with end dates and sponsoring managers.
Operators use these guards before a write is allowed to settle.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

DOMAIN_KEY = 'contractors'
DOMAIN_TITLE = 'Contractor Bench'
ACCENT = '#c4b5fd'
STATUSES = ['active', 'ending', 'ended']
SOFT_HOLD_STATUSES = ['ending', 'ended']


def _as_int(value: Any, default: int = 0) -> int:
    try:
        if value in (None, ''):
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def contractors_policy_version() -> str:
    return 'contractors.policy.4'


def contractors_is_terminal(status: str) -> bool:
    return status == 'ended'


def contractors_requires_dual_control(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    if status in SOFT_HOLD_STATUSES:
        return True
    score = _as_int(row.get('health_score'))
    return score < 35


class ContractorsPolicy:
    """Named checks that finance, people, and platform leads can quote."""

    def __init__(self) -> None:
        self.domain = 'contractors'
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
            self.violations.append('Contractor Bench: status is missing.')
            return
        if status not in STATUSES:
            self.violations.append('Contractor Bench: status is outside the published ladder.')

    def check_identity(self, row: dict[str, Any]) -> None:
        record_id = str(row.get('id') or '')
        if record_id and ' ' in record_id:
            self.violations.append('Contractor Bench: record id cannot contain spaces.')

    def check_freshness(self, row: dict[str, Any]) -> None:
        stamp = str(row.get('updated_at') or '')
        if not stamp:
            return
        try:
            parsed = datetime.fromisoformat(stamp.replace('Z', ''))
        except ValueError:
            self.violations.append('Contractor Bench: updated_at is not parseable.')
            return
        age = (datetime.utcnow() - parsed).days
        if age > 800:
            self.violations.append('Contractor Bench: record is older than the archive window.')

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
                self.violations.append('Contractor Bench: ' + name + ' is out of bounds.')

    def check_text_hygiene(self, row: dict[str, Any]) -> None:
        for name, value in row.items():
            if not isinstance(value, str):
                continue
            if '\x00' in value:
                self.violations.append('Contractor Bench: ' + name + ' contains a null byte.')
            if value != value.strip() and name not in ('comment',):
                self.violations.append('Contractor Bench: ' + name + ' has surrounding whitespace.')

    def check_lifecycle(self, row: dict[str, Any]) -> None:
        status = str(row.get('status') or '')
        if status == 'ended' and _as_int(row.get('health_score')) > 90:
            self.violations.append('Contractor Bench: terminal status with a high health score needs a note.')

    def allow_write(self, row: dict[str, Any]) -> bool:
        return not self.collect(row)


policy = ContractorsPolicy()


def contractors_gate_create(payload: dict[str, Any]) -> list[str]:
    return policy.collect(payload)


def contractors_gate_transition(current: str, nxt: str) -> list[str]:
    errors: list[str] = []
    if nxt not in STATUSES:
        errors.append('Contractor Bench cannot move to an unknown status.')
    if current == 'ended' and nxt != current:
        if nxt not in STATUSES[:1]:
            errors.append('Contractor Bench is sealed; only a reopen to the first status is modeled.')
    return errors


def contractors_risk_band(row: dict[str, Any]) -> str:
    score = _as_int(row.get('health_score'))
    if score >= 80:
        return 'calm'
    if score >= 55:
        return 'watch'
    if score >= 30:
        return 'elevated'
    return 'critical'


def contractors_owner_hint(row: dict[str, Any]) -> str:
    for candidate in ('owner', 'assignee', 'steward', 'manager', 'legal_owner', 'processor', 'host_name', 'sponsor'):
        value = str(row.get(candidate) or '').strip()
        if value:
            return value
    return 'unassigned-contractors'


def contractors_sla_hours(row: dict[str, Any]) -> int:
    band = contractors_risk_band(row)
    mapping = {'calm': 72, 'watch': 36, 'elevated': 12, 'critical': 4}
    return mapping[band]


def contractors_escalation_copy(row: dict[str, Any]) -> str:
    band = contractors_risk_band(row)
    owner = contractors_owner_hint(row)
    hours = contractors_sla_hours(row)
    return DOMAIN_TITLE + ' ' + band + ' item assigned to ' + owner + ' must move within ' + str(hours) + ' hours.'


PLAYBOOK_CONTRACTORS = [
    {'step': 1, 'title': 'Triage', 'domain': 'contractors', 'hint': 'Triage for Contractor Bench before the shift ends.'},
    {'step': 2, 'title': 'Confirm identifiers', 'domain': 'contractors', 'hint': 'Confirm identifiers for Contractor Bench before the shift ends.'},
    {'step': 3, 'title': 'Check policy exceptions', 'domain': 'contractors', 'hint': 'Check policy exceptions for Contractor Bench before the shift ends.'},
    {'step': 4, 'title': 'Notify the owner', 'domain': 'contractors', 'hint': 'Notify the owner for Contractor Bench before the shift ends.'},
    {'step': 5, 'title': 'Capture evidence', 'domain': 'contractors', 'hint': 'Capture evidence for Contractor Bench before the shift ends.'},
    {'step': 6, 'title': 'Propose a next status', 'domain': 'contractors', 'hint': 'Propose a next status for Contractor Bench before the shift ends.'},
    {'step': 7, 'title': 'Record the decision', 'domain': 'contractors', 'hint': 'Record the decision for Contractor Bench before the shift ends.'},
    {'step': 8, 'title': 'Close the loop with finance', 'domain': 'contractors', 'hint': 'Close the loop with finance for Contractor Bench before the shift ends.'},
    {'step': 9, 'title': 'File the audit crumb', 'domain': 'contractors', 'hint': 'File the audit crumb for Contractor Bench before the shift ends.'},
    {'step': 10, 'title': 'Schedule the next review', 'domain': 'contractors', 'hint': 'Schedule the next review for Contractor Bench before the shift ends.'},
]


def contractors_playbook() -> list[dict[str, Any]]:
    return list(PLAYBOOK_CONTRACTORS)


def contractors_exception_needed(row: dict[str, Any]) -> bool:
    return contractors_risk_band(row) in ('elevated', 'critical')


def contractors_freeze_window(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    return status in ['ending', 'ended'] and date.today().weekday() >= 5


def contractors_summary_line(row: dict[str, Any]) -> str:
    ident = str(row.get('id') or 'new')
    status = str(row.get('status') or 'n/a')
    band = contractors_risk_band(row)
    return DOMAIN_TITLE + ' ' + ident + ' is ' + status + ' (' + band + ').'

def contractors_check_contractor_no(value: Any) -> list[str]:
    """Field policy for Contractor No inside Contractor Bench."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Contractor No is required on Contractor Bench.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Contractor No is zero; confirm the Contractor Bench case.')
        if number > 9_000_000_000:
            notes.append('Contractor No exceeds the Contractor Bench ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Contractor No must be YYYY-MM-DD for Contractor Bench.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Contractor No is longer than the Contractor Bench ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Contractor No placeholder values are not allowed on Contractor Bench.')
    return notes


def contractors_normalize_contractor_no(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def contractors_describe_contractor_no() -> str:
    required = 'required' if True else 'optional'
    return 'Contractor No is a ' + required + ' str field on Contractor Bench (contractors).'


def contractors_check_full_name(value: Any) -> list[str]:
    """Field policy for Full Name inside Contractor Bench."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Full Name is required on Contractor Bench.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Full Name is zero; confirm the Contractor Bench case.')
        if number > 9_000_000_000:
            notes.append('Full Name exceeds the Contractor Bench ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Full Name must be YYYY-MM-DD for Contractor Bench.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Full Name is longer than the Contractor Bench ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Full Name placeholder values are not allowed on Contractor Bench.')
    return notes


def contractors_normalize_full_name(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def contractors_describe_full_name() -> str:
    required = 'required' if True else 'optional'
    return 'Full Name is a ' + required + ' str field on Contractor Bench (contractors).'


def contractors_check_sponsor(value: Any) -> list[str]:
    """Field policy for Sponsor inside Contractor Bench."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Sponsor is required on Contractor Bench.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Sponsor is zero; confirm the Contractor Bench case.')
        if number > 9_000_000_000:
            notes.append('Sponsor exceeds the Contractor Bench ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Sponsor must be YYYY-MM-DD for Contractor Bench.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Sponsor is longer than the Contractor Bench ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Sponsor placeholder values are not allowed on Contractor Bench.')
    return notes


def contractors_normalize_sponsor(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def contractors_describe_sponsor() -> str:
    required = 'required' if True else 'optional'
    return 'Sponsor is a ' + required + ' str field on Contractor Bench (contractors).'


def contractors_check_ends_on(value: Any) -> list[str]:
    """Field policy for Ends On inside Contractor Bench."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Ends On is required on Contractor Bench.')
        return notes
    if 'date' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Ends On is zero; confirm the Contractor Bench case.')
        if number > 9_000_000_000:
            notes.append('Ends On exceeds the Contractor Bench ceiling.')
        return notes
    if 'date' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Ends On must be YYYY-MM-DD for Contractor Bench.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Ends On is longer than the Contractor Bench ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Ends On placeholder values are not allowed on Contractor Bench.')
    return notes


def contractors_normalize_ends_on(value: Any) -> Any:
    if 'date' == 'int':
        return _as_int(value)
    if 'date' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def contractors_describe_ends_on() -> str:
    required = 'required' if True else 'optional'
    return 'Ends On is a ' + required + ' date field on Contractor Bench (contractors).'


def contractors_check_status(value: Any) -> list[str]:
    """Field policy for Status inside Contractor Bench."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Status is required on Contractor Bench.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Status is zero; confirm the Contractor Bench case.')
        if number > 9_000_000_000:
            notes.append('Status exceeds the Contractor Bench ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Status must be YYYY-MM-DD for Contractor Bench.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Status is longer than the Contractor Bench ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Status placeholder values are not allowed on Contractor Bench.')
    return notes


def contractors_normalize_status(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def contractors_describe_status() -> str:
    required = 'required' if True else 'optional'
    return 'Status is a ' + required + ' str field on Contractor Bench (contractors).'


FIELD_CHECKS_CONTRACTORS = {
    'contractor_no': contractors_check_contractor_no,
    'full_name': contractors_check_full_name,
    'sponsor': contractors_check_sponsor,
    'ends_on': contractors_check_ends_on,
    'status': contractors_check_status,
}


def contractors_run_field_checks(row: dict[str, Any]) -> list[str]:
    found: list[str] = []
    for name, checker in FIELD_CHECKS_CONTRACTORS.items():
        found.extend(checker(row.get(name)))
    return found


def contractors_policy_card(row: dict[str, Any]) -> dict[str, Any]:
    return {
        'domain': DOMAIN_KEY,
        'title': DOMAIN_TITLE,
        'band': contractors_risk_band(row),
        'owner': contractors_owner_hint(row),
        'sla_hours': contractors_sla_hours(row),
        'exceptions': contractors_exception_needed(row),
        'freeze': contractors_freeze_window(row),
        'violations': policy.collect(row) + contractors_run_field_checks(row),
        'summary': contractors_summary_line(row),
    }

