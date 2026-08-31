"""Period reports and operator briefings for Role Catalog."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from app.domains.roles_catalog.queries import roles_catalog_group_status, roles_catalog_health_bands, roles_catalog_completeness
from app.domains.roles_catalog.policies import roles_catalog_risk_band, roles_catalog_sla_hours, roles_catalog_owner_hint

DOMAIN_TITLE = 'Role Catalog'


def roles_catalog_age_days(row: dict[str, Any]) -> int:
    created = str(row.get('created_at') or '')
    try:
        parsed = datetime.fromisoformat(created.replace('Z', ''))
    except ValueError:
        return 0
    return max(0, (datetime.utcnow() - parsed).days)


def roles_catalog_bucket(days: int) -> str:
    if days < 3:
        return 'fresh'
    if days < 14:
        return 'current'
    if days < 45:
        return 'aging'
    return 'legacy'


def roles_catalog_line_item(row: dict[str, Any]) -> dict[str, Any]:
    days = roles_catalog_age_days(row)
    return {
        'id': row.get('id'),
        'title': row.get('role_key'),
        'status': row.get('status'),
        'days': days,
        'bucket': roles_catalog_bucket(days),
        'band': roles_catalog_risk_band(row),
        'owner': roles_catalog_owner_hint(row),
        'sla_hours': roles_catalog_sla_hours(row),
        'completeness': roles_catalog_completeness(row),
        'health_score': row.get('health_score'),
    }


def roles_catalog_briefing(rows: list[dict[str, Any]]) -> dict[str, Any]:
    items = [roles_catalog_line_item(row) for row in rows]
    by_bucket = {'fresh': 0, 'current': 0, 'aging': 0, 'legacy': 0}
    for item in items:
        by_bucket[str(item['bucket'])] += 1
    return {
        'title': DOMAIN_TITLE,
        'generated_at': datetime.utcnow().replace(microsecond=0).isoformat() + 'Z',
        'count': len(items),
        'bands': roles_catalog_health_bands(rows),
        'buckets': by_bucket,
        'headline': roles_catalog_headline(rows),
        'items': items[:40],
    }


def roles_catalog_headline(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return 'Role Catalog has no rows in the local ledger yet.'
    bands = roles_catalog_health_bands(rows)
    critical = bands.get('critical', 0)
    if critical:
        return f'Role Catalog: {critical} critical records need a named owner this shift.'
    return f'Role Catalog: {len(rows)} records are inside the operating range.'


def roles_catalog_csv_lines(rows: list[dict[str, Any]]) -> list[str]:
    header = ['id', 'title', 'status', 'days', 'bucket', 'band', 'owner', 'health_score']
    lines = [','.join(header)]
    for row in rows:
        item = roles_catalog_line_item(row)
        lines.append(','.join(str(item.get(col, '')).replace(',', ' ') for col in header))
    return lines


def roles_catalog_status_share(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped = roles_catalog_group_status(rows)
    total = max(1, len(rows))
    share = []
    for status in ['draft', 'published', 'deprecated']:
        count = len(grouped.get(status, []))
        share.append({'status': status, 'count': count, 'pct': int((count / total) * 100)})
    return share


def roles_catalog_owner_load(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    load: dict[str, int] = {}
    for row in rows:
        owner = roles_catalog_owner_hint(row)
        load[owner] = load.get(owner, 0) + 1
    ranked = sorted(load.items(), key=lambda pair: pair[1], reverse=True)
    return [{'owner': name, 'count': count} for name, count in ranked]


def roles_catalog_weekly_story(rows: list[dict[str, Any]]) -> list[str]:
    story = []
    briefing = roles_catalog_briefing(rows)
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
    story.append('Role Catalog briefing is local-only and does not call an external network.')
    return story


def roles_catalog_print_pack(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        'briefing': roles_catalog_briefing(rows),
        'share': roles_catalog_status_share(rows),
        'owners': roles_catalog_owner_load(rows),
        'story': roles_catalog_weekly_story(rows),
    }


class RolesCatalogReporter:
    """Builds operator-facing packs for Role Catalog."""

    def __init__(self, rows: list[dict[str, Any]] | None = None) -> None:
        self.rows = list(rows or [])

    def refresh(self, rows: list[dict[str, Any]]) -> None:
        self.rows = list(rows)

    def briefing(self) -> dict[str, Any]:
        return roles_catalog_briefing(self.rows)

    def story(self) -> list[str]:
        return roles_catalog_weekly_story(self.rows)

    def csv(self) -> str:
        return '\n'.join(roles_catalog_csv_lines(self.rows)) + '\n'

    def pack(self) -> dict[str, Any]:
        return roles_catalog_print_pack(self.rows)


def build_roles_catalog_reporter(rows: list[dict[str, Any]]) -> RolesCatalogReporter:
    return RolesCatalogReporter(rows)

def roles_catalog_report_by_role_key(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Role Catalog by Role Key."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('role_key') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'role_key'} for label, count in ranked]


def roles_catalog_report_by_display_name(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Role Catalog by Display Name."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('display_name') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'display_name'} for label, count in ranked]


def roles_catalog_report_by_risk_level(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Role Catalog by Risk Level."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('risk_level') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'risk_level'} for label, count in ranked]


def roles_catalog_report_by_owner_team(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Role Catalog by Owner Team."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('owner_team') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'owner_team'} for label, count in ranked]


def roles_catalog_report_by_max_holders(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Role Catalog by Max Holders."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('max_holders') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'max_holders'} for label, count in ranked]


def roles_catalog_outlier_max_holders(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    values = []
    for row in rows:
        try:
            values.append(int(row.get('max_holders') or 0))
        except (TypeError, ValueError):
            values.append(0)
    if not values:
        return []
    avg = sum(values) / len(values)
    flagged = []
    for row, value in zip(rows, values):
        if value > avg * 3 and value > 0:
            flagged.append({'id': row.get('id'), 'field': 'max_holders', 'value': value, 'avg': int(avg)})
    return flagged


def roles_catalog_report_by_review_days(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Role Catalog by Review Days."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('review_days') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'review_days'} for label, count in ranked]


def roles_catalog_outlier_review_days(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    values = []
    for row in rows:
        try:
            values.append(int(row.get('review_days') or 0))
        except (TypeError, ValueError):
            values.append(0)
    if not values:
        return []
    avg = sum(values) / len(values)
    flagged = []
    for row, value in zip(rows, values):
        if value > avg * 3 and value > 0:
            flagged.append({'id': row.get('id'), 'field': 'review_days', 'value': value, 'avg': int(avg)})
    return flagged


def roles_catalog_report_by_status(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Role Catalog by Status."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('status') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'status'} for label, count in ranked]


