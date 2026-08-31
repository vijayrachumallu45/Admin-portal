"""Period reports and operator briefings for SLA Policies."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from app.domains.sla_policies.queries import sla_policies_group_status, sla_policies_health_bands, sla_policies_completeness
from app.domains.sla_policies.policies import sla_policies_risk_band, sla_policies_sla_hours, sla_policies_owner_hint

DOMAIN_TITLE = 'SLA Policies'


def sla_policies_age_days(row: dict[str, Any]) -> int:
    created = str(row.get('created_at') or '')
    try:
        parsed = datetime.fromisoformat(created.replace('Z', ''))
    except ValueError:
        return 0
    return max(0, (datetime.utcnow() - parsed).days)


def sla_policies_bucket(days: int) -> str:
    if days < 3:
        return 'fresh'
    if days < 14:
        return 'current'
    if days < 45:
        return 'aging'
    return 'legacy'


def sla_policies_line_item(row: dict[str, Any]) -> dict[str, Any]:
    days = sla_policies_age_days(row)
    return {
        'id': row.get('id'),
        'title': row.get('policy_code'),
        'status': row.get('status'),
        'days': days,
        'bucket': sla_policies_bucket(days),
        'band': sla_policies_risk_band(row),
        'owner': sla_policies_owner_hint(row),
        'sla_hours': sla_policies_sla_hours(row),
        'completeness': sla_policies_completeness(row),
        'health_score': row.get('health_score'),
    }


def sla_policies_briefing(rows: list[dict[str, Any]]) -> dict[str, Any]:
    items = [sla_policies_line_item(row) for row in rows]
    by_bucket = {'fresh': 0, 'current': 0, 'aging': 0, 'legacy': 0}
    for item in items:
        by_bucket[str(item['bucket'])] += 1
    return {
        'title': DOMAIN_TITLE,
        'generated_at': datetime.utcnow().replace(microsecond=0).isoformat() + 'Z',
        'count': len(items),
        'bands': sla_policies_health_bands(rows),
        'buckets': by_bucket,
        'headline': sla_policies_headline(rows),
        'items': items[:40],
    }


def sla_policies_headline(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return 'SLA Policies has no rows in the local ledger yet.'
    bands = sla_policies_health_bands(rows)
    critical = bands.get('critical', 0)
    if critical:
        return f'SLA Policies: {critical} critical records need a named owner this shift.'
    return f'SLA Policies: {len(rows)} records are inside the operating range.'


def sla_policies_csv_lines(rows: list[dict[str, Any]]) -> list[str]:
    header = ['id', 'title', 'status', 'days', 'bucket', 'band', 'owner', 'health_score']
    lines = [','.join(header)]
    for row in rows:
        item = sla_policies_line_item(row)
        lines.append(','.join(str(item.get(col, '')).replace(',', ' ') for col in header))
    return lines


def sla_policies_status_share(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped = sla_policies_group_status(rows)
    total = max(1, len(rows))
    share = []
    for status in ['draft', 'live', 'paused']:
        count = len(grouped.get(status, []))
        share.append({'status': status, 'count': count, 'pct': int((count / total) * 100)})
    return share


def sla_policies_owner_load(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    load: dict[str, int] = {}
    for row in rows:
        owner = sla_policies_owner_hint(row)
        load[owner] = load.get(owner, 0) + 1
    ranked = sorted(load.items(), key=lambda pair: pair[1], reverse=True)
    return [{'owner': name, 'count': count} for name, count in ranked]


def sla_policies_weekly_story(rows: list[dict[str, Any]]) -> list[str]:
    story = []
    briefing = sla_policies_briefing(rows)
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
    story.append('SLA Policies briefing is local-only and does not call an external network.')
    return story


def sla_policies_print_pack(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        'briefing': sla_policies_briefing(rows),
        'share': sla_policies_status_share(rows),
        'owners': sla_policies_owner_load(rows),
        'story': sla_policies_weekly_story(rows),
    }


class SlaPoliciesReporter:
    """Builds operator-facing packs for SLA Policies."""

    def __init__(self, rows: list[dict[str, Any]] | None = None) -> None:
        self.rows = list(rows or [])

    def refresh(self, rows: list[dict[str, Any]]) -> None:
        self.rows = list(rows)

    def briefing(self) -> dict[str, Any]:
        return sla_policies_briefing(self.rows)

    def story(self) -> list[str]:
        return sla_policies_weekly_story(self.rows)

    def csv(self) -> str:
        return '\n'.join(sla_policies_csv_lines(self.rows)) + '\n'

    def pack(self) -> dict[str, Any]:
        return sla_policies_print_pack(self.rows)


def build_sla_policies_reporter(rows: list[dict[str, Any]]) -> SlaPoliciesReporter:
    return SlaPoliciesReporter(rows)

def sla_policies_report_by_policy_code(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice SLA Policies by Policy Code."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('policy_code') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'policy_code'} for label, count in ranked]


def sla_policies_report_by_severity(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice SLA Policies by Severity."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('severity') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'severity'} for label, count in ranked]


def sla_policies_report_by_respond_minutes(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice SLA Policies by Respond Minutes."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('respond_minutes') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'respond_minutes'} for label, count in ranked]


def sla_policies_outlier_respond_minutes(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    values = []
    for row in rows:
        try:
            values.append(int(row.get('respond_minutes') or 0))
        except (TypeError, ValueError):
            values.append(0)
    if not values:
        return []
    avg = sum(values) / len(values)
    flagged = []
    for row, value in zip(rows, values):
        if value > avg * 3 and value > 0:
            flagged.append({'id': row.get('id'), 'field': 'respond_minutes', 'value': value, 'avg': int(avg)})
    return flagged


def sla_policies_report_by_restore_minutes(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice SLA Policies by Restore Minutes."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('restore_minutes') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'restore_minutes'} for label, count in ranked]


def sla_policies_outlier_restore_minutes(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    values = []
    for row in rows:
        try:
            values.append(int(row.get('restore_minutes') or 0))
        except (TypeError, ValueError):
            values.append(0)
    if not values:
        return []
    avg = sum(values) / len(values)
    flagged = []
    for row, value in zip(rows, values):
        if value > avg * 3 and value > 0:
            flagged.append({'id': row.get('id'), 'field': 'restore_minutes', 'value': value, 'avg': int(avg)})
    return flagged


def sla_policies_report_by_status(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice SLA Policies by Status."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('status') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'status'} for label, count in ranked]


