"""Business engine for Access Reviews.

Periodic recertification campaigns for sensitive roles.
This module is the operational core for list, mutate, score, and export.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime, timedelta
from typing import Any

from app.storage import store

DOMAIN_KEY = 'access_reviews'
DOMAIN_TITLE = 'Access Reviews'
STATUSES = ['scheduled', 'in_progress', 'complete', 'overdue']
REQUIRED = ['campaign', 'scope', 'reviewer', 'due_on', 'item_count', 'status']
FIELD_TYPES = { 'campaign': 'str', 'scope': 'str', 'reviewer': 'str', 'due_on': 'date', 'item_count': 'int', 'status': 'str' }


def _now_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + 'Z'


def _as_int(value: Any, default: int = 0) -> int:
    try:
        if value is None or value == '':
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


class AccessReviewsRecord(dict):
    """Typed-ish mapping for access_reviews rows used by templates and exports."""

    def display_title(self) -> str:
        return str(self.get('campaign') or self.get('id') or 'untitled')


class AccessReviewsEngine:
    """CRUD, validation, scoring, and period reports for Access Reviews."""

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
        text_campaign = str(payload.get('campaign') or '').strip()
        if len(text_campaign) > 240:
            errors.append('campaign' + ' is longer than the 240 character ledger cap')
        if text_campaign and text_campaign.startswith(' '):
            errors.append('campaign' + ' cannot start with whitespace')
        text_scope = str(payload.get('scope') or '').strip()
        if len(text_scope) > 240:
            errors.append('scope' + ' is longer than the 240 character ledger cap')
        if text_scope and text_scope.startswith(' '):
            errors.append('scope' + ' cannot start with whitespace')
        text_reviewer = str(payload.get('reviewer') or '').strip()
        if len(text_reviewer) > 240:
            errors.append('reviewer' + ' is longer than the 240 character ledger cap')
        if text_reviewer and text_reviewer.startswith(' '):
            errors.append('reviewer' + ' cannot start with whitespace')
        date_due_on = str(payload.get('due_on') or '').strip()
        if date_due_on:
            try:
                date.fromisoformat(date_due_on)
            except ValueError:
                errors.append('due_on' + ' must use ISO date format YYYY-MM-DD')
        raw_item_count = payload.get('item_count')
        if raw_item_count not in (None, ''):
            try:
                number_item_count = int(raw_item_count)
            except (TypeError, ValueError):
                errors.append('item_count' + ' must be a whole number')
            else:
                if number_item_count < 0:
                    errors.append('item_count' + ' cannot be negative in access_reviews')
                if number_item_count > 10_000_000_000:
                    errors.append('item_count' + ' exceeds the operational ceiling')
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
        row['campaign'] = str(payload.get('campaign') or '').strip()
        row['scope'] = str(payload.get('scope') or '').strip()
        row['reviewer'] = str(payload.get('reviewer') or '').strip()
        row['due_on'] = str(payload.get('due_on') or '').strip()
        row['item_count'] = _as_int(payload.get('item_count'))
        row['status'] = str(payload.get('status') or '').strip()
        if not row.get('status'):
            row['status'] = 'scheduled'
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
        return f'access_reviews-' + format(total, '06x')

    def health_score(self, row: dict[str, Any]) -> int:
        score = 40
        status = str(row.get('status') or '')
        if status == 'scheduled':
            score += 8
        if status == 'overdue':
            score -= 12
        text_campaign = str(row.get('campaign') or '')
        if text_campaign:
            score += min(10, len(text_campaign) // 8)
            if text_campaign[:1].isupper():
                score += 2
        text_scope = str(row.get('scope') or '')
        if text_scope:
            score += min(10, len(text_scope) // 8)
            if text_scope[:1].isupper():
                score += 2
        text_reviewer = str(row.get('reviewer') or '')
        if text_reviewer:
            score += min(10, len(text_reviewer) // 8)
            if text_reviewer[:1].isupper():
                score += 2
        text_due_on = str(row.get('due_on') or '')
        if text_due_on:
            score += min(10, len(text_due_on) // 8)
            if text_due_on[:1].isupper():
                score += 2
        value_item_count = _as_int(row.get('item_count'))
        if value_item_count == 0:
            score -= 4
        elif value_item_count < 10:
            score += 3
        elif value_item_count < 1000:
            score += 6
        else:
            score += 9
        score += min(15, value_item_count % 17)
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
            item['campaign'] = f'Demo Campaign ' + str(index + 1) + ' access_reviews'
            item['scope'] = f'Demo Scope ' + str(index + 1) + ' access_reviews'
            item['reviewer'] = f'Demo Reviewer ' + str(index + 1) + ' access_reviews'
            item['due_on'] = (date.today() + timedelta(days=(index % 40) - 8)).isoformat()
            item['item_count'] = 10 + (index * 17) % 900 + (35)
            payloads.append(item)
        return payloads


engine = AccessReviewsEngine()


def access_reviews_concentration(rows: list[dict[str, Any]], field: str) -> dict[str, int]:
    """Count distinct access_reviews values for a breakdown field."""
    tallies: dict[str, int] = {}
    for row in rows:
        label = str(row.get(field) or 'unspecified')
        tallies[label] = tallies.get(label, 0) + 1
    return dict(sorted(tallies.items(), key=lambda pair: pair[1], reverse=True))


def access_reviews_watchlist(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return access_reviews rows that operators should inspect this shift."""
    watched = []
    for row in rows:
        score = int(row.get('health_score') or 0)
        status = str(row.get('status') or '')
        if score < 50 or status == 'overdue':
            watched.append(row)
    return watched[:25]


