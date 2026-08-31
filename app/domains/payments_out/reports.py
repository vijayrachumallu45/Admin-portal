"""Period reports and operator briefings for Outbound Payments."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from app.domains.payments_out.queries import payments_out_group_status, payments_out_health_bands, payments_out_completeness
from app.domains.payments_out.policies import payments_out_risk_band, payments_out_sla_hours, payments_out_owner_hint

DOMAIN_TITLE = 'Outbound Payments'


def payments_out_age_days(row: dict[str, Any]) -> int:
    created = str(row.get('created_at') or '')
    try:
        parsed = datetime.fromisoformat(created.replace('Z', ''))
    except ValueError:
        return 0
    return max(0, (datetime.utcnow() - parsed).days)


def payments_out_bucket(days: int) -> str:
    if days < 3:
        return 'fresh'
    if days < 14:
        return 'current'
    if days < 45:
        return 'aging'
    return 'legacy'


def payments_out_line_item(row: dict[str, Any]) -> dict[str, Any]:
    days = payments_out_age_days(row)
    return {
        'id': row.get('id'),
        'title': row.get('payment_no'),
        'status': row.get('status'),
        'days': days,
        'bucket': payments_out_bucket(days),
        'band': payments_out_risk_band(row),
        'owner': payments_out_owner_hint(row),
        'sla_hours': payments_out_sla_hours(row),
        'completeness': payments_out_completeness(row),
        'health_score': row.get('health_score'),
    }


def payments_out_briefing(rows: list[dict[str, Any]]) -> dict[str, Any]:
    items = [payments_out_line_item(row) for row in rows]
    by_bucket = {'fresh': 0, 'current': 0, 'aging': 0, 'legacy': 0}
    for item in items:
        by_bucket[str(item['bucket'])] += 1
    return {
        'title': DOMAIN_TITLE,
        'generated_at': datetime.utcnow().replace(microsecond=0).isoformat() + 'Z',
        'count': len(items),
        'bands': payments_out_health_bands(rows),
        'buckets': by_bucket,
        'headline': payments_out_headline(rows),
        'items': items[:40],
    }


def payments_out_headline(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return 'Outbound Payments has no rows in the local ledger yet.'
    bands = payments_out_health_bands(rows)
    critical = bands.get('critical', 0)
    if critical:
        return f'Outbound Payments: {critical} critical records need a named owner this shift.'
    return f'Outbound Payments: {len(rows)} records are inside the operating range.'


def payments_out_csv_lines(rows: list[dict[str, Any]]) -> list[str]:
    header = ['id', 'title', 'status', 'days', 'bucket', 'band', 'owner', 'health_score']
    lines = [','.join(header)]
    for row in rows:
        item = payments_out_line_item(row)
        lines.append(','.join(str(item.get(col, '')).replace(',', ' ') for col in header))
    return lines


def payments_out_status_share(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped = payments_out_group_status(rows)
    total = max(1, len(rows))
    share = []
    for status in ['queued', 'approved', 'sent', 'failed', 'void']:
        count = len(grouped.get(status, []))
        share.append({'status': status, 'count': count, 'pct': int((count / total) * 100)})
    return share


def payments_out_owner_load(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    load: dict[str, int] = {}
    for row in rows:
        owner = payments_out_owner_hint(row)
        load[owner] = load.get(owner, 0) + 1
    ranked = sorted(load.items(), key=lambda pair: pair[1], reverse=True)
    return [{'owner': name, 'count': count} for name, count in ranked]


def payments_out_weekly_story(rows: list[dict[str, Any]]) -> list[str]:
    story = []
    briefing = payments_out_briefing(rows)
    story.append(str(briefing['headline']))
    story.append('Generated ' + str(briefing['generated_at']) + '.')
    bands = briefing['bands']
    story.append(
        'Bands — calm {calm}, watch {watch}, elevated {elevated}, critical {critical}.'.format(
            **bands
        )
    )
    buckets = briefing['buckets']
    story.append(
        'Age — fresh {fresh}, current {current}, aging {aging}, legacy {legacy}.'.format(
            **buckets
        )
    )
    story.append('Outbound Payments briefing is local-only and does not call an external network.')
    return story


def payments_out_print_pack(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        'briefing': payments_out_briefing(rows),
        'share': payments_out_status_share(rows),
        'owners': payments_out_owner_load(rows),
        'story': payments_out_weekly_story(rows),
    }


class PaymentsOutReporter:
    """Builds operator-facing packs for Outbound Payments."""

    def __init__(self, rows: list[dict[str, Any]] | None = None) -> None:
        self.rows = list(rows or [])

    def refresh(self, rows: list[dict[str, Any]]) -> None:
        self.rows = list(rows)

    def briefing(self) -> dict[str, Any]:
        return payments_out_briefing(self.rows)

    def story(self) -> list[str]:
        return payments_out_weekly_story(self.rows)

    def csv(self) -> str:
        return '\n'.join(payments_out_csv_lines(self.rows)) + '\n'

    def pack(self) -> dict[str, Any]:
        return payments_out_print_pack(self.rows)


def build_payments_out_reporter(rows: list[dict[str, Any]]) -> PaymentsOutReporter:
    return PaymentsOutReporter(rows)

def payments_out_report_by_payment_no(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Outbound Payments by Payment No."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('payment_no') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'payment_no'} for label, count in ranked]


def payments_out_report_by_payee(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Outbound Payments by Payee."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('payee') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'payee'} for label, count in ranked]


def payments_out_report_by_amount_cents(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Outbound Payments by Amount Cents."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('amount_cents') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'amount_cents'} for label, count in ranked]


def payments_out_outlier_amount_cents(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    values = []
    for row in rows:
        try:
            values.append(int(row.get('amount_cents') or 0))
        except (TypeError, ValueError):
            values.append(0)
    if not values:
        return []
    avg = sum(values) / len(values)
    flagged = []
    for row, value in zip(rows, values):
        if value > avg * 3 and value > 0:
            flagged.append({'id': row.get('id'), 'field': 'amount_cents', 'value': value, 'avg': int(avg)})
    return flagged


def payments_out_report_by_method(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Outbound Payments by Method."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('method') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'method'} for label, count in ranked]


def payments_out_report_by_paid_on(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Outbound Payments by Paid On."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('paid_on') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'paid_on'} for label, count in ranked]


def payments_out_report_by_status(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Outbound Payments by Status."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('status') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'status'} for label, count in ranked]


