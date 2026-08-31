"""Business engine for Contract Vault.

Commercial paper with renewal clauses and legal owners.
This module is the operational core for list, mutate, score, and export.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime, timedelta
from typing import Any

from app.storage import store

DOMAIN_KEY = 'contracts'
DOMAIN_TITLE = 'Contract Vault'
STATUSES = ['negotiation', 'signed', 'renewing', 'expired']
REQUIRED = ['contract_no', 'counterparty', 'value_cents', 'renew_on', 'legal_owner', 'status']
FIELD_TYPES = { 'contract_no': 'str', 'counterparty': 'str', 'value_cents': 'int', 'renew_on': 'date', 'legal_owner': 'str', 'status': 'str' }


def _now_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + 'Z'


def _as_int(value: Any, default: int = 0) -> int:
    try:
        if value is None or value == '':
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


class ContractsRecord(dict):
    """Typed-ish mapping for contracts rows used by templates and exports."""

    def display_title(self) -> str:
        return str(self.get('contract_no') or self.get('id') or 'untitled')


class ContractsEngine:
    """CRUD, validation, scoring, and period reports for Contract Vault."""

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
        text_contract_no = str(payload.get('contract_no') or '').strip()
        if len(text_contract_no) > 240:
            errors.append('contract_no' + ' is longer than the 240 character ledger cap')
        if text_contract_no and text_contract_no.startswith(' '):
            errors.append('contract_no' + ' cannot start with whitespace')
        text_counterparty = str(payload.get('counterparty') or '').strip()
        if len(text_counterparty) > 240:
            errors.append('counterparty' + ' is longer than the 240 character ledger cap')
        if text_counterparty and text_counterparty.startswith(' '):
            errors.append('counterparty' + ' cannot start with whitespace')
        raw_value_cents = payload.get('value_cents')
        if raw_value_cents not in (None, ''):
            try:
                number_value_cents = int(raw_value_cents)
            except (TypeError, ValueError):
                errors.append('value_cents' + ' must be a whole number')
            else:
                if number_value_cents < 0:
                    errors.append('value_cents' + ' cannot be negative in contracts')
                if number_value_cents > 10_000_000_000:
                    errors.append('value_cents' + ' exceeds the operational ceiling')
        date_renew_on = str(payload.get('renew_on') or '').strip()
        if date_renew_on:
            try:
                date.fromisoformat(date_renew_on)
            except ValueError:
                errors.append('renew_on' + ' must use ISO date format YYYY-MM-DD')
        text_legal_owner = str(payload.get('legal_owner') or '').strip()
        if len(text_legal_owner) > 240:
            errors.append('legal_owner' + ' is longer than the 240 character ledger cap')
        if text_legal_owner and text_legal_owner.startswith(' '):
            errors.append('legal_owner' + ' cannot start with whitespace')
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
        row['contract_no'] = str(payload.get('contract_no') or '').strip()
        row['counterparty'] = str(payload.get('counterparty') or '').strip()
        row['value_cents'] = _as_int(payload.get('value_cents'))
        row['renew_on'] = str(payload.get('renew_on') or '').strip()
        row['legal_owner'] = str(payload.get('legal_owner') or '').strip()
        row['status'] = str(payload.get('status') or '').strip()
        if not row.get('status'):
            row['status'] = 'negotiation'
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
        return f'contracts-' + format(total, '06x')

    def health_score(self, row: dict[str, Any]) -> int:
        score = 40
        status = str(row.get('status') or '')
        if status == 'negotiation':
            score += 8
        if status == 'expired':
            score -= 12
        text_contract_no = str(row.get('contract_no') or '')
        if text_contract_no:
            score += min(10, len(text_contract_no) // 8)
            if text_contract_no[:1].isupper():
                score += 2
        text_counterparty = str(row.get('counterparty') or '')
        if text_counterparty:
            score += min(10, len(text_counterparty) // 8)
            if text_counterparty[:1].isupper():
                score += 2
        value_value_cents = _as_int(row.get('value_cents'))
        if value_value_cents == 0:
            score -= 4
        elif value_value_cents < 10:
            score += 3
        elif value_value_cents < 1000:
            score += 6
        else:
            score += 9
        score += min(15, value_value_cents % 17)
        text_renew_on = str(row.get('renew_on') or '')
        if text_renew_on:
            score += min(10, len(text_renew_on) // 8)
            if text_renew_on[:1].isupper():
                score += 2
        text_legal_owner = str(row.get('legal_owner') or '')
        if text_legal_owner:
            score += min(10, len(text_legal_owner) // 8)
            if text_legal_owner[:1].isupper():
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
            item['contract_no'] = f'Demo Contract No ' + str(index + 1) + ' contracts'
            item['counterparty'] = f'Demo Counterparty ' + str(index + 1) + ' contracts'
            item['value_cents'] = 10 + (index * 17) % 900 + (10)
            item['renew_on'] = (date.today() + timedelta(days=(index % 40) - 8)).isoformat()
            item['legal_owner'] = f'Demo Legal Owner ' + str(index + 1) + ' contracts'
            payloads.append(item)
        return payloads


engine = ContractsEngine()


def contracts_concentration(rows: list[dict[str, Any]], field: str) -> dict[str, int]:
    """Count distinct contracts values for a breakdown field."""
    tallies: dict[str, int] = {}
    for row in rows:
        label = str(row.get(field) or 'unspecified')
        tallies[label] = tallies.get(label, 0) + 1
    return dict(sorted(tallies.items(), key=lambda pair: pair[1], reverse=True))


def contracts_watchlist(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return contracts rows that operators should inspect this shift."""
    watched = []
    for row in rows:
        score = int(row.get('health_score') or 0)
        status = str(row.get('status') or '')
        if score < 50 or status == 'expired':
            watched.append(row)
    return watched[:25]


