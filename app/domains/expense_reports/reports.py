"""Period reports and operator briefings for Expense Reports."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from app.domains.expense_reports.queries import expense_reports_group_status, expense_reports_health_bands, expense_reports_completeness
from app.domains.expense_reports.policies import expense_reports_risk_band, expense_reports_sla_hours, expense_reports_owner_hint

DOMAIN_TITLE = 'Expense Reports'


def expense_reports_age_days(row: dict[str, Any]) -> int:
    created = str(row.get('created_at') or '')
    try:
        parsed = datetime.fromisoformat(created.replace('Z', ''))
    except ValueError:
        return 0
    return max(0, (datetime.utcnow() - parsed).days)


def expense_reports_bucket(days: int) -> str:
    if days < 3:
        return 'fresh'
    if days < 14:
        return 'current'
    if days < 45:
        return 'aging'
    return 'legacy'


def expense_reports_line_item(row: dict[str, Any]) -> dict[str, Any]:
    days = expense_reports_age_days(row)
    return {
        'id': row.get('id'),
        'title': row.get('report_no'),
        'status': row.get('status'),
        'days': days,
        'bucket': expense_reports_bucket(days),
        'band': expense_reports_risk_band(row),
        'owner': expense_reports_owner_hint(row),
        'sla_hours': expense_reports_sla_hours(row),
        'completeness': expense_reports_completeness(row),
        'health_score': row.get('health_score'),
    }


def expense_reports_briefing(rows: list[dict[str, Any]]) -> dict[str, Any]:
    items = [expense_reports_line_item(row) for row in rows]
    by_bucket = {'fresh': 0, 'current': 0, 'aging': 0, 'legacy': 0}
    for item in items:
        by_bucket[str(item['bucket'])] += 1
    return {
        'title': DOMAIN_TITLE,
        'generated_at': datetime.utcnow().replace(microsecond=0).isoformat() + 'Z',
        'count': len(items),
        'bands': expense_reports_health_bands(rows),
        'buckets': by_bucket,
        'headline': expense_reports_headline(rows),
        'items': items[:40],
    }


def expense_reports_headline(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return 'Expense Reports has no rows in the local ledger yet.'
    bands = expense_reports_health_bands(rows)
    critical = bands.get('critical', 0)
    if critical:
        return f'Expense Reports: {critical} critical records need a named owner this shift.'
    return f'Expense Reports: {len(rows)} records are inside the operating range.'


def expense_reports_csv_lines(rows: list[dict[str, Any]]) -> list[str]:
    header = ['id', 'title', 'status', 'days', 'bucket', 'band', 'owner', 'health_score']
    lines = [','.join(header)]
    for row in rows:
        item = expense_reports_line_item(row)
        lines.append(','.join(str(item.get(col, '')).replace(',', ' ') for col in header))
    return lines


def expense_reports_status_share(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped = expense_reports_group_status(rows)
    total = max(1, len(rows))
    share = []
    for status in ['draft', 'submitted', 'approved', 'paid', 'rejected']:
        count = len(grouped.get(status, []))
        share.append({'status': status, 'count': count, 'pct': int((count / total) * 100)})
    return share


def expense_reports_owner_load(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    load: dict[str, int] = {}
    for row in rows:
        owner = expense_reports_owner_hint(row)
        load[owner] = load.get(owner, 0) + 1
    ranked = sorted(load.items(), key=lambda pair: pair[1], reverse=True)
    return [{'owner': name, 'count': count} for name, count in ranked]


def expense_reports_weekly_story(rows: list[dict[str, Any]]) -> list[str]:
    story = []
    briefing = expense_reports_briefing(rows)
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
    story.append('Expense Reports briefing is local-only and does not call an external network.')
    return story


def expense_reports_print_pack(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        'briefing': expense_reports_briefing(rows),
        'share': expense_reports_status_share(rows),
        'owners': expense_reports_owner_load(rows),
        'story': expense_reports_weekly_story(rows),
    }


class ExpenseReportsReporter:
    """Builds operator-facing packs for Expense Reports."""

    def __init__(self, rows: list[dict[str, Any]] | None = None) -> None:
        self.rows = list(rows or [])

    def refresh(self, rows: list[dict[str, Any]]) -> None:
        self.rows = list(rows)

    def briefing(self) -> dict[str, Any]:
        return expense_reports_briefing(self.rows)

    def story(self) -> list[str]:
        return expense_reports_weekly_story(self.rows)

    def csv(self) -> str:
        return '\n'.join(expense_reports_csv_lines(self.rows)) + '\n'

    def pack(self) -> dict[str, Any]:
        return expense_reports_print_pack(self.rows)


def build_expense_reports_reporter(rows: list[dict[str, Any]]) -> ExpenseReportsReporter:
    return ExpenseReportsReporter(rows)

def expense_reports_report_by_report_no(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Expense Reports by Report No."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('report_no') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'report_no'} for label, count in ranked]


def expense_reports_report_by_employee_no(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Expense Reports by Employee No."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('employee_no') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'employee_no'} for label, count in ranked]


def expense_reports_report_by_amount_cents(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Expense Reports by Amount Cents."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('amount_cents') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'amount_cents'} for label, count in ranked]


def expense_reports_outlier_amount_cents(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    values = []
    for row in rows:
        try:
            values.append(int(row.get('amount_cents') or 0))
        except (TypeError, ValueError):
            values.append(0)
    if not values:
        return []
    avg = sum(values) / len(values)
    flagged = []
    for row, value in zip(rows, values):
        if value > avg * 3 and value > 0:
            flagged.append({'id': row.get('id'), 'field': 'amount_cents', 'value': value, 'avg': int(avg)})
    return flagged


def expense_reports_report_by_cost_center(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Expense Reports by Cost Center."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('cost_center') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'cost_center'} for label, count in ranked]


def expense_reports_report_by_submitted_on(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Expense Reports by Submitted On."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('submitted_on') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'submitted_on'} for label, count in ranked]


def expense_reports_report_by_status(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Expense Reports by Status."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('status') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'status'} for label, count in ranked]


