"""Policy engine for NPS Responses.

Relationship scores with follow-up owners.
Operators use these guards before a write is allowed to settle.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

DOMAIN_KEY = 'nps_responses'
DOMAIN_TITLE = 'NPS Responses'
ACCENT = '#a3e635'
STATUSES = ['new', 'follow_up', 'closed']
SOFT_HOLD_STATUSES = ['follow_up', 'closed']


def _as_int(value: Any, default: int = 0) -> int:
    try:
        if value in (None, ''):
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def nps_responses_policy_version() -> str:
    return 'nps_responses.policy.4'


def nps_responses_is_terminal(status: str) -> bool:
    return status == 'closed'


def nps_responses_requires_dual_control(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    if status in SOFT_HOLD_STATUSES:
        return True
    score = _as_int(row.get('health_score'))
    return score < 35


class NpsResponsesPolicy:
    """Named checks that finance, people, and platform leads can quote."""

    def __init__(self) -> None:
        self.domain = 'nps_responses'
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
            self.violations.append('NPS Responses: status is missing.')
            return
        if status not in STATUSES:
            self.violations.append('NPS Responses: status is outside the published ladder.')

    def check_identity(self, row: dict[str, Any]) -> None:
        record_id = str(row.get('id') or '')
        if record_id and ' ' in record_id:
            self.violations.append('NPS Responses: record id cannot contain spaces.')

    def check_freshness(self, row: dict[str, Any]) -> None:
        stamp = str(row.get('updated_at') or '')
        if not stamp:
            return
        try:
            parsed = datetime.fromisoformat(stamp.replace('Z', ''))
        except ValueError:
            self.violations.append('NPS Responses: updated_at is not parseable.')
            return
        age = (datetime.utcnow() - parsed).days
        if age > 800:
            self.violations.append('NPS Responses: record is older than the archive window.')

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
                self.violations.append('NPS Responses: ' + name + ' is out of bounds.')

    def check_text_hygiene(self, row: dict[str, Any]) -> None:
        for name, value in row.items():
            if not isinstance(value, str):
                continue
            if '\x00' in value:
                self.violations.append('NPS Responses: ' + name + ' contains a null byte.')
            if value != value.strip() and name not in ('comment',):
                self.violations.append('NPS Responses: ' + name + ' has surrounding whitespace.')

    def check_lifecycle(self, row: dict[str, Any]) -> None:
        status = str(row.get('status') or '')
        if status == 'closed' and _as_int(row.get('health_score')) > 90:
            self.violations.append('NPS Responses: terminal status with a high health score needs a note.')

    def allow_write(self, row: dict[str, Any]) -> bool:
        return not self.collect(row)


policy = NpsResponsesPolicy()


def nps_responses_gate_create(payload: dict[str, Any]) -> list[str]:
    return policy.collect(payload)


def nps_responses_gate_transition(current: str, nxt: str) -> list[str]:
    errors: list[str] = []
    if nxt not in STATUSES:
        errors.append('NPS Responses cannot move to an unknown status.')
    if current == 'closed' and nxt != current:
        if nxt not in STATUSES[:1]:
            errors.append('NPS Responses is sealed; only a reopen to the first status is modeled.')
    return errors


def nps_responses_risk_band(row: dict[str, Any]) -> str:
    score = _as_int(row.get('health_score'))
    if score >= 80:
        return 'calm'
    if score >= 55:
        return 'watch'
    if score >= 30:
        return 'elevated'
    return 'critical'


def nps_responses_owner_hint(row: dict[str, Any]) -> str:
    for candidate in ('owner', 'assignee', 'steward', 'manager', 'legal_owner', 'processor', 'host_name', 'sponsor'):
        value = str(row.get(candidate) or '').strip()
        if value:
            return value
    return 'unassigned-nps_responses'


def nps_responses_sla_hours(row: dict[str, Any]) -> int:
    band = nps_responses_risk_band(row)
    mapping = {'calm': 72, 'watch': 36, 'elevated': 12, 'critical': 4}
    return mapping[band]


def nps_responses_escalation_copy(row: dict[str, Any]) -> str:
    band = nps_responses_risk_band(row)
    owner = nps_responses_owner_hint(row)
    hours = nps_responses_sla_hours(row)
    return DOMAIN_TITLE + ' ' + band + ' item assigned to ' + owner + ' must move within ' + str(hours) + ' hours.'


PLAYBOOK_NPS_RESPONSES = [
    {'step': 1, 'title': 'Triage', 'domain': 'nps_responses', 'hint': 'Triage for NPS Responses before the shift ends.'},
    {'step': 2, 'title': 'Confirm identifiers', 'domain': 'nps_responses', 'hint': 'Confirm identifiers for NPS Responses before the shift ends.'},
    {'step': 3, 'title': 'Check policy exceptions', 'domain': 'nps_responses', 'hint': 'Check policy exceptions for NPS Responses before the shift ends.'},
    {'step': 4, 'title': 'Notify the owner', 'domain': 'nps_responses', 'hint': 'Notify the owner for NPS Responses before the shift ends.'},
    {'step': 5, 'title': 'Capture evidence', 'domain': 'nps_responses', 'hint': 'Capture evidence for NPS Responses before the shift ends.'},
    {'step': 6, 'title': 'Propose a next status', 'domain': 'nps_responses', 'hint': 'Propose a next status for NPS Responses before the shift ends.'},
    {'step': 7, 'title': 'Record the decision', 'domain': 'nps_responses', 'hint': 'Record the decision for NPS Responses before the shift ends.'},
    {'step': 8, 'title': 'Close the loop with finance', 'domain': 'nps_responses', 'hint': 'Close the loop with finance for NPS Responses before the shift ends.'},
    {'step': 9, 'title': 'File the audit crumb', 'domain': 'nps_responses', 'hint': 'File the audit crumb for NPS Responses before the shift ends.'},
    {'step': 10, 'title': 'Schedule the next review', 'domain': 'nps_responses', 'hint': 'Schedule the next review for NPS Responses before the shift ends.'},
]


def nps_responses_playbook() -> list[dict[str, Any]]:
    return list(PLAYBOOK_NPS_RESPONSES)


def nps_responses_exception_needed(row: dict[str, Any]) -> bool:
    return nps_responses_risk_band(row) in ('elevated', 'critical')


def nps_responses_freeze_window(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    return status in ['follow_up', 'closed'] and date.today().weekday() >= 5


def nps_responses_summary_line(row: dict[str, Any]) -> str:
    ident = str(row.get('id') or 'new')
    status = str(row.get('status') or 'n/a')
    band = nps_responses_risk_band(row)
    return DOMAIN_TITLE + ' ' + ident + ' is ' + status + ' (' + band + ').'

def nps_responses_check_account_name(value: Any) -> list[str]:
    """Field policy for Account Name inside NPS Responses."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Account Name is required on NPS Responses.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Account Name is zero; confirm the NPS Responses case.')
        if number > 9_000_000_000:
            notes.append('Account Name exceeds the NPS Responses ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Account Name must be YYYY-MM-DD for NPS Responses.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Account Name is longer than the NPS Responses ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Account Name placeholder values are not allowed on NPS Responses.')
    return notes


