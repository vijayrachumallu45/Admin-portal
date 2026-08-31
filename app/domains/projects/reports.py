"""Period reports and operator briefings for Delivery Projects."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from app.domains.projects.queries import projects_group_status, projects_health_bands, projects_completeness
from app.domains.projects.policies import projects_risk_band, projects_sla_hours, projects_owner_hint

DOMAIN_TITLE = 'Delivery Projects'


def projects_age_days(row: dict[str, Any]) -> int:
    created = str(row.get('created_at') or '')
    try:
        parsed = datetime.fromisoformat(created.replace('Z', ''))
    except ValueError:
        return 0
    return max(0, (datetime.utcnow() - parsed).days)


def projects_bucket(days: int) -> str:
    if days < 3:
        return 'fresh'
    if days < 14:
        return 'current'
    if days < 45:
        return 'aging'
    return 'legacy'


def projects_line_item(row: dict[str, Any]) -> dict[str, Any]:
    days = projects_age_days(row)
    return {
        'id': row.get('id'),
        'title': row.get('project_code'),
        'status': row.get('status'),
        'days': days,
        'bucket': projects_bucket(days),
        'band': projects_risk_band(row),
        'owner': projects_owner_hint(row),
        'sla_hours': projects_sla_hours(row),
        'completeness': projects_completeness(row),
        'health_score': row.get('health_score'),
    }


def projects_briefing(rows: list[dict[str, Any]]) -> dict[str, Any]:
    items = [projects_line_item(row) for row in rows]
    by_bucket = {'fresh': 0, 'current': 0, 'aging': 0, 'legacy': 0}
    for item in items:
        by_bucket[str(item['bucket'])] += 1
    return {
        'title': DOMAIN_TITLE,
        'generated_at': datetime.utcnow().replace(microsecond=0).isoformat() + 'Z',
        'count': len(items),
        'bands': projects_health_bands(rows),
        'buckets': by_bucket,
        'headline': projects_headline(rows),
        'items': items[:40],
    }


def projects_headline(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return 'Delivery Projects has no rows in the local ledger yet.'
    bands = projects_health_bands(rows)
    critical = bands.get('critical', 0)
    if critical:
        return f'Delivery Projects: {critical} critical records need a named owner this shift.'
    return f'Delivery Projects: {len(rows)} records are inside the operating range.'


def projects_csv_lines(rows: list[dict[str, Any]]) -> list[str]:
    header = ['id', 'title', 'status', 'days', 'bucket', 'band', 'owner', 'health_score']
    lines = [','.join(header)]
    for row in rows:
        item = projects_line_item(row)
        lines.append(','.join(str(item.get(col, '')).replace(',', ' ') for col in header))
    return lines


def projects_status_share(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped = projects_group_status(rows)
    total = max(1, len(rows))
    share = []
    for status in ['planning', 'active', 'blocked', 'done']:
        count = len(grouped.get(status, []))
        share.append({'status': status, 'count': count, 'pct': int((count / total) * 100)})
    return share


def projects_owner_load(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    load: dict[str, int] = {}
    for row in rows:
        owner = projects_owner_hint(row)
        load[owner] = load.get(owner, 0) + 1
    ranked = sorted(load.items(), key=lambda pair: pair[1], reverse=True)
    return [{'owner': name, 'count': count} for name, count in ranked]


def projects_weekly_story(rows: list[dict[str, Any]]) -> list[str]:
    story = []
    briefing = projects_briefing(rows)
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
    story.append('Delivery Projects briefing is local-only and does not call an external network.')
    return story


def projects_print_pack(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        'briefing': projects_briefing(rows),
        'share': projects_status_share(rows),
        'owners': projects_owner_load(rows),
        'story': projects_weekly_story(rows),
    }


class ProjectsReporter:
    """Builds operator-facing packs for Delivery Projects."""

    def __init__(self, rows: list[dict[str, Any]] | None = None) -> None:
        self.rows = list(rows or [])

    def refresh(self, rows: list[dict[str, Any]]) -> None:
        self.rows = list(rows)

    def briefing(self) -> dict[str, Any]:
        return projects_briefing(self.rows)

    def story(self) -> list[str]:
        return projects_weekly_story(self.rows)

    def csv(self) -> str:
        return '\n'.join(projects_csv_lines(self.rows)) + '\n'

    def pack(self) -> dict[str, Any]:
        return projects_print_pack(self.rows)


def build_projects_reporter(rows: list[dict[str, Any]]) -> ProjectsReporter:
    return ProjectsReporter(rows)

def projects_report_by_project_code(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Delivery Projects by Project Code."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('project_code') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'project_code'} for label, count in ranked]


def projects_report_by_name(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Delivery Projects by Name."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('name') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'name'} for label, count in ranked]


def projects_report_by_sponsor(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Delivery Projects by Sponsor."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('sponsor') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'sponsor'} for label, count in ranked]


def projects_report_by_budget_cents(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Delivery Projects by Budget Cents."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('budget_cents') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'budget_cents'} for label, count in ranked]


def projects_outlier_budget_cents(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    values = []
    for row in rows:
        try:
            values.append(int(row.get('budget_cents') or 0))
        except (TypeError, ValueError):
            values.append(0)
    if not values:
        return []
    avg = sum(values) / len(values)
    flagged = []
    for row, value in zip(rows, values):
        if value > avg * 3 and value > 0:
            flagged.append({'id': row.get('id'), 'field': 'budget_cents', 'value': value, 'avg': int(avg)})
    return flagged


def projects_report_by_health(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Delivery Projects by Health."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('health') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'health'} for label, count in ranked]


def projects_report_by_status(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Delivery Projects by Status."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('status') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'status'} for label, count in ranked]


