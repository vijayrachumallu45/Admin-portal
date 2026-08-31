"""Policy engine for OKR Board.

Objectives and key results with owners and confidence.
Operators use these guards before a write is allowed to settle.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

DOMAIN_KEY = 'okrs'
DOMAIN_TITLE = 'OKR Board'
ACCENT = '#818cf8'
STATUSES = ['draft', 'active', 'missed', 'hit']
SOFT_HOLD_STATUSES = ['missed', 'hit']


def _as_int(value: Any, default: int = 0) -> int:
    try:
        if value in (None, ''):
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def okrs_policy_version() -> str:
    return 'okrs.policy.4'


def okrs_is_terminal(status: str) -> bool:
    return status == 'hit'


def okrs_requires_dual_control(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    if status in SOFT_HOLD_STATUSES:
        return True
    score = _as_int(row.get('health_score'))
    return score < 35


class OkrsPolicy:
    """Named checks that finance, people, and platform leads can quote."""

    def __init__(self) -> None:
        self.domain = 'okrs'
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
            self.violations.append('OKR Board: status is missing.')
            return
        if status not in STATUSES:
            self.violations.append('OKR Board: status is outside the published ladder.')

    def check_identity(self, row: dict[str, Any]) -> None:
        record_id = str(row.get('id') or '')
        if record_id and ' ' in record_id:
            self.violations.append('OKR Board: record id cannot contain spaces.')

    def check_freshness(self, row: dict[str, Any]) -> None:
        stamp = str(row.get('updated_at') or '')
        if not stamp:
            return
        try:
            parsed = datetime.fromisoformat(stamp.replace('Z', ''))
        except ValueError:
            self.violations.append('OKR Board: updated_at is not parseable.')
            return
        age = (datetime.utcnow() - parsed).days
        if age > 800:
            self.violations.append('OKR Board: record is older than the archive window.')

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
                self.violations.append('OKR Board: ' + name + ' is out of bounds.')

    def check_text_hygiene(self, row: dict[str, Any]) -> None:
        for name, value in row.items():
            if not isinstance(value, str):
                continue
            if '\x00' in value:
                self.violations.append('OKR Board: ' + name + ' contains a null byte.')
            if value != value.strip() and name not in ('comment',):
                self.violations.append('OKR Board: ' + name + ' has surrounding whitespace.')

    def check_lifecycle(self, row: dict[str, Any]) -> None:
        status = str(row.get('status') or '')
        if status == 'hit' and _as_int(row.get('health_score')) > 90:
            self.violations.append('OKR Board: terminal status with a high health score needs a note.')

    def allow_write(self, row: dict[str, Any]) -> bool:
        return not self.collect(row)


policy = OkrsPolicy()


def okrs_gate_create(payload: dict[str, Any]) -> list[str]:
    return policy.collect(payload)


def okrs_gate_transition(current: str, nxt: str) -> list[str]:
    errors: list[str] = []
    if nxt not in STATUSES:
        errors.append('OKR Board cannot move to an unknown status.')
    if current == 'hit' and nxt != current:
        if nxt not in STATUSES[:1]:
            errors.append('OKR Board is sealed; only a reopen to the first status is modeled.')
    return errors


def okrs_risk_band(row: dict[str, Any]) -> str:
    score = _as_int(row.get('health_score'))
    if score >= 80:
        return 'calm'
    if score >= 55:
        return 'watch'
    if score >= 30:
        return 'elevated'
    return 'critical'


def okrs_owner_hint(row: dict[str, Any]) -> str:
    for candidate in ('owner', 'assignee', 'steward', 'manager', 'legal_owner', 'processor', 'host_name', 'sponsor'):
        value = str(row.get(candidate) or '').strip()
        if value:
            return value
    return 'unassigned-okrs'


def okrs_sla_hours(row: dict[str, Any]) -> int:
    band = okrs_risk_band(row)
    mapping = {'calm': 72, 'watch': 36, 'elevated': 12, 'critical': 4}
    return mapping[band]


def okrs_escalation_copy(row: dict[str, Any]) -> str:
    band = okrs_risk_band(row)
    owner = okrs_owner_hint(row)
    hours = okrs_sla_hours(row)
    return DOMAIN_TITLE + ' ' + band + ' item assigned to ' + owner + ' must move within ' + str(hours) + ' hours.'


PLAYBOOK_OKRS = [
    {'step': 1, 'title': 'Triage', 'domain': 'okrs', 'hint': 'Triage for OKR Board before the shift ends.'},
    {'step': 2, 'title': 'Confirm identifiers', 'domain': 'okrs', 'hint': 'Confirm identifiers for OKR Board before the shift ends.'},
    {'step': 3, 'title': 'Check policy exceptions', 'domain': 'okrs', 'hint': 'Check policy exceptions for OKR Board before the shift ends.'},
    {'step': 4, 'title': 'Notify the owner', 'domain': 'okrs', 'hint': 'Notify the owner for OKR Board before the shift ends.'},
    {'step': 5, 'title': 'Capture evidence', 'domain': 'okrs', 'hint': 'Capture evidence for OKR Board before the shift ends.'},
    {'step': 6, 'title': 'Propose a next status', 'domain': 'okrs', 'hint': 'Propose a next status for OKR Board before the shift ends.'},
    {'step': 7, 'title': 'Record the decision', 'domain': 'okrs', 'hint': 'Record the decision for OKR Board before the shift ends.'},
    {'step': 8, 'title': 'Close the loop with finance', 'domain': 'okrs', 'hint': 'Close the loop with finance for OKR Board before the shift ends.'},
    {'step': 9, 'title': 'File the audit crumb', 'domain': 'okrs', 'hint': 'File the audit crumb for OKR Board before the shift ends.'},
    {'step': 10, 'title': 'Schedule the next review', 'domain': 'okrs', 'hint': 'Schedule the next review for OKR Board before the shift ends.'},
]


def okrs_playbook() -> list[dict[str, Any]]:
    return list(PLAYBOOK_OKRS)


def okrs_exception_needed(row: dict[str, Any]) -> bool:
    return okrs_risk_band(row) in ('elevated', 'critical')


def okrs_freeze_window(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    return status in ['missed', 'hit'] and date.today().weekday() >= 5


def okrs_summary_line(row: dict[str, Any]) -> str:
    ident = str(row.get('id') or 'new')
    status = str(row.get('status') or 'n/a')
    band = okrs_risk_band(row)
    return DOMAIN_TITLE + ' ' + ident + ' is ' + status + ' (' + band + ').'

def okrs_check_okr_key(value: Any) -> list[str]:
    """Field policy for Okr Key inside OKR Board."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Okr Key is required on OKR Board.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Okr Key is zero; confirm the OKR Board case.')
        if number > 9_000_000_000:
            notes.append('Okr Key exceeds the OKR Board ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Okr Key must be YYYY-MM-DD for OKR Board.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Okr Key is longer than the OKR Board ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Okr Key placeholder values are not allowed on OKR Board.')
    return notes