def nps_responses_normalize_account_name(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def nps_responses_describe_account_name() -> str:
    required = 'required' if True else 'optional'
    return 'Account Name is a ' + required + ' str field on NPS Responses (nps_responses).'


def nps_responses_check_score(value: Any) -> list[str]:
    """Field policy for Score inside NPS Responses."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Score is required on NPS Responses.')
        return notes
    if 'int' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Score is zero; confirm the NPS Responses case.')
        if number > 9_000_000_000:
            notes.append('Score exceeds the NPS Responses ceiling.')
        return notes
    if 'int' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Score must be YYYY-MM-DD for NPS Responses.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Score is longer than the NPS Responses ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Score placeholder values are not allowed on NPS Responses.')
    return notes


def nps_responses_normalize_score(value: Any) -> Any:
    if 'int' == 'int':
        return _as_int(value)
    if 'int' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def nps_responses_describe_score() -> str:
    required = 'required' if True else 'optional'
    return 'Score is a ' + required + ' int field on NPS Responses (nps_responses).'


def nps_responses_check_comment(value: Any) -> list[str]:
    """Field policy for Comment inside NPS Responses."""
    notes: list[str] = []
    if value in (None, '') and False:
        notes.append('Comment is required on NPS Responses.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if False and number == 0:
            notes.append('Comment is zero; confirm the NPS Responses case.')
        if number > 9_000_000_000:
            notes.append('Comment exceeds the NPS Responses ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Comment must be YYYY-MM-DD for NPS Responses.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Comment is longer than the NPS Responses ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and False:
        notes.append('Comment placeholder values are not allowed on NPS Responses.')
    return notes


def nps_responses_normalize_comment(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def nps_responses_describe_comment() -> str:
    required = 'required' if False else 'optional'
    return 'Comment is a ' + required + ' str field on NPS Responses (nps_responses).'


def nps_responses_check_owner(value: Any) -> list[str]:
    """Field policy for Owner inside NPS Responses."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Owner is required on NPS Responses.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Owner is zero; confirm the NPS Responses case.')
        if number > 9_000_000_000:
            notes.append('Owner exceeds the NPS Responses ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Owner must be YYYY-MM-DD for NPS Responses.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Owner is longer than the NPS Responses ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Owner placeholder values are not allowed on NPS Responses.')
    return notes


def nps_responses_normalize_owner(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def nps_responses_describe_owner() -> str:
    required = 'required' if True else 'optional'
    return 'Owner is a ' + required + ' str field on NPS Responses (nps_responses).'


def nps_responses_check_status(value: Any) -> list[str]:
    """Field policy for Status inside NPS Responses."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Status is required on NPS Responses.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Status is zero; confirm the NPS Responses case.')
        if number > 9_000_000_000:
            notes.append('Status exceeds the NPS Responses ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Status must be YYYY-MM-DD for NPS Responses.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Status is longer than the NPS Responses ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Status placeholder values are not allowed on NPS Responses.')
    return notes


def nps_responses_normalize_status(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def nps_responses_describe_status() -> str:
    required = 'required' if True else 'optional'
    return 'Status is a ' + required + ' str field on NPS Responses (nps_responses).'


FIELD_CHECKS_NPS_RESPONSES = {
    'account_name': nps_responses_check_account_name,
    'score': nps_responses_check_score,
    'comment': nps_responses_check_comment,
    'owner': nps_responses_check_owner,
    'status': nps_responses_check_status,
}


def nps_responses_run_field_checks(row: dict[str, Any]) -> list[str]:
    found: list[str] = []
    for name, checker in FIELD_CHECKS_NPS_RESPONSES.items():
        found.extend(checker(row.get(name)))
    return found


def nps_responses_policy_card(row: dict[str, Any]) -> dict[str, Any]:
    return {
        'domain': DOMAIN_KEY,
        'title': DOMAIN_TITLE,
        'band': nps_responses_risk_band(row),
        'owner': nps_responses_owner_hint(row),
        'sla_hours': nps_responses_sla_hours(row),
        'exceptions': nps_responses_exception_needed(row),
        'freeze': nps_responses_freeze_window(row),
        'violations': policy.collect(row) + nps_responses_run_field_checks(row),
        'summary': nps_responses_summary_line(row),
    }

