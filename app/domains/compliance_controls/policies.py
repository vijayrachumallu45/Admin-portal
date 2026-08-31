"""Policy engine for Compliance Controls.

SOC-style control statements, owners, and test cadence.
Operators use these guards before a write is allowed to settle.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

DOMAIN_KEY = 'compliance_controls'
DOMAIN_TITLE = 'Compliance Controls'
ACCENT = '#e2e8f0'
STATUSES = ['designed', 'operating', 'gap', 'retired']
SOFT_HOLD_STATUSES = ['gap', 'retired']


def _as_int(value: Any, default: int = 0) -> int:
    try:
        if value in (None, ''):
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def compliance_controls_policy_version() -> str:
    return 'compliance_controls.policy.4'


def compliance_controls_is_terminal(status: str) -> bool:
    return status == 'retired'


def compliance_controls_requires_dual_control(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    if status in SOFT_HOLD_STATUSES:
        return True
    score = _as_int(row.get('health_score'))
    return score < 35


class ComplianceControlsPolicy:
    """Named checks that finance, people, and platform leads can quote."""

    def __init__(self) -> None:
        self.domain = 'compliance_controls'
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
            self.violations.append('Compliance Controls: status is missing.')
            return
        if status not in STATUSES:
            self.violations.append('Compliance Controls: status is outside the published ladder.')

    def check_identity(self, row: dict[str, Any]) -> None:
        record_id = str(row.get('id') or '')
        if record_id and ' ' in record_id:
            self.violations.append('Compliance Controls: record id cannot contain spaces.')

    def check_freshness(self, row: dict[str, Any]) -> None:
        stamp = str(row.get('updated_at') or '')
        if not stamp:
            return
        try:
            parsed = datetime.fromisoformat(stamp.replace('Z', ''))
        except ValueError:
            self.violations.append('Compliance Controls: updated_at is not parseable.')
            return
        age = (datetime.utcnow() - parsed).days
        if age > 800:
            self.violations.append('Compliance Controls: record is older than the archive window.')

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
                self.violations.append('Compliance Controls: ' + name + ' is out of bounds.')

    def check_text_hygiene(self, row: dict[str, Any]) -> None:
        for name, value in row.items():
            if not isinstance(value, str):
                continue
            if '\x00' in value:
                self.violations.append('Compliance Controls: ' + name + ' contains a null byte.')
            if value != value.strip() and name not in ('comment',):
                self.violations.append('Compliance Controls: ' + name + ' has surrounding whitespace.')

    def check_lifecycle(self, row: dict[str, Any]) -> None:
        status = str(row.get('status') or '')
        if status == 'retired' and _as_int(row.get('health_score')) > 90:
            self.violations.append('Compliance Controls: terminal status with a high health score needs a note.')

    def allow_write(self, row: dict[str, Any]) -> bool:
        return not self.collect(row)


policy = ComplianceControlsPolicy()


def compliance_controls_gate_create(payload: dict[str, Any]) -> list[str]:
    return policy.collect(payload)


def compliance_controls_gate_transition(current: str, nxt: str) -> list[str]:
    errors: list[str] = []
    if nxt not in STATUSES:
        errors.append('Compliance Controls cannot move to an unknown status.')
    if current == 'retired' and nxt != current:
        if nxt not in STATUSES[:1]:
            errors.append('Compliance Controls is sealed; only a reopen to the first status is modeled.')
    return errors


def compliance_controls_risk_band(row: dict[str, Any]) -> str:
    score = _as_int(row.get('health_score'))
    if score >= 80:
        return 'calm'
    if score >= 55:
        return 'watch'
    if score >= 30:
        return 'elevated'
    return 'critical'


def compliance_controls_owner_hint(row: dict[str, Any]) -> str:
    for candidate in ('owner', 'assignee', 'steward', 'manager', 'legal_owner', 'processor', 'host_name', 'sponsor'):
        value = str(row.get(candidate) or '').strip()
        if value:
            return value
    return 'unassigned-compliance_controls'


def compliance_controls_sla_hours(row: dict[str, Any]) -> int:
    band = compliance_controls_risk_band(row)
    mapping = {'calm': 72, 'watch': 36, 'elevated': 12, 'critical': 4}
    return mapping[band]


def compliance_controls_escalation_copy(row: dict[str, Any]) -> str:
    band = compliance_controls_risk_band(row)
    owner = compliance_controls_owner_hint(row)
    hours = compliance_controls_sla_hours(row)
    return DOMAIN_TITLE + ' ' + band + ' item assigned to ' + owner + ' must move within ' + str(hours) + ' hours.'


PLAYBOOK_COMPLIANCE_CONTROLS = [
    {'step': 1, 'title': 'Triage', 'domain': 'compliance_controls', 'hint': 'Triage for Compliance Controls before the shift ends.'},
    {'step': 2, 'title': 'Confirm identifiers', 'domain': 'compliance_controls', 'hint': 'Confirm identifiers for Compliance Controls before the shift ends.'},
    {'step': 3, 'title': 'Check policy exceptions', 'domain': 'compliance_controls', 'hint': 'Check policy exceptions for Compliance Controls before the shift ends.'},
    {'step': 4, 'title': 'Notify the owner', 'domain': 'compliance_controls', 'hint': 'Notify the owner for Compliance Controls before the shift ends.'},
    {'step': 5, 'title': 'Capture evidence', 'domain': 'compliance_controls', 'hint': 'Capture evidence for Compliance Controls before the shift ends.'},
    {'step': 6, 'title': 'Propose a next status', 'domain': 'compliance_controls', 'hint': 'Propose a next status for Compliance Controls before the shift ends.'},
    {'step': 7, 'title': 'Record the decision', 'domain': 'compliance_controls', 'hint': 'Record the decision for Compliance Controls before the shift ends.'},
    {'step': 8, 'title': 'Close the loop with finance', 'domain': 'compliance_controls', 'hint': 'Close the loop with finance for Compliance Controls before the shift ends.'},
    {'step': 9, 'title': 'File the audit crumb', 'domain': 'compliance_controls', 'hint': 'File the audit crumb for Compliance Controls before the shift ends.'},
    {'step': 10, 'title': 'Schedule the next review', 'domain': 'compliance_controls', 'hint': 'Schedule the next review for Compliance Controls before the shift ends.'},
]


def compliance_controls_playbook() -> list[dict[str, Any]]:
    return list(PLAYBOOK_COMPLIANCE_CONTROLS)


def compliance_controls_exception_needed(row: dict[str, Any]) -> bool:
    return compliance_controls_risk_band(row) in ('elevated', 'critical')


def compliance_controls_freeze_window(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    return status in ['gap', 'retired'] and date.today().weekday() >= 5


def compliance_controls_summary_line(row: dict[str, Any]) -> str:
    ident = str(row.get('id') or 'new')
    status = str(row.get('status') or 'n/a')
    band = compliance_controls_risk_band(row)
    return DOMAIN_TITLE + ' ' + ident + ' is ' + status + ' (' + band + ').'

def compliance_controls_check_control_id(value: Any) -> list[str]:
    """Field policy for Control Id inside Compliance Controls."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Control Id is required on Compliance Controls.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Control Id is zero; confirm the Compliance Controls case.')
        if number > 9_000_000_000:
            notes.append('Control Id exceeds the Compliance Controls ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Control Id must be YYYY-MM-DD for Compliance Controls.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Control Id is longer than the Compliance Controls ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Control Id placeholder values are not allowed on Compliance Controls.')
    return notes


