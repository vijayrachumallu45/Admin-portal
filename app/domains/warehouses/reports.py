"""Period reports and operator briefings for Warehouse Map."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from app.domains.warehouses.queries import warehouses_group_status, warehouses_health_bands, warehouses_completeness
from app.domains.warehouses.policies import warehouses_risk_band, warehouses_sla_hours, warehouses_owner_hint

DOMAIN_TITLE = 'Warehouse Map'


def warehouses_age_days(row: dict[str, Any]) -> int:
    created = str(row.get('created_at') or '')
    try:
        parsed = datetime.fromisoformat(created.replace('Z', ''))
    except ValueError:
        return 0
    return max(0, (datetime.utcnow() - parsed).days)


def warehouses_bucket(days: int) -> str:
    if days < 3:
        return 'fresh'
    if days < 14:
        return 'current'
    if days < 45:
        return 'aging'
    return 'legacy'


def warehouses_line_item(row: dict[str, Any]) -> dict[str, Any]:
    days = warehouses_age_days(row)
    return {
        'id': row.get('id'),
        'title': row.get('site_code'),
        'status': row.get('status'),
        'days': days,
        'bucket': warehouses_bucket(days),
        'band': warehouses_risk_band(row),
        'owner': warehouses_owner_hint(row),
        'sla_hours': warehouses_sla_hours(row),
        'completeness': warehouses_completeness(row),
        'health_score': row.get('health_score'),
    }


def warehouses_briefing(rows: list[dict[str, Any]]) -> dict[str, Any]:
    items = [warehouses_line_item(row) for row in rows]
    by_bucket = {'fresh': 0, 'current': 0, 'aging': 0, 'legacy': 0}
    for item in items:
        by_bucket[str(item['bucket'])] += 1
    return {
        'title': DOMAIN_TITLE,
        'generated_at': datetime.utcnow().replace(microsecond=0).isoformat() + 'Z',
        'count': len(items),
        'bands': warehouses_health_bands(rows),
        'buckets': by_bucket,
        'headline': warehouses_headline(rows),
        'items': items[:40],
    }


def warehouses_headline(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return 'Warehouse Map has no rows in the local ledger yet.'
    bands = warehouses_health_bands(rows)
    critical = bands.get('critical', 0)
    if critical:
        return f'Warehouse Map: {critical} critical records need a named owner this shift.'
    return f'Warehouse Map: {len(rows)} records are inside the operating range.'


def warehouses_csv_lines(rows: list[dict[str, Any]]) -> list[str]:
    header = ['id', 'title', 'status', 'days', 'bucket', 'band', 'owner', 'health_score']
    lines = [','.join(header)]
    for row in rows:
        item = warehouses_line_item(row)
        lines.append(','.join(str(item.get(col, '')).replace(',', ' ') for col in header))
    return lines


def warehouses_status_share(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped = warehouses_group_status(rows)
    total = max(1, len(rows))
    share = []
    for status in ['active', 'maintenance', 'closed']:
        count = len(grouped.get(status, []))
        share.append({'status': status, 'count': count, 'pct': int((count / total) * 100)})
    return share


def warehouses_owner_load(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    load: dict[str, int] = {}
    for row in rows:
        owner = warehouses_owner_hint(row)
        load[owner] = load.get(owner, 0) + 1
    ranked = sorted(load.items(), key=lambda pair: pair[1], reverse=True)
    return [{'owner': name, 'count': count} for name, count in ranked]


def warehouses_weekly_story(rows: list[dict[str, Any]]) -> list[str]:
    story = []
    briefing = warehouses_briefing(rows)
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
    story.append('Warehouse Map briefing is local-only and does not call an external network.')
    return story


def warehouses_print_pack(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        'briefing': warehouses_briefing(rows),
        'share': warehouses_status_share(rows),
        'owners': warehouses_owner_load(rows),
        'story': warehouses_weekly_story(rows),
    }


class WarehousesReporter:
    """Builds operator-facing packs for Warehouse Map."""

    def __init__(self, rows: list[dict[str, Any]] | None = None) -> None:
        self.rows = list(rows or [])

    def refresh(self, rows: list[dict[str, Any]]) -> None:
        self.rows = list(rows)

    def briefing(self) -> dict[str, Any]:
        return warehouses_briefing(self.rows)

    def story(self) -> list[str]:
        return warehouses_weekly_story(self.rows)

    def csv(self) -> str:
        return '\n'.join(warehouses_csv_lines(self.rows)) + '\n'

    def pack(self) -> dict[str, Any]:
        return warehouses_print_pack(self.rows)


def build_warehouses_reporter(rows: list[dict[str, Any]]) -> WarehousesReporter:
    return WarehousesReporter(rows)

def warehouses_report_by_site_code(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Warehouse Map by Site Code."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('site_code') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'site_code'} for label, count in ranked]


def warehouses_report_by_city(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Warehouse Map by City."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('city') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'city'} for label, count in ranked]


def warehouses_report_by_capacity_pallets(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Warehouse Map by Capacity Pallets."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('capacity_pallets') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'capacity_pallets'} for label, count in ranked]


def warehouses_outlier_capacity_pallets(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    values = []
    for row in rows:
        try:
            values.append(int(row.get('capacity_pallets') or 0))
        except (TypeError, ValueError):
            values.append(0)
    if not values:
        return []
    avg = sum(values) / len(values)
    flagged = []
    for row, value in zip(rows, values):
        if value > avg * 3 and value > 0:
            flagged.append({'id': row.get('id'), 'field': 'capacity_pallets', 'value': value, 'avg': int(avg)})
    return flagged


def warehouses_report_by_timezone(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Warehouse Map by Timezone."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('timezone') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'timezone'} for label, count in ranked]


def warehouses_report_by_manager(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Warehouse Map by Manager."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('manager') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'manager'} for label, count in ranked]


def warehouses_report_by_status(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Warehouse Map by Status."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('status') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'status'} for label, count in ranked]


