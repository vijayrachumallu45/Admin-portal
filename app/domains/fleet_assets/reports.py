"""Period reports and operator briefings for Fleet Assets."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from app.domains.fleet_assets.queries import fleet_assets_group_status, fleet_assets_health_bands, fleet_assets_completeness
from app.domains.fleet_assets.policies import fleet_assets_risk_band, fleet_assets_sla_hours, fleet_assets_owner_hint

DOMAIN_TITLE = 'Fleet Assets'


def fleet_assets_age_days(row: dict[str, Any]) -> int:
    created = str(row.get('created_at') or '')
    try:
        parsed = datetime.fromisoformat(created.replace('Z', ''))
    except ValueError:
        return 0
    return max(0, (datetime.utcnow() - parsed).days)


def fleet_assets_bucket(days: int) -> str:
    if days < 3:
        return 'fresh'
    if days < 14:
        return 'current'
    if days < 45:
        return 'aging'
    return 'legacy'


def fleet_assets_line_item(row: dict[str, Any]) -> dict[str, Any]:
    days = fleet_assets_age_days(row)
    return {
        'id': row.get('id'),
        'title': row.get('asset_tag'),
        'status': row.get('status'),
        'days': days,
        'bucket': fleet_assets_bucket(days),
        'band': fleet_assets_risk_band(row),
        'owner': fleet_assets_owner_hint(row),
        'sla_hours': fleet_assets_sla_hours(row),
        'completeness': fleet_assets_completeness(row),
        'health_score': row.get('health_score'),
    }


def fleet_assets_briefing(rows: list[dict[str, Any]]) -> dict[str, Any]:
    items = [fleet_assets_line_item(row) for row in rows]
    by_bucket = {'fresh': 0, 'current': 0, 'aging': 0, 'legacy': 0}
    for item in items:
        by_bucket[str(item['bucket'])] += 1
    return {
        'title': DOMAIN_TITLE,
        'generated_at': datetime.utcnow().replace(microsecond=0).isoformat() + 'Z',
        'count': len(items),
        'bands': fleet_assets_health_bands(rows),
        'buckets': by_bucket,
        'headline': fleet_assets_headline(rows),
        'items': items[:40],
    }


def fleet_assets_headline(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return 'Fleet Assets has no rows in the local ledger yet.'
    bands = fleet_assets_health_bands(rows)
    critical = bands.get('critical', 0)
    if critical:
        return f'Fleet Assets: {critical} critical records need a named owner this shift.'
    return f'Fleet Assets: {len(rows)} records are inside the operating range.'


def fleet_assets_csv_lines(rows: list[dict[str, Any]]) -> list[str]:
    header = ['id', 'title', 'status', 'days', 'bucket', 'band', 'owner', 'health_score']
    lines = [','.join(header)]
    for row in rows:
        item = fleet_assets_line_item(row)
        lines.append(','.join(str(item.get(col, '')).replace(',', ' ') for col in header))
    return lines


def fleet_assets_status_share(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped = fleet_assets_group_status(rows)
    total = max(1, len(rows))
    share = []
    for status in ['ready', 'service', 'down', 'retired']:
        count = len(grouped.get(status, []))
        share.append({'status': status, 'count': count, 'pct': int((count / total) * 100)})
    return share


def fleet_assets_owner_load(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    load: dict[str, int] = {}
    for row in rows:
        owner = fleet_assets_owner_hint(row)
        load[owner] = load.get(owner, 0) + 1
    ranked = sorted(load.items(), key=lambda pair: pair[1], reverse=True)
    return [{'owner': name, 'count': count} for name, count in ranked]


def fleet_assets_weekly_story(rows: list[dict[str, Any]]) -> list[str]:
    story = []
    briefing = fleet_assets_briefing(rows)
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
    story.append('Fleet Assets briefing is local-only and does not call an external network.')
    return story


def fleet_assets_print_pack(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        'briefing': fleet_assets_briefing(rows),
        'share': fleet_assets_status_share(rows),
        'owners': fleet_assets_owner_load(rows),
        'story': fleet_assets_weekly_story(rows),
    }


class FleetAssetsReporter:
    """Builds operator-facing packs for Fleet Assets."""

    def __init__(self, rows: list[dict[str, Any]] | None = None) -> None:
        self.rows = list(rows or [])

    def refresh(self, rows: list[dict[str, Any]]) -> None:
        self.rows = list(rows)

    def briefing(self) -> dict[str, Any]:
        return fleet_assets_briefing(self.rows)

    def story(self) -> list[str]:
        return fleet_assets_weekly_story(self.rows)

    def csv(self) -> str:
        return '\n'.join(fleet_assets_csv_lines(self.rows)) + '\n'

    def pack(self) -> dict[str, Any]:
        return fleet_assets_print_pack(self.rows)


def build_fleet_assets_reporter(rows: list[dict[str, Any]]) -> FleetAssetsReporter:
    return FleetAssetsReporter(rows)

def fleet_assets_report_by_asset_tag(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Fleet Assets by Asset Tag."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('asset_tag') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'asset_tag'} for label, count in ranked]


def fleet_assets_report_by_kind(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Fleet Assets by Kind."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('kind') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'kind'} for label, count in ranked]


def fleet_assets_report_by_odometer(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Fleet Assets by Odometer."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('odometer') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'odometer'} for label, count in ranked]


def fleet_assets_outlier_odometer(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    values = []
    for row in rows:
        try:
            values.append(int(row.get('odometer') or 0))
        except (TypeError, ValueError):
            values.append(0)
    if not values:
        return []
    avg = sum(values) / len(values)
    flagged = []
    for row, value in zip(rows, values):
        if value > avg * 3 and value > 0:
            flagged.append({'id': row.get('id'), 'field': 'odometer', 'value': value, 'avg': int(avg)})
    return flagged


def fleet_assets_report_by_next_service(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Fleet Assets by Next Service."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('next_service') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'next_service'} for label, count in ranked]


def fleet_assets_report_by_status(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Fleet Assets by Status."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('status') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'status'} for label, count in ranked]


