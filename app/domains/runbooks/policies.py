"""Policy engine for Ops Runbooks.

Stepwise recovery guides owned by platform teams.
Operators use these guards before a write is allowed to settle.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

DOMAIN_KEY = 'runbooks'
DOMAIN_TITLE = 'Ops Runbooks'
ACCENT = '#67e8f9'
STATUSES = ['draft', 'certified', 'stale']
SOFT_HOLD_STATUSES = ['certified', 'stale']


def _as_int(value: Any, default: int = 0) -> int:
    try:
        if value in (None, ''):
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def runbooks_policy_version() -> str:
    return 'runbooks.policy.4'


def runbooks_is_terminal(status: str) -> bool:
    return status == 'stale'


def runbooks_requires_dual_control(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    if status in SOFT_HOLD_STATUSES:
        return True
    score = _as_int(row.get('health_score'))
    return score < 35


class RunbooksPolicy:
    """Named checks that finance, people, and platform leads can quote."""

    def __init__(self) -> None:
        self.domain = 'runbooks'
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
            self.violations.append('Ops Runbooks: status is missing.')
            return
        if status not in STATUSES:
            self.violations.append('Ops Runbooks: status is outside the published ladder.')

    def check_identity(self, row: dict[str, Any]) -> None:
        record_id = str(row.get('id') or '')
        if record_id and ' ' in record_id:
            self.violations.append('Ops Runbooks: record id cannot contain spaces.')

    def check_freshness(self, row: dict[str, Any]) -> None:
        stamp = str(row.get('updated_at') or '')
        if not stamp:
            return
        try:
            parsed = datetime.fromisoformat(stamp.replace('Z', ''))
        except ValueError:
            self.violations.append('Ops Runbooks: updated_at is not parseable.')
            return
        age = (datetime.utcnow() - parsed).days
        if age > 800:
            self.violations.append('Ops Runbooks: record is older than the archive window.')

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
                self.violations.append('Ops Runbooks: ' + name + ' is out of bounds.')

    def check_text_hygiene(self, row: dict[str, Any]) -> None:
        for name, value in row.items():
            if not isinstance(value, str):
                continue
            if '\x00' in value:
                self.violations.append('Ops Runbooks: ' + name + ' contains a null byte.')
            if value != value.strip() and name not in ('comment',):
                self.violations.append('Ops Runbooks: ' + name + ' has surrounding whitespace.')

    def check_lifecycle(self, row: dict[str, Any]) -> None:
        status = str(row.get('status') or '')
        if status == 'stale' and _as_int(row.get('health_score')) > 90:
            self.violations.append('Ops Runbooks: terminal status with a high health score needs a note.')

    def allow_write(self, row: dict[str, Any]) -> bool:
        return not self.collect(row)


policy = RunbooksPolicy()


def runbooks_gate_create(payload: dict[str, Any]) -> list[str]:
    return policy.collect(payload)


def runbooks_gate_transition(current: str, nxt: str) -> list[str]:
    errors: list[str] = []
    if nxt not in STATUSES:
        errors.append('Ops Runbooks cannot move to an unknown status.')
    if current == 'stale' and nxt != current:
        if nxt not in STATUSES[:1]:
            errors.append('Ops Runbooks is sealed; only a reopen to the first status is modeled.')
    return errors


def runbooks_risk_band(row: dict[str, Any]) -> str:
    score = _as_int(row.get('health_score'))
    if score >= 80:
        return 'calm'
    if score >= 55:
        return 'watch'
    if score >= 30:
        return 'elevated'
    return 'critical'


def runbooks_owner_hint(row: dict[str, Any]) -> str:
    for candidate in ('owner', 'assignee', 'steward', 'manager', 'legal_owner', 'processor', 'host_name', 'sponsor'):
        value = str(row.get(candidate) or '').strip()
        if value:
            return value
    return 'unassigned-runbooks'


def runbooks_sla_hours(row: dict[str, Any]) -> int:
    band = runbooks_risk_band(row)
    mapping = {'calm': 72, 'watch': 36, 'elevated': 12, 'critical': 4}
    return mapping[band]


def runbooks_escalation_copy(row: dict[str, Any]) -> str:
    band = runbooks_risk_band(row)
    owner = runbooks_owner_hint(row)
    hours = runbooks_sla_hours(row)
    return DOMAIN_TITLE + ' ' + band + ' item assigned to ' + owner + ' must move within ' + str(hours) + ' hours.'


PLAYBOOK_RUNBOOKS = [
    {'step': 1, 'title': 'Triage', 'domain': 'runbooks', 'hint': 'Triage for Ops Runbooks before the shift ends.'},
    {'step': 2, 'title': 'Confirm identifiers', 'domain': 'runbooks', 'hint': 'Confirm identifiers for Ops Runbooks before the shift ends.'},
    {'step': 3, 'title': 'Check policy exceptions', 'domain': 'runbooks', 'hint': 'Check policy exceptions for Ops Runbooks before the shift ends.'},
    {'step': 4, 'title': 'Notify the owner', 'domain': 'runbooks', 'hint': 'Notify the owner for Ops Runbooks before the shift ends.'},
    {'step': 5, 'title': 'Capture evidence', 'domain': 'runbooks', 'hint': 'Capture evidence for Ops Runbooks before the shift ends.'},
    {'step': 6, 'title': 'Propose a next status', 'domain': 'runbooks', 'hint': 'Propose a next status for Ops Runbooks before the shift ends.'},
    {'step': 7, 'title': 'Record the decision', 'domain': 'runbooks', 'hint': 'Record the decision for Ops Runbooks before the shift ends.'},
    {'step': 8, 'title': 'Close the loop with finance', 'domain': 'runbooks', 'hint': 'Close the loop with finance for Ops Runbooks before the shift ends.'},
    {'step': 9, 'title': 'File the audit crumb', 'domain': 'runbooks', 'hint': 'File the audit crumb for Ops Runbooks before the shift ends.'},
    {'step': 10, 'title': 'Schedule the next review', 'domain': 'runbooks', 'hint': 'Schedule the next review for Ops Runbooks before the shift ends.'},
]


def runbooks_playbook() -> list[dict[str, Any]]:
    return list(PLAYBOOK_RUNBOOKS)


def runbooks_exception_needed(row: dict[str, Any]) -> bool:
    return runbooks_risk_band(row) in ('elevated', 'critical')


def runbooks_freeze_window(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    return status in ['certified', 'stale'] and date.today().weekday() >= 5


def runbooks_summary_line(row: dict[str, Any]) -> str:
    ident = str(row.get('id') or 'new')
    status = str(row.get('status') or 'n/a')
    band = runbooks_risk_band(row)
    return DOMAIN_TITLE + ' ' + ident + ' is ' + status + ' (' + band + ').'

def runbooks_check_runbook_key(value: Any) -> list[str]:
    """Field policy for Runbook Key inside Ops Runbooks."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Runbook Key is required on Ops Runbooks.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Runbook Key is zero; confirm the Ops Runbooks case.')
        if number > 9_000_000_000:
            notes.append('Runbook Key exceeds the Ops Runbooks ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Runbook Key must be YYYY-MM-DD for Ops Runbooks.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Runbook Key is longer than the Ops Runbooks ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Runbook Key placeholder values are not allowed on Ops Runbooks.')
    return notes


