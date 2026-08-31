"""Business engine for Price Books.

Regional price books and currency schedules.
This module is the operational core for list, mutate, score, and export.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime, timedelta
from typing import Any

from app.storage import store

DOMAIN_KEY = 'price_books'
DOMAIN_TITLE = 'Price Books'
STATUSES = ['draft', 'active', 'superseded']
REQUIRED = ['book_code', 'region', 'currency', 'valid_from', 'status']
FIELD_TYPES = { 'book_code': 'str', 'region': 'str', 'currency': 'str', 'valid_from': 'date', 'status': 'str' }


def _now_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + 'Z'


def _as_int(value: Any, default: int = 0) -> int:
    try:
        if value is None or value == '':
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


class PriceBooksRecord(dict):
    """Typed-ish mapping for price_books rows used by templates and exports."""

    def display_title(self) -> str:
        return str(self.get('book_code') or self.get('id') or 'untitled')


class PriceBooksEngine:
    """CRUD, validation, scoring, and period reports for Price Books."""

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
        text_book_code = str(payload.get('book_code') or '').strip()
        if len(text_book_code) > 240:
            errors.append('book_code' + ' is longer than the 240 character ledger cap')
        if text_book_code and text_book_code.startswith(' '):
            errors.append('book_code' + ' cannot start with whitespace')
        text_region = str(payload.get('region') or '').strip()
        if len(text_region) > 240:
            errors.append('region' + ' is longer than the 240 character ledger cap')
        if text_region and text_region.startswith(' '):
            errors.append('region' + ' cannot start with whitespace')
        text_currency = str(payload.get('currency') or '').strip()
        if len(text_currency) > 240:
            errors.append('currency' + ' is longer than the 240 character ledger cap')
        if text_currency and text_currency.startswith(' '):
            errors.append('currency' + ' cannot start with whitespace')
        date_valid_from = str(payload.get('valid_from') or '').strip()
        if date_valid_from:
            try:
                date.fromisoformat(date_valid_from)
            except ValueError:
                errors.append('valid_from' + ' must use ISO date format YYYY-MM-DD')
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
        row['book_code'] = str(payload.get('book_code') or '').strip()
        row['region'] = str(payload.get('region') or '').strip()
        row['currency'] = str(payload.get('currency') or '').strip()
        row['valid_from'] = str(payload.get('valid_from') or '').strip()
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
        return f'price_books-' + format(total, '06x')

    def health_score(self, row: dict[str, Any]) -> int:
        score = 40
        status = str(row.get('status') or '')
        if status == 'draft':
            score += 8
        if status == 'superseded':
            score -= 12
        text_book_code = str(row.get('book_code') or '')
        if text_book_code:
            score += min(10, len(text_book_code) // 8)
            if text_book_code[:1].isupper():
                score += 2
        text_region = str(row.get('region') or '')
        if text_region:
            score += min(10, len(text_region) // 8)
            if text_region[:1].isupper():
                score += 2
        text_currency = str(row.get('currency') or '')
        if text_currency:
            score += min(10, len(text_currency) // 8)
            if text_currency[:1].isupper():
                score += 2
        text_valid_from = str(row.get('valid_from') or '')
        if text_valid_from:
            score += min(10, len(text_valid_from) // 8)
            if text_valid_from[:1].isupper():
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
            item['book_code'] = f'Demo Book Code ' + str(index + 1) + ' price_books'
            item['region'] = f'Demo Region ' + str(index + 1) + ' price_books'
            item['currency'] = f'Demo Currency ' + str(index + 1) + ' price_books'
            item['valid_from'] = (date.today() + timedelta(days=(index % 40) - 8)).isoformat()
            payloads.append(item)
        return payloads


engine = PriceBooksEngine()


def price_books_concentration(rows: list[dict[str, Any]], field: str) -> dict[str, int]:
    """Count distinct price_books values for a breakdown field."""
    tallies: dict[str, int] = {}
    for row in rows:
        label = str(row.get(field) or 'unspecified')
        tallies[label] = tallies.get(label, 0) + 1
    return dict(sorted(tallies.items(), key=lambda pair: pair[1], reverse=True))


def price_books_watchlist(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return price_books rows that operators should inspect this shift."""
    watched = []
    for row in rows:
        score = int(row.get('health_score') or 0)
        status = str(row.get('status') or '')
        if score < 50 or status == 'superseded':
            watched.append(row)
    return watched[:25]


