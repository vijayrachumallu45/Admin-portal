"""Policy engine for Access Reviews.

Periodic recertification campaigns for sensitive roles.
Operators use these guards before a write is allowed to settle.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

DOMAIN_KEY = 'access_reviews'
DOMAIN_TITLE = 'Access Reviews'
ACCENT = '#fdba74'
STATUSES = ['scheduled', 'in_progress', 'complete', 'overdue']
SOFT_HOLD_STATUSES = ['complete', 'overdue']


def _as_int(value: Any, default: int = 0) -> int:
    try:
        if value in (None, ''):
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def access_reviews_policy_version() -> str:
    return 'access_reviews.policy.4'


def access_reviews_is_terminal(status: str) -> bool:
    return status == 'overdue'


def access_reviews_requires_dual_control(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    if status in SOFT_HOLD_STATUSES:
        return True
    score = _as_int(row.get('health_score'))
    return score < 35


class AccessReviewsPolicy:
    """Named checks that finance, people, and platform leads can quote."""

    def __init__(self) -> None:
        self.domain = 'access_reviews'
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
            self.violations.append('Access Reviews: status is missing.')
            return
        if status not in STATUSES:
            self.violations.append('Access Reviews: status is outside the published ladder.')

    def check_identity(self, row: dict[str, Any]) -> None:
        record_id = str(row.get('id') or '')
        if record_id and ' ' in record_id:
            self.violations.append('Access Reviews: record id cannot contain spaces.')

    def check_freshness(self, row: dict[str, Any]) -> None:
        stamp = str(row.get('updated_at') or '')
        if not stamp:
            return
        try:
            parsed = datetime.fromisoformat(stamp.replace('Z', ''))
        except ValueError:
            self.violations.append('Access Reviews: updated_at is not parseable.')
            return
        age = (datetime.utcnow() - parsed).days
        if age > 800:
            self.violations.append('Access Reviews: record is older than the archive window.')

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
                self.violations.append('Access Reviews: ' + name + ' is out of bounds.')

    def check_text_hygiene(self, row: dict[str, Any]) -> None:
        for name, value in row.items():
            if not isinstance(value, str):
                continue
            if '\x00' in value:
                self.violations.append('Access Reviews: ' + name + ' contains a null byte.')
            if value != value.strip() and name not in ('comment',):
                self.violations.append('Access Reviews: ' + name + ' has surrounding whitespace.')

    def check_lifecycle(self, row: dict[str, Any]) -> None:
        status = str(row.get('status') or '')
        if status == 'overdue' and _as_int(row.get('health_score')) > 90:
            self.violations.append('Access Reviews: terminal status with a high health score needs a note.')

    def allow_write(self, row: dict[str, Any]) -> bool:
        return not self.collect(row)


policy = AccessReviewsPolicy()


def access_reviews_gate_create(payload: dict[str, Any]) -> list[str]:
    return policy.collect(payload)


def access_reviews_gate_transition(current: str, nxt: str) -> list[str]:
    errors: list[str] = []
    if nxt not in STATUSES:
        errors.append('Access Reviews cannot move to an unknown status.')
    if current == 'overdue' and nxt != current:
        if nxt not in STATUSES[:1]:
            errors.append('Access Reviews is sealed; only a reopen to the first status is modeled.')
    return errors


def access_reviews_risk_band(row: dict[str, Any]) -> str:
    score = _as_int(row.get('health_score'))
    if score >= 80:
        return 'calm'
    if score >= 55:
        return 'watch'
    if score >= 30:
        return 'elevated'
    return 'critical'


def access_reviews_owner_hint(row: dict[str, Any]) -> str:
    for candidate in ('owner', 'assignee', 'steward', 'manager', 'legal_owner', 'processor', 'host_name', 'sponsor'):
        value = str(row.get(candidate) or '').strip()
        if value:
            return value
    return 'unassigned-access_reviews'


def access_reviews_sla_hours(row: dict[str, Any]) -> int:
    band = access_reviews_risk_band(row)
    mapping = {'calm': 72, 'watch': 36, 'elevated': 12, 'critical': 4}
    return mapping[band]


def access_reviews_escalation_copy(row: dict[str, Any]) -> str:
    band = access_reviews_risk_band(row)
    owner = access_reviews_owner_hint(row)
    hours = access_reviews_sla_hours(row)
    return DOMAIN_TITLE + ' ' + band + ' item assigned to ' + owner + ' must move within ' + str(hours) + ' hours.'


PLAYBOOK_ACCESS_REVIEWS = [
    {'step': 1, 'title': 'Triage', 'domain': 'access_reviews', 'hint': 'Triage for Access Reviews before the shift ends.'},
    {'step': 2, 'title': 'Confirm identifiers', 'domain': 'access_reviews', 'hint': 'Confirm identifiers for Access Reviews before the shift ends.'},
    {'step': 3, 'title': 'Check policy exceptions', 'domain': 'access_reviews', 'hint': 'Check policy exceptions for Access Reviews before the shift ends.'},
    {'step': 4, 'title': 'Notify the owner', 'domain': 'access_reviews', 'hint': 'Notify the owner for Access Reviews before the shift ends.'},
    {'step': 5, 'title': 'Capture evidence', 'domain': 'access_reviews', 'hint': 'Capture evidence for Access Reviews before the shift ends.'},
    {'step': 6, 'title': 'Propose a next status', 'domain': 'access_reviews', 'hint': 'Propose a next status for Access Reviews before the shift ends.'},
    {'step': 7, 'title': 'Record the decision', 'domain': 'access_reviews', 'hint': 'Record the decision for Access Reviews before the shift ends.'},
    {'step': 8, 'title': 'Close the loop with finance', 'domain': 'access_reviews', 'hint': 'Close the loop with finance for Access Reviews before the shift ends.'},
    {'step': 9, 'title': 'File the audit crumb', 'domain': 'access_reviews', 'hint': 'File the audit crumb for Access Reviews before the shift ends.'},
    {'step': 10, 'title': 'Schedule the next review', 'domain': 'access_reviews', 'hint': 'Schedule the next review for Access Reviews before the shift ends.'},
]


def access_reviews_playbook() -> list[dict[str, Any]]:
    return list(PLAYBOOK_ACCESS_REVIEWS)


def access_reviews_exception_needed(row: dict[str, Any]) -> bool:
    return access_reviews_risk_band(row) in ('elevated', 'critical')


def access_reviews_freeze_window(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    return status in ['complete', 'overdue'] and date.today().weekday() >= 5


def access_reviews_summary_line(row: dict[str, Any]) -> str:
    ident = str(row.get('id') or 'new')
    status = str(row.get('status') or 'n/a')
    band = access_reviews_risk_band(row)
    return DOMAIN_TITLE + ' ' + ident + ' is ' + status + ' (' + band + ').'

def access_reviews_check_campaign(value: Any) -> list[str]:
    """Field policy for Campaign inside Access Reviews."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Campaign is required on Access Reviews.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Campaign is zero; confirm the Access Reviews case.')
        if number > 9_000_000_000:
            notes.append('Campaign exceeds the Access Reviews ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Campaign must be YYYY-MM-DD for Access Reviews.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Campaign is longer than the Access Reviews ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Campaign placeholder values are not allowed on Access Reviews.')
    return notes


