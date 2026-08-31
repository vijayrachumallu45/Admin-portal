"""Period reports and operator briefings for Timesheets."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from app.domains.timesheets.queries import timesheets_group_status, timesheets_health_bands, timesheets_completeness
from app.domains.timesheets.policies import timesheets_risk_band, timesheets_sla_hours, timesheets_owner_hint

DOMAIN_TITLE = 'Timesheets'


def timesheets_age_days(row: dict[str, Any]) -> int:
    created = str(row.get('created_at') or '')
    try:
        parsed = datetime.fromisoformat(created.replace('Z', ''))
    except ValueError:
        return 0
    return max(0, (datetime.utcnow() - parsed).days)


def timesheets_bucket(days: int) -> str:
    if days < 3:
        return 'fresh'
    if days < 14:
        return 'current'
    if days < 45:
        return 'aging'
    return 'legacy'


def timesheets_line_item(row: dict[str, Any]) -> dict[str, Any]:
    days = timesheets_age_days(row)
    return {
        'id': row.get('id'),
        'title': row.get('employee_no'),
        'status': row.get('status'),
        'days': days,
        'bucket': timesheets_bucket(days),
        'band': timesheets_risk_band(row),
        'owner': timesheets_owner_hint(row),
        'sla_hours': timesheets_sla_hours(row),
        'completeness': timesheets_completeness(row),
        'health_score': row.get('health_score'),
    }


def timesheets_briefing(rows: list[dict[str, Any]]) -> dict[str, Any]:
    items = [timesheets_line_item(row) for row in rows]
    by_bucket = {'fresh': 0, 'current': 0, 'aging': 0, 'legacy': 0}
    for item in items:
        by_bucket[str(item['bucket'])] += 1
    return {
        'title': DOMAIN_TITLE,
        'generated_at': datetime.utcnow().replace(microsecond=0).isoformat() + 'Z',
        'count': len(items),
        'bands': timesheets_health_bands(rows),
        'buckets': by_bucket,
        'headline': timesheets_headline(rows),
        'items': items[:40],
    }


def timesheets_headline(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return 'Timesheets has no rows in the local ledger yet.'
    bands = timesheets_health_bands(rows)
    critical = bands.get('critical', 0)
    if critical:
        return f'Timesheets: {critical} critical records need a named owner this shift.'
    return f'Timesheets: {len(rows)} records are inside the operating range.'


def timesheets_csv_lines(rows: list[dict[str, Any]]) -> list[str]:
    header = ['id', 'title', 'status', 'days', 'bucket', 'band', 'owner', 'health_score']
    lines = [','.join(header)]
    for row in rows:
        item = timesheets_line_item(row)
        lines.append(','.join(str(item.get(col, '')).replace(',', ' ') for col in header))
    return lines


def timesheets_status_share(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped = timesheets_group_status(rows)
    total = max(1, len(rows))
    share = []
    for status in ['draft', 'submitted', 'approved', 'locked']:
        count = len(grouped.get(status, []))
        share.append({'status': status, 'count': count, 'pct': int((count / total) * 100)})
    return share


def timesheets_owner_load(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    load: dict[str, int] = {}
    for row in rows:
        owner = timesheets_owner_hint(row)
        load[owner] = load.get(owner, 0) + 1
    ranked = sorted(load.items(), key=lambda pair: pair[1], reverse=True)
    return [{'owner': name, 'count': count} for name, count in ranked]


def timesheets_weekly_story(rows: list[dict[str, Any]]) -> list[str]:
    story = []
    briefing = timesheets_briefing(rows)
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
    story.append('Timesheets briefing is local-only and does not call an external network.')
    return story


def timesheets_print_pack(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        'briefing': timesheets_briefing(rows),
        'share': timesheets_status_share(rows),
        'owners': timesheets_owner_load(rows),
        'story': timesheets_weekly_story(rows),
    }


class TimesheetsReporter:
    """Builds operator-facing packs for Timesheets."""

    def __init__(self, rows: list[dict[str, Any]] | None = None) -> None:
        self.rows = list(rows or [])

    def refresh(self, rows: list[dict[str, Any]]) -> None:
        self.rows = list(rows)

    def briefing(self) -> dict[str, Any]:
        return timesheets_briefing(self.rows)

    def story(self) -> list[str]:
        return timesheets_weekly_story(self.rows)

    def csv(self) -> str:
        return '\n'.join(timesheets_csv_lines(self.rows)) + '\n'

    def pack(self) -> dict[str, Any]:
        return timesheets_print_pack(self.rows)


def build_timesheets_reporter(rows: list[dict[str, Any]]) -> TimesheetsReporter:
    return TimesheetsReporter(rows)

def timesheets_report_by_employee_no(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Timesheets by Employee No."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('employee_no') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'employee_no'} for label, count in ranked]


def timesheets_report_by_week_start(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Timesheets by Week Start."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('week_start') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'week_start'} for label, count in ranked]


def timesheets_report_by_project_code(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Timesheets by Project Code."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('project_code') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'project_code'} for label, count in ranked]


def timesheets_report_by_minutes(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Timesheets by Minutes."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('minutes') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'minutes'} for label, count in ranked]


def timesheets_outlier_minutes(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    values = []
    for row in rows:
        try:
            values.append(int(row.get('minutes') or 0))
        except (TypeError, ValueError):
            values.append(0)
    if not values:
        return []
    avg = sum(values) / len(values)
    flagged = []
    for row, value in zip(rows, values):
        if value > avg * 3 and value > 0:
            flagged.append({'id': row.get('id'), 'field': 'minutes', 'value': value, 'avg': int(avg)})
    return flagged


def timesheets_report_by_billable(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Timesheets by Billable."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('billable') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'billable'} for label, count in ranked]


def timesheets_report_by_status(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Timesheets by Status."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('status') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'status'} for label, count in ranked]


