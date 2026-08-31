"""Period reports and operator briefings for Partner Desk."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from app.domains.partners.queries import partners_group_status, partners_health_bands, partners_completeness
from app.domains.partners.policies import partners_risk_band, partners_sla_hours, partners_owner_hint

DOMAIN_TITLE = 'Partner Desk'


def partners_age_days(row: dict[str, Any]) -> int:
    created = str(row.get('created_at') or '')
    try:
        parsed = datetime.fromisoformat(created.replace('Z', ''))
    except ValueError:
        return 0
    return max(0, (datetime.utcnow() - parsed).days)


def partners_bucket(days: int) -> str:
    if days < 3:
        return 'fresh'
    if days < 14:
        return 'current'
    if days < 45:
        return 'aging'
    return 'legacy'


def partners_line_item(row: dict[str, Any]) -> dict[str, Any]:
    days = partners_age_days(row)
    return {
        'id': row.get('id'),
        'title': row.get('partner_code'),
        'status': row.get('status'),
        'days': days,
        'bucket': partners_bucket(days),
        'band': partners_risk_band(row),
        'owner': partners_owner_hint(row),
        'sla_hours': partners_sla_hours(row),
        'completeness': partners_completeness(row),
        'health_score': row.get('health_score'),
    }


def partners_briefing(rows: list[dict[str, Any]]) -> dict[str, Any]:
    items = [partners_line_item(row) for row in rows]
    by_bucket = {'fresh': 0, 'current': 0, 'aging': 0, 'legacy': 0}
    for item in items:
        by_bucket[str(item['bucket'])] += 1
    return {
        'title': DOMAIN_TITLE,
        'generated_at': datetime.utcnow().replace(microsecond=0).isoformat() + 'Z',
        'count': len(items),
        'bands': partners_health_bands(rows),
        'buckets': by_bucket,
        'headline': partners_headline(rows),
        'items': items[:40],
    }


def partners_headline(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return 'Partner Desk has no rows in the local ledger yet.'
    bands = partners_health_bands(rows)
    critical = bands.get('critical', 0)
    if critical:
        return f'Partner Desk: {critical} critical records need a named owner this shift.'
    return f'Partner Desk: {len(rows)} records are inside the operating range.'


def partners_csv_lines(rows: list[dict[str, Any]]) -> list[str]:
    header = ['id', 'title', 'status', 'days', 'bucket', 'band', 'owner', 'health_score']
    lines = [','.join(header)]
    for row in rows:
        item = partners_line_item(row)
        lines.append(','.join(str(item.get(col, '')).replace(',', ' ') for col in header))
    return lines


def partners_status_share(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped = partners_group_status(rows)
    total = max(1, len(rows))
    share = []
    for status in ['applicant', 'active', 'probation', 'ended']:
        count = len(grouped.get(status, []))
        share.append({'status': status, 'count': count, 'pct': int((count / total) * 100)})
    return share


def partners_owner_load(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    load: dict[str, int] = {}
    for row in rows:
        owner = partners_owner_hint(row)
        load[owner] = load.get(owner, 0) + 1
    ranked = sorted(load.items(), key=lambda pair: pair[1], reverse=True)
    return [{'owner': name, 'count': count} for name, count in ranked]


def partners_weekly_story(rows: list[dict[str, Any]]) -> list[str]:
    story = []
    briefing = partners_briefing(rows)
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
    story.append('Partner Desk briefing is local-only and does not call an external network.')
    return story


def partners_print_pack(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        'briefing': partners_briefing(rows),
        'share': partners_status_share(rows),
        'owners': partners_owner_load(rows),
        'story': partners_weekly_story(rows),
    }


class PartnersReporter:
    """Builds operator-facing packs for Partner Desk."""

    def __init__(self, rows: list[dict[str, Any]] | None = None) -> None:
        self.rows = list(rows or [])

    def refresh(self, rows: list[dict[str, Any]]) -> None:
        self.rows = list(rows)

    def briefing(self) -> dict[str, Any]:
        return partners_briefing(self.rows)

    def story(self) -> list[str]:
        return partners_weekly_story(self.rows)

    def csv(self) -> str:
        return '\n'.join(partners_csv_lines(self.rows)) + '\n'

    def pack(self) -> dict[str, Any]:
        return partners_print_pack(self.rows)


def build_partners_reporter(rows: list[dict[str, Any]]) -> PartnersReporter:
    return PartnersReporter(rows)

def partners_report_by_partner_code(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Partner Desk by Partner Code."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('partner_code') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'partner_code'} for label, count in ranked]


def partners_report_by_name(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Partner Desk by Name."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('name') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'name'} for label, count in ranked]


def partners_report_by_tier(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Partner Desk by Tier."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('tier') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'tier'} for label, count in ranked]


def partners_report_by_region(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Partner Desk by Region."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('region') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'region'} for label, count in ranked]


def partners_report_by_certified(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Partner Desk by Certified."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('certified') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'certified'} for label, count in ranked]


def partners_report_by_status(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Partner Desk by Status."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('status') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'status'} for label, count in ranked]


