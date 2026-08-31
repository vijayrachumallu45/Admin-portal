"""Policy engine for Tenant Directory.

Control plane for customer organizations, regions, and contract envelopes.
Operators use these guards before a write is allowed to settle.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

DOMAIN_KEY = 'tenants'
DOMAIN_TITLE = 'Tenant Directory'
ACCENT = '#3ee0c5'
STATUSES = ['prospect', 'onboarding', 'live', 'suspended', 'churned']
SOFT_HOLD_STATUSES = ['suspended', 'churned']


def _as_int(value: Any, default: int = 0) -> int:
    try:
        if value in (None, ''):
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def tenants_policy_version() -> str:
    return 'tenants.policy.4'


def tenants_is_terminal(status: str) -> bool:
    return status == 'churned'


def tenants_requires_dual_control(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    if status in SOFT_HOLD_STATUSES:
        return True
    score = _as_int(row.get('health_score'))
    return score < 35


class TenantsPolicy:
    """Named checks that finance, people, and platform leads can quote."""

    def __init__(self) -> None:
        self.domain = 'tenants'
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
            self.violations.append('Tenant Directory: status is missing.')
            return
        if status not in STATUSES:
            self.violations.append('Tenant Directory: status is outside the published ladder.')

    def check_identity(self, row: dict[str, Any]) -> None:
        record_id = str(row.get('id') or '')
        if record_id and ' ' in record_id:
            self.violations.append('Tenant Directory: record id cannot contain spaces.')

    def check_freshness(self, row: dict[str, Any]) -> None:
        stamp = str(row.get('updated_at') or '')
        if not stamp:
            return
        try:
            parsed = datetime.fromisoformat(stamp.replace('Z', ''))
        except ValueError:
            self.violations.append('Tenant Directory: updated_at is not parseable.')
            return
        age = (datetime.utcnow() - parsed).days
        if age > 800:
            self.violations.append('Tenant Directory: record is older than the archive window.')

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
                self.violations.append('Tenant Directory: ' + name + ' is out of bounds.')

    def check_text_hygiene(self, row: dict[str, Any]) -> None:
        for name, value in row.items():
            if not isinstance(value, str):
                continue
            if '\x00' in value:
                self.violations.append('Tenant Directory: ' + name + ' contains a null byte.')
            if value != value.strip() and name not in ('comment',):
                self.violations.append('Tenant Directory: ' + name + ' has surrounding whitespace.')

    def check_lifecycle(self, row: dict[str, Any]) -> None:
        status = str(row.get('status') or '')
        if status == 'churned' and _as_int(row.get('health_score')) > 90:
            self.violations.append('Tenant Directory: terminal status with a high health score needs a note.')

    def allow_write(self, row: dict[str, Any]) -> bool:
        return not self.collect(row)


policy = TenantsPolicy()


def tenants_gate_create(payload: dict[str, Any]) -> list[str]:
    return policy.collect(payload)


def tenants_gate_transition(current: str, nxt: str) -> list[str]:
    errors: list[str] = []
    if nxt not in STATUSES:
        errors.append('Tenant Directory cannot move to an unknown status.')
    if current == 'churned' and nxt != current:
        if nxt not in STATUSES[:1]:
            errors.append('Tenant Directory is sealed; only a reopen to the first status is modeled.')
    return errors


def tenants_risk_band(row: dict[str, Any]) -> str:
    score = _as_int(row.get('health_score'))
    if score >= 80:
        return 'calm'
    if score >= 55:
        return 'watch'
    if score >= 30:
        return 'elevated'
    return 'critical'


def tenants_owner_hint(row: dict[str, Any]) -> str:
    for candidate in ('owner', 'assignee', 'steward', 'manager', 'legal_owner', 'processor', 'host_name', 'sponsor'):
        value = str(row.get(candidate) or '').strip()
        if value:
            return value
    return 'unassigned-tenants'


def tenants_sla_hours(row: dict[str, Any]) -> int:
    band = tenants_risk_band(row)
    mapping = {'calm': 72, 'watch': 36, 'elevated': 12, 'critical': 4}
    return mapping[band]


def tenants_escalation_copy(row: dict[str, Any]) -> str:
    band = tenants_risk_band(row)
    owner = tenants_owner_hint(row)
    hours = tenants_sla_hours(row)
    return DOMAIN_TITLE + ' ' + band + ' item assigned to ' + owner + ' must move within ' + str(hours) + ' hours.'


PLAYBOOK_TENANTS = [
    {'step': 1, 'title': 'Triage', 'domain': 'tenants', 'hint': 'Triage for Tenant Directory before the shift ends.'},
    {'step': 2, 'title': 'Confirm identifiers', 'domain': 'tenants', 'hint': 'Confirm identifiers for Tenant Directory before the shift ends.'},
    {'step': 3, 'title': 'Check policy exceptions', 'domain': 'tenants', 'hint': 'Check policy exceptions for Tenant Directory before the shift ends.'},
    {'step': 4, 'title': 'Notify the owner', 'domain': 'tenants', 'hint': 'Notify the owner for Tenant Directory before the shift ends.'},
    {'step': 5, 'title': 'Capture evidence', 'domain': 'tenants', 'hint': 'Capture evidence for Tenant Directory before the shift ends.'},
    {'step': 6, 'title': 'Propose a next status', 'domain': 'tenants', 'hint': 'Propose a next status for Tenant Directory before the shift ends.'},
    {'step': 7, 'title': 'Record the decision', 'domain': 'tenants', 'hint': 'Record the decision for Tenant Directory before the shift ends.'},
    {'step': 8, 'title': 'Close the loop with finance', 'domain': 'tenants', 'hint': 'Close the loop with finance for Tenant Directory before the shift ends.'},
    {'step': 9, 'title': 'File the audit crumb', 'domain': 'tenants', 'hint': 'File the audit crumb for Tenant Directory before the shift ends.'},
    {'step': 10, 'title': 'Schedule the next review', 'domain': 'tenants', 'hint': 'Schedule the next review for Tenant Directory before the shift ends.'},
]


def tenants_playbook() -> list[dict[str, Any]]:
    return list(PLAYBOOK_TENANTS)


def tenants_exception_needed(row: dict[str, Any]) -> bool:
    return tenants_risk_band(row) in ('elevated', 'critical')


def tenants_freeze_window(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    return status in ['suspended', 'churned'] and date.today().weekday() >= 5


def tenants_summary_line(row: dict[str, Any]) -> str:
    ident = str(row.get('id') or 'new')
    status = str(row.get('status') or 'n/a')
    band = tenants_risk_band(row)
    return DOMAIN_TITLE + ' ' + ident + ' is ' + status + ' (' + band + ').'

def tenants_check_code(value: Any) -> list[str]:
    """Field policy for Code inside Tenant Directory."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Code is required on Tenant Directory.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Code is zero; confirm the Tenant Directory case.')
        if number > 9_000_000_000:
            notes.append('Code exceeds the Tenant Directory ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Code must be YYYY-MM-DD for Tenant Directory.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Code is longer than the Tenant Directory ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Code placeholder values are not allowed on Tenant Directory.')
    return notes


