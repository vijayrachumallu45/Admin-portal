"""Policy engine for SLA Policies.

Response and restore targets by severity.
Operators use these guards before a write is allowed to settle.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

DOMAIN_KEY = 'sla_policies'
DOMAIN_TITLE = 'SLA Policies'
ACCENT = '#fca5a5'
STATUSES = ['draft', 'live', 'paused']
SOFT_HOLD_STATUSES = ['live', 'paused']


def _as_int(value: Any, default: int = 0) -> int:
    try:
        if value in (None, ''):
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def sla_policies_policy_version() -> str:
    return 'sla_policies.policy.4'


def sla_policies_is_terminal(status: str) -> bool:
    return status == 'paused'


def sla_policies_requires_dual_control(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    if status in SOFT_HOLD_STATUSES:
        return True
    score = _as_int(row.get('health_score'))
    return score < 35


class SlaPoliciesPolicy:
    """Named checks that finance, people, and platform leads can quote."""

    def __init__(self) -> None:
        self.domain = 'sla_policies'
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
            self.violations.append('SLA Policies: status is missing.')
            return
        if status not in STATUSES:
            self.violations.append('SLA Policies: status is outside the published ladder.')

    def check_identity(self, row: dict[str, Any]) -> None:
        record_id = str(row.get('id') or '')
        if record_id and ' ' in record_id:
            self.violations.append('SLA Policies: record id cannot contain spaces.')

    def check_freshness(self, row: dict[str, Any]) -> None:
        stamp = str(row.get('updated_at') or '')
        if not stamp:
            return
        try:
            parsed = datetime.fromisoformat(stamp.replace('Z', ''))
        except ValueError:
            self.violations.append('SLA Policies: updated_at is not parseable.')
            return
        age = (datetime.utcnow() - parsed).days
        if age > 800:
            self.violations.append('SLA Policies: record is older than the archive window.')

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
                self.violations.append('SLA Policies: ' + name + ' is out of bounds.')

    def check_text_hygiene(self, row: dict[str, Any]) -> None:
        for name, value in row.items():
            if not isinstance(value, str):
                continue
            if '\x00' in value:
                self.violations.append('SLA Policies: ' + name + ' contains a null byte.')
            if value != value.strip() and name not in ('comment',):
                self.violations.append('SLA Policies: ' + name + ' has surrounding whitespace.')

    def check_lifecycle(self, row: dict[str, Any]) -> None:
        status = str(row.get('status') or '')
        if status == 'paused' and _as_int(row.get('health_score')) > 90:
            self.violations.append('SLA Policies: terminal status with a high health score needs a note.')

    def allow_write(self, row: dict[str, Any]) -> bool:
        return not self.collect(row)


policy = SlaPoliciesPolicy()


def sla_policies_gate_create(payload: dict[str, Any]) -> list[str]:
    return policy.collect(payload)


def sla_policies_gate_transition(current: str, nxt: str) -> list[str]:
    errors: list[str] = []
    if nxt not in STATUSES:
        errors.append('SLA Policies cannot move to an unknown status.')
    if current == 'paused' and nxt != current:
        if nxt not in STATUSES[:1]:
            errors.append('SLA Policies is sealed; only a reopen to the first status is modeled.')
    return errors


def sla_policies_risk_band(row: dict[str, Any]) -> str:
    score = _as_int(row.get('health_score'))
    if score >= 80:
        return 'calm'
    if score >= 55:
        return 'watch'
    if score >= 30:
        return 'elevated'
    return 'critical'


def sla_policies_owner_hint(row: dict[str, Any]) -> str:
    for candidate in ('owner', 'assignee', 'steward', 'manager', 'legal_owner', 'processor', 'host_name', 'sponsor'):
        value = str(row.get(candidate) or '').strip()
        if value:
            return value
    return 'unassigned-sla_policies'


def sla_policies_sla_hours(row: dict[str, Any]) -> int:
    band = sla_policies_risk_band(row)
    mapping = {'calm': 72, 'watch': 36, 'elevated': 12, 'critical': 4}
    return mapping[band]


def sla_policies_escalation_copy(row: dict[str, Any]) -> str:
    band = sla_policies_risk_band(row)
    owner = sla_policies_owner_hint(row)
    hours = sla_policies_sla_hours(row)
    return DOMAIN_TITLE + ' ' + band + ' item assigned to ' + owner + ' must move within ' + str(hours) + ' hours.'


PLAYBOOK_SLA_POLICIES = [
    {'step': 1, 'title': 'Triage', 'domain': 'sla_policies', 'hint': 'Triage for SLA Policies before the shift ends.'},
    {'step': 2, 'title': 'Confirm identifiers', 'domain': 'sla_policies', 'hint': 'Confirm identifiers for SLA Policies before the shift ends.'},
    {'step': 3, 'title': 'Check policy exceptions', 'domain': 'sla_policies', 'hint': 'Check policy exceptions for SLA Policies before the shift ends.'},
    {'step': 4, 'title': 'Notify the owner', 'domain': 'sla_policies', 'hint': 'Notify the owner for SLA Policies before the shift ends.'},
    {'step': 5, 'title': 'Capture evidence', 'domain': 'sla_policies', 'hint': 'Capture evidence for SLA Policies before the shift ends.'},
    {'step': 6, 'title': 'Propose a next status', 'domain': 'sla_policies', 'hint': 'Propose a next status for SLA Policies before the shift ends.'},
    {'step': 7, 'title': 'Record the decision', 'domain': 'sla_policies', 'hint': 'Record the decision for SLA Policies before the shift ends.'},
    {'step': 8, 'title': 'Close the loop with finance', 'domain': 'sla_policies', 'hint': 'Close the loop with finance for SLA Policies before the shift ends.'},
    {'step': 9, 'title': 'File the audit crumb', 'domain': 'sla_policies', 'hint': 'File the audit crumb for SLA Policies before the shift ends.'},
    {'step': 10, 'title': 'Schedule the next review', 'domain': 'sla_policies', 'hint': 'Schedule the next review for SLA Policies before the shift ends.'},
]


def sla_policies_playbook() -> list[dict[str, Any]]:
    return list(PLAYBOOK_SLA_POLICIES)


def sla_policies_exception_needed(row: dict[str, Any]) -> bool:
    return sla_policies_risk_band(row) in ('elevated', 'critical')


def sla_policies_freeze_window(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    return status in ['live', 'paused'] and date.today().weekday() >= 5


def sla_policies_summary_line(row: dict[str, Any]) -> str:
    ident = str(row.get('id') or 'new')
    status = str(row.get('status') or 'n/a')
    band = sla_policies_risk_band(row)
    return DOMAIN_TITLE + ' ' + ident + ' is ' + status + ' (' + band + ').'

def sla_policies_check_policy_code(value: Any) -> list[str]:
    """Field policy for Policy Code inside SLA Policies."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Policy Code is required on SLA Policies.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Policy Code is zero; confirm the SLA Policies case.')
        if number > 9_000_000_000:
            notes.append('Policy Code exceeds the SLA Policies ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Policy Code must be YYYY-MM-DD for SLA Policies.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Policy Code is longer than the SLA Policies ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Policy Code placeholder values are not allowed on SLA Policies.')
    return notes