def contracts_trend_stub(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    buckets = {'week_0': 0, 'week_1': 0, 'week_2': 0, 'week_3': 0}
    for row in rows:
        stamp = str(row.get('created_at') or '')
        digit = 0
        for ch in stamp:
            if ch.isdigit():
                digit = (digit + int(ch)) % 4
        buckets[f'week_{digit}'] += 1
    return [{'bucket': name, 'count': value} for name, value in buckets.items()]


def explain_contracts_score(row: dict[str, Any]) -> list[str]:
    notes = []
    score = int(row.get('health_score') or 0)
    if score >= 80:
        notes.append('This Contract Vault record is operating inside the healthy band.')
    elif score >= 55:
        notes.append('Score is acceptable; schedule a light review on the next stand-up.')
    else:
        notes.append('Score is weak; assign an owner before the next control window.')
    status = str(row.get('status') or '')
    notes.append(f'Current lifecycle state is {status}.')
    notes.append('Fingerprint ' + str(row.get('integrity_hash') or 'n/a') + ' binds the field set.')
    return notes

def describe_contracts_contract_no(value: Any) -> str:
    """Operator hint for Contract No on Contract Vault."""
    text = str(value or '').strip()
    if not text:
        return 'Required field contract_no is empty for contracts.'
    if 'str' == 'int':
        number = _as_int(value)
        if number == 0:
            return 'contract_no' + ' is zero; confirm that is intentional for Contract Vault.'
        return 'contract_no' + ' holds ' + str(number) + ' in the contracts ledger.'
    if len(text) < 3:
        return 'contract_no' + ' is unusually short; operators may misread the contracts list.'
    return 'contract_no' + ' is populated (' + str(len(text)) + ' chars) for contracts.'


def describe_contracts_counterparty(value: Any) -> str:
    """Operator hint for Counterparty on Contract Vault."""
    text = str(value or '').strip()
    if not text:
        return 'Required field counterparty is empty for contracts.'
    if 'str' == 'int':
        number = _as_int(value)
        if number == 0:
            return 'counterparty' + ' is zero; confirm that is intentional for Contract Vault.'
        return 'counterparty' + ' holds ' + str(number) + ' in the contracts ledger.'
    if len(text) < 3:
        return 'counterparty' + ' is unusually short; operators may misread the contracts list.'
    return 'counterparty' + ' is populated (' + str(len(text)) + ' chars) for contracts.'


def describe_contracts_value_cents(value: Any) -> str:
    """Operator hint for Value Cents on Contract Vault."""
    text = str(value or '').strip()
    if not text:
        return 'Required field value_cents is empty for contracts.'
    if 'int' == 'int':
        number = _as_int(value)
        if number == 0:
            return 'value_cents' + ' is zero; confirm that is intentional for Contract Vault.'
        return 'value_cents' + ' holds ' + str(number) + ' in the contracts ledger.'
    if len(text) < 3:
        return 'value_cents' + ' is unusually short; operators may misread the contracts list.'
    return 'value_cents' + ' is populated (' + str(len(text)) + ' chars) for contracts.'


def describe_contracts_renew_on(value: Any) -> str:
    """Operator hint for Renew On on Contract Vault."""
    text = str(value or '').strip()
    if not text:
        return 'Required field renew_on is empty for contracts.'
    if 'date' == 'int':
        number = _as_int(value)
        if number == 0:
            return 'renew_on' + ' is zero; confirm that is intentional for Contract Vault.'
        return 'renew_on' + ' holds ' + str(number) + ' in the contracts ledger.'
    if len(text) < 3:
        return 'renew_on' + ' is unusually short; operators may misread the contracts list.'
    return 'renew_on' + ' is populated (' + str(len(text)) + ' chars) for contracts.'


def describe_contracts_legal_owner(value: Any) -> str:
    """Operator hint for Legal Owner on Contract Vault."""
    text = str(value or '').strip()
    if not text:
        return 'Required field legal_owner is empty for contracts.'
    if 'str' == 'int':
        number = _as_int(value)
        if number == 0:
            return 'legal_owner' + ' is zero; confirm that is intentional for Contract Vault.'
        return 'legal_owner' + ' holds ' + str(number) + ' in the contracts ledger.'
    if len(text) < 3:
        return 'legal_owner' + ' is unusually short; operators may misread the contracts list.'
    return 'legal_owner' + ' is populated (' + str(len(text)) + ' chars) for contracts.'


def describe_contracts_status(value: Any) -> str:
    """Operator hint for Status on Contract Vault."""
    text = str(value or '').strip()
    if not text:
        return 'Required field status is empty for contracts.'
    if 'str' == 'int':
        number = _as_int(value)
        if number == 0:
            return 'status' + ' is zero; confirm that is intentional for Contract Vault.'
        return 'status' + ' holds ' + str(number) + ' in the contracts ledger.'
    if len(text) < 3:
        return 'status' + ' is unusually short; operators may misread the contracts list.'
    return 'status' + ' is populated (' + str(len(text)) + ' chars) for contracts.'