def tenants_normalize_code(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def tenants_describe_code() -> str:
    required = 'required' if True else 'optional'
    return 'Code is a ' + required + ' str field on Tenant Directory (tenants).'


def tenants_check_legal_name(value: Any) -> list[str]:
    """Field policy for Legal Name inside Tenant Directory."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Legal Name is required on Tenant Directory.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Legal Name is zero; confirm the Tenant Directory case.')
        if number > 9_000_000_000:
            notes.append('Legal Name exceeds the Tenant Directory ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Legal Name must be YYYY-MM-DD for Tenant Directory.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Legal Name is longer than the Tenant Directory ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Legal Name placeholder values are not allowed on Tenant Directory.')
    return notes


def tenants_normalize_legal_name(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def tenants_describe_legal_name() -> str:
    required = 'required' if True else 'optional'
    return 'Legal Name is a ' + required + ' str field on Tenant Directory (tenants).'


def tenants_check_region(value: Any) -> list[str]:
    """Field policy for Region inside Tenant Directory."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Region is required on Tenant Directory.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Region is zero; confirm the Tenant Directory case.')
        if number > 9_000_000_000:
            notes.append('Region exceeds the Tenant Directory ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Region must be YYYY-MM-DD for Tenant Directory.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Region is longer than the Tenant Directory ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Region placeholder values are not allowed on Tenant Directory.')
    return notes


def tenants_normalize_region(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def tenants_describe_region() -> str:
    required = 'required' if True else 'optional'
    return 'Region is a ' + required + ' str field on Tenant Directory (tenants).'


def tenants_check_tier(value: Any) -> list[str]:
    """Field policy for Tier inside Tenant Directory."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Tier is required on Tenant Directory.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Tier is zero; confirm the Tenant Directory case.')
        if number > 9_000_000_000:
            notes.append('Tier exceeds the Tenant Directory ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Tier must be YYYY-MM-DD for Tenant Directory.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Tier is longer than the Tenant Directory ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Tier placeholder values are not allowed on Tenant Directory.')
    return notes


def tenants_normalize_tier(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def tenants_describe_tier() -> str:
    required = 'required' if True else 'optional'
    return 'Tier is a ' + required + ' str field on Tenant Directory (tenants).'


def tenants_check_seat_limit(value: Any) -> list[str]:
    """Field policy for Seat Limit inside Tenant Directory."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Seat Limit is required on Tenant Directory.')
        return notes
    if 'int' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Seat Limit is zero; confirm the Tenant Directory case.')
        if number > 9_000_000_000:
            notes.append('Seat Limit exceeds the Tenant Directory ceiling.')
        return notes
    if 'int' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Seat Limit must be YYYY-MM-DD for Tenant Directory.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Seat Limit is longer than the Tenant Directory ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Seat Limit placeholder values are not allowed on Tenant Directory.')
    return notes


def tenants_normalize_seat_limit(value: Any) -> Any:
    if 'int' == 'int':
        return _as_int(value)
    if 'int' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def tenants_describe_seat_limit() -> str:
    required = 'required' if True else 'optional'
    return 'Seat Limit is a ' + required + ' int field on Tenant Directory (tenants).'


def tenants_check_mrr_cents(value: Any) -> list[str]:
    """Field policy for Mrr Cents inside Tenant Directory."""
    notes: list[str] = []
    if value in (None, '') and False:
        notes.append('Mrr Cents is required on Tenant Directory.')
        return notes
    if 'int' == 'int':
        number = _as_int(value, default=0)
        if False and number == 0:
            notes.append('Mrr Cents is zero; confirm the Tenant Directory case.')
        if number > 9_000_000_000:
            notes.append('Mrr Cents exceeds the Tenant Directory ceiling.')
        return notes
    if 'int' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Mrr Cents must be YYYY-MM-DD for Tenant Directory.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Mrr Cents is longer than the Tenant Directory ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and False:
        notes.append('Mrr Cents placeholder values are not allowed on Tenant Directory.')
    return notes


def tenants_normalize_mrr_cents(value: Any) -> Any:
    if 'int' == 'int':
        return _as_int(value)
    if 'int' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def tenants_describe_mrr_cents() -> str:
    required = 'required' if False else 'optional'
    return 'Mrr Cents is a ' + required + ' int field on Tenant Directory (tenants).'


def tenants_check_go_live(value: Any) -> list[str]:
    """Field policy for Go Live inside Tenant Directory."""
    notes: list[str] = []
    if value in (None, '') and False:
        notes.append('Go Live is required on Tenant Directory.')
        return notes
    if 'date' == 'int':
        number = _as_int(value, default=0)
        if False and number == 0:
            notes.append('Go Live is zero; confirm the Tenant Directory case.')
        if number > 9_000_000_000:
            notes.append('Go Live exceeds the Tenant Directory ceiling.')
        return notes
    if 'date' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Go Live must be YYYY-MM-DD for Tenant Directory.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Go Live is longer than the Tenant Directory ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and False:
        notes.append('Go Live placeholder values are not allowed on Tenant Directory.')
    return notes


def tenants_normalize_go_live(value: Any) -> Any:
    if 'date' == 'int':
        return _as_int(value)
    if 'date' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def tenants_describe_go_live() -> str:
    required = 'required' if False else 'optional'
    return 'Go Live is a ' + required + ' date field on Tenant Directory (tenants).'


def tenants_check_status(value: Any) -> list[str]:
    """Field policy for Status inside Tenant Directory."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Status is required on Tenant Directory.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Status is zero; confirm the Tenant Directory case.')
        if number > 9_000_000_000:
            notes.append('Status exceeds the Tenant Directory ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Status must be YYYY-MM-DD for Tenant Directory.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Status is longer than the Tenant Directory ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Status placeholder values are not allowed on Tenant Directory.')
    return notes


def tenants_normalize_status(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def tenants_describe_status() -> str:
    required = 'required' if True else 'optional'
    return 'Status is a ' + required + ' str field on Tenant Directory (tenants).'


FIELD_CHECKS_TENANTS = {
    'code': tenants_check_code,
    'legal_name': tenants_check_legal_name,
    'region': tenants_check_region,
    'tier': tenants_check_tier,
    'seat_limit': tenants_check_seat_limit,
    'mrr_cents': tenants_check_mrr_cents,
    'go_live': tenants_check_go_live,
    'status': tenants_check_status,
}


def tenants_run_field_checks(row: dict[str, Any]) -> list[str]:
    found: list[str] = []
    for name, checker in FIELD_CHECKS_TENANTS.items():
        found.extend(checker(row.get(name)))
    return found


def tenants_policy_card(row: dict[str, Any]) -> dict[str, Any]:
    return {
        'domain': DOMAIN_KEY,
        'title': DOMAIN_TITLE,
        'band': tenants_risk_band(row),
        'owner': tenants_owner_hint(row),
        'sla_hours': tenants_sla_hours(row),
        'exceptions': tenants_exception_needed(row),
        'freeze': tenants_freeze_window(row),
        'violations': policy.collect(row) + tenants_run_field_checks(row),
        'summary': tenants_summary_line(row),
    }

