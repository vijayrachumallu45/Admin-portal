"""Period reports and operator briefings for Tenant Directory."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from app.domains.tenants.queries import tenants_group_status, tenants_health_bands, tenants_completeness
from app.domains.tenants.policies import tenants_risk_band, tenants_sla_hours, tenants_owner_hint

DOMAIN_TITLE = 'Tenant Directory'


def tenants_age_days(row: dict[str, Any]) -> int:
    created = str(row.get('created_at') or '')
    try:
        parsed = datetime.fromisoformat(created.replace('Z', ''))
    except ValueError:
        return 0
    return max(0, (datetime.utcnow() - parsed).days)


def tenants_bucket(days: int) -> str:
    if days < 3:
        return 'fresh'
    if days < 14:
        return 'current'
    if days < 45:
        return 'aging'
    return 'legacy'


def tenants_line_item(row: dict[str, Any]) -> dict[str, Any]:
    days = tenants_age_days(row)
    return {
        'id': row.get('id'),
        'title': row.get('code'),
        'status': row.get('status'),
        'days': days,
        'bucket': tenants_bucket(days),
        'band': tenants_risk_band(row),
        'owner': tenants_owner_hint(row),
        'sla_hours': tenants_sla_hours(row),
        'completeness': tenants_completeness(row),
        'health_score': row.get('health_score'),
    }


def tenants_briefing(rows: list[dict[str, Any]]) -> dict[str, Any]:
    items = [tenants_line_item(row) for row in rows]
    by_bucket = {'fresh': 0, 'current': 0, 'aging': 0, 'legacy': 0}
    for item in items:
        by_bucket[str(item['bucket'])] += 1
    return {
        'title': DOMAIN_TITLE,
        'generated_at': datetime.utcnow().replace(microsecond=0).isoformat() + 'Z',
        'count': len(items),
        'bands': tenants_health_bands(rows),
        'buckets': by_bucket,
        'headline': tenants_headline(rows),
        'items': items[:40],
    }


def tenants_headline(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return 'Tenant Directory has no rows in the local ledger yet.'
    bands = tenants_health_bands(rows)
    critical = bands.get('critical', 0)
    if critical:
        return f'Tenant Directory: {critical} critical records need a named owner this shift.'
    return f'Tenant Directory: {len(rows)} records are inside the operating range.'


def tenants_csv_lines(rows: list[dict[str, Any]]) -> list[str]:
    header = ['id', 'title', 'status', 'days', 'bucket', 'band', 'owner', 'health_score']
    lines = [','.join(header)]
    for row in rows:
        item = tenants_line_item(row)
        lines.append(','.join(str(item.get(col, '')).replace(',', ' ') for col in header))
    return lines


def tenants_status_share(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped = tenants_group_status(rows)
    total = max(1, len(rows))
    share = []
    for status in ['prospect', 'onboarding', 'live', 'suspended', 'churned']:
        count = len(grouped.get(status, []))
        share.append({'status': status, 'count': count, 'pct': int((count / total) * 100)})
    return share


def tenants_owner_load(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    load: dict[str, int] = {}
    for row in rows:
        owner = tenants_owner_hint(row)
        load[owner] = load.get(owner, 0) + 1
    ranked = sorted(load.items(), key=lambda pair: pair[1], reverse=True)
    return [{'owner': name, 'count': count} for name, count in ranked]


def tenants_weekly_story(rows: list[dict[str, Any]]) -> list[str]:
    story = []
    briefing = tenants_briefing(rows)
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
    story.append('Tenant Directory briefing is local-only and does not call an external network.')
    return story


def tenants_print_pack(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        'briefing': tenants_briefing(rows),
        'share': tenants_status_share(rows),
        'owners': tenants_owner_load(rows),
        'story': tenants_weekly_story(rows),
    }


class TenantsReporter:
    """Builds operator-facing packs for Tenant Directory."""

    def __init__(self, rows: list[dict[str, Any]] | None = None) -> None:
        self.rows = list(rows or [])

    def refresh(self, rows: list[dict[str, Any]]) -> None:
        self.rows = list(rows)

    def briefing(self) -> dict[str, Any]:
        return tenants_briefing(self.rows)

    def story(self) -> list[str]:
        return tenants_weekly_story(self.rows)

    def csv(self) -> str:
        return '\n'.join(tenants_csv_lines(self.rows)) + '\n'

    def pack(self) -> dict[str, Any]:
        return tenants_print_pack(self.rows)


def build_tenants_reporter(rows: list[dict[str, Any]]) -> TenantsReporter:
    return TenantsReporter(rows)

def tenants_report_by_code(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Tenant Directory by Code."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('code') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'code'} for label, count in ranked]


def tenants_report_by_legal_name(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Tenant Directory by Legal Name."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('legal_name') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'legal_name'} for label, count in ranked]


def tenants_report_by_region(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Tenant Directory by Region."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('region') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'region'} for label, count in ranked]


def tenants_report_by_tier(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Tenant Directory by Tier."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('tier') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'tier'} for label, count in ranked]


def tenants_report_by_seat_limit(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Tenant Directory by Seat Limit."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('seat_limit') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'seat_limit'} for label, count in ranked]


def tenants_outlier_seat_limit(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    values = []
    for row in rows:
        try:
            values.append(int(row.get('seat_limit') or 0))
        except (TypeError, ValueError):
            values.append(0)
    if not values:
        return []
    avg = sum(values) / len(values)
    flagged = []
    for row, value in zip(rows, values):
        if value > avg * 3 and value > 0:
            flagged.append({'id': row.get('id'), 'field': 'seat_limit', 'value': value, 'avg': int(avg)})
    return flagged


def tenants_report_by_mrr_cents(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Tenant Directory by Mrr Cents."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('mrr_cents') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'mrr_cents'} for label, count in ranked]


def tenants_outlier_mrr_cents(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    values = []
    for row in rows:
        try:
            values.append(int(row.get('mrr_cents') or 0))
        except (TypeError, ValueError):
            values.append(0)
    if not values:
        return []
    avg = sum(values) / len(values)
    flagged = []
    for row, value in zip(rows, values):
        if value > avg * 3 and value > 0:
            flagged.append({'id': row.get('id'), 'field': 'mrr_cents', 'value': value, 'avg': int(avg)})
    return flagged


def tenants_report_by_go_live(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Tenant Directory by Go Live."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('go_live') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'go_live'} for label, count in ranked]


def tenants_report_by_status(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Tenant Directory by Status."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('status') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'status'} for label, count in ranked]


