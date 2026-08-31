"""Period reports and operator briefings for Visitor Desk."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from app.domains.visitors.queries import visitors_group_status, visitors_health_bands, visitors_completeness
from app.domains.visitors.policies import visitors_risk_band, visitors_sla_hours, visitors_owner_hint

DOMAIN_TITLE = 'Visitor Desk'


def visitors_age_days(row: dict[str, Any]) -> int:
    created = str(row.get('created_at') or '')
    try:
        parsed = datetime.fromisoformat(created.replace('Z', ''))
    except ValueError:
        return 0
    return max(0, (datetime.utcnow() - parsed).days)


def visitors_bucket(days: int) -> str:
    if days < 3:
        return 'fresh'
    if days < 14:
        return 'current'
    if days < 45:
        return 'aging'
    return 'legacy'


def visitors_line_item(row: dict[str, Any]) -> dict[str, Any]:
    days = visitors_age_days(row)
    return {
        'id': row.get('id'),
        'title': row.get('visitor_name'),
        'status': row.get('status'),
        'days': days,
        'bucket': visitors_bucket(days),
        'band': visitors_risk_band(row),
        'owner': visitors_owner_hint(row),
        'sla_hours': visitors_sla_hours(row),
        'completeness': visitors_completeness(row),
        'health_score': row.get('health_score'),
    }


def visitors_briefing(rows: list[dict[str, Any]]) -> dict[str, Any]:
    items = [visitors_line_item(row) for row in rows]
    by_bucket = {'fresh': 0, 'current': 0, 'aging': 0, 'legacy': 0}
    for item in items:
        by_bucket[str(item['bucket'])] += 1
    return {
        'title': DOMAIN_TITLE,
        'generated_at': datetime.utcnow().replace(microsecond=0).isoformat() + 'Z',
        'count': len(items),
        'bands': visitors_health_bands(rows),
        'buckets': by_bucket,
        'headline': visitors_headline(rows),
        'items': items[:40],
    }


def visitors_headline(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return 'Visitor Desk has no rows in the local ledger yet.'
    bands = visitors_health_bands(rows)
    critical = bands.get('critical', 0)
    if critical:
        return f'Visitor Desk: {critical} critical records need a named owner this shift.'
    return f'Visitor Desk: {len(rows)} records are inside the operating range.'


def visitors_csv_lines(rows: list[dict[str, Any]]) -> list[str]:
    header = ['id', 'title', 'status', 'days', 'bucket', 'band', 'owner', 'health_score']
    lines = [','.join(header)]
    for row in rows:
        item = visitors_line_item(row)
        lines.append(','.join(str(item.get(col, '')).replace(',', ' ') for col in header))
    return lines


def visitors_status_share(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped = visitors_group_status(rows)
    total = max(1, len(rows))
    share = []
    for status in ['expected', 'on_site', 'departed']:
        count = len(grouped.get(status, []))
        share.append({'status': status, 'count': count, 'pct': int((count / total) * 100)})
    return share


def visitors_owner_load(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    load: dict[str, int] = {}
    for row in rows:
        owner = visitors_owner_hint(row)
        load[owner] = load.get(owner, 0) + 1
    ranked = sorted(load.items(), key=lambda pair: pair[1], reverse=True)
    return [{'owner': name, 'count': count} for name, count in ranked]


def visitors_weekly_story(rows: list[dict[str, Any]]) -> list[str]:
    story = []
    briefing = visitors_briefing(rows)
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
    story.append('Visitor Desk briefing is local-only and does not call an external network.')
    return story


def visitors_print_pack(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        'briefing': visitors_briefing(rows),
        'share': visitors_status_share(rows),
        'owners': visitors_owner_load(rows),
        'story': visitors_weekly_story(rows),
    }


class VisitorsReporter:
    """Builds operator-facing packs for Visitor Desk."""

    def __init__(self, rows: list[dict[str, Any]] | None = None) -> None:
        self.rows = list(rows or [])

    def refresh(self, rows: list[dict[str, Any]]) -> None:
        self.rows = list(rows)

    def briefing(self) -> dict[str, Any]:
        return visitors_briefing(self.rows)

    def story(self) -> list[str]:
        return visitors_weekly_story(self.rows)

    def csv(self) -> str:
        return '\n'.join(visitors_csv_lines(self.rows)) + '\n'

    def pack(self) -> dict[str, Any]:
        return visitors_print_pack(self.rows)


def build_visitors_reporter(rows: list[dict[str, Any]]) -> VisitorsReporter:
    return VisitorsReporter(rows)

def visitors_report_by_visitor_name(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Visitor Desk by Visitor Name."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('visitor_name') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'visitor_name'} for label, count in ranked]


def visitors_report_by_host_name(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Visitor Desk by Host Name."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('host_name') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'host_name'} for label, count in ranked]


def visitors_report_by_company(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Visitor Desk by Company."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('company') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'company'} for label, count in ranked]


def visitors_report_by_arrives_on(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Visitor Desk by Arrives On."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('arrives_on') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'arrives_on'} for label, count in ranked]


def visitors_report_by_status(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Visitor Desk by Status."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('status') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'status'} for label, count in ranked]


