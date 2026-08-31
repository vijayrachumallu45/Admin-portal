"""Policy engine for Knowledge Base.

Operator runbooks and customer-facing how-to articles.
Operators use these guards before a write is allowed to settle.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

DOMAIN_KEY = 'knowledge_articles'
DOMAIN_TITLE = 'Knowledge Base'
ACCENT = '#38bdf8'
STATUSES = ['draft', 'review', 'published', 'retired']
SOFT_HOLD_STATUSES = ['published', 'retired']


def _as_int(value: Any, default: int = 0) -> int:
    try:
        if value in (None, ''):
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def knowledge_articles_policy_version() -> str:
    return 'knowledge_articles.policy.4'


def knowledge_articles_is_terminal(status: str) -> bool:
    return status == 'retired'


def knowledge_articles_requires_dual_control(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    if status in SOFT_HOLD_STATUSES:
        return True
    score = _as_int(row.get('health_score'))
    return score < 35


class KnowledgeArticlesPolicy:
    """Named checks that finance, people, and platform leads can quote."""

    def __init__(self) -> None:
        self.domain = 'knowledge_articles'
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
            self.violations.append('Knowledge Base: status is missing.')
            return
        if status not in STATUSES:
            self.violations.append('Knowledge Base: status is outside the published ladder.')

    def check_identity(self, row: dict[str, Any]) -> None:
        record_id = str(row.get('id') or '')
        if record_id and ' ' in record_id:
            self.violations.append('Knowledge Base: record id cannot contain spaces.')

    def check_freshness(self, row: dict[str, Any]) -> None:
        stamp = str(row.get('updated_at') or '')
        if not stamp:
            return
        try:
            parsed = datetime.fromisoformat(stamp.replace('Z', ''))
        except ValueError:
            self.violations.append('Knowledge Base: updated_at is not parseable.')
            return
        age = (datetime.utcnow() - parsed).days
        if age > 800:
            self.violations.append('Knowledge Base: record is older than the archive window.')

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
                self.violations.append('Knowledge Base: ' + name + ' is out of bounds.')

    def check_text_hygiene(self, row: dict[str, Any]) -> None:
        for name, value in row.items():
            if not isinstance(value, str):
                continue
            if '\x00' in value:
                self.violations.append('Knowledge Base: ' + name + ' contains a null byte.')
            if value != value.strip() and name not in ('comment',):
                self.violations.append('Knowledge Base: ' + name + ' has surrounding whitespace.')

    def check_lifecycle(self, row: dict[str, Any]) -> None:
        status = str(row.get('status') or '')
        if status == 'retired' and _as_int(row.get('health_score')) > 90:
            self.violations.append('Knowledge Base: terminal status with a high health score needs a note.')

    def allow_write(self, row: dict[str, Any]) -> bool:
        return not self.collect(row)


policy = KnowledgeArticlesPolicy()


def knowledge_articles_gate_create(payload: dict[str, Any]) -> list[str]:
    return policy.collect(payload)


def knowledge_articles_gate_transition(current: str, nxt: str) -> list[str]:
    errors: list[str] = []
    if nxt not in STATUSES:
        errors.append('Knowledge Base cannot move to an unknown status.')
    if current == 'retired' and nxt != current:
        if nxt not in STATUSES[:1]:
            errors.append('Knowledge Base is sealed; only a reopen to the first status is modeled.')
    return errors


def knowledge_articles_risk_band(row: dict[str, Any]) -> str:
    score = _as_int(row.get('health_score'))
    if score >= 80:
        return 'calm'
    if score >= 55:
        return 'watch'
    if score >= 30:
        return 'elevated'
    return 'critical'


def knowledge_articles_owner_hint(row: dict[str, Any]) -> str:
    for candidate in ('owner', 'assignee', 'steward', 'manager', 'legal_owner', 'processor', 'host_name', 'sponsor'):
        value = str(row.get(candidate) or '').strip()
        if value:
            return value
    return 'unassigned-knowledge_articles'


def knowledge_articles_sla_hours(row: dict[str, Any]) -> int:
    band = knowledge_articles_risk_band(row)
    mapping = {'calm': 72, 'watch': 36, 'elevated': 12, 'critical': 4}
    return mapping[band]


def knowledge_articles_escalation_copy(row: dict[str, Any]) -> str:
    band = knowledge_articles_risk_band(row)
    owner = knowledge_articles_owner_hint(row)
    hours = knowledge_articles_sla_hours(row)
    return DOMAIN_TITLE + ' ' + band + ' item assigned to ' + owner + ' must move within ' + str(hours) + ' hours.'


PLAYBOOK_KNOWLEDGE_ARTICLES = [
    {'step': 1, 'title': 'Triage', 'domain': 'knowledge_articles', 'hint': 'Triage for Knowledge Base before the shift ends.'},
    {'step': 2, 'title': 'Confirm identifiers', 'domain': 'knowledge_articles', 'hint': 'Confirm identifiers for Knowledge Base before the shift ends.'},
    {'step': 3, 'title': 'Check policy exceptions', 'domain': 'knowledge_articles', 'hint': 'Check policy exceptions for Knowledge Base before the shift ends.'},
    {'step': 4, 'title': 'Notify the owner', 'domain': 'knowledge_articles', 'hint': 'Notify the owner for Knowledge Base before the shift ends.'},
    {'step': 5, 'title': 'Capture evidence', 'domain': 'knowledge_articles', 'hint': 'Capture evidence for Knowledge Base before the shift ends.'},
    {'step': 6, 'title': 'Propose a next status', 'domain': 'knowledge_articles', 'hint': 'Propose a next status for Knowledge Base before the shift ends.'},
    {'step': 7, 'title': 'Record the decision', 'domain': 'knowledge_articles', 'hint': 'Record the decision for Knowledge Base before the shift ends.'},
    {'step': 8, 'title': 'Close the loop with finance', 'domain': 'knowledge_articles', 'hint': 'Close the loop with finance for Knowledge Base before the shift ends.'},
    {'step': 9, 'title': 'File the audit crumb', 'domain': 'knowledge_articles', 'hint': 'File the audit crumb for Knowledge Base before the shift ends.'},
    {'step': 10, 'title': 'Schedule the next review', 'domain': 'knowledge_articles', 'hint': 'Schedule the next review for Knowledge Base before the shift ends.'},
]


def knowledge_articles_playbook() -> list[dict[str, Any]]:
    return list(PLAYBOOK_KNOWLEDGE_ARTICLES)


def knowledge_articles_exception_needed(row: dict[str, Any]) -> bool:
    return knowledge_articles_risk_band(row) in ('elevated', 'critical')


def knowledge_articles_freeze_window(row: dict[str, Any]) -> bool:
    status = str(row.get('status') or '')
    return status in ['published', 'retired'] and date.today().weekday() >= 5


def knowledge_articles_summary_line(row: dict[str, Any]) -> str:
    ident = str(row.get('id') or 'new')
    status = str(row.get('status') or 'n/a')
    band = knowledge_articles_risk_band(row)
    return DOMAIN_TITLE + ' ' + ident + ' is ' + status + ' (' + band + ').'

def knowledge_articles_check_slug_key(value: Any) -> list[str]:
    """Field policy for Slug Key inside Knowledge Base."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Slug Key is required on Knowledge Base.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Slug Key is zero; confirm the Knowledge Base case.')
        if number > 9_000_000_000:
            notes.append('Slug Key exceeds the Knowledge Base ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Slug Key must be YYYY-MM-DD for Knowledge Base.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Slug Key is longer than the Knowledge Base ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Slug Key placeholder values are not allowed on Knowledge Base.')
    return notes


