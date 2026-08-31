"""Period reports and operator briefings for Ops Runbooks."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from app.domains.runbooks.queries import runbooks_group_status, runbooks_health_bands, runbooks_completeness
from app.domains.runbooks.policies import runbooks_risk_band, runbooks_sla_hours, runbooks_owner_hint

DOMAIN_TITLE = 'Ops Runbooks'


def runbooks_age_days(row: dict[str, Any]) -> int:
    created = str(row.get('created_at') or '')
    try:
        parsed = datetime.fromisoformat(created.replace('Z', ''))
    except ValueError:
        return 0
    return max(0, (datetime.utcnow() - parsed).days)


def runbooks_bucket(days: int) -> str:
    if days < 3:
        return 'fresh'
    if days < 14:
        return 'current'
    if days < 45:
        return 'aging'
    return 'legacy'


def runbooks_line_item(row: dict[str, Any]) -> dict[str, Any]:
    days = runbooks_age_days(row)
    return {
        'id': row.get('id'),
        'title': row.get('runbook_key'),
        'status': row.get('status'),
        'days': days,
        'bucket': runbooks_bucket(days),
        'band': runbooks_risk_band(row),
        'owner': runbooks_owner_hint(row),
        'sla_hours': runbooks_sla_hours(row),
        'completeness': runbooks_completeness(row),
        'health_score': row.get('health_score'),
    }


def runbooks_briefing(rows: list[dict[str, Any]]) -> dict[str, Any]:
    items = [runbooks_line_item(row) for row in rows]
    by_bucket = {'fresh': 0, 'current': 0, 'aging': 0, 'legacy': 0}
    for item in items:
        by_bucket[str(item['bucket'])] += 1
    return {
        'title': DOMAIN_TITLE,
        'generated_at': datetime.utcnow().replace(microsecond=0).isoformat() + 'Z',
        'count': len(items),
        'bands': runbooks_health_bands(rows),
        'buckets': by_bucket,
        'headline': runbooks_headline(rows),
        'items': items[:40],
    }


def runbooks_headline(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return 'Ops Runbooks has no rows in the local ledger yet.'
    bands = runbooks_health_bands(rows)
    critical = bands.get('critical', 0)
    if critical:
        return f'Ops Runbooks: {critical} critical records need a named owner this shift.'
    return f'Ops Runbooks: {len(rows)} records are inside the operating range.'


def runbooks_csv_lines(rows: list[dict[str, Any]]) -> list[str]:
    header = ['id', 'title', 'status', 'days', 'bucket', 'band', 'owner', 'health_score']
    lines = [','.join(header)]
    for row in rows:
        item = runbooks_line_item(row)
        lines.append(','.join(str(item.get(col, '')).replace(',', ' ') for col in header))
    return lines


def runbooks_status_share(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped = runbooks_group_status(rows)
    total = max(1, len(rows))
    share = []
    for status in ['draft', 'certified', 'stale']:
        count = len(grouped.get(status, []))
        share.append({'status': status, 'count': count, 'pct': int((count / total) * 100)})
    return share


def runbooks_owner_load(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    load: dict[str, int] = {}
    for row in rows:
        owner = runbooks_owner_hint(row)
        load[owner] = load.get(owner, 0) + 1
    ranked = sorted(load.items(), key=lambda pair: pair[1], reverse=True)
    return [{'owner': name, 'count': count} for name, count in ranked]


def runbooks_weekly_story(rows: list[dict[str, Any]]) -> list[str]:
    story = []
    briefing = runbooks_briefing(rows)
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
    story.append('Ops Runbooks briefing is local-only and does not call an external network.')
    return story


def runbooks_print_pack(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        'briefing': runbooks_briefing(rows),
        'share': runbooks_status_share(rows),
        'owners': runbooks_owner_load(rows),
        'story': runbooks_weekly_story(rows),
    }


class RunbooksReporter:
    """Builds operator-facing packs for Ops Runbooks."""

    def __init__(self, rows: list[dict[str, Any]] | None = None) -> None:
        self.rows = list(rows or [])

    def refresh(self, rows: list[dict[str, Any]]) -> None:
        self.rows = list(rows)

    def briefing(self) -> dict[str, Any]:
        return runbooks_briefing(self.rows)

    def story(self) -> list[str]:
        return runbooks_weekly_story(self.rows)

    def csv(self) -> str:
        return '\n'.join(runbooks_csv_lines(self.rows)) + '\n'

    def pack(self) -> dict[str, Any]:
        return runbooks_print_pack(self.rows)


def build_runbooks_reporter(rows: list[dict[str, Any]]) -> RunbooksReporter:
    return RunbooksReporter(rows)

def runbooks_report_by_runbook_key(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Ops Runbooks by Runbook Key."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('runbook_key') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'runbook_key'} for label, count in ranked]


def runbooks_report_by_title(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Ops Runbooks by Title."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('title') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'title'} for label, count in ranked]


def runbooks_report_by_owner(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Ops Runbooks by Owner."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('owner') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'owner'} for label, count in ranked]


def runbooks_report_by_step_count(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Ops Runbooks by Step Count."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('step_count') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'step_count'} for label, count in ranked]


def runbooks_outlier_step_count(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
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


def runbooks_report_by_status(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Ops Runbooks by Status."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('status') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'status'} for label, count in ranked]