def runbooks_normalize_runbook_key(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def runbooks_describe_runbook_key() -> str:
    required = 'required' if True else 'optional'
    return 'Runbook Key is a ' + required + ' str field on Ops Runbooks (runbooks).'


def runbooks_check_title(value: Any) -> list[str]:
    """Field policy for Title inside Ops Runbooks."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Title is required on Ops Runbooks.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Title is zero; confirm the Ops Runbooks case.')
        if number > 9_000_000_000:
            notes.append('Title exceeds the Ops Runbooks ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Title must be YYYY-MM-DD for Ops Runbooks.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Title is longer than the Ops Runbooks ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Title placeholder values are not allowed on Ops Runbooks.')
    return notes


def runbooks_normalize_title(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def runbooks_describe_title() -> str:
    required = 'required' if True else 'optional'
    return 'Title is a ' + required + ' str field on Ops Runbooks (runbooks).'


def runbooks_check_owner(value: Any) -> list[str]:
    """Field policy for Owner inside Ops Runbooks."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Owner is required on Ops Runbooks.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Owner is zero; confirm the Ops Runbooks case.')
        if number > 9_000_000_000:
            notes.append('Owner exceeds the Ops Runbooks ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Owner must be YYYY-MM-DD for Ops Runbooks.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Owner is longer than the Ops Runbooks ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Owner placeholder values are not allowed on Ops Runbooks.')
    return notes


def runbooks_normalize_owner(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def runbooks_describe_owner() -> str:
    required = 'required' if True else 'optional'
    return 'Owner is a ' + required + ' str field on Ops Runbooks (runbooks).'


def runbooks_check_step_count(value: Any) -> list[str]:
    """Field policy for Step Count inside Ops Runbooks."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Step Count is required on Ops Runbooks.')
        return notes
    if 'int' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Step Count is zero; confirm the Ops Runbooks case.')
        if number > 9_000_000_000:
            notes.append('Step Count exceeds the Ops Runbooks ceiling.')
        return notes
    if 'int' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Step Count must be YYYY-MM-DD for Ops Runbooks.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Step Count is longer than the Ops Runbooks ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Step Count placeholder values are not allowed on Ops Runbooks.')
    return notes


def runbooks_normalize_step_count(value: Any) -> Any:
    if 'int' == 'int':
        return _as_int(value)
    if 'int' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def runbooks_describe_step_count() -> str:
    required = 'required' if True else 'optional'
    return 'Step Count is a ' + required + ' int field on Ops Runbooks (runbooks).'


def runbooks_check_status(value: Any) -> list[str]:
    """Field policy for Status inside Ops Runbooks."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Status is required on Ops Runbooks.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Status is zero; confirm the Ops Runbooks case.')
        if number > 9_000_000_000:
            notes.append('Status exceeds the Ops Runbooks ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Status must be YYYY-MM-DD for Ops Runbooks.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Status is longer than the Ops Runbooks ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Status placeholder values are not allowed on Ops Runbooks.')
    return notes


def runbooks_normalize_status(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def runbooks_describe_status() -> str:
    required = 'required' if True else 'optional'
    return 'Status is a ' + required + ' str field on Ops Runbooks (runbooks).'


FIELD_CHECKS_RUNBOOKS = {
    'runbook_key': runbooks_check_runbook_key,
    'title': runbooks_check_title,
    'owner': runbooks_check_owner,
    'step_count': runbooks_check_step_count,
    'status': runbooks_check_status,
}


def runbooks_run_field_checks(row: dict[str, Any]) -> list[str]:
    found: list[str] = []
    for name, checker in FIELD_CHECKS_RUNBOOKS.items():
        found.extend(checker(row.get(name)))
    return found


def runbooks_policy_card(row: dict[str, Any]) -> dict[str, Any]:
    return {
        'domain': DOMAIN_KEY,
        'title': DOMAIN_TITLE,
        'band': runbooks_risk_band(row),
        'owner': runbooks_owner_hint(row),
        'sla_hours': runbooks_sla_hours(row),
        'exceptions': runbooks_exception_needed(row),
        'freeze': runbooks_freeze_window(row),
        'violations': policy.collect(row) + runbooks_run_field_checks(row),
        'summary': runbooks_summary_line(row),
    }

