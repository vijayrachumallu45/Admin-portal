"""Policy engine for Access Grants.

Time-boxed entitlements with justification and recertification windows.
Operators use these guards before a write is allowed to settle.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

DOMAIN_KEY = 'access_grants'
DOMAIN_TITLE = 'Access Grants'
ACCENT = '#ff8a65'
STATUSES = ['requested', 'approved', 'active', 'expired', 'revoked']
SOFT_HOLD_STATUSES = ['expired', 'revoked']


def _as_int(value: Any, default: int = 0) -> int:
    try:
        if value in (None, ''):
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def access_grants_policy_version() -> str:
    return 'access_grants.policy.4'


def access_grants_is_terminal(status: str) -> bool:
    return status == 'revoked'


def access_grants_requires_dual_control(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    if status in SOFT_HOLD_STATUSES:
        return True
    score = _as_int(row.get('health_score'))
    return score < 35


class AccessGrantsPolicy:
    """Named checks that finance, people, and platform leads can quote."""

    def __init__(self) -> None:
        self.domain = 'access_grants'
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
            self.violations.append('Access Grants: status is missing.')
            return
        if status not in STATUSES:
            self.violations.append('Access Grants: status is outside the published ladder.')

    def check_identity(self, row: dict[str, Any]) -> None:
        record_id = str(row.get('id') or '')
        if record_id and ' ' in record_id:
            self.violations.append('Access Grants: record id cannot contain spaces.')

    def check_freshness(self, row: dict[str, Any]) -> None:
        stamp = str(row.get('updated_at') or '')
        if not stamp:
            return
        try:
            parsed = datetime.fromisoformat(stamp.replace('Z', ''))
        except ValueError:
            self.violations.append('Access Grants: updated_at is not parseable.')
            return
        age = (datetime.utcnow() - parsed).days
        if age > 800:
            self.violations.append('Access Grants: record is older than the archive window.')

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
                self.violations.append('Access Grants: ' + name + ' is out of bounds.')

    def check_text_hygiene(self, row: dict[str, Any]) -> None:
        for name, value in row.items():
            if not isinstance(value, str):
                continue
            if '\x00' in value:
                self.violations.append('Access Grants: ' + name + ' contains a null byte.')
            if value != value.strip() and name not in ('comment',):
                self.violations.append('Access Grants: ' + name + ' has surrounding whitespace.')

    def check_lifecycle(self, row: dict[str, Any]) -> None:
        status = str(row.get('status') or '')
        if status == 'revoked' and _as_int(row.get('health_score')) > 90:
            self.violations.append('Access Grants: terminal status with a high health score needs a note.')

    def allow_write(self, row: dict[str, Any]) -> bool:
        return not self.collect(row)


policy = AccessGrantsPolicy()


def access_grants_gate_create(payload: dict[str, Any]) -> list[str]:
    return policy.collect(payload)


def access_grants_gate_transition(current: str, nxt: str) -> list[str]:
    errors: list[str] = []
    if nxt not in STATUSES:
        errors.append('Access Grants cannot move to an unknown status.')
    if current == 'revoked' and nxt != current:
        if nxt not in STATUSES[:1]:
            errors.append('Access Grants is sealed; only a reopen to the first status is modeled.')
    return errors


def access_grants_risk_band(row: dict[str, Any]) -> str:
    score = _as_int(row.get('health_score'))
    if score >= 80:
        return 'calm'
    if score >= 55:
        return 'watch'
    if score >= 30:
        return 'elevated'
    return 'critical'


def access_grants_owner_hint(row: dict[str, Any]) -> str:
    for candidate in ('owner', 'assignee', 'steward', 'manager', 'legal_owner', 'processor', 'host_name', 'sponsor'):
        value = str(row.get(candidate) or '').strip()
        if value:
            return value
    return 'unassigned-access_grants'


def access_grants_sla_hours(row: dict[str, Any]) -> int:
    band = access_grants_risk_band(row)
    mapping = {'calm': 72, 'watch': 36, 'elevated': 12, 'critical': 4}
    return mapping[band]


def access_grants_escalation_copy(row: dict[str, Any]) -> str:
    band = access_grants_risk_band(row)
    owner = access_grants_owner_hint(row)
    hours = access_grants_sla_hours(row)
    return DOMAIN_TITLE + ' ' + band + ' item assigned to ' + owner + ' must move within ' + str(hours) + ' hours.'


PLAYBOOK_ACCESS_GRANTS = [
    {'step': 1, 'title': 'Triage', 'domain': 'access_grants', 'hint': 'Triage for Access Grants before the shift ends.'},
    {'step': 2, 'title': 'Confirm identifiers', 'domain': 'access_grants', 'hint': 'Confirm identifiers for Access Grants before the shift ends.'},
    {'step': 3, 'title': 'Check policy exceptions', 'domain': 'access_grants', 'hint': 'Check policy exceptions for Access Grants before the shift ends.'},
    {'step': 4, 'title': 'Notify the owner', 'domain': 'access_grants', 'hint': 'Notify the owner for Access Grants before the shift ends.'},
    {'step': 5, 'title': 'Capture evidence', 'domain': 'access_grants', 'hint': 'Capture evidence for Access Grants before the shift ends.'},
    {'step': 6, 'title': 'Propose a next status', 'domain': 'access_grants', 'hint': 'Propose a next status for Access Grants before the shift ends.'},
    {'step': 7, 'title': 'Record the decision', 'domain': 'access_grants', 'hint': 'Record the decision for Access Grants before the shift ends.'},
    {'step': 8, 'title': 'Close the loop with finance', 'domain': 'access_grants', 'hint': 'Close the loop with finance for Access Grants before the shift ends.'},
    {'step': 9, 'title': 'File the audit crumb', 'domain': 'access_grants', 'hint': 'File the audit crumb for Access Grants before the shift ends.'},
    {'step': 10, 'title': 'Schedule the next review', 'domain': 'access_grants', 'hint': 'Schedule the next review for Access Grants before the shift ends.'},
]


def access_grants_playbook() -> list[dict[str, Any]]:
    return list(PLAYBOOK_ACCESS_GRANTS)


def access_grants_exception_needed(row: dict[str, Any]) -> bool:
    return access_grants_risk_band(row) in ('elevated', 'critical')


def access_grants_freeze_window(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    return status in ['expired', 'revoked'] and date.today().weekday() >= 5


def access_grants_summary_line(row: dict[str, Any]) -> str:
    ident = str(row.get('id') or 'new')
    status = str(row.get('status') or 'n/a')
    band = access_grants_risk_band(row)
    return DOMAIN_TITLE + ' ' + ident + ' is ' + status + ' (' + band + ').'

def access_grants_check_principal(value: Any) -> list[str]:
    """Field policy for Principal inside Access Grants."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Principal is required on Access Grants.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Principal is zero; confirm the Access Grants case.')
        if number > 9_000_000_000:
            notes.append('Principal exceeds the Access Grants ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Principal must be YYYY-MM-DD for Access Grants.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Principal is longer than the Access Grants ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Principal placeholder values are not allowed on Access Grants.')
    return notes


