"""Period reports and operator briefings for HR Employees."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from app.domains.employees.queries import employees_group_status, employees_health_bands, employees_completeness
from app.domains.employees.policies import employees_risk_band, employees_sla_hours, employees_owner_hint

DOMAIN_TITLE = 'HR Employees'


def employees_age_days(row: dict[str, Any]) -> int:
    created = str(row.get('created_at') or '')
    try:
        parsed = datetime.fromisoformat(created.replace('Z', ''))
    except ValueError:
        return 0
    return max(0, (datetime.utcnow() - parsed).days)


def employees_bucket(days: int) -> str:
    if days < 3:
        return 'fresh'
    if days < 14:
        return 'current'
    if days < 45:
        return 'aging'
    return 'legacy'


def employees_line_item(row: dict[str, Any]) -> dict[str, Any]:
    days = employees_age_days(row)
    return {
        'id': row.get('id'),
        'title': row.get('employee_no'),
        'status': row.get('status'),
        'days': days,
        'bucket': employees_bucket(days),
        'band': employees_risk_band(row),
        'owner': employees_owner_hint(row),
        'sla_hours': employees_sla_hours(row),
        'completeness': employees_completeness(row),
        'health_score': row.get('health_score'),
    }


def employees_briefing(rows: list[dict[str, Any]]) -> dict[str, Any]:
    items = [employees_line_item(row) for row in rows]
    by_bucket = {'fresh': 0, 'current': 0, 'aging': 0, 'legacy': 0}
    for item in items:
        by_bucket[str(item['bucket'])] += 1
    return {
        'title': DOMAIN_TITLE,
        'generated_at': datetime.utcnow().replace(microsecond=0).isoformat() + 'Z',
        'count': len(items),
        'bands': employees_health_bands(rows),
        'buckets': by_bucket,
        'headline': employees_headline(rows),
        'items': items[:40],
    }


def employees_headline(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return 'HR Employees has no rows in the local ledger yet.'
    bands = employees_health_bands(rows)
    critical = bands.get('critical', 0)
    if critical:
        return f'HR Employees: {critical} critical records need a named owner this shift.'
    return f'HR Employees: {len(rows)} records are inside the operating range.'


def employees_csv_lines(rows: list[dict[str, Any]]) -> list[str]:
    header = ['id', 'title', 'status', 'days', 'bucket', 'band', 'owner', 'health_score']
    lines = [','.join(header)]
    for row in rows:
        item = employees_line_item(row)
        lines.append(','.join(str(item.get(col, '')).replace(',', ' ') for col in header))
    return lines


def employees_status_share(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped = employees_group_status(rows)
    total = max(1, len(rows))
    share = []
    for status in ['active', 'leave', 'terminated']:
        count = len(grouped.get(status, []))
        share.append({'status': status, 'count': count, 'pct': int((count / total) * 100)})
    return share


def employees_owner_load(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    load: dict[str, int] = {}
    for row in rows:
        owner = employees_owner_hint(row)
        load[owner] = load.get(owner, 0) + 1
    ranked = sorted(load.items(), key=lambda pair: pair[1], reverse=True)
    return [{'owner': name, 'count': count} for name, count in ranked]


def employees_weekly_story(rows: list[dict[str, Any]]) -> list[str]:
    story = []
    briefing = employees_briefing(rows)
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
    story.append('HR Employees briefing is local-only and does not call an external network.')
    return story


def employees_print_pack(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        'briefing': employees_briefing(rows),
        'share': employees_status_share(rows),
        'owners': employees_owner_load(rows),
        'story': employees_weekly_story(rows),
    }


class EmployeesReporter:
    """Builds operator-facing packs for HR Employees."""

    def __init__(self, rows: list[dict[str, Any]] | None = None) -> None:
        self.rows = list(rows or [])

    def refresh(self, rows: list[dict[str, Any]]) -> None:
        self.rows = list(rows)

    def briefing(self) -> dict[str, Any]:
        return employees_briefing(self.rows)

    def story(self) -> list[str]:
        return employees_weekly_story(self.rows)

    def csv(self) -> str:
        return '\n'.join(employees_csv_lines(self.rows)) + '\n'

    def pack(self) -> dict[str, Any]:
        return employees_print_pack(self.rows)


def build_employees_reporter(rows: list[dict[str, Any]]) -> EmployeesReporter:
    return EmployeesReporter(rows)

def employees_report_by_employee_no(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice HR Employees by Employee No."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('employee_no') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'employee_no'} for label, count in ranked]


def employees_report_by_full_name(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice HR Employees by Full Name."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('full_name') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'full_name'} for label, count in ranked]


def employees_report_by_cost_center(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice HR Employees by Cost Center."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('cost_center') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'cost_center'} for label, count in ranked]


def employees_report_by_hire_on(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice HR Employees by Hire On."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('hire_on') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'hire_on'} for label, count in ranked]


def employees_report_by_fte_bps(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice HR Employees by Fte Bps."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('fte_bps') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'fte_bps'} for label, count in ranked]


def employees_outlier_fte_bps(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    values = []
    for row in rows:
        try:
            values.append(int(row.get('fte_bps') or 0))
        except (TypeError, ValueError):
            values.append(0)
    if not values:
        return []
    avg = sum(values) / len(values)
    flagged = []
    for row, value in zip(rows, values):
        if value > avg * 3 and value > 0:
            flagged.append({'id': row.get('id'), 'field': 'fte_bps', 'value': value, 'avg': int(avg)})
    return flagged


def employees_report_by_status(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice HR Employees by Status."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('status') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'status'} for label, count in ranked]


