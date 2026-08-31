"""Period reports and operator briefings for People Directory."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from app.domains.directory_users.queries import directory_users_group_status, directory_users_health_bands, directory_users_completeness
from app.domains.directory_users.policies import directory_users_risk_band, directory_users_sla_hours, directory_users_owner_hint

DOMAIN_TITLE = 'People Directory'


def directory_users_age_days(row: dict[str, Any]) -> int:
    created = str(row.get('created_at') or '')
    try:
        parsed = datetime.fromisoformat(created.replace('Z', ''))
    except ValueError:
        return 0
    return max(0, (datetime.utcnow() - parsed).days)


def directory_users_bucket(days: int) -> str:
    if days < 3:
        return 'fresh'
    if days < 14:
        return 'current'
    if days < 45:
        return 'aging'
    return 'legacy'


def directory_users_line_item(row: dict[str, Any]) -> dict[str, Any]:
    days = directory_users_age_days(row)
    return {
        'id': row.get('id'),
        'title': row.get('email'),
        'status': row.get('status'),
        'days': days,
        'bucket': directory_users_bucket(days),
        'band': directory_users_risk_band(row),
        'owner': directory_users_owner_hint(row),
        'sla_hours': directory_users_sla_hours(row),
        'completeness': directory_users_completeness(row),
        'health_score': row.get('health_score'),
    }


def directory_users_briefing(rows: list[dict[str, Any]]) -> dict[str, Any]:
    items = [directory_users_line_item(row) for row in rows]
    by_bucket = {'fresh': 0, 'current': 0, 'aging': 0, 'legacy': 0}
    for item in items:
        by_bucket[str(item['bucket'])] += 1
    return {
        'title': DOMAIN_TITLE,
        'generated_at': datetime.utcnow().replace(microsecond=0).isoformat() + 'Z',
        'count': len(items),
        'bands': directory_users_health_bands(rows),
        'buckets': by_bucket,
        'headline': directory_users_headline(rows),
        'items': items[:40],
    }


def directory_users_headline(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return 'People Directory has no rows in the local ledger yet.'
    bands = directory_users_health_bands(rows)
    critical = bands.get('critical', 0)
    if critical:
        return f'People Directory: {critical} critical records need a named owner this shift.'
    return f'People Directory: {len(rows)} records are inside the operating range.'


def directory_users_csv_lines(rows: list[dict[str, Any]]) -> list[str]:
    header = ['id', 'title', 'status', 'days', 'bucket', 'band', 'owner', 'health_score']
    lines = [','.join(header)]
    for row in rows:
        item = directory_users_line_item(row)
        lines.append(','.join(str(item.get(col, '')).replace(',', ' ') for col in header))
    return lines


def directory_users_status_share(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped = directory_users_group_status(rows)
    total = max(1, len(rows))
    share = []
    for status in ['invited', 'active', 'leave', 'offboarded']:
        count = len(grouped.get(status, []))
        share.append({'status': status, 'count': count, 'pct': int((count / total) * 100)})
    return share


def directory_users_owner_load(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    load: dict[str, int] = {}
    for row in rows:
        owner = directory_users_owner_hint(row)
        load[owner] = load.get(owner, 0) + 1
    ranked = sorted(load.items(), key=lambda pair: pair[1], reverse=True)
    return [{'owner': name, 'count': count} for name, count in ranked]


def directory_users_weekly_story(rows: list[dict[str, Any]]) -> list[str]:
    story = []
    briefing = directory_users_briefing(rows)
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
    story.append('People Directory briefing is local-only and does not call an external network.')
    return story


def directory_users_print_pack(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        'briefing': directory_users_briefing(rows),
        'share': directory_users_status_share(rows),
        'owners': directory_users_owner_load(rows),
        'story': directory_users_weekly_story(rows),
    }


class DirectoryUsersReporter:
    """Builds operator-facing packs for People Directory."""

    def __init__(self, rows: list[dict[str, Any]] | None = None) -> None:
        self.rows = list(rows or [])

    def refresh(self, rows: list[dict[str, Any]]) -> None:
        self.rows = list(rows)

    def briefing(self) -> dict[str, Any]:
        return directory_users_briefing(self.rows)

    def story(self) -> list[str]:
        return directory_users_weekly_story(self.rows)

    def csv(self) -> str:
        return '\n'.join(directory_users_csv_lines(self.rows)) + '\n'

    def pack(self) -> dict[str, Any]:
        return directory_users_print_pack(self.rows)


def build_directory_users_reporter(rows: list[dict[str, Any]]) -> DirectoryUsersReporter:
    return DirectoryUsersReporter(rows)

def directory_users_report_by_email(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice People Directory by Email."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('email') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'email'} for label, count in ranked]


def directory_users_report_by_full_name(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice People Directory by Full Name."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('full_name') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'full_name'} for label, count in ranked]


def directory_users_report_by_job_title(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice People Directory by Job Title."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('job_title') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'job_title'} for label, count in ranked]


def directory_users_report_by_department(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice People Directory by Department."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('department') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'department'} for label, count in ranked]


def directory_users_report_by_manager_email(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice People Directory by Manager Email."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('manager_email') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'manager_email'} for label, count in ranked]


def directory_users_report_by_location(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice People Directory by Location."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('location') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'location'} for label, count in ranked]


def directory_users_report_by_band(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice People Directory by Band."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('band') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'band'} for label, count in ranked]


def directory_users_report_by_status(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice People Directory by Status."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('status') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'status'} for label, count in ranked]