def access_grants_normalize_principal(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def access_grants_describe_principal() -> str:
    required = 'required' if True else 'optional'
    return 'Principal is a ' + required + ' str field on Access Grants (access_grants).'


def access_grants_check_role_key(value: Any) -> list[str]:
    """Field policy for Role Key inside Access Grants."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Role Key is required on Access Grants.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Role Key is zero; confirm the Access Grants case.')
        if number > 9_000_000_000:
            notes.append('Role Key exceeds the Access Grants ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Role Key must be YYYY-MM-DD for Access Grants.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Role Key is longer than the Access Grants ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Role Key placeholder values are not allowed on Access Grants.')
    return notes


def access_grants_normalize_role_key(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def access_grants_describe_role_key() -> str:
    required = 'required' if True else 'optional'
    return 'Role Key is a ' + required + ' str field on Access Grants (access_grants).'


def access_grants_check_scope(value: Any) -> list[str]:
    """Field policy for Scope inside Access Grants."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Scope is required on Access Grants.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Scope is zero; confirm the Access Grants case.')
        if number > 9_000_000_000:
            notes.append('Scope exceeds the Access Grants ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Scope must be YYYY-MM-DD for Access Grants.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Scope is longer than the Access Grants ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Scope placeholder values are not allowed on Access Grants.')
    return notes


def access_grants_normalize_scope(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def access_grants_describe_scope() -> str:
    required = 'required' if True else 'optional'
    return 'Scope is a ' + required + ' str field on Access Grants (access_grants).'


def access_grants_check_justification(value: Any) -> list[str]:
    """Field policy for Justification inside Access Grants."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Justification is required on Access Grants.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Justification is zero; confirm the Access Grants case.')
        if number > 9_000_000_000:
            notes.append('Justification exceeds the Access Grants ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Justification must be YYYY-MM-DD for Access Grants.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Justification is longer than the Access Grants ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Justification placeholder values are not allowed on Access Grants.')
    return notes


def access_grants_normalize_justification(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def access_grants_describe_justification() -> str:
    required = 'required' if True else 'optional'
    return 'Justification is a ' + required + ' str field on Access Grants (access_grants).'


def access_grants_check_starts_on(value: Any) -> list[str]:
    """Field policy for Starts On inside Access Grants."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Starts On is required on Access Grants.')
        return notes
    if 'date' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Starts On is zero; confirm the Access Grants case.')
        if number > 9_000_000_000:
            notes.append('Starts On exceeds the Access Grants ceiling.')
        return notes
    if 'date' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Starts On must be YYYY-MM-DD for Access Grants.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Starts On is longer than the Access Grants ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Starts On placeholder values are not allowed on Access Grants.')
    return notes


def access_grants_normalize_starts_on(value: Any) -> Any:
    if 'date' == 'int':
        return _as_int(value)
    if 'date' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def access_grants_describe_starts_on() -> str:
    required = 'required' if True else 'optional'
    return 'Starts On is a ' + required + ' date field on Access Grants (access_grants).'


def access_grants_check_ends_on(value: Any) -> list[str]:
    """Field policy for Ends On inside Access Grants."""
    notes: list[str] = []
    if value in (None, '') and False:
        notes.append('Ends On is required on Access Grants.')
        return notes
    if 'date' == 'int':
        number = _as_int(value, default=0)
        if False and number == 0:
            notes.append('Ends On is zero; confirm the Access Grants case.')
        if number > 9_000_000_000:
            notes.append('Ends On exceeds the Access Grants ceiling.')
        return notes
    if 'date' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Ends On must be YYYY-MM-DD for Access Grants.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Ends On is longer than the Access Grants ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and False:
        notes.append('Ends On placeholder values are not allowed on Access Grants.')
    return notes


def access_grants_normalize_ends_on(value: Any) -> Any:
    if 'date' == 'int':
        return _as_int(value)
    if 'date' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def access_grants_describe_ends_on() -> str:
    required = 'required' if False else 'optional'
    return 'Ends On is a ' + required + ' date field on Access Grants (access_grants).'


def access_grants_check_status(value: Any) -> list[str]:
    """Field policy for Status inside Access Grants."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Status is required on Access Grants.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Status is zero; confirm the Access Grants case.')
        if number > 9_000_000_000:
            notes.append('Status exceeds the Access Grants ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Status must be YYYY-MM-DD for Access Grants.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Status is longer than the Access Grants ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Status placeholder values are not allowed on Access Grants.')
    return notes


def access_grants_normalize_status(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def access_grants_describe_status() -> str:
    required = 'required' if True else 'optional'
    return 'Status is a ' + required + ' str field on Access Grants (access_grants).'


FIELD_CHECKS_ACCESS_GRANTS = {
    'principal': access_grants_check_principal,
    'role_key': access_grants_check_role_key,
    'scope': access_grants_check_scope,
    'justification': access_grants_check_justification,
    'starts_on': access_grants_check_starts_on,
    'ends_on': access_grants_check_ends_on,
    'status': access_grants_check_status,
}


def access_grants_run_field_checks(row: dict[str, Any]) -> list[str]:
    found: list[str] = []
    for name, checker in FIELD_CHECKS_ACCESS_GRANTS.items():
        found.extend(checker(row.get(name)))
    return found


def access_grants_policy_card(row: dict[str, Any]) -> dict[str, Any]:
    return {
        'domain': DOMAIN_KEY,
        'title': DOMAIN_TITLE,
        'band': access_grants_risk_band(row),
        'owner': access_grants_owner_hint(row),
        'sla_hours': access_grants_sla_hours(row),
        'exceptions': access_grants_exception_needed(row),
        'freeze': access_grants_freeze_window(row),
        'violations': policy.collect(row) + access_grants_run_field_checks(row),
        'summary': access_grants_summary_line(row),
    }

