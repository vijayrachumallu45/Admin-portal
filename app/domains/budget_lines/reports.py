"""Period reports and operator briefings for Budget Lines."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from app.domains.budget_lines.queries import budget_lines_group_status, budget_lines_health_bands, budget_lines_completeness
from app.domains.budget_lines.policies import budget_lines_risk_band, budget_lines_sla_hours, budget_lines_owner_hint

DOMAIN_TITLE = 'Budget Lines'


def budget_lines_age_days(row: dict[str, Any]) -> int:
    created = str(row.get('created_at') or '')
    try:
        parsed = datetime.fromisoformat(created.replace('Z', ''))
    except ValueError:
        return 0
    return max(0, (datetime.utcnow() - parsed).days)


def budget_lines_bucket(days: int) -> str:
    if days < 3:
        return 'fresh'
    if days < 14:
        return 'current'
    if days < 45:
        return 'aging'
    return 'legacy'


def budget_lines_line_item(row: dict[str, Any]) -> dict[str, Any]:
    days = budget_lines_age_days(row)
    return {
        'id': row.get('id'),
        'title': row.get('line_code'),
        'status': row.get('status'),
        'days': days,
        'bucket': budget_lines_bucket(days),
        'band': budget_lines_risk_band(row),
        'owner': budget_lines_owner_hint(row),
        'sla_hours': budget_lines_sla_hours(row),
        'completeness': budget_lines_completeness(row),
        'health_score': row.get('health_score'),
    }


def budget_lines_briefing(rows: list[dict[str, Any]]) -> dict[str, Any]:
    items = [budget_lines_line_item(row) for row in rows]
    by_bucket = {'fresh': 0, 'current': 0, 'aging': 0, 'legacy': 0}
    for item in items:
        by_bucket[str(item['bucket'])] += 1
    return {
        'title': DOMAIN_TITLE,
        'generated_at': datetime.utcnow().replace(microsecond=0).isoformat() + 'Z',
        'count': len(items),
        'bands': budget_lines_health_bands(rows),
        'buckets': by_bucket,
        'headline': budget_lines_headline(rows),
        'items': items[:40],
    }


def budget_lines_headline(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return 'Budget Lines has no rows in the local ledger yet.'
    bands = budget_lines_health_bands(rows)
    critical = bands.get('critical', 0)
    if critical:
        return f'Budget Lines: {critical} critical records need a named owner this shift.'
    return f'Budget Lines: {len(rows)} records are inside the operating range.'


def budget_lines_csv_lines(rows: list[dict[str, Any]]) -> list[str]:
    header = ['id', 'title', 'status', 'days', 'bucket', 'band', 'owner', 'health_score']
    lines = [','.join(header)]
    for row in rows:
        item = budget_lines_line_item(row)
        lines.append(','.join(str(item.get(col, '')).replace(',', ' ') for col in header))
    return lines


def budget_lines_status_share(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped = budget_lines_group_status(rows)
    total = max(1, len(rows))
    share = []
    for status in ['open', 'watch', 'frozen', 'closed']:
        count = len(grouped.get(status, []))
        share.append({'status': status, 'count': count, 'pct': int((count / total) * 100)})
    return share


def budget_lines_owner_load(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    load: dict[str, int] = {}
    for row in rows:
        owner = budget_lines_owner_hint(row)
        load[owner] = load.get(owner, 0) + 1
    ranked = sorted(load.items(), key=lambda pair: pair[1], reverse=True)
    return [{'owner': name, 'count': count} for name, count in ranked]


def budget_lines_weekly_story(rows: list[dict[str, Any]]) -> list[str]:
    story = []
    briefing = budget_lines_briefing(rows)
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
    story.append('Budget Lines briefing is local-only and does not call an external network.')
    return story


def budget_lines_print_pack(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        'briefing': budget_lines_briefing(rows),
        'share': budget_lines_status_share(rows),
        'owners': budget_lines_owner_load(rows),
        'story': budget_lines_weekly_story(rows),
    }


class BudgetLinesReporter:
    """Builds operator-facing packs for Budget Lines."""

    def __init__(self, rows: list[dict[str, Any]] | None = None) -> None:
        self.rows = list(rows or [])

    def refresh(self, rows: list[dict[str, Any]]) -> None:
        self.rows = list(rows)

    def briefing(self) -> dict[str, Any]:
        return budget_lines_briefing(self.rows)

    def story(self) -> list[str]:
        return budget_lines_weekly_story(self.rows)

    def csv(self) -> str:
        return '\n'.join(budget_lines_csv_lines(self.rows)) + '\n'

    def pack(self) -> dict[str, Any]:
        return budget_lines_print_pack(self.rows)


def build_budget_lines_reporter(rows: list[dict[str, Any]]) -> BudgetLinesReporter:
    return BudgetLinesReporter(rows)

def budget_lines_report_by_line_code(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Budget Lines by Line Code."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('line_code') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'line_code'} for label, count in ranked]


def budget_lines_report_by_owner(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Budget Lines by Owner."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('owner') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'owner'} for label, count in ranked]


def budget_lines_report_by_annual_cents(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Budget Lines by Annual Cents."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('annual_cents') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'annual_cents'} for label, count in ranked]


def budget_lines_outlier_annual_cents(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    values = []
    for row in rows:
        try:
            values.append(int(row.get('annual_cents') or 0))
        except (TypeError, ValueError):
            values.append(0)
    if not values:
        return []
    avg = sum(values) / len(values)
    flagged = []
    for row, value in zip(rows, values):
        if value > avg * 3 and value > 0:
            flagged.append({'id': row.get('id'), 'field': 'annual_cents', 'value': value, 'avg': int(avg)})
    return flagged


def budget_lines_report_by_spent_cents(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Budget Lines by Spent Cents."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('spent_cents') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'spent_cents'} for label, count in ranked]


def budget_lines_outlier_spent_cents(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    values = []
    for row in rows:
        try:
            values.append(int(row.get('spent_cents') or 0))
        except (TypeError, ValueError):
            values.append(0)
    if not values:
        return []
    avg = sum(values) / len(values)
    flagged = []
    for row, value in zip(rows, values):
        if value > avg * 3 and value > 0:
            flagged.append({'id': row.get('id'), 'field': 'spent_cents', 'value': value, 'avg': int(avg)})
    return flagged


def budget_lines_report_by_status(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Budget Lines by Status."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('status') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'status'} for label, count in ranked]