def compliance_controls_normalize_control_id(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def compliance_controls_describe_control_id() -> str:
    required = 'required' if True else 'optional'
    return 'Control Id is a ' + required + ' str field on Compliance Controls (compliance_controls).'


def compliance_controls_check_statement(value: Any) -> list[str]:
    """Field policy for Statement inside Compliance Controls."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Statement is required on Compliance Controls.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Statement is zero; confirm the Compliance Controls case.')
        if number > 9_000_000_000:
            notes.append('Statement exceeds the Compliance Controls ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Statement must be YYYY-MM-DD for Compliance Controls.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Statement is longer than the Compliance Controls ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Statement placeholder values are not allowed on Compliance Controls.')
    return notes


def compliance_controls_normalize_statement(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def compliance_controls_describe_statement() -> str:
    required = 'required' if True else 'optional'
    return 'Statement is a ' + required + ' str field on Compliance Controls (compliance_controls).'


def compliance_controls_check_framework(value: Any) -> list[str]:
    """Field policy for Framework inside Compliance Controls."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Framework is required on Compliance Controls.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Framework is zero; confirm the Compliance Controls case.')
        if number > 9_000_000_000:
            notes.append('Framework exceeds the Compliance Controls ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Framework must be YYYY-MM-DD for Compliance Controls.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Framework is longer than the Compliance Controls ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Framework placeholder values are not allowed on Compliance Controls.')
    return notes


def compliance_controls_normalize_framework(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def compliance_controls_describe_framework() -> str:
    required = 'required' if True else 'optional'
    return 'Framework is a ' + required + ' str field on Compliance Controls (compliance_controls).'


def compliance_controls_check_owner(value: Any) -> list[str]:
    """Field policy for Owner inside Compliance Controls."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Owner is required on Compliance Controls.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Owner is zero; confirm the Compliance Controls case.')
        if number > 9_000_000_000:
            notes.append('Owner exceeds the Compliance Controls ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Owner must be YYYY-MM-DD for Compliance Controls.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Owner is longer than the Compliance Controls ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Owner placeholder values are not allowed on Compliance Controls.')
    return notes


def compliance_controls_normalize_owner(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def compliance_controls_describe_owner() -> str:
    required = 'required' if True else 'optional'
    return 'Owner is a ' + required + ' str field on Compliance Controls (compliance_controls).'


def compliance_controls_check_test_days(value: Any) -> list[str]:
    """Field policy for Test Days inside Compliance Controls."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Test Days is required on Compliance Controls.')
        return notes
    if 'int' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Test Days is zero; confirm the Compliance Controls case.')
        if number > 9_000_000_000:
            notes.append('Test Days exceeds the Compliance Controls ceiling.')
        return notes
    if 'int' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Test Days must be YYYY-MM-DD for Compliance Controls.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Test Days is longer than the Compliance Controls ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Test Days placeholder values are not allowed on Compliance Controls.')
    return notes


def compliance_controls_normalize_test_days(value: Any) -> Any:
    if 'int' == 'int':
        return _as_int(value)
    if 'int' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def compliance_controls_describe_test_days() -> str:
    required = 'required' if True else 'optional'
    return 'Test Days is a ' + required + ' int field on Compliance Controls (compliance_controls).'


def compliance_controls_check_status(value: Any) -> list[str]:
    """Field policy for Status inside Compliance Controls."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Status is required on Compliance Controls.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Status is zero; confirm the Compliance Controls case.')
        if number > 9_000_000_000:
            notes.append('Status exceeds the Compliance Controls ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Status must be YYYY-MM-DD for Compliance Controls.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Status is longer than the Compliance Controls ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Status placeholder values are not allowed on Compliance Controls.')
    return notes


def compliance_controls_normalize_status(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def compliance_controls_describe_status() -> str:
    required = 'required' if True else 'optional'
    return 'Status is a ' + required + ' str field on Compliance Controls (compliance_controls).'


FIELD_CHECKS_COMPLIANCE_CONTROLS = {
    'control_id': compliance_controls_check_control_id,
    'statement': compliance_controls_check_statement,
    'framework': compliance_controls_check_framework,
    'owner': compliance_controls_check_owner,
    'test_days': compliance_controls_check_test_days,
    'status': compliance_controls_check_status,
}


def compliance_controls_run_field_checks(row: dict[str, Any]) -> list[str]:
    found: list[str] = []
    for name, checker in FIELD_CHECKS_COMPLIANCE_CONTROLS.items():
        found.extend(checker(row.get(name)))
    return found


def compliance_controls_policy_card(row: dict[str, Any]) -> dict[str, Any]:
    return {
        'domain': DOMAIN_KEY,
        'title': DOMAIN_TITLE,
        'band': compliance_controls_risk_band(row),
        'owner': compliance_controls_owner_hint(row),
        'sla_hours': compliance_controls_sla_hours(row),
        'exceptions': compliance_controls_exception_needed(row),
        'freeze': compliance_controls_freeze_window(row),
        'violations': policy.collect(row) + compliance_controls_run_field_checks(row),
        'summary': compliance_controls_summary_line(row),
    }