def okrs_normalize_okr_key(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def okrs_describe_okr_key() -> str:
    required = 'required' if True else 'optional'
    return 'Okr Key is a ' + required + ' str field on OKR Board (okrs).'


def okrs_check_objective(value: Any) -> list[str]:
    """Field policy for Objective inside OKR Board."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Objective is required on OKR Board.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Objective is zero; confirm the OKR Board case.')
        if number > 9_000_000_000:
            notes.append('Objective exceeds the OKR Board ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Objective must be YYYY-MM-DD for OKR Board.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Objective is longer than the OKR Board ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Objective placeholder values are not allowed on OKR Board.')
    return notes


def okrs_normalize_objective(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def okrs_describe_objective() -> str:
    required = 'required' if True else 'optional'
    return 'Objective is a ' + required + ' str field on OKR Board (okrs).'


def okrs_check_owner(value: Any) -> list[str]:
    """Field policy for Owner inside OKR Board."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Owner is required on OKR Board.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Owner is zero; confirm the OKR Board case.')
        if number > 9_000_000_000:
            notes.append('Owner exceeds the OKR Board ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Owner must be YYYY-MM-DD for OKR Board.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Owner is longer than the OKR Board ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Owner placeholder values are not allowed on OKR Board.')
    return notes


def okrs_normalize_owner(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def okrs_describe_owner() -> str:
    required = 'required' if True else 'optional'
    return 'Owner is a ' + required + ' str field on OKR Board (okrs).'


def okrs_check_confidence(value: Any) -> list[str]:
    """Field policy for Confidence inside OKR Board."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Confidence is required on OKR Board.')
        return notes
    if 'int' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Confidence is zero; confirm the OKR Board case.')
        if number > 9_000_000_000:
            notes.append('Confidence exceeds the OKR Board ceiling.')
        return notes
    if 'int' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Confidence must be YYYY-MM-DD for OKR Board.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Confidence is longer than the OKR Board ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Confidence placeholder values are not allowed on OKR Board.')
    return notes


def okrs_normalize_confidence(value: Any) -> Any:
    if 'int' == 'int':
        return _as_int(value)
    if 'int' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def okrs_describe_confidence() -> str:
    required = 'required' if True else 'optional'
    return 'Confidence is a ' + required + ' int field on OKR Board (okrs).'


def okrs_check_status(value: Any) -> list[str]:
    """Field policy for Status inside OKR Board."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Status is required on OKR Board.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Status is zero; confirm the OKR Board case.')
        if number > 9_000_000_000:
            notes.append('Status exceeds the OKR Board ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Status must be YYYY-MM-DD for OKR Board.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Status is longer than the OKR Board ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Status placeholder values are not allowed on OKR Board.')
    return notes


def okrs_normalize_status(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def okrs_describe_status() -> str:
    required = 'required' if True else 'optional'
    return 'Status is a ' + required + ' str field on OKR Board (okrs).'


FIELD_CHECKS_OKRS = {
    'okr_key': okrs_check_okr_key,
    'objective': okrs_check_objective,
    'owner': okrs_check_owner,
    'confidence': okrs_check_confidence,
    'status': okrs_check_status,
}


def okrs_run_field_checks(row: dict[str, Any]) -> list[str]:
    found: list[str] = []
    for name, checker in FIELD_CHECKS_OKRS.items():
        found.extend(checker(row.get(name)))
    return found


def okrs_policy_card(row: dict[str, Any]) -> dict[str, Any]:
    return {
        'domain': DOMAIN_KEY,
        'title': DOMAIN_TITLE,
        'band': okrs_risk_band(row),
        'owner': okrs_owner_hint(row),
        'sla_hours': okrs_sla_hours(row),
        'exceptions': okrs_exception_needed(row),
        'freeze': okrs_freeze_window(row),
        'violations': policy.collect(row) + okrs_run_field_checks(row),
        'summary': okrs_summary_line(row),
    }

