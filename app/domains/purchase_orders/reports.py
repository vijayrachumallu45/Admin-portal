"""Period reports and operator briefings for Purchase Orders."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from app.domains.purchase_orders.queries import purchase_orders_group_status, purchase_orders_health_bands, purchase_orders_completeness
from app.domains.purchase_orders.policies import purchase_orders_risk_band, purchase_orders_sla_hours, purchase_orders_owner_hint

DOMAIN_TITLE = 'Purchase Orders'


def purchase_orders_age_days(row: dict[str, Any]) -> int:
    created = str(row.get('created_at') or '')
    try:
        parsed = datetime.fromisoformat(created.replace('Z', ''))
    except ValueError:
        return 0
    return max(0, (datetime.utcnow() - parsed).days)


def purchase_orders_bucket(days: int) -> str:
    if days < 3:
        return 'fresh'
    if days < 14:
        return 'current'
    if days < 45:
        return 'aging'
    return 'legacy'


def purchase_orders_line_item(row: dict[str, Any]) -> dict[str, Any]:
    days = purchase_orders_age_days(row)
    return {
        'id': row.get('id'),
        'title': row.get('po_number'),
        'status': row.get('status'),
        'days': days,
        'bucket': purchase_orders_bucket(days),
        'band': purchase_orders_risk_band(row),
        'owner': purchase_orders_owner_hint(row),
        'sla_hours': purchase_orders_sla_hours(row),
        'completeness': purchase_orders_completeness(row),
        'health_score': row.get('health_score'),
    }


def purchase_orders_briefing(rows: list[dict[str, Any]]) -> dict[str, Any]:
    items = [purchase_orders_line_item(row) for row in rows]
    by_bucket = {'fresh': 0, 'current': 0, 'aging': 0, 'legacy': 0}
    for item in items:
        by_bucket[str(item['bucket'])] += 1
    return {
        'title': DOMAIN_TITLE,
        'generated_at': datetime.utcnow().replace(microsecond=0).isoformat() + 'Z',
        'count': len(items),
        'bands': purchase_orders_health_bands(rows),
        'buckets': by_bucket,
        'headline': purchase_orders_headline(rows),
        'items': items[:40],
    }


def purchase_orders_headline(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return 'Purchase Orders has no rows in the local ledger yet.'
    bands = purchase_orders_health_bands(rows)
    critical = bands.get('critical', 0)
    if critical:
        return f'Purchase Orders: {critical} critical records need a named owner this shift.'
    return f'Purchase Orders: {len(rows)} records are inside the operating range.'


def purchase_orders_csv_lines(rows: list[dict[str, Any]]) -> list[str]:
    header = ['id', 'title', 'status', 'days', 'bucket', 'band', 'owner', 'health_score']
    lines = [','.join(header)]
    for row in rows:
        item = purchase_orders_line_item(row)
        lines.append(','.join(str(item.get(col, '')).replace(',', ' ') for col in header))
    return lines


def purchase_orders_status_share(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped = purchase_orders_group_status(rows)
    total = max(1, len(rows))
    share = []
    for status in ['open', 'partial', 'received', 'closed', 'cancelled']:
        count = len(grouped.get(status, []))
        share.append({'status': status, 'count': count, 'pct': int((count / total) * 100)})
    return share


def purchase_orders_owner_load(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    load: dict[str, int] = {}
    for row in rows:
        owner = purchase_orders_owner_hint(row)
        load[owner] = load.get(owner, 0) + 1
    ranked = sorted(load.items(), key=lambda pair: pair[1], reverse=True)
    return [{'owner': name, 'count': count} for name, count in ranked]


def purchase_orders_weekly_story(rows: list[dict[str, Any]]) -> list[str]:
    story = []
    briefing = purchase_orders_briefing(rows)
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
    story.append('Purchase Orders briefing is local-only and does not call an external network.')
    return story


def purchase_orders_print_pack(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        'briefing': purchase_orders_briefing(rows),
        'share': purchase_orders_status_share(rows),
        'owners': purchase_orders_owner_load(rows),
        'story': purchase_orders_weekly_story(rows),
    }


class PurchaseOrdersReporter:
    """Builds operator-facing packs for Purchase Orders."""

    def __init__(self, rows: list[dict[str, Any]] | None = None) -> None:
        self.rows = list(rows or [])

    def refresh(self, rows: list[dict[str, Any]]) -> None:
        self.rows = list(rows)

    def briefing(self) -> dict[str, Any]:
        return purchase_orders_briefing(self.rows)

    def story(self) -> list[str]:
        return purchase_orders_weekly_story(self.rows)

    def csv(self) -> str:
        return '\n'.join(purchase_orders_csv_lines(self.rows)) + '\n'

    def pack(self) -> dict[str, Any]:
        return purchase_orders_print_pack(self.rows)


def build_purchase_orders_reporter(rows: list[dict[str, Any]]) -> PurchaseOrdersReporter:
    return PurchaseOrdersReporter(rows)

def purchase_orders_report_by_po_number(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Purchase Orders by Po Number."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('po_number') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'po_number'} for label, count in ranked]


def purchase_orders_report_by_vendor_code(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Purchase Orders by Vendor Code."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('vendor_code') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'vendor_code'} for label, count in ranked]


def purchase_orders_report_by_budget_code(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Purchase Orders by Budget Code."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('budget_code') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'budget_code'} for label, count in ranked]


def purchase_orders_report_by_amount_cents(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Purchase Orders by Amount Cents."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('amount_cents') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'amount_cents'} for label, count in ranked]


def purchase_orders_outlier_amount_cents(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
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


def purchase_orders_report_by_needed_by(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Purchase Orders by Needed By."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('needed_by') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'needed_by'} for label, count in ranked]


def purchase_orders_report_by_status(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Purchase Orders by Status."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('status') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'status'} for label, count in ranked]


