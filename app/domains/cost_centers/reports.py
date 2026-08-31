"""Period reports and operator briefings for Cost Centers."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from app.domains.cost_centers.queries import cost_centers_group_status, cost_centers_health_bands, cost_centers_completeness
from app.domains.cost_centers.policies import cost_centers_risk_band, cost_centers_sla_hours, cost_centers_owner_hint

DOMAIN_TITLE = 'Cost Centers'


def cost_centers_age_days(row: dict[str, Any]) -> int:
    created = str(row.get('created_at') or '')
    try:
        parsed = datetime.fromisoformat(created.replace('Z', ''))
    except ValueError:
        return 0
    return max(0, (datetime.utcnow() - parsed).days)


def cost_centers_bucket(days: int) -> str:
    if days < 3:
        return 'fresh'
    if days < 14:
        return 'current'
    if days < 45:
        return 'aging'
    return 'legacy'


def cost_centers_line_item(row: dict[str, Any]) -> dict[str, Any]:
    days = cost_centers_age_days(row)
    return {
        'id': row.get('id'),
        'title': row.get('cc_code'),
        'status': row.get('status'),
        'days': days,
        'bucket': cost_centers_bucket(days),
        'band': cost_centers_risk_band(row),
        'owner': cost_centers_owner_hint(row),
        'sla_hours': cost_centers_sla_hours(row),
        'completeness': cost_centers_completeness(row),
        'health_score': row.get('health_score'),
    }


def cost_centers_briefing(rows: list[dict[str, Any]]) -> dict[str, Any]:
    items = [cost_centers_line_item(row) for row in rows]
    by_bucket = {'fresh': 0, 'current': 0, 'aging': 0, 'legacy': 0}
    for item in items:
        by_bucket[str(item['bucket'])] += 1
    return {
        'title': DOMAIN_TITLE,
        'generated_at': datetime.utcnow().replace(microsecond=0).isoformat() + 'Z',
        'count': len(items),
        'bands': cost_centers_health_bands(rows),
        'buckets': by_bucket,
        'headline': cost_centers_headline(rows),
        'items': items[:40],
    }


def cost_centers_headline(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return 'Cost Centers has no rows in the local ledger yet.'
    bands = cost_centers_health_bands(rows)
    critical = bands.get('critical', 0)
    if critical:
        return f'Cost Centers: {critical} critical records need a named owner this shift.'
    return f'Cost Centers: {len(rows)} records are inside the operating range.'


def cost_centers_csv_lines(rows: list[dict[str, Any]]) -> list[str]:
    header = ['id', 'title', 'status', 'days', 'bucket', 'band', 'owner', 'health_score']
    lines = [','.join(header)]
    for row in rows:
        item = cost_centers_line_item(row)
        lines.append(','.join(str(item.get(col, '')).replace(',', ' ') for col in header))
    return lines


def cost_centers_status_share(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped = cost_centers_group_status(rows)
    total = max(1, len(rows))
    share = []
    for status in ['active', 'merging', 'retired']:
        count = len(grouped.get(status, []))
        share.append({'status': status, 'count': count, 'pct': int((count / total) * 100)})
    return share


def cost_centers_owner_load(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    load: dict[str, int] = {}
    for row in rows:
        owner = cost_centers_owner_hint(row)
        load[owner] = load.get(owner, 0) + 1
    ranked = sorted(load.items(), key=lambda pair: pair[1], reverse=True)
    return [{'owner': name, 'count': count} for name, count in ranked]


def cost_centers_weekly_story(rows: list[dict[str, Any]]) -> list[str]:
    story = []
    briefing = cost_centers_briefing(rows)
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
    story.append('Cost Centers briefing is local-only and does not call an external network.')
    return story


def cost_centers_print_pack(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        'briefing': cost_centers_briefing(rows),
        'share': cost_centers_status_share(rows),
        'owners': cost_centers_owner_load(rows),
        'story': cost_centers_weekly_story(rows),
    }


class CostCentersReporter:
    """Builds operator-facing packs for Cost Centers."""

    def __init__(self, rows: list[dict[str, Any]] | None = None) -> None:
        self.rows = list(rows or [])

    def refresh(self, rows: list[dict[str, Any]]) -> None:
        self.rows = list(rows)

    def briefing(self) -> dict[str, Any]:
        return cost_centers_briefing(self.rows)

    def story(self) -> list[str]:
        return cost_centers_weekly_story(self.rows)

    def csv(self) -> str:
        return '\n'.join(cost_centers_csv_lines(self.rows)) + '\n'

    def pack(self) -> dict[str, Any]:
        return cost_centers_print_pack(self.rows)


def build_cost_centers_reporter(rows: list[dict[str, Any]]) -> CostCentersReporter:
    return CostCentersReporter(rows)

def cost_centers_report_by_cc_code(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Cost Centers by Cc Code."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('cc_code') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'cc_code'} for label, count in ranked]


def cost_centers_report_by_name(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Cost Centers by Name."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('name') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'name'} for label, count in ranked]


def cost_centers_report_by_director(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Cost Centers by Director."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('director') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'director'} for label, count in ranked]


def cost_centers_report_by_headcount(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Cost Centers by Headcount."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('headcount') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'headcount'} for label, count in ranked]


def cost_centers_outlier_headcount(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    values = []
    for row in rows:
        try:
            values.append(int(row.get('headcount') or 0))
        except (TypeError, ValueError):
            values.append(0)
    if not values:
        return []
    avg = sum(values) / len(values)
    flagged = []
    for row, value in zip(rows, values):
        if value > avg * 3 and value > 0:
            flagged.append({'id': row.get('id'), 'field': 'headcount', 'value': value, 'avg': int(avg)})
    return flagged


def cost_centers_report_by_status(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Cost Centers by Status."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('status') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'status'} for label, count in ranked]


