"""Policy engine for Retention Policies.

Keep-or-purge rules by record class and region.
Operators use these guards before a write is allowed to settle.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

DOMAIN_KEY = 'retention_policies'
DOMAIN_TITLE = 'Retention Policies'
ACCENT = '#5eead4'
STATUSES = ['draft', 'enforced', 'waived']
SOFT_HOLD_STATUSES = ['enforced', 'waived']


def _as_int(value: Any, default: int = 0) -> int:
    try:
        if value in (None, ''):
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def retention_policies_policy_version() -> str:
    return 'retention_policies.policy.4'


def retention_policies_is_terminal(status: str) -> bool:
    return status == 'waived'


def retention_policies_requires_dual_control(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    if status in SOFT_HOLD_STATUSES:
        return True
    score = _as_int(row.get('health_score'))
    return score < 35


class RetentionPoliciesPolicy:
    """Named checks that finance, people, and platform leads can quote."""

    def __init__(self) -> None:
        self.domain = 'retention_policies'
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
            self.violations.append('Retention Policies: status is missing.')
            return
        if status not in STATUSES:
            self.violations.append('Retention Policies: status is outside the published ladder.')

    def check_identity(self, row: dict[str, Any]) -> None:
        record_id = str(row.get('id') or '')
        if record_id and ' ' in record_id:
            self.violations.append('Retention Policies: record id cannot contain spaces.')

    def check_freshness(self, row: dict[str, Any]) -> None:
        stamp = str(row.get('updated_at') or '')
        if not stamp:
            return
        try:
            parsed = datetime.fromisoformat(stamp.replace('Z', ''))
        except ValueError:
            self.violations.append('Retention Policies: updated_at is not parseable.')
            return
        age = (datetime.utcnow() - parsed).days
        if age > 800:
            self.violations.append('Retention Policies: record is older than the archive window.')

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
                self.violations.append('Retention Policies: ' + name + ' is out of bounds.')

    def check_text_hygiene(self, row: dict[str, Any]) -> None:
        for name, value in row.items():
            if not isinstance(value, str):
                continue
            if '\x00' in value:
                self.violations.append('Retention Policies: ' + name + ' contains a null byte.')
            if value != value.strip() and name not in ('comment',):
                self.violations.append('Retention Policies: ' + name + ' has surrounding whitespace.')

    def check_lifecycle(self, row: dict[str, Any]) -> None:
        status = str(row.get('status') or '')
        if status == 'waived' and _as_int(row.get('health_score')) > 90:
            self.violations.append('Retention Policies: terminal status with a high health score needs a note.')

    def allow_write(self, row: dict[str, Any]) -> bool:
        return not self.collect(row)


policy = RetentionPoliciesPolicy()


def retention_policies_gate_create(payload: dict[str, Any]) -> list[str]:
    return policy.collect(payload)


def retention_policies_gate_transition(current: str, nxt: str) -> list[str]:
    errors: list[str] = []
    if nxt not in STATUSES:
        errors.append('Retention Policies cannot move to an unknown status.')
    if current == 'waived' and nxt != current:
        if nxt not in STATUSES[:1]:
            errors.append('Retention Policies is sealed; only a reopen to the first status is modeled.')
    return errors


def retention_policies_risk_band(row: dict[str, Any]) -> str:
    score = _as_int(row.get('health_score'))
    if score >= 80:
        return 'calm'
    if score >= 55:
        return 'watch'
    if score >= 30:
        return 'elevated'
    return 'critical'


def retention_policies_owner_hint(row: dict[str, Any]) -> str:
    for candidate in ('owner', 'assignee', 'steward', 'manager', 'legal_owner', 'processor', 'host_name', 'sponsor'):
        value = str(row.get(candidate) or '').strip()
        if value:
            return value
    return 'unassigned-retention_policies'


def retention_policies_sla_hours(row: dict[str, Any]) -> int:
    band = retention_policies_risk_band(row)
    mapping = {'calm': 72, 'watch': 36, 'elevated': 12, 'critical': 4}
    return mapping[band]


def retention_policies_escalation_copy(row: dict[str, Any]) -> str:
    band = retention_policies_risk_band(row)
    owner = retention_policies_owner_hint(row)
    hours = retention_policies_sla_hours(row)
    return DOMAIN_TITLE + ' ' + band + ' item assigned to ' + owner + ' must move within ' + str(hours) + ' hours.'


PLAYBOOK_RETENTION_POLICIES = [
    {'step': 1, 'title': 'Triage', 'domain': 'retention_policies', 'hint': 'Triage for Retention Policies before the shift ends.'},
    {'step': 2, 'title': 'Confirm identifiers', 'domain': 'retention_policies', 'hint': 'Confirm identifiers for Retention Policies before the shift ends.'},
    {'step': 3, 'title': 'Check policy exceptions', 'domain': 'retention_policies', 'hint': 'Check policy exceptions for Retention Policies before the shift ends.'},
    {'step': 4, 'title': 'Notify the owner', 'domain': 'retention_policies', 'hint': 'Notify the owner for Retention Policies before the shift ends.'},
    {'step': 5, 'title': 'Capture evidence', 'domain': 'retention_policies', 'hint': 'Capture evidence for Retention Policies before the shift ends.'},
    {'step': 6, 'title': 'Propose a next status', 'domain': 'retention_policies', 'hint': 'Propose a next status for Retention Policies before the shift ends.'},
    {'step': 7, 'title': 'Record the decision', 'domain': 'retention_policies', 'hint': 'Record the decision for Retention Policies before the shift ends.'},
    {'step': 8, 'title': 'Close the loop with finance', 'domain': 'retention_policies', 'hint': 'Close the loop with finance for Retention Policies before the shift ends.'},
    {'step': 9, 'title': 'File the audit crumb', 'domain': 'retention_policies', 'hint': 'File the audit crumb for Retention Policies before the shift ends.'},
    {'step': 10, 'title': 'Schedule the next review', 'domain': 'retention_policies', 'hint': 'Schedule the next review for Retention Policies before the shift ends.'},
]


def retention_policies_playbook() -> list[dict[str, Any]]:
    return list(PLAYBOOK_RETENTION_POLICIES)


def retention_policies_exception_needed(row: dict[str, Any]) -> bool:
    return retention_policies_risk_band(row) in ('elevated', 'critical')


def retention_policies_freeze_window(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    return status in ['enforced', 'waived'] and date.today().weekday() >= 5


def retention_policies_summary_line(row: dict[str, Any]) -> str:
    ident = str(row.get('id') or 'new')
    status = str(row.get('status') or 'n/a')
    band = retention_policies_risk_band(row)
    return DOMAIN_TITLE + ' ' + ident + ' is ' + status + ' (' + band + ').'

def retention_policies_check_policy_code(value: Any) -> list[str]:
    """Field policy for Policy Code inside Retention Policies."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Policy Code is required on Retention Policies.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Policy Code is zero; confirm the Retention Policies case.')
        if number > 9_000_000_000:
            notes.append('Policy Code exceeds the Retention Policies ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Policy Code must be YYYY-MM-DD for Retention Policies.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Policy Code is longer than the Retention Policies ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Policy Code placeholder values are not allowed on Retention Policies.')
    return notes


