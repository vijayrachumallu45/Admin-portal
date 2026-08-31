"""Period reports and operator briefings for Workflow Studio."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from app.domains.workflow_defs.queries import workflow_defs_group_status, workflow_defs_health_bands, workflow_defs_completeness
from app.domains.workflow_defs.policies import workflow_defs_risk_band, workflow_defs_sla_hours, workflow_defs_owner_hint

DOMAIN_TITLE = 'Workflow Studio'


def workflow_defs_age_days(row: dict[str, Any]) -> int:
    created = str(row.get('created_at') or '')
    try:
        parsed = datetime.fromisoformat(created.replace('Z', ''))
    except ValueError:
        return 0
    return max(0, (datetime.utcnow() - parsed).days)


def workflow_defs_bucket(days: int) -> str:
    if days < 3:
        return 'fresh'
    if days < 14:
        return 'current'
    if days < 45:
        return 'aging'
    return 'legacy'


def workflow_defs_line_item(row: dict[str, Any]) -> dict[str, Any]:
    days = workflow_defs_age_days(row)
    return {
        'id': row.get('id'),
        'title': row.get('workflow_key'),
        'status': row.get('status'),
        'days': days,
        'bucket': workflow_defs_bucket(days),
        'band': workflow_defs_risk_band(row),
        'owner': workflow_defs_owner_hint(row),
        'sla_hours': workflow_defs_sla_hours(row),
        'completeness': workflow_defs_completeness(row),
        'health_score': row.get('health_score'),
    }


def workflow_defs_briefing(rows: list[dict[str, Any]]) -> dict[str, Any]:
    items = [workflow_defs_line_item(row) for row in rows]
    by_bucket = {'fresh': 0, 'current': 0, 'aging': 0, 'legacy': 0}
    for item in items:
        by_bucket[str(item['bucket'])] += 1
    return {
        'title': DOMAIN_TITLE,
        'generated_at': datetime.utcnow().replace(microsecond=0).isoformat() + 'Z',
        'count': len(items),
        'bands': workflow_defs_health_bands(rows),
        'buckets': by_bucket,
        'headline': workflow_defs_headline(rows),
        'items': items[:40],
    }


def workflow_defs_headline(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return 'Workflow Studio has no rows in the local ledger yet.'
    bands = workflow_defs_health_bands(rows)
    critical = bands.get('critical', 0)
    if critical:
        return f'Workflow Studio: {critical} critical records need a named owner this shift.'
    return f'Workflow Studio: {len(rows)} records are inside the operating range.'


def workflow_defs_csv_lines(rows: list[dict[str, Any]]) -> list[str]:
    header = ['id', 'title', 'status', 'days', 'bucket', 'band', 'owner', 'health_score']
    lines = [','.join(header)]
    for row in rows:
        item = workflow_defs_line_item(row)
        lines.append(','.join(str(item.get(col, '')).replace(',', ' ') for col in header))
    return lines


def workflow_defs_status_share(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped = workflow_defs_group_status(rows)
    total = max(1, len(rows))
    share = []
    for status in ['draft', 'live', 'paused']:
        count = len(grouped.get(status, []))
        share.append({'status': status, 'count': count, 'pct': int((count / total) * 100)})
    return share


def workflow_defs_owner_load(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    load: dict[str, int] = {}
    for row in rows:
        owner = workflow_defs_owner_hint(row)
        load[owner] = load.get(owner, 0) + 1
    ranked = sorted(load.items(), key=lambda pair: pair[1], reverse=True)
    return [{'owner': name, 'count': count} for name, count in ranked]


def workflow_defs_weekly_story(rows: list[dict[str, Any]]) -> list[str]:
    story = []
    briefing = workflow_defs_briefing(rows)
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
    story.append('Workflow Studio briefing is local-only and does not call an external network.')
    return story


def workflow_defs_print_pack(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        'briefing': workflow_defs_briefing(rows),
        'share': workflow_defs_status_share(rows),
        'owners': workflow_defs_owner_load(rows),
        'story': workflow_defs_weekly_story(rows),
    }


class WorkflowDefsReporter:
    """Builds operator-facing packs for Workflow Studio."""

    def __init__(self, rows: list[dict[str, Any]] | None = None) -> None:
        self.rows = list(rows or [])

    def refresh(self, rows: list[dict[str, Any]]) -> None:
        self.rows = list(rows)

    def briefing(self) -> dict[str, Any]:
        return workflow_defs_briefing(self.rows)

    def story(self) -> list[str]:
        return workflow_defs_weekly_story(self.rows)

    def csv(self) -> str:
        return '\n'.join(workflow_defs_csv_lines(self.rows)) + '\n'

    def pack(self) -> dict[str, Any]:
        return workflow_defs_print_pack(self.rows)


def build_workflow_defs_reporter(rows: list[dict[str, Any]]) -> WorkflowDefsReporter:
    return WorkflowDefsReporter(rows)

def workflow_defs_report_by_workflow_key(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Workflow Studio by Workflow Key."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('workflow_key') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'workflow_key'} for label, count in ranked]


def workflow_defs_report_by_name(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Workflow Studio by Name."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('name') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'name'} for label, count in ranked]


def workflow_defs_report_by_trigger_event(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Workflow Studio by Trigger Event."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('trigger_event') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'trigger_event'} for label, count in ranked]


def workflow_defs_report_by_step_count(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Workflow Studio by Step Count."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('step_count') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'step_count'} for label, count in ranked]


def workflow_defs_outlier_step_count(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    values = []
    for row in rows:
        try:
            values.append(int(row.get('step_count') or 0))
        except (TypeError, ValueError):
            values.append(0)
    if not values:
        return []
    avg = sum(values) / len(values)
    flagged = []
    for row, value in zip(rows, values):
        if value > avg * 3 and value > 0:
            flagged.append({'id': row.get('id'), 'field': 'step_count', 'value': value, 'avg': int(avg)})
    return flagged


def workflow_defs_report_by_status(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Workflow Studio by Status."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('status') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'status'} for label, count in ranked]


