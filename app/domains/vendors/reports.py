"""Period reports and operator briefings for Vendor Register."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from app.domains.vendors.queries import vendors_group_status, vendors_health_bands, vendors_completeness
from app.domains.vendors.policies import vendors_risk_band, vendors_sla_hours, vendors_owner_hint

DOMAIN_TITLE = 'Vendor Register'


def vendors_age_days(row: dict[str, Any]) -> int:
    created = str(row.get('created_at') or '')
    try:
        parsed = datetime.fromisoformat(created.replace('Z', ''))
    except ValueError:
        return 0
    return max(0, (datetime.utcnow() - parsed).days)


def vendors_bucket(days: int) -> str:
    if days < 3:
        return 'fresh'
    if days < 14:
        return 'current'
    if days < 45:
        return 'aging'
    return 'legacy'


def vendors_line_item(row: dict[str, Any]) -> dict[str, Any]:
    days = vendors_age_days(row)
    return {
        'id': row.get('id'),
        'title': row.get('vendor_code'),
        'status': row.get('status'),
        'days': days,
        'bucket': vendors_bucket(days),
        'band': vendors_risk_band(row),
        'owner': vendors_owner_hint(row),
        'sla_hours': vendors_sla_hours(row),
        'completeness': vendors_completeness(row),
        'health_score': row.get('health_score'),
    }


def vendors_briefing(rows: list[dict[str, Any]]) -> dict[str, Any]:
    items = [vendors_line_item(row) for row in rows]
    by_bucket = {'fresh': 0, 'current': 0, 'aging': 0, 'legacy': 0}
    for item in items:
        by_bucket[str(item['bucket'])] += 1
    return {
        'title': DOMAIN_TITLE,
        'generated_at': datetime.utcnow().replace(microsecond=0).isoformat() + 'Z',
        'count': len(items),
        'bands': vendors_health_bands(rows),
        'buckets': by_bucket,
        'headline': vendors_headline(rows),
        'items': items[:40],
    }


def vendors_headline(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return 'Vendor Register has no rows in the local ledger yet.'
    bands = vendors_health_bands(rows)
    critical = bands.get('critical', 0)
    if critical:
        return f'Vendor Register: {critical} critical records need a named owner this shift.'
    return f'Vendor Register: {len(rows)} records are inside the operating range.'


def vendors_csv_lines(rows: list[dict[str, Any]]) -> list[str]:
    header = ['id', 'title', 'status', 'days', 'bucket', 'band', 'owner', 'health_score']
    lines = [','.join(header)]
    for row in rows:
        item = vendors_line_item(row)
        lines.append(','.join(str(item.get(col, '')).replace(',', ' ') for col in header))
    return lines


def vendors_status_share(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped = vendors_group_status(rows)
    total = max(1, len(rows))
    share = []
    for status in ['screening', 'approved', 'watchlist', 'exited']:
        count = len(grouped.get(status, []))
        share.append({'status': status, 'count': count, 'pct': int((count / total) * 100)})
    return share


def vendors_owner_load(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    load: dict[str, int] = {}
    for row in rows:
        owner = vendors_owner_hint(row)
        load[owner] = load.get(owner, 0) + 1
    ranked = sorted(load.items(), key=lambda pair: pair[1], reverse=True)
    return [{'owner': name, 'count': count} for name, count in ranked]


def vendors_weekly_story(rows: list[dict[str, Any]]) -> list[str]:
    story = []
    briefing = vendors_briefing(rows)
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
    story.append('Vendor Register briefing is local-only and does not call an external network.')
    return story


def vendors_print_pack(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        'briefing': vendors_briefing(rows),
        'share': vendors_status_share(rows),
        'owners': vendors_owner_load(rows),
        'story': vendors_weekly_story(rows),
    }


class VendorsReporter:
    """Builds operator-facing packs for Vendor Register."""

    def __init__(self, rows: list[dict[str, Any]] | None = None) -> None:
        self.rows = list(rows or [])

    def refresh(self, rows: list[dict[str, Any]]) -> None:
        self.rows = list(rows)

    def briefing(self) -> dict[str, Any]:
        return vendors_briefing(self.rows)

    def story(self) -> list[str]:
        return vendors_weekly_story(self.rows)

    def csv(self) -> str:
        return '\n'.join(vendors_csv_lines(self.rows)) + '\n'

    def pack(self) -> dict[str, Any]:
        return vendors_print_pack(self.rows)


def build_vendors_reporter(rows: list[dict[str, Any]]) -> VendorsReporter:
    return VendorsReporter(rows)

def vendors_report_by_vendor_code(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Vendor Register by Vendor Code."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('vendor_code') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'vendor_code'} for label, count in ranked]


def vendors_report_by_name(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Vendor Register by Name."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('name') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'name'} for label, count in ranked]


def vendors_report_by_category(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Vendor Register by Category."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('category') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'category'} for label, count in ranked]


def vendors_report_by_country(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Vendor Register by Country."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('country') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'country'} for label, count in ranked]


def vendors_report_by_risk_score(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Vendor Register by Risk Score."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('risk_score') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'risk_score'} for label, count in ranked]


def vendors_outlier_risk_score(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    values = []
    for row in rows:
        try:
            values.append(int(row.get('risk_score') or 0))
        except (TypeError, ValueError):
            values.append(0)
    if not values:
        return []
    avg = sum(values) / len(values)
    flagged = []
    for row, value in zip(rows, values):
        if value > avg * 3 and value > 0:
            flagged.append({'id': row.get('id'), 'field': 'risk_score', 'value': value, 'avg': int(avg)})
    return flagged


def vendors_report_by_status(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Vendor Register by Status."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('status') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'status'} for label, count in ranked]