def retention_policies_normalize_policy_code(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def retention_policies_describe_policy_code() -> str:
    required = 'required' if True else 'optional'
    return 'Policy Code is a ' + required + ' str field on Retention Policies (retention_policies).'


def retention_policies_check_record_class(value: Any) -> list[str]:
    """Field policy for Record Class inside Retention Policies."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Record Class is required on Retention Policies.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Record Class is zero; confirm the Retention Policies case.')
        if number > 9_000_000_000:
            notes.append('Record Class exceeds the Retention Policies ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Record Class must be YYYY-MM-DD for Retention Policies.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Record Class is longer than the Retention Policies ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Record Class placeholder values are not allowed on Retention Policies.')
    return notes


def retention_policies_normalize_record_class(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def retention_policies_describe_record_class() -> str:
    required = 'required' if True else 'optional'
    return 'Record Class is a ' + required + ' str field on Retention Policies (retention_policies).'


def retention_policies_check_keep_days(value: Any) -> list[str]:
    """Field policy for Keep Days inside Retention Policies."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Keep Days is required on Retention Policies.')
        return notes
    if 'int' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Keep Days is zero; confirm the Retention Policies case.')
        if number > 9_000_000_000:
            notes.append('Keep Days exceeds the Retention Policies ceiling.')
        return notes
    if 'int' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Keep Days must be YYYY-MM-DD for Retention Policies.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Keep Days is longer than the Retention Policies ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Keep Days placeholder values are not allowed on Retention Policies.')
    return notes


def retention_policies_normalize_keep_days(value: Any) -> Any:
    if 'int' == 'int':
        return _as_int(value)
    if 'int' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def retention_policies_describe_keep_days() -> str:
    required = 'required' if True else 'optional'
    return 'Keep Days is a ' + required + ' int field on Retention Policies (retention_policies).'


def retention_policies_check_region(value: Any) -> list[str]:
    """Field policy for Region inside Retention Policies."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Region is required on Retention Policies.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Region is zero; confirm the Retention Policies case.')
        if number > 9_000_000_000:
            notes.append('Region exceeds the Retention Policies ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Region must be YYYY-MM-DD for Retention Policies.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Region is longer than the Retention Policies ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Region placeholder values are not allowed on Retention Policies.')
    return notes


def retention_policies_normalize_region(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def retention_policies_describe_region() -> str:
    required = 'required' if True else 'optional'
    return 'Region is a ' + required + ' str field on Retention Policies (retention_policies).'


def retention_policies_check_status(value: Any) -> list[str]:
    """Field policy for Status inside Retention Policies."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Status is required on Retention Policies.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Status is zero; confirm the Retention Policies case.')
        if number > 9_000_000_000:
            notes.append('Status exceeds the Retention Policies ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Status must be YYYY-MM-DD for Retention Policies.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Status is longer than the Retention Policies ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Status placeholder values are not allowed on Retention Policies.')
    return notes


def retention_policies_normalize_status(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def retention_policies_describe_status() -> str:
    required = 'required' if True else 'optional'
    return 'Status is a ' + required + ' str field on Retention Policies (retention_policies).'


FIELD_CHECKS_RETENTION_POLICIES = {
    'policy_code': retention_policies_check_policy_code,
    'record_class': retention_policies_check_record_class,
    'keep_days': retention_policies_check_keep_days,
    'region': retention_policies_check_region,
    'status': retention_policies_check_status,
}


def retention_policies_run_field_checks(row: dict[str, Any]) -> list[str]:
    found: list[str] = []
    for name, checker in FIELD_CHECKS_RETENTION_POLICIES.items():
        found.extend(checker(row.get(name)))
    return found


def retention_policies_policy_card(row: dict[str, Any]) -> dict[str, Any]:
    return {
        'domain': DOMAIN_KEY,
        'title': DOMAIN_TITLE,
        'band': retention_policies_risk_band(row),
        'owner': retention_policies_owner_hint(row),
        'sla_hours': retention_policies_sla_hours(row),
        'exceptions': retention_policies_exception_needed(row),
        'freeze': retention_policies_freeze_window(row),
        'violations': policy.collect(row) + retention_policies_run_field_checks(row),
        'summary': retention_policies_summary_line(row),
    }

