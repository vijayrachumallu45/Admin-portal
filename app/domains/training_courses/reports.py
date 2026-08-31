"""Period reports and operator briefings for Training Catalog."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from app.domains.training_courses.queries import training_courses_group_status, training_courses_health_bands, training_courses_completeness
from app.domains.training_courses.policies import training_courses_risk_band, training_courses_sla_hours, training_courses_owner_hint

DOMAIN_TITLE = 'Training Catalog'


def training_courses_age_days(row: dict[str, Any]) -> int:
    created = str(row.get('created_at') or '')
    try:
        parsed = datetime.fromisoformat(created.replace('Z', ''))
    except ValueError:
        return 0
    return max(0, (datetime.utcnow() - parsed).days)


def training_courses_bucket(days: int) -> str:
    if days < 3:
        return 'fresh'
    if days < 14:
        return 'current'
    if days < 45:
        return 'aging'
    return 'legacy'


def training_courses_line_item(row: dict[str, Any]) -> dict[str, Any]:
    days = training_courses_age_days(row)
    return {
        'id': row.get('id'),
        'title': row.get('course_code'),
        'status': row.get('status'),
        'days': days,
        'bucket': training_courses_bucket(days),
        'band': training_courses_risk_band(row),
        'owner': training_courses_owner_hint(row),
        'sla_hours': training_courses_sla_hours(row),
        'completeness': training_courses_completeness(row),
        'health_score': row.get('health_score'),
    }


def training_courses_briefing(rows: list[dict[str, Any]]) -> dict[str, Any]:
    items = [training_courses_line_item(row) for row in rows]
    by_bucket = {'fresh': 0, 'current': 0, 'aging': 0, 'legacy': 0}
    for item in items:
        by_bucket[str(item['bucket'])] += 1
    return {
        'title': DOMAIN_TITLE,
        'generated_at': datetime.utcnow().replace(microsecond=0).isoformat() + 'Z',
        'count': len(items),
        'bands': training_courses_health_bands(rows),
        'buckets': by_bucket,
        'headline': training_courses_headline(rows),
        'items': items[:40],
    }


def training_courses_headline(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return 'Training Catalog has no rows in the local ledger yet.'
    bands = training_courses_health_bands(rows)
    critical = bands.get('critical', 0)
    if critical:
        return f'Training Catalog: {critical} critical records need a named owner this shift.'
    return f'Training Catalog: {len(rows)} records are inside the operating range.'


def training_courses_csv_lines(rows: list[dict[str, Any]]) -> list[str]:
    header = ['id', 'title', 'status', 'days', 'bucket', 'band', 'owner', 'health_score']
    lines = [','.join(header)]
    for row in rows:
        item = training_courses_line_item(row)
        lines.append(','.join(str(item.get(col, '')).replace(',', ' ') for col in header))
    return lines


def training_courses_status_share(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped = training_courses_group_status(rows)
    total = max(1, len(rows))
    share = []
    for status in ['draft', 'required', 'optional', 'retired']:
        count = len(grouped.get(status, []))
        share.append({'status': status, 'count': count, 'pct': int((count / total) * 100)})
    return share


def training_courses_owner_load(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    load: dict[str, int] = {}
    for row in rows:
        owner = training_courses_owner_hint(row)
        load[owner] = load.get(owner, 0) + 1
    ranked = sorted(load.items(), key=lambda pair: pair[1], reverse=True)
    return [{'owner': name, 'count': count} for name, count in ranked]


def training_courses_weekly_story(rows: list[dict[str, Any]]) -> list[str]:
    story = []
    briefing = training_courses_briefing(rows)
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
    story.append('Training Catalog briefing is local-only and does not call an external network.')
    return story


def training_courses_print_pack(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        'briefing': training_courses_briefing(rows),
        'share': training_courses_status_share(rows),
        'owners': training_courses_owner_load(rows),
        'story': training_courses_weekly_story(rows),
    }


class TrainingCoursesReporter:
    """Builds operator-facing packs for Training Catalog."""

    def __init__(self, rows: list[dict[str, Any]] | None = None) -> None:
        self.rows = list(rows or [])

    def refresh(self, rows: list[dict[str, Any]]) -> None:
        self.rows = list(rows)

    def briefing(self) -> dict[str, Any]:
        return training_courses_briefing(self.rows)

    def story(self) -> list[str]:
        return training_courses_weekly_story(self.rows)

    def csv(self) -> str:
        return '\n'.join(training_courses_csv_lines(self.rows)) + '\n'

    def pack(self) -> dict[str, Any]:
        return training_courses_print_pack(self.rows)


def build_training_courses_reporter(rows: list[dict[str, Any]]) -> TrainingCoursesReporter:
    return TrainingCoursesReporter(rows)

def training_courses_report_by_course_code(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Training Catalog by Course Code."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('course_code') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'course_code'} for label, count in ranked]


def training_courses_report_by_title(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Training Catalog by Title."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('title') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'title'} for label, count in ranked]


def training_courses_report_by_hours(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Training Catalog by Hours."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('hours') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'hours'} for label, count in ranked]


def training_courses_outlier_hours(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    values = []
    for row in rows:
        try:
            values.append(int(row.get('hours') or 0))
        except (TypeError, ValueError):
            values.append(0)
    if not values:
        return []
    avg = sum(values) / len(values)
    flagged = []
    for row, value in zip(rows, values):
        if value > avg * 3 and value > 0:
            flagged.append({'id': row.get('id'), 'field': 'hours', 'value': value, 'avg': int(avg)})
    return flagged


def training_courses_report_by_audience(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Training Catalog by Audience."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('audience') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'audience'} for label, count in ranked]


def training_courses_report_by_status(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Training Catalog by Status."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('status') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'status'} for label, count in ranked]