def access_reviews_normalize_campaign(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def access_reviews_describe_campaign() -> str:
    required = 'required' if True else 'optional'
    return 'Campaign is a ' + required + ' str field on Access Reviews (access_reviews).'


def access_reviews_check_scope(value: Any) -> list[str]:
    """Field policy for Scope inside Access Reviews."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Scope is required on Access Reviews.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Scope is zero; confirm the Access Reviews case.')
        if number > 9_000_000_000:
            notes.append('Scope exceeds the Access Reviews ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Scope must be YYYY-MM-DD for Access Reviews.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Scope is longer than the Access Reviews ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Scope placeholder values are not allowed on Access Reviews.')
    return notes


def access_reviews_normalize_scope(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def access_reviews_describe_scope() -> str:
    required = 'required' if True else 'optional'
    return 'Scope is a ' + required + ' str field on Access Reviews (access_reviews).'


def access_reviews_check_reviewer(value: Any) -> list[str]:
    """Field policy for Reviewer inside Access Reviews."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Reviewer is required on Access Reviews.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Reviewer is zero; confirm the Access Reviews case.')
        if number > 9_000_000_000:
            notes.append('Reviewer exceeds the Access Reviews ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Reviewer must be YYYY-MM-DD for Access Reviews.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Reviewer is longer than the Access Reviews ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Reviewer placeholder values are not allowed on Access Reviews.')
    return notes


def access_reviews_normalize_reviewer(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def access_reviews_describe_reviewer() -> str:
    required = 'required' if True else 'optional'
    return 'Reviewer is a ' + required + ' str field on Access Reviews (access_reviews).'


def access_reviews_check_due_on(value: Any) -> list[str]:
    """Field policy for Due On inside Access Reviews."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Due On is required on Access Reviews.')
        return notes
    if 'date' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Due On is zero; confirm the Access Reviews case.')
        if number > 9_000_000_000:
            notes.append('Due On exceeds the Access Reviews ceiling.')
        return notes
    if 'date' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Due On must be YYYY-MM-DD for Access Reviews.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Due On is longer than the Access Reviews ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Due On placeholder values are not allowed on Access Reviews.')
    return notes


def access_reviews_normalize_due_on(value: Any) -> Any:
    if 'date' == 'int':
        return _as_int(value)
    if 'date' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def access_reviews_describe_due_on() -> str:
    required = 'required' if True else 'optional'
    return 'Due On is a ' + required + ' date field on Access Reviews (access_reviews).'


def access_reviews_check_item_count(value: Any) -> list[str]:
    """Field policy for Item Count inside Access Reviews."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Item Count is required on Access Reviews.')
        return notes
    if 'int' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Item Count is zero; confirm the Access Reviews case.')
        if number > 9_000_000_000:
            notes.append('Item Count exceeds the Access Reviews ceiling.')
        return notes
    if 'int' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Item Count must be YYYY-MM-DD for Access Reviews.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Item Count is longer than the Access Reviews ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Item Count placeholder values are not allowed on Access Reviews.')
    return notes


def access_reviews_normalize_item_count(value: Any) -> Any:
    if 'int' == 'int':
        return _as_int(value)
    if 'int' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def access_reviews_describe_item_count() -> str:
    required = 'required' if True else 'optional'
    return 'Item Count is a ' + required + ' int field on Access Reviews (access_reviews).'


def access_reviews_check_status(value: Any) -> list[str]:
    """Field policy for Status inside Access Reviews."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Status is required on Access Reviews.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Status is zero; confirm the Access Reviews case.')
        if number > 9_000_000_000:
            notes.append('Status exceeds the Access Reviews ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Status must be YYYY-MM-DD for Access Reviews.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Status is longer than the Access Reviews ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Status placeholder values are not allowed on Access Reviews.')
    return notes


def access_reviews_normalize_status(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def access_reviews_describe_status() -> str:
    required = 'required' if True else 'optional'
    return 'Status is a ' + required + ' str field on Access Reviews (access_reviews).'


FIELD_CHECKS_ACCESS_REVIEWS = {
    'campaign': access_reviews_check_campaign,
    'scope': access_reviews_check_scope,
    'reviewer': access_reviews_check_reviewer,
    'due_on': access_reviews_check_due_on,
    'item_count': access_reviews_check_item_count,
    'status': access_reviews_check_status,
}


def access_reviews_run_field_checks(row: dict[str, Any]) -> list[str]:
    found: list[str] = []
    for name, checker in FIELD_CHECKS_ACCESS_REVIEWS.items():
        found.extend(checker(row.get(name)))
    return found


def access_reviews_policy_card(row: dict[str, Any]) -> dict[str, Any]:
    return {
        'domain': DOMAIN_KEY,
        'title': DOMAIN_TITLE,
        'band': access_reviews_risk_band(row),
        'owner': access_reviews_owner_hint(row),
        'sla_hours': access_reviews_sla_hours(row),
        'exceptions': access_reviews_exception_needed(row),
        'freeze': access_reviews_freeze_window(row),
        'violations': policy.collect(row) + access_reviews_run_field_checks(row),
        'summary': access_reviews_summary_line(row),
    }