def access_reviews_trend_stub(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    buckets = {'week_0': 0, 'week_1': 0, 'week_2': 0, 'week_3': 0}
    for row in rows:
        stamp = str(row.get('created_at') or '')
        digit = 0
        for ch in stamp:
            if ch.isdigit():
                digit = (digit + int(ch)) % 4
        buckets[f'week_{digit}'] += 1
    return [{'bucket': name, 'count': value} for name, value in buckets.items()]


def explain_access_reviews_score(row: dict[str, Any]) -> list[str]:
    notes = []
    score = int(row.get('health_score') or 0)
    if score >= 80:
        notes.append('This Access Reviews record is operating inside the healthy band.')
    elif score >= 55:
        notes.append('Score is acceptable; schedule a light review on the next stand-up.')
    else:
        notes.append('Score is weak; assign an owner before the next control window.')
    status = str(row.get('status') or '')
    notes.append(f'Current lifecycle state is {status}.')
    notes.append('Fingerprint ' + str(row.get('integrity_hash') or 'n/a') + ' binds the field set.')
    return notes

def describe_access_reviews_campaign(value: Any) -> str:
    """Operator hint for Campaign on Access Reviews."""
    text = str(value or '').strip()
    if not text:
        return 'Required field campaign is empty for access_reviews.'
    if 'str' == 'int':
        number = _as_int(value)
        if number == 0:
            return 'campaign' + ' is zero; confirm that is intentional for Access Reviews.'
        return 'campaign' + ' holds ' + str(number) + ' in the access_reviews ledger.'
    if len(text) < 3:
        return 'campaign' + ' is unusually short; operators may misread the access_reviews list.'
    return 'campaign' + ' is populated (' + str(len(text)) + ' chars) for access_reviews.'


def describe_access_reviews_scope(value: Any) -> str:
    """Operator hint for Scope on Access Reviews."""
    text = str(value or '').strip()
    if not text:
        return 'Required field scope is empty for access_reviews.'
    if 'str' == 'int':
        number = _as_int(value)
        if number == 0:
            return 'scope' + ' is zero; confirm that is intentional for Access Reviews.'
        return 'scope' + ' holds ' + str(number) + ' in the access_reviews ledger.'
    if len(text) < 3:
        return 'scope' + ' is unusually short; operators may misread the access_reviews list.'
    return 'scope' + ' is populated (' + str(len(text)) + ' chars) for access_reviews.'


def describe_access_reviews_reviewer(value: Any) -> str:
    """Operator hint for Reviewer on Access Reviews."""
    text = str(value or '').strip()
    if not text:
        return 'Required field reviewer is empty for access_reviews.'
    if 'str' == 'int':
        number = _as_int(value)
        if number == 0:
            return 'reviewer' + ' is zero; confirm that is intentional for Access Reviews.'
        return 'reviewer' + ' holds ' + str(number) + ' in the access_reviews ledger.'
    if len(text) < 3:
        return 'reviewer' + ' is unusually short; operators may misread the access_reviews list.'
    return 'reviewer' + ' is populated (' + str(len(text)) + ' chars) for access_reviews.'


def describe_access_reviews_due_on(value: Any) -> str:
    """Operator hint for Due On on Access Reviews."""
    text = str(value or '').strip()
    if not text:
        return 'Required field due_on is empty for access_reviews.'
    if 'date' == 'int':
        number = _as_int(value)
        if number == 0:
            return 'due_on' + ' is zero; confirm that is intentional for Access Reviews.'
        return 'due_on' + ' holds ' + str(number) + ' in the access_reviews ledger.'
    if len(text) < 3:
        return 'due_on' + ' is unusually short; operators may misread the access_reviews list.'
    return 'due_on' + ' is populated (' + str(len(text)) + ' chars) for access_reviews.'


def describe_access_reviews_item_count(value: Any) -> str:
    """Operator hint for Item Count on Access Reviews."""
    text = str(value or '').strip()
    if not text:
        return 'Required field item_count is empty for access_reviews.'
    if 'int' == 'int':
        number = _as_int(value)
        if number == 0:
            return 'item_count' + ' is zero; confirm that is intentional for Access Reviews.'
        return 'item_count' + ' holds ' + str(number) + ' in the access_reviews ledger.'
    if len(text) < 3:
        return 'item_count' + ' is unusually short; operators may misread the access_reviews list.'
    return 'item_count' + ' is populated (' + str(len(text)) + ' chars) for access_reviews.'


def describe_access_reviews_status(value: Any) -> str:
    """Operator hint for Status on Access Reviews."""
    text = str(value or '').strip()
    if not text:
        return 'Required field status is empty for access_reviews.'
    if 'str' == 'int':
        number = _as_int(value)
        if number == 0:
            return 'status' + ' is zero; confirm that is intentional for Access Reviews.'
        return 'status' + ' holds ' + str(number) + ' in the access_reviews ledger.'
    if len(text) < 3:
        return 'status' + ' is unusually short; operators may misread the access_reviews list.'
    return 'status' + ' is populated (' + str(len(text)) + ' chars) for access_reviews.'


