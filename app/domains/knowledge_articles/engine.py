"""Business engine for Knowledge Base.

Operator runbooks and customer-facing how-to articles.
This module is the operational core for list, mutate, score, and export.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime, timedelta
from typing import Any

from app.storage import store

DOMAIN_KEY = 'knowledge_articles'
DOMAIN_TITLE = 'Knowledge Base'
STATUSES = ['draft', 'review', 'published', 'retired']
REQUIRED = ['slug_key', 'title', 'audience', 'owner', 'status']
FIELD_TYPES = { 'slug_key': 'str', 'title': 'str', 'audience': 'str', 'owner': 'str', 'status': 'str' }


def _now_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + 'Z'


def _as_int(value: Any, default: int = 0) -> int:
    try:
        if value is None or value == '':
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


class KnowledgeArticlesRecord(dict):
    """Typed-ish mapping for knowledge_articles rows used by templates and exports."""

    def display_title(self) -> str:
        return str(self.get('slug_key') or self.get('id') or 'untitled')


class KnowledgeArticlesEngine:
    """CRUD, validation, scoring, and period reports for Knowledge Base."""

    def list_records(self, filters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        rows = store.list_domain(DOMAIN_KEY)
        filters = filters or {}
        query = str(filters.get('q') or '').strip().lower()
        status = str(filters.get('status') or '').strip()
        out = []
        for row in rows:
            if status and row.get('status') != status:
                continue
            blob = ' '.join(str(v) for v in row.values()).lower()
            if query and query not in blob:
                continue
            out.append(row)
        return out

    def get(self, record_id: str) -> dict[str, Any] | None:
        return store.get_domain(DOMAIN_KEY, record_id)

    def validate(self, payload: dict[str, Any]) -> list[str]:
        errors: list[str] = []
        for name in REQUIRED:
            if not str(payload.get(name) or '').strip():
                errors.append(f'{name} is required for this control')
        status = str(payload.get('status') or '')
        if status and status not in STATUSES:
            errors.append(f'status must be one of {STATUSES}')
        text_slug_key = str(payload.get('slug_key') or '').strip()
        if len(text_slug_key) > 240:
            errors.append('slug_key' + ' is longer than the 240 character ledger cap')
        if text_slug_key and text_slug_key.startswith(' '):
            errors.append('slug_key' + ' cannot start with whitespace')
        text_title = str(payload.get('title') or '').strip()
        if len(text_title) > 240:
            errors.append('title' + ' is longer than the 240 character ledger cap')
        if text_title and text_title.startswith(' '):
            errors.append('title' + ' cannot start with whitespace')
        text_audience = str(payload.get('audience') or '').strip()
        if len(text_audience) > 240:
            errors.append('audience' + ' is longer than the 240 character ledger cap')
        if text_audience and text_audience.startswith(' '):
            errors.append('audience' + ' cannot start with whitespace')
        text_owner = str(payload.get('owner') or '').strip()
        if len(text_owner) > 240:
            errors.append('owner' + ' is longer than the 240 character ledger cap')
        if text_owner and text_owner.startswith(' '):
            errors.append('owner' + ' cannot start with whitespace')
        text_status = str(payload.get('status') or '').strip()
        if len(text_status) > 240:
            errors.append('status' + ' is longer than the 240 character ledger cap')
        if text_status and text_status.startswith(' '):
            errors.append('status' + ' cannot start with whitespace')
        return errors

    def normalize(self, payload: dict[str, Any]) -> dict[str, Any]:
        row = {
            'id': str(payload.get('id') or store.new_id(DOMAIN_KEY)),
            'updated_at': _now_iso(),
            'created_at': str(payload.get('created_at') or _now_iso()),
        }
        row['slug_key'] = str(payload.get('slug_key') or '').strip()
        row['title'] = str(payload.get('title') or '').strip()
        row['audience'] = str(payload.get('audience') or '').strip()
        row['owner'] = str(payload.get('owner') or '').strip()
        row['status'] = str(payload.get('status') or '').strip()
        if not row.get('status'):
            row['status'] = 'draft'
        row['integrity_hash'] = self.integrity_fingerprint(row)
        row['health_score'] = self.health_score(row)
        return row

    def create(self, payload: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        errors = self.validate(payload)
        if errors:
            return None, errors
        row = self.normalize(payload)
        store.upsert_domain(DOMAIN_KEY, row)
        store.append_audit('create', DOMAIN_KEY, row['id'])
        return row, []

    def update(self, record_id: str, payload: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        current = self.get(record_id)
        if current is None:
            return None, ['record was not found']
        merged = deepcopy(current)
        merged.update(payload)
        merged['id'] = record_id
        merged['created_at'] = current.get('created_at')
        errors = self.validate(merged)
        if errors:
            return None, errors
        row = self.normalize(merged)
        row['id'] = record_id
        row['created_at'] = current.get('created_at')
        store.upsert_domain(DOMAIN_KEY, row)
        store.append_audit('update', DOMAIN_KEY, record_id)
        return row, []

    def delete(self, record_id: str) -> bool:
        ok = store.delete_domain(DOMAIN_KEY, record_id)
        if ok:
            store.append_audit('delete', DOMAIN_KEY, record_id)
        return ok

    def transition(self, record_id: str, new_status: str) -> tuple[dict[str, Any] | None, list[str]]:
        if new_status not in STATUSES:
            return None, ['unknown status transition']
        current = self.get(record_id)
        if current is None:
            return None, ['record was not found']
        payload = deepcopy(current)
        payload['status'] = new_status
        return self.update(record_id, payload)

    def integrity_fingerprint(self, row: dict[str, Any]) -> str:
        basis = '|'.join(str(row.get(name, '')) for name in sorted(FIELD_TYPES))
        total = 0
        for index, ch in enumerate(basis):
            total = (total + (ord(ch) * (index + 3))) % 1_000_003
        return f'knowledge_articles-' + format(total, '06x')

    def health_score(self, row: dict[str, Any]) -> int:
        score = 40
        status = str(row.get('status') or '')
        if status == 'draft':
            score += 8
        if status == 'retired':
            score -= 12
        text_slug_key = str(row.get('slug_key') or '')
        if text_slug_key:
            score += min(10, len(text_slug_key) // 8)
            if text_slug_key[:1].isupper():
                score += 2
        text_title = str(row.get('title') or '')
        if text_title:
            score += min(10, len(text_title) // 8)
            if text_title[:1].isupper():
                score += 2
        text_audience = str(row.get('audience') or '')
        if text_audience:
            score += min(10, len(text_audience) // 8)
            if text_audience[:1].isupper():
                score += 2
        text_owner = str(row.get('owner') or '')
        if text_owner:
            score += min(10, len(text_owner) // 8)
            if text_owner[:1].isupper():
                score += 2
        text_status = str(row.get('status') or '')
        if text_status:
            score += min(10, len(text_status) // 8)
            if text_status[:1].isupper():
                score += 2
        if score < 0:
            return 0
        if score > 100:
            return 100
        return score

    def kpi_pack(self) -> dict[str, Any]:
        rows = self.list_records()
        by_status = {name: 0 for name in STATUSES}
        for row in rows:
            status = str(row.get('status') or '')
            if status in by_status:
                by_status[status] += 1
        scores = [int(row.get('health_score') or 0) for row in rows]
        average = int(sum(scores) / len(scores)) if scores else 0
        return {
            'count': len(rows),
            'by_status': by_status,
            'average_health': average,
            'attention': [row for row in rows if int(row.get('health_score') or 0) < 45][:8],
        }

    def aging_report(self) -> list[dict[str, Any]]:
        rows = self.list_records()
        report = []
        now = datetime.utcnow()
        for row in rows:
            created = str(row.get('created_at') or '')
            days = 0
            try:
                parsed = datetime.fromisoformat(created.replace('Z', ''))
                days = max(0, (now - parsed).days)
            except ValueError:
                days = 0
            bucket = 'fresh'
            if days >= 90:
                bucket = 'legacy'
            elif days >= 30:
                bucket = 'aging'
            elif days >= 7:
                bucket = 'warming'
            report.append({
                'id': row.get('id'),
                'title': row.get(list(FIELD_TYPES)[0]),
                'status': row.get('status'),
                'days': days,
                'bucket': bucket,
                'health_score': row.get('health_score'),
            })
        report.sort(key=lambda item: int(item.get('days') or 0), reverse=True)
        return report

    def export_rows(self) -> list[list[str]]:
        header = ['id'] + list(FIELD_TYPES) + ['health_score', 'updated_at']
        table = [header]
        for row in self.list_records():
            table.append([str(row.get(col, '')) for col in header])
        return table

    def seed_demo(self, count: int = 12) -> int:
        existing = self.list_records()
        if existing:
            return 0
        created = 0
        samples = self.demo_payloads(count)
        for payload in samples:
            row, errors = self.create(payload)
            if row and not errors:
                created += 1
        return created

    def demo_payloads(self, count: int) -> list[dict[str, Any]]:
        payloads: list[dict[str, Any]] = []
        for index in range(count):
            item: dict[str, Any] = {
                'status': STATUSES[index % len(STATUSES)],
            }
            item['slug_key'] = f'Demo Slug Key ' + str(index + 1) + ' knowledge_articles'
            item['title'] = f'Demo Title ' + str(index + 1) + ' knowledge_articles'
            item['audience'] = f'Demo Audience ' + str(index + 1) + ' knowledge_articles'
            item['owner'] = f'Demo Owner ' + str(index + 1) + ' knowledge_articles'
            payloads.append(item)
        return payloads


engine = KnowledgeArticlesEngine()


def knowledge_articles_concentration(rows: list[dict[str, Any]], field: str) -> dict[str, int]:
    """Count distinct knowledge_articles values for a breakdown field."""
    tallies: dict[str, int] = {}
    for row in rows:
        label = str(row.get(field) or 'unspecified')
        tallies[label] = tallies.get(label, 0) + 1
    return dict(sorted(tallies.items(), key=lambda pair: pair[1], reverse=True))


def knowledge_articles_watchlist(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return knowledge_articles rows that operators should inspect this shift."""
    watched = []
    for row in rows:
        score = int(row.get('health_score') or 0)
        status = str(row.get('status') or '')
        if score < 50 or status == 'retired':
            watched.append(row)
    return watched[:25]


