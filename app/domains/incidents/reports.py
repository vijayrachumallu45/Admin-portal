"""Period reports and operator briefings for Incident Room."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from app.domains.incidents.queries import incidents_group_status, incidents_health_bands, incidents_completeness
from app.domains.incidents.policies import incidents_risk_band, incidents_sla_hours, incidents_owner_hint

DOMAIN_TITLE = 'Incident Room'


def incidents_age_days(row: dict[str, Any]) -> int:
    created = str(row.get('created_at') or '')
    try:
        parsed = datetime.fromisoformat(created.replace('Z', ''))
    except ValueError:
        return 0
    return max(0, (datetime.utcnow() - parsed).days)


def incidents_bucket(days: int) -> str:
    if days < 3:
        return 'fresh'
    if days < 14:
        return 'current'
    if days < 45:
        return 'aging'
    return 'legacy'


def incidents_line_item(row: dict[str, Any]) -> dict[str, Any]:
    days = incidents_age_days(row)
    return {
        'id': row.get('id'),
        'title': row.get('incident_no'),
        'status': row.get('status'),
        'days': days,
        'bucket': incidents_bucket(days),
        'band': incidents_risk_band(row),
        'owner': incidents_owner_hint(row),
        'sla_hours': incidents_sla_hours(row),
        'completeness': incidents_completeness(row),
        'health_score': row.get('health_score'),
    }


def incidents_briefing(rows: list[dict[str, Any]]) -> dict[str, Any]:
    items = [incidents_line_item(row) for row in rows]
    by_bucket = {'fresh': 0, 'current': 0, 'aging': 0, 'legacy': 0}
    for item in items:
        by_bucket[str(item['bucket'])] += 1
    return {
        'title': DOMAIN_TITLE,
        'generated_at': datetime.utcnow().replace(microsecond=0).isoformat() + 'Z',
        'count': len(items),
        'bands': incidents_health_bands(rows),
        'buckets': by_bucket,
        'headline': incidents_headline(rows),
        'items': items[:40],
    }


def incidents_headline(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return 'Incident Room has no rows in the local ledger yet.'
    bands = incidents_health_bands(rows)
    critical = bands.get('critical', 0)
    if critical:
        return f'Incident Room: {critical} critical records need a named owner this shift.'
    return f'Incident Room: {len(rows)} records are inside the operating range.'


def incidents_csv_lines(rows: list[dict[str, Any]]) -> list[str]:
    header = ['id', 'title', 'status', 'days', 'bucket', 'band', 'owner', 'health_score']
    lines = [','.join(header)]
    for row in rows:
        item = incidents_line_item(row)
        lines.append(','.join(str(item.get(col, '')).replace(',', ' ') for col in header))
    return lines


def incidents_status_share(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped = incidents_group_status(rows)
    total = max(1, len(rows))
    share = []
    for status in ['investigating', 'identified', 'monitoring', 'resolved']:
        count = len(grouped.get(status, []))
        share.append({'status': status, 'count': count, 'pct': int((count / total) * 100)})
    return share


def incidents_owner_load(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    load: dict[str, int] = {}
    for row in rows:
        owner = incidents_owner_hint(row)
        load[owner] = load.get(owner, 0) + 1
    ranked = sorted(load.items(), key=lambda pair: pair[1], reverse=True)
    return [{'owner': name, 'count': count} for name, count in ranked]


def incidents_weekly_story(rows: list[dict[str, Any]]) -> list[str]:
    story = []
    briefing = incidents_briefing(rows)
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
    story.append('Incident Room briefing is local-only and does not call an external network.')
    return story


def incidents_print_pack(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        'briefing': incidents_briefing(rows),
        'share': incidents_status_share(rows),
        'owners': incidents_owner_load(rows),
        'story': incidents_weekly_story(rows),
    }


class IncidentsReporter:
    """Builds operator-facing packs for Incident Room."""

    def __init__(self, rows: list[dict[str, Any]] | None = None) -> None:
        self.rows = list(rows or [])

    def refresh(self, rows: list[dict[str, Any]]) -> None:
        self.rows = list(rows)

    def briefing(self) -> dict[str, Any]:
        return incidents_briefing(self.rows)

    def story(self) -> list[str]:
        return incidents_weekly_story(self.rows)

    def csv(self) -> str:
        return '\n'.join(incidents_csv_lines(self.rows)) + '\n'

    def pack(self) -> dict[str, Any]:
        return incidents_print_pack(self.rows)


def build_incidents_reporter(rows: list[dict[str, Any]]) -> IncidentsReporter:
    return IncidentsReporter(rows)

def incidents_report_by_incident_no(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Incident Room by Incident No."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('incident_no') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'incident_no'} for label, count in ranked]


def incidents_report_by_title(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Incident Room by Title."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('title') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'title'} for label, count in ranked]


def incidents_report_by_severity(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Incident Room by Severity."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('severity') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'severity'} for label, count in ranked]


def incidents_report_by_commander(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Incident Room by Commander."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('commander') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'commander'} for label, count in ranked]


def incidents_report_by_started_at(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Incident Room by Started At."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('started_at') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'started_at'} for label, count in ranked]


def incidents_report_by_status(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Incident Room by Status."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('status') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'status'} for label, count in ranked]


