"""Policy engine for Workflow Studio.

Approval graphs and automation steps without external keys.
Operators use these guards before a write is allowed to settle.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

DOMAIN_KEY = 'workflow_defs'
DOMAIN_TITLE = 'Workflow Studio'
ACCENT = '#c4b5fd'
STATUSES = ['draft', 'live', 'paused']
SOFT_HOLD_STATUSES = ['live', 'paused']


def _as_int(value: Any, default: int = 0) -> int:
    try:
        if value in (None, ''):
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def workflow_defs_policy_version() -> str:
    return 'workflow_defs.policy.4'


def workflow_defs_is_terminal(status: str) -> bool:
    return status == 'paused'


def workflow_defs_requires_dual_control(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    if status in SOFT_HOLD_STATUSES:
        return True
    score = _as_int(row.get('health_score'))
    return score < 35


class WorkflowDefsPolicy:
    """Named checks that finance, people, and platform leads can quote."""

    def __init__(self) -> None:
        self.domain = 'workflow_defs'
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
            self.violations.append('Workflow Studio: status is missing.')
            return
        if status not in STATUSES:
            self.violations.append('Workflow Studio: status is outside the published ladder.')

    def check_identity(self, row: dict[str, Any]) -> None:
        record_id = str(row.get('id') or '')
        if record_id and ' ' in record_id:
            self.violations.append('Workflow Studio: record id cannot contain spaces.')

    def check_freshness(self, row: dict[str, Any]) -> None:
        stamp = str(row.get('updated_at') or '')
        if not stamp:
            return
        try:
            parsed = datetime.fromisoformat(stamp.replace('Z', ''))
        except ValueError:
            self.violations.append('Workflow Studio: updated_at is not parseable.')
            return
        age = (datetime.utcnow() - parsed).days
        if age > 800:
            self.violations.append('Workflow Studio: record is older than the archive window.')

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
                self.violations.append('Workflow Studio: ' + name + ' is out of bounds.')

    def check_text_hygiene(self, row: dict[str, Any]) -> None:
        for name, value in row.items():
            if not isinstance(value, str):
                continue
            if '\x00' in value:
                self.violations.append('Workflow Studio: ' + name + ' contains a null byte.')
            if value != value.strip() and name not in ('comment',):
                self.violations.append('Workflow Studio: ' + name + ' has surrounding whitespace.')

    def check_lifecycle(self, row: dict[str, Any]) -> None:
        status = str(row.get('status') or '')
        if status == 'paused' and _as_int(row.get('health_score')) > 90:
            self.violations.append('Workflow Studio: terminal status with a high health score needs a note.')

    def allow_write(self, row: dict[str, Any]) -> bool:
        return not self.collect(row)


policy = WorkflowDefsPolicy()


def workflow_defs_gate_create(payload: dict[str, Any]) -> list[str]:
    return policy.collect(payload)


def workflow_defs_gate_transition(current: str, nxt: str) -> list[str]:
    errors: list[str] = []
    if nxt not in STATUSES:
        errors.append('Workflow Studio cannot move to an unknown status.')
    if current == 'paused' and nxt != current:
        if nxt not in STATUSES[:1]:
            errors.append('Workflow Studio is sealed; only a reopen to the first status is modeled.')
    return errors


def workflow_defs_risk_band(row: dict[str, Any]) -> str:
    score = _as_int(row.get('health_score'))
    if score >= 80:
        return 'calm'
    if score >= 55:
        return 'watch'
    if score >= 30:
        return 'elevated'
    return 'critical'


def workflow_defs_owner_hint(row: dict[str, Any]) -> str:
    for candidate in ('owner', 'assignee', 'steward', 'manager', 'legal_owner', 'processor', 'host_name', 'sponsor'):
        value = str(row.get(candidate) or '').strip()
        if value:
            return value
    return 'unassigned-workflow_defs'


def workflow_defs_sla_hours(row: dict[str, Any]) -> int:
    band = workflow_defs_risk_band(row)
    mapping = {'calm': 72, 'watch': 36, 'elevated': 12, 'critical': 4}
    return mapping[band]


def workflow_defs_escalation_copy(row: dict[str, Any]) -> str:
    band = workflow_defs_risk_band(row)
    owner = workflow_defs_owner_hint(row)
    hours = workflow_defs_sla_hours(row)
    return DOMAIN_TITLE + ' ' + band + ' item assigned to ' + owner + ' must move within ' + str(hours) + ' hours.'


PLAYBOOK_WORKFLOW_DEFS = [
    {'step': 1, 'title': 'Triage', 'domain': 'workflow_defs', 'hint': 'Triage for Workflow Studio before the shift ends.'},
    {'step': 2, 'title': 'Confirm identifiers', 'domain': 'workflow_defs', 'hint': 'Confirm identifiers for Workflow Studio before the shift ends.'},
    {'step': 3, 'title': 'Check policy exceptions', 'domain': 'workflow_defs', 'hint': 'Check policy exceptions for Workflow Studio before the shift ends.'},
    {'step': 4, 'title': 'Notify the owner', 'domain': 'workflow_defs', 'hint': 'Notify the owner for Workflow Studio before the shift ends.'},
    {'step': 5, 'title': 'Capture evidence', 'domain': 'workflow_defs', 'hint': 'Capture evidence for Workflow Studio before the shift ends.'},
    {'step': 6, 'title': 'Propose a next status', 'domain': 'workflow_defs', 'hint': 'Propose a next status for Workflow Studio before the shift ends.'},
    {'step': 7, 'title': 'Record the decision', 'domain': 'workflow_defs', 'hint': 'Record the decision for Workflow Studio before the shift ends.'},
    {'step': 8, 'title': 'Close the loop with finance', 'domain': 'workflow_defs', 'hint': 'Close the loop with finance for Workflow Studio before the shift ends.'},
    {'step': 9, 'title': 'File the audit crumb', 'domain': 'workflow_defs', 'hint': 'File the audit crumb for Workflow Studio before the shift ends.'},
    {'step': 10, 'title': 'Schedule the next review', 'domain': 'workflow_defs', 'hint': 'Schedule the next review for Workflow Studio before the shift ends.'},
]


def workflow_defs_playbook() -> list[dict[str, Any]]:
    return list(PLAYBOOK_WORKFLOW_DEFS)


def workflow_defs_exception_needed(row: dict[str, Any]) -> bool:
    return workflow_defs_risk_band(row) in ('elevated', 'critical')


def workflow_defs_freeze_window(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    return status in ['live', 'paused'] and date.today().weekday() >= 5


def workflow_defs_summary_line(row: dict[str, Any]) -> str:
    ident = str(row.get('id') or 'new')
    status = str(row.get('status') or 'n/a')
    band = workflow_defs_risk_band(row)
    return DOMAIN_TITLE + ' ' + ident + ' is ' + status + ' (' + band + ').'

def workflow_defs_check_workflow_key(value: Any) -> list[str]:
    """Field policy for Workflow Key inside Workflow Studio."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Workflow Key is required on Workflow Studio.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Workflow Key is zero; confirm the Workflow Studio case.')
        if number > 9_000_000_000:
            notes.append('Workflow Key exceeds the Workflow Studio ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Workflow Key must be YYYY-MM-DD for Workflow Studio.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Workflow Key is longer than the Workflow Studio ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Workflow Key placeholder values are not allowed on Workflow Studio.')
    return notes