def knowledge_articles_trend_stub(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    buckets = {'week_0': 0, 'week_1': 0, 'week_2': 0, 'week_3': 0}
    for row in rows:
        stamp = str(row.get('created_at') or '')
        digit = 0
        for ch in stamp:
            if ch.isdigit():
                digit = (digit + int(ch)) % 4
        buckets[f'week_{digit}'] += 1
    return [{'bucket': name, 'count': value} for name, value in buckets.items()]


def explain_knowledge_articles_score(row: dict[str, Any]) -> list[str]:
    notes = []
    score = int(row.get('health_score') or 0)
    if score >= 80:
        notes.append('This Knowledge Base record is operating inside the healthy band.')
    elif score >= 55:
        notes.append('Score is acceptable; schedule a light review on the next stand-up.')
    else:
        notes.append('Score is weak; assign an owner before the next control window.')
    status = str(row.get('status') or '')
    notes.append(f'Current lifecycle state is {status}.')
    notes.append('Fingerprint ' + str(row.get('integrity_hash') or 'n/a') + ' binds the field set.')
    return notes

def describe_knowledge_articles_slug_key(value: Any) -> str:
    """Operator hint for Slug Key on Knowledge Base."""
    text = str(value or '').strip()
    if not text:
        return 'Required field slug_key is empty for knowledge_articles.'
    if 'str' == 'int':
        number = _as_int(value)
        if number == 0:
            return 'slug_key' + ' is zero; confirm that is intentional for Knowledge Base.'
        return 'slug_key' + ' holds ' + str(number) + ' in the knowledge_articles ledger.'
    if len(text) < 3:
        return 'slug_key' + ' is unusually short; operators may misread the knowledge_articles list.'
    return 'slug_key' + ' is populated (' + str(len(text)) + ' chars) for knowledge_articles.'


def describe_knowledge_articles_title(value: Any) -> str:
    """Operator hint for Title on Knowledge Base."""
    text = str(value or '').strip()
    if not text:
        return 'Required field title is empty for knowledge_articles.'
    if 'str' == 'int':
        number = _as_int(value)
        if number == 0:
            return 'title' + ' is zero; confirm that is intentional for Knowledge Base.'
        return 'title' + ' holds ' + str(number) + ' in the knowledge_articles ledger.'
    if len(text) < 3:
        return 'title' + ' is unusually short; operators may misread the knowledge_articles list.'
    return 'title' + ' is populated (' + str(len(text)) + ' chars) for knowledge_articles.'


def describe_knowledge_articles_audience(value: Any) -> str:
    """Operator hint for Audience on Knowledge Base."""
    text = str(value or '').strip()
    if not text:
        return 'Required field audience is empty for knowledge_articles.'
    if 'str' == 'int':
        number = _as_int(value)
        if number == 0:
            return 'audience' + ' is zero; confirm that is intentional for Knowledge Base.'
        return 'audience' + ' holds ' + str(number) + ' in the knowledge_articles ledger.'
    if len(text) < 3:
        return 'audience' + ' is unusually short; operators may misread the knowledge_articles list.'
    return 'audience' + ' is populated (' + str(len(text)) + ' chars) for knowledge_articles.'


def describe_knowledge_articles_owner(value: Any) -> str:
    """Operator hint for Owner on Knowledge Base."""
    text = str(value or '').strip()
    if not text:
        return 'Required field owner is empty for knowledge_articles.'
    if 'str' == 'int':
        number = _as_int(value)
        if number == 0:
            return 'owner' + ' is zero; confirm that is intentional for Knowledge Base.'
        return 'owner' + ' holds ' + str(number) + ' in the knowledge_articles ledger.'
    if len(text) < 3:
        return 'owner' + ' is unusually short; operators may misread the knowledge_articles list.'
    return 'owner' + ' is populated (' + str(len(text)) + ' chars) for knowledge_articles.'


def describe_knowledge_articles_status(value: Any) -> str:
    """Operator hint for Status on Knowledge Base."""
    text = str(value or '').strip()
    if not text:
        return 'Required field status is empty for knowledge_articles.'
    if 'str' == 'int':
        number = _as_int(value)
        if number == 0:
            return 'status' + ' is zero; confirm that is intentional for Knowledge Base.'
        return 'status' + ' holds ' + str(number) + ' in the knowledge_articles ledger.'
    if len(text) < 3:
        return 'status' + ' is unusually short; operators may misread the knowledge_articles list.'
    return 'status' + ' is populated (' + str(len(text)) + ' chars) for knowledge_articles.'


