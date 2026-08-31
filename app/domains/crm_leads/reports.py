"""Period reports and operator briefings for Lead Inbox."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from app.domains.crm_leads.queries import crm_leads_group_status, crm_leads_health_bands, crm_leads_completeness
from app.domains.crm_leads.policies import crm_leads_risk_band, crm_leads_sla_hours, crm_leads_owner_hint

DOMAIN_TITLE = 'Lead Inbox'


def crm_leads_age_days(row: dict[str, Any]) -> int:
    created = str(row.get('created_at') or '')
    try:
        parsed = datetime.fromisoformat(created.replace('Z', ''))
    except ValueError:
        return 0
    return max(0, (datetime.utcnow() - parsed).days)


def crm_leads_bucket(days: int) -> str:
    if days < 3:
        return 'fresh'
    if days < 14:
        return 'current'
    if days < 45:
        return 'aging'
    return 'legacy'


def crm_leads_line_item(row: dict[str, Any]) -> dict[str, Any]:
    days = crm_leads_age_days(row)
    return {
        'id': row.get('id'),
        'title': row.get('company'),
        'status': row.get('status'),
        'days': days,
        'bucket': crm_leads_bucket(days),
        'band': crm_leads_risk_band(row),
        'owner': crm_leads_owner_hint(row),
        'sla_hours': crm_leads_sla_hours(row),
        'completeness': crm_leads_completeness(row),
        'health_score': row.get('health_score'),
    }


def crm_leads_briefing(rows: list[dict[str, Any]]) -> dict[str, Any]:
    items = [crm_leads_line_item(row) for row in rows]
    by_bucket = {'fresh': 0, 'current': 0, 'aging': 0, 'legacy': 0}
    for item in items:
        by_bucket[str(item['bucket'])] += 1
    return {
        'title': DOMAIN_TITLE,
        'generated_at': datetime.utcnow().replace(microsecond=0).isoformat() + 'Z',
        'count': len(items),
        'bands': crm_leads_health_bands(rows),
        'buckets': by_bucket,
        'headline': crm_leads_headline(rows),
        'items': items[:40],
    }


def crm_leads_headline(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return 'Lead Inbox has no rows in the local ledger yet.'
    bands = crm_leads_health_bands(rows)
    critical = bands.get('critical', 0)
    if critical:
        return f'Lead Inbox: {critical} critical records need a named owner this shift.'
    return f'Lead Inbox: {len(rows)} records are inside the operating range.'


def crm_leads_csv_lines(rows: list[dict[str, Any]]) -> list[str]:
    header = ['id', 'title', 'status', 'days', 'bucket', 'band', 'owner', 'health_score']
    lines = [','.join(header)]
    for row in rows:
        item = crm_leads_line_item(row)
        lines.append(','.join(str(item.get(col, '')).replace(',', ' ') for col in header))
    return lines


def crm_leads_status_share(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped = crm_leads_group_status(rows)
    total = max(1, len(rows))
    share = []
    for status in ['new', 'working', 'qualified', 'disqualified']:
        count = len(grouped.get(status, []))
        share.append({'status': status, 'count': count, 'pct': int((count / total) * 100)})
    return share


def crm_leads_owner_load(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    load: dict[str, int] = {}
    for row in rows:
        owner = crm_leads_owner_hint(row)
        load[owner] = load.get(owner, 0) + 1
    ranked = sorted(load.items(), key=lambda pair: pair[1], reverse=True)
    return [{'owner': name, 'count': count} for name, count in ranked]


def crm_leads_weekly_story(rows: list[dict[str, Any]]) -> list[str]:
    story = []
    briefing = crm_leads_briefing(rows)
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
    story.append('Lead Inbox briefing is local-only and does not call an external network.')
    return story


def crm_leads_print_pack(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        'briefing': crm_leads_briefing(rows),
        'share': crm_leads_status_share(rows),
        'owners': crm_leads_owner_load(rows),
        'story': crm_leads_weekly_story(rows),
    }


class CrmLeadsReporter:
    """Builds operator-facing packs for Lead Inbox."""

    def __init__(self, rows: list[dict[str, Any]] | None = None) -> None:
        self.rows = list(rows or [])

    def refresh(self, rows: list[dict[str, Any]]) -> None:
        self.rows = list(rows)

    def briefing(self) -> dict[str, Any]:
        return crm_leads_briefing(self.rows)

    def story(self) -> list[str]:
        return crm_leads_weekly_story(self.rows)

    def csv(self) -> str:
        return '\n'.join(crm_leads_csv_lines(self.rows)) + '\n'

    def pack(self) -> dict[str, Any]:
        return crm_leads_print_pack(self.rows)


def build_crm_leads_reporter(rows: list[dict[str, Any]]) -> CrmLeadsReporter:
    return CrmLeadsReporter(rows)

def crm_leads_report_by_company(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Lead Inbox by Company."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('company') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'company'} for label, count in ranked]


def crm_leads_report_by_contact(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Lead Inbox by Contact."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('contact') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'contact'} for label, count in ranked]


def crm_leads_report_by_source(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Lead Inbox by Source."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('source') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'source'} for label, count in ranked]


def crm_leads_report_by_score(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Lead Inbox by Score."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('score') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'score'} for label, count in ranked]


def crm_leads_outlier_score(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    values = []
    for row in rows:
        try:
            values.append(int(row.get('score') or 0))
        except (TypeError, ValueError):
            values.append(0)
    if not values:
        return []
    avg = sum(values) / len(values)
    flagged = []
    for row, value in zip(rows, values):
        if value > avg * 3 and value > 0:
            flagged.append({'id': row.get('id'), 'field': 'score', 'value': value, 'avg': int(avg)})
    return flagged


def crm_leads_report_by_owner(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Lead Inbox by Owner."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('owner') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'owner'} for label, count in ranked]


def crm_leads_report_by_status(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Lead Inbox by Status."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('status') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'status'} for label, count in ranked]