def workflow_defs_normalize_workflow_key(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def workflow_defs_describe_workflow_key() -> str:
    required = 'required' if True else 'optional'
    return 'Workflow Key is a ' + required + ' str field on Workflow Studio (workflow_defs).'


def workflow_defs_check_name(value: Any) -> list[str]:
    """Field policy for Name inside Workflow Studio."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Name is required on Workflow Studio.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Name is zero; confirm the Workflow Studio case.')
        if number > 9_000_000_000:
            notes.append('Name exceeds the Workflow Studio ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Name must be YYYY-MM-DD for Workflow Studio.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Name is longer than the Workflow Studio ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Name placeholder values are not allowed on Workflow Studio.')
    return notes


def workflow_defs_normalize_name(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def workflow_defs_describe_name() -> str:
    required = 'required' if True else 'optional'
    return 'Name is a ' + required + ' str field on Workflow Studio (workflow_defs).'


def workflow_defs_check_trigger_event(value: Any) -> list[str]:
    """Field policy for Trigger Event inside Workflow Studio."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Trigger Event is required on Workflow Studio.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Trigger Event is zero; confirm the Workflow Studio case.')
        if number > 9_000_000_000:
            notes.append('Trigger Event exceeds the Workflow Studio ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Trigger Event must be YYYY-MM-DD for Workflow Studio.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Trigger Event is longer than the Workflow Studio ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Trigger Event placeholder values are not allowed on Workflow Studio.')
    return notes


def workflow_defs_normalize_trigger_event(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def workflow_defs_describe_trigger_event() -> str:
    required = 'required' if True else 'optional'
    return 'Trigger Event is a ' + required + ' str field on Workflow Studio (workflow_defs).'


def workflow_defs_check_step_count(value: Any) -> list[str]:
    """Field policy for Step Count inside Workflow Studio."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Step Count is required on Workflow Studio.')
        return notes
    if 'int' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Step Count is zero; confirm the Workflow Studio case.')
        if number > 9_000_000_000:
            notes.append('Step Count exceeds the Workflow Studio ceiling.')
        return notes
    if 'int' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Step Count must be YYYY-MM-DD for Workflow Studio.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Step Count is longer than the Workflow Studio ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Step Count placeholder values are not allowed on Workflow Studio.')
    return notes


def workflow_defs_normalize_step_count(value: Any) -> Any:
    if 'int' == 'int':
        return _as_int(value)
    if 'int' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def workflow_defs_describe_step_count() -> str:
    required = 'required' if True else 'optional'
    return 'Step Count is a ' + required + ' int field on Workflow Studio (workflow_defs).'


def workflow_defs_check_status(value: Any) -> list[str]:
    """Field policy for Status inside Workflow Studio."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Status is required on Workflow Studio.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Status is zero; confirm the Workflow Studio case.')
        if number > 9_000_000_000:
            notes.append('Status exceeds the Workflow Studio ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Status must be YYYY-MM-DD for Workflow Studio.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Status is longer than the Workflow Studio ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Status placeholder values are not allowed on Workflow Studio.')
    return notes


def workflow_defs_normalize_status(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def workflow_defs_describe_status() -> str:
    required = 'required' if True else 'optional'
    return 'Status is a ' + required + ' str field on Workflow Studio (workflow_defs).'


FIELD_CHECKS_WORKFLOW_DEFS = {
    'workflow_key': workflow_defs_check_workflow_key,
    'name': workflow_defs_check_name,
    'trigger_event': workflow_defs_check_trigger_event,
    'step_count': workflow_defs_check_step_count,
    'status': workflow_defs_check_status,
}


def workflow_defs_run_field_checks(row: dict[str, Any]) -> list[str]:
    found: list[str] = []
    for name, checker in FIELD_CHECKS_WORKFLOW_DEFS.items():
        found.extend(checker(row.get(name)))
    return found


def workflow_defs_policy_card(row: dict[str, Any]) -> dict[str, Any]:
    return {
        'domain': DOMAIN_KEY,
        'title': DOMAIN_TITLE,
        'band': workflow_defs_risk_band(row),
        'owner': workflow_defs_owner_hint(row),
        'sla_hours': workflow_defs_sla_hours(row),
        'exceptions': workflow_defs_exception_needed(row),
        'freeze': workflow_defs_freeze_window(row),
        'violations': policy.collect(row) + workflow_defs_run_field_checks(row),
        'summary': workflow_defs_summary_line(row),
    }

