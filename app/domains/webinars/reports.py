"""Period reports and operator briefings for Webinar Desk."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from app.domains.webinars.queries import webinars_group_status, webinars_health_bands, webinars_completeness
from app.domains.webinars.policies import webinars_risk_band, webinars_sla_hours, webinars_owner_hint

DOMAIN_TITLE = 'Webinar Desk'


def webinars_age_days(row: dict[str, Any]) -> int:
    created = str(row.get('created_at') or '')
    try:
        parsed = datetime.fromisoformat(created.replace('Z', ''))
    except ValueError:
        return 0
    return max(0, (datetime.utcnow() - parsed).days)


def webinars_bucket(days: int) -> str:
    if days < 3:
        return 'fresh'
    if days < 14:
        return 'current'
    if days < 45:
        return 'aging'
    return 'legacy'


def webinars_line_item(row: dict[str, Any]) -> dict[str, Any]:
    days = webinars_age_days(row)
    return {
        'id': row.get('id'),
        'title': row.get('webinar_code'),
        'status': row.get('status'),
        'days': days,
        'bucket': webinars_bucket(days),
        'band': webinars_risk_band(row),
        'owner': webinars_owner_hint(row),
        'sla_hours': webinars_sla_hours(row),
        'completeness': webinars_completeness(row),
        'health_score': row.get('health_score'),
    }


def webinars_briefing(rows: list[dict[str, Any]]) -> dict[str, Any]:
    items = [webinars_line_item(row) for row in rows]
    by_bucket = {'fresh': 0, 'current': 0, 'aging': 0, 'legacy': 0}
    for item in items:
        by_bucket[str(item['bucket'])] += 1
    return {
        'title': DOMAIN_TITLE,
        'generated_at': datetime.utcnow().replace(microsecond=0).isoformat() + 'Z',
        'count': len(items),
        'bands': webinars_health_bands(rows),
        'buckets': by_bucket,
        'headline': webinars_headline(rows),
        'items': items[:40],
    }


def webinars_headline(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return 'Webinar Desk has no rows in the local ledger yet.'
    bands = webinars_health_bands(rows)
    critical = bands.get('critical', 0)
    if critical:
        return f'Webinar Desk: {critical} critical records need a named owner this shift.'
    return f'Webinar Desk: {len(rows)} records are inside the operating range.'


def webinars_csv_lines(rows: list[dict[str, Any]]) -> list[str]:
    header = ['id', 'title', 'status', 'days', 'bucket', 'band', 'owner', 'health_score']
    lines = [','.join(header)]
    for row in rows:
        item = webinars_line_item(row)
        lines.append(','.join(str(item.get(col, '')).replace(',', ' ') for col in header))
    return lines


def webinars_status_share(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped = webinars_group_status(rows)
    total = max(1, len(rows))
    share = []
    for status in ['planned', 'live', 'complete', 'cancelled']:
        count = len(grouped.get(status, []))
        share.append({'status': status, 'count': count, 'pct': int((count / total) * 100)})
    return share


def webinars_owner_load(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    load: dict[str, int] = {}
    for row in rows:
        owner = webinars_owner_hint(row)
        load[owner] = load.get(owner, 0) + 1
    ranked = sorted(load.items(), key=lambda pair: pair[1], reverse=True)
    return [{'owner': name, 'count': count} for name, count in ranked]


def webinars_weekly_story(rows: list[dict[str, Any]]) -> list[str]:
    story = []
    briefing = webinars_briefing(rows)
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
    story.append('Webinar Desk briefing is local-only and does not call an external network.')
    return story


def webinars_print_pack(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        'briefing': webinars_briefing(rows),
        'share': webinars_status_share(rows),
        'owners': webinars_owner_load(rows),
        'story': webinars_weekly_story(rows),
    }


class WebinarsReporter:
    """Builds operator-facing packs for Webinar Desk."""

    def __init__(self, rows: list[dict[str, Any]] | None = None) -> None:
        self.rows = list(rows or [])

    def refresh(self, rows: list[dict[str, Any]]) -> None:
        self.rows = list(rows)

    def briefing(self) -> dict[str, Any]:
        return webinars_briefing(self.rows)

    def story(self) -> list[str]:
        return webinars_weekly_story(self.rows)

    def csv(self) -> str:
        return '\n'.join(webinars_csv_lines(self.rows)) + '\n'

    def pack(self) -> dict[str, Any]:
        return webinars_print_pack(self.rows)


def build_webinars_reporter(rows: list[dict[str, Any]]) -> WebinarsReporter:
    return WebinarsReporter(rows)

def webinars_report_by_webinar_code(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Webinar Desk by Webinar Code."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('webinar_code') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'webinar_code'} for label, count in ranked]


def webinars_report_by_title(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Webinar Desk by Title."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('title') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'title'} for label, count in ranked]


def webinars_report_by_host_name(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Webinar Desk by Host Name."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('host_name') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'host_name'} for label, count in ranked]


def webinars_report_by_starts_on(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Webinar Desk by Starts On."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('starts_on') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'starts_on'} for label, count in ranked]


def webinars_report_by_cap(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Webinar Desk by Cap."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('cap') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'cap'} for label, count in ranked]


def webinars_outlier_cap(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    values = []
    for row in rows:
        try:
            values.append(int(row.get('cap') or 0))
        except (TypeError, ValueError):
            values.append(0)
    if not values:
        return []
    avg = sum(values) / len(values)
    flagged = []
    for row, value in zip(rows, values):
        if value > avg * 3 and value > 0:
            flagged.append({'id': row.get('id'), 'field': 'cap', 'value': value, 'avg': int(avg)})
    return flagged


def webinars_report_by_status(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Webinar Desk by Status."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('status') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'status'} for label, count in ranked]