def knowledge_articles_normalize_slug_key(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def knowledge_articles_describe_slug_key() -> str:
    required = 'required' if True else 'optional'
    return 'Slug Key is a ' + required + ' str field on Knowledge Base (knowledge_articles).'


def knowledge_articles_check_title(value: Any) -> list[str]:
    """Field policy for Title inside Knowledge Base."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Title is required on Knowledge Base.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Title is zero; confirm the Knowledge Base case.')
        if number > 9_000_000_000:
            notes.append('Title exceeds the Knowledge Base ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Title must be YYYY-MM-DD for Knowledge Base.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Title is longer than the Knowledge Base ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Title placeholder values are not allowed on Knowledge Base.')
    return notes


def knowledge_articles_normalize_title(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def knowledge_articles_describe_title() -> str:
    required = 'required' if True else 'optional'
    return 'Title is a ' + required + ' str field on Knowledge Base (knowledge_articles).'


def knowledge_articles_check_audience(value: Any) -> list[str]:
    """Field policy for Audience inside Knowledge Base."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Audience is required on Knowledge Base.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Audience is zero; confirm the Knowledge Base case.')
        if number > 9_000_000_000:
            notes.append('Audience exceeds the Knowledge Base ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Audience must be YYYY-MM-DD for Knowledge Base.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Audience is longer than the Knowledge Base ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Audience placeholder values are not allowed on Knowledge Base.')
    return notes


def knowledge_articles_normalize_audience(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def knowledge_articles_describe_audience() -> str:
    required = 'required' if True else 'optional'
    return 'Audience is a ' + required + ' str field on Knowledge Base (knowledge_articles).'


def knowledge_articles_check_owner(value: Any) -> list[str]:
    """Field policy for Owner inside Knowledge Base."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Owner is required on Knowledge Base.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Owner is zero; confirm the Knowledge Base case.')
        if number > 9_000_000_000:
            notes.append('Owner exceeds the Knowledge Base ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Owner must be YYYY-MM-DD for Knowledge Base.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Owner is longer than the Knowledge Base ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Owner placeholder values are not allowed on Knowledge Base.')
    return notes


def knowledge_articles_normalize_owner(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def knowledge_articles_describe_owner() -> str:
    required = 'required' if True else 'optional'
    return 'Owner is a ' + required + ' str field on Knowledge Base (knowledge_articles).'


def knowledge_articles_check_status(value: Any) -> list[str]:
    """Field policy for Status inside Knowledge Base."""
    notes: list[str] = []
    if value in (None, '') and True:
        notes.append('Status is required on Knowledge Base.')
        return notes
    if 'str' == 'int':
        number = _as_int(value, default=0)
        if True and number == 0:
            notes.append('Status is zero; confirm the Knowledge Base case.')
        if number > 9_000_000_000:
            notes.append('Status exceeds the Knowledge Base ceiling.')
        return notes
    if 'str' == 'date':
        text = str(value or '').strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                notes.append('Status must be YYYY-MM-DD for Knowledge Base.')
        return notes
    text = str(value or '').strip()
    if len(text) > 240:
        notes.append('Status is longer than the Knowledge Base ledger allows.')
    if text.lower() in ('n/a', 'todo', 'tbd') and True:
        notes.append('Status placeholder values are not allowed on Knowledge Base.')
    return notes


def knowledge_articles_normalize_status(value: Any) -> Any:
    if 'str' == 'int':
        return _as_int(value)
    if 'str' == 'date':
        return str(value or '').strip()
    return str(value or '').strip()


def knowledge_articles_describe_status() -> str:
    required = 'required' if True else 'optional'
    return 'Status is a ' + required + ' str field on Knowledge Base (knowledge_articles).'


FIELD_CHECKS_KNOWLEDGE_ARTICLES = {
    'slug_key': knowledge_articles_check_slug_key,
    'title': knowledge_articles_check_title,
    'audience': knowledge_articles_check_audience,
    'owner': knowledge_articles_check_owner,
    'status': knowledge_articles_check_status,
}


def knowledge_articles_run_field_checks(row: dict[str, Any]) -> list[str]:
    found: list[str] = []
    for name, checker in FIELD_CHECKS_KNOWLEDGE_ARTICLES.items():
        found.extend(checker(row.get(name)))
    return found


def knowledge_articles_policy_card(row: dict[str, Any]) -> dict[str, Any]:
    return {
        'domain': DOMAIN_KEY,
        'title': DOMAIN_TITLE,
        'band': knowledge_articles_risk_band(row),
        'owner': knowledge_articles_owner_hint(row),
        'sla_hours': knowledge_articles_sla_hours(row),
        'exceptions': knowledge_articles_exception_needed(row),
        'freeze': knowledge_articles_freeze_window(row),
        'violations': policy.collect(row) + knowledge_articles_run_field_checks(row),
        'summary': knowledge_articles_summary_line(row),
    }