def sla_policies_normalize_policy_code(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def sla_policies_describe_policy_code() -> str:
    required = 'required' if True else 'optional'
    return 'Policy Code is a ' + required + ' str field on SLA Policies (sla_policies).'


def sla_policies_check_severity(value: Any) -> list[str]:
    """Field policy for Severity inside SLA Policies."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Severity is required on SLA Policies.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Severity is zero; confirm the SLA Policies case.')
        if number > 9_000_000_000:
            notes.append('Severity exceeds the SLA Policies ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Severity must be YYYY-MM-DD for SLA Policies.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Severity is longer than the SLA Policies ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Severity placeholder values are not allowed on SLA Policies.')
    return notes


def sla_policies_normalize_severity(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def sla_policies_describe_severity() -> str:
    required = 'required' if True else 'optional'
    return 'Severity is a ' + required + ' str field on SLA Policies (sla_policies).'


def sla_policies_check_respond_minutes(value: Any) -> list[str]:
    """Field policy for Respond Minutes inside SLA Policies."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Respond Minutes is required on SLA Policies.')
        return notes
    if 'int' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Respond Minutes is zero; confirm the SLA Policies case.')
        if number > 9_000_000_000:
            notes.append('Respond Minutes exceeds the SLA Policies ceiling.')
        return notes
    if 'int' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Respond Minutes must be YYYY-MM-DD for SLA Policies.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Respond Minutes is longer than the SLA Policies ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Respond Minutes placeholder values are not allowed on SLA Policies.')
    return notes


def sla_policies_normalize_respond_minutes(value: Any) -> Any:
    if 'int' == 'int':
        return _as_int(value)
    if 'int' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def sla_policies_describe_respond_minutes() -> str:
    required = 'required' if True else 'optional'
    return 'Respond Minutes is a ' + required + ' int field on SLA Policies (sla_policies).'


def sla_policies_check_restore_minutes(value: Any) -> list[str]:
    """Field policy for Restore Minutes inside SLA Policies."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Restore Minutes is required on SLA Policies.')
        return notes
    if 'int' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Restore Minutes is zero; confirm the SLA Policies case.')
        if number > 9_000_000_000:
            notes.append('Restore Minutes exceeds the SLA Policies ceiling.')
        return notes
    if 'int' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Restore Minutes must be YYYY-MM-DD for SLA Policies.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Restore Minutes is longer than the SLA Policies ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Restore Minutes placeholder values are not allowed on SLA Policies.')
    return notes


def sla_policies_normalize_restore_minutes(value: Any) -> Any:
    if 'int' == 'int':
        return _as_int(value)
    if 'int' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def sla_policies_describe_restore_minutes() -> str:
    required = 'required' if True else 'optional'
    return 'Restore Minutes is a ' + required + ' int field on SLA Policies (sla_policies).'


def sla_policies_check_status(value: Any) -> list[str]:
    """Field policy for Status inside SLA Policies."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Status is required on SLA Policies.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Status is zero; confirm the SLA Policies case.')
        if number > 9_000_000_000:
            notes.append('Status exceeds the SLA Policies ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Status must be YYYY-MM-DD for SLA Policies.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Status is longer than the SLA Policies ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Status placeholder values are not allowed on SLA Policies.')
    return notes


def sla_policies_normalize_status(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def sla_policies_describe_status() -> str:
    required = 'required' if True else 'optional'
    return 'Status is a ' + required + ' str field on SLA Policies (sla_policies).'


FIELD_CHECKS_SLA_POLICIES = {
    'policy_code': sla_policies_check_policy_code,
    'severity': sla_policies_check_severity,
    'respond_minutes': sla_policies_check_respond_minutes,
    'restore_minutes': sla_policies_check_restore_minutes,
    'status': sla_policies_check_status,
}


def sla_policies_run_field_checks(row: dict[str, Any]) -> list[str]:
    found: list[str] = []
    for name, checker in FIELD_CHECKS_SLA_POLICIES.items():
        found.extend(checker(row.get(name)))
    return found


def sla_policies_policy_card(row: dict[str, Any]) -> dict[str, Any]:
    return {
        'domain': DOMAIN_KEY,
        'title': DOMAIN_TITLE,
        'band': sla_policies_risk_band(row),
        'owner': sla_policies_owner_hint(row),
        'sla_hours': sla_policies_sla_hours(row),
        'exceptions': sla_policies_exception_needed(row),
        'freeze': sla_policies_freeze_window(row),
        'violations': policy.collect(row) + sla_policies_run_field_checks(row),
        'summary': sla_policies_summary_line(row),
    }