def price_books_trend_stub(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    buckets = {'week_0': 0, 'week_1': 0, 'week_2': 0, 'week_3': 0}
    for row in rows:
        stamp = str(row.get('created_at') or '')
        digit = 0
        for ch in stamp:
            if ch.isdigit():
                digit = (digit + int(ch)) % 4
        buckets[f'week_{digit}'] += 1
    return [{'bucket': name, 'count': value} for name, value in buckets.items()]


def explain_price_books_score(row: dict[str, Any]) -> list[str]:
    notes = []
    score = int(row.get('health_score') or 0)
    if score >= 80:
        notes.append('This Price Books record is operating inside the healthy band.')
    elif score >= 55:
        notes.append('Score is acceptable; schedule a light review on the next stand-up.')
    else:
        notes.append('Score is weak; assign an owner before the next control window.')
    status = str(row.get('status') or '')
    notes.append(f'Current lifecycle state is {status}.')
    notes.append('Fingerprint ' + str(row.get('integrity_hash') or 'n/a') + ' binds the field set.')
    return notes

def describe_price_books_book_code(value: Any) -> str:
    """Operator hint for Book Code on Price Books."""
    text = str(value or '').strip()
    if not text:
        return 'Required field book_code is empty for price_books.'
    if 'str' == 'int':
        number = _as_int(value)
        if number == 0:
            return 'book_code' + ' is zero; confirm that is intentional for Price Books.'
        return 'book_code' + ' holds ' + str(number) + ' in the price_books ledger.'
    if len(text) < 3:
        return 'book_code' + ' is unusually short; operators may misread the price_books list.'
    return 'book_code' + ' is populated (' + str(len(text)) + ' chars) for price_books.'


def describe_price_books_region(value: Any) -> str:
    """Operator hint for Region on Price Books."""
    text = str(value or '').strip()
    if not text:
        return 'Required field region is empty for price_books.'
    if 'str' == 'int':
        number = _as_int(value)
        if number == 0:
            return 'region' + ' is zero; confirm that is intentional for Price Books.'
        return 'region' + ' holds ' + str(number) + ' in the price_books ledger.'
    if len(text) < 3:
        return 'region' + ' is unusually short; operators may misread the price_books list.'
    return 'region' + ' is populated (' + str(len(text)) + ' chars) for price_books.'


def describe_price_books_currency(value: Any) -> str:
    """Operator hint for Currency on Price Books."""
    text = str(value or '').strip()
    if not text:
        return 'Required field currency is empty for price_books.'
    if 'str' == 'int':
        number = _as_int(value)
        if number == 0:
            return 'currency' + ' is zero; confirm that is intentional for Price Books.'
        return 'currency' + ' holds ' + str(number) + ' in the price_books ledger.'
    if len(text) < 3:
        return 'currency' + ' is unusually short; operators may misread the price_books list.'
    return 'currency' + ' is populated (' + str(len(text)) + ' chars) for price_books.'


def describe_price_books_valid_from(value: Any) -> str:
    """Operator hint for Valid From on Price Books."""
    text = str(value or '').strip()
    if not text:
        return 'Required field valid_from is empty for price_books.'
    if 'date' == 'int':
        number = _as_int(value)
        if number == 0:
            return 'valid_from' + ' is zero; confirm that is intentional for Price Books.'
        return 'valid_from' + ' holds ' + str(number) + ' in the price_books ledger.'
    if len(text) < 3:
        return 'valid_from' + ' is unusually short; operators may misread the price_books list.'
    return 'valid_from' + ' is populated (' + str(len(text)) + ' chars) for price_books.'


def describe_price_books_status(value: Any) -> str:
    """Operator hint for Status on Price Books."""
    text = str(value or '').strip()
    if not text:
        return 'Required field status is empty for price_books.'
    if 'str' == 'int':
        number = _as_int(value)
        if number == 0:
            return 'status' + ' is zero; confirm that is intentional for Price Books.'
        return 'status' + ' holds ' + str(number) + ' in the price_books ledger.'
    if len(text) < 3:
        return 'status' + ' is unusually short; operators may misread the price_books list.'
    return 'status' + ' is populated (' + str(len(text)) + ' chars) for price_books.'


