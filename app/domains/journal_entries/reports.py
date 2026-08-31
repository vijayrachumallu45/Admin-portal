"""Period reports and operator briefings for Journal Entries."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from app.domains.journal_entries.queries import journal_entries_group_status, journal_entries_health_bands, journal_entries_completeness
from app.domains.journal_entries.policies import journal_entries_risk_band, journal_entries_sla_hours, journal_entries_owner_hint

DOMAIN_TITLE = 'Journal Entries'


def journal_entries_age_days(row: dict[str, Any]) -> int:
    created = str(row.get('created_at') or '')
    try:
        parsed = datetime.fromisoformat(created.replace('Z', ''))
    except ValueError:
        return 0
    return max(0, (datetime.utcnow() - parsed).days)


def journal_entries_bucket(days: int) -> str:
    if days < 3:
        return 'fresh'
    if days < 14:
        return 'current'
    if days < 45:
        return 'aging'
    return 'legacy'


def journal_entries_line_item(row: dict[str, Any]) -> dict[str, Any]:
    days = journal_entries_age_days(row)
    return {
        'id': row.get('id'),
        'title': row.get('entry_no'),
        'status': row.get('status'),
        'days': days,
        'bucket': journal_entries_bucket(days),
        'band': journal_entries_risk_band(row),
        'owner': journal_entries_owner_hint(row),
        'sla_hours': journal_entries_sla_hours(row),
        'completeness': journal_entries_completeness(row),
        'health_score': row.get('health_score'),
    }


def journal_entries_briefing(rows: list[dict[str, Any]]) -> dict[str, Any]:
    items = [journal_entries_line_item(row) for row in rows]
    by_bucket = {'fresh': 0, 'current': 0, 'aging': 0, 'legacy': 0}
    for item in items:
        by_bucket[str(item['bucket'])] += 1
    return {
        'title': DOMAIN_TITLE,
        'generated_at': datetime.utcnow().replace(microsecond=0).isoformat() + 'Z',
        'count': len(items),
        'bands': journal_entries_health_bands(rows),
        'buckets': by_bucket,
        'headline': journal_entries_headline(rows),
        'items': items[:40],
    }


def journal_entries_headline(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return 'Journal Entries has no rows in the local ledger yet.'
    bands = journal_entries_health_bands(rows)
    critical = bands.get('critical', 0)
    if critical:
        return f'Journal Entries: {critical} critical records need a named owner this shift.'
    return f'Journal Entries: {len(rows)} records are inside the operating range.'


def journal_entries_csv_lines(rows: list[dict[str, Any]]) -> list[str]:
    header = ['id', 'title', 'status', 'days', 'bucket', 'band', 'owner', 'health_score']
    lines = [','.join(header)]
    for row in rows:
        item = journal_entries_line_item(row)
        lines.append(','.join(str(item.get(col, '')).replace(',', ' ') for col in header))
    return lines


def journal_entries_status_share(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped = journal_entries_group_status(rows)
    total = max(1, len(rows))
    share = []
    for status in ['draft', 'posted', 'reversed']:
        count = len(grouped.get(status, []))
        share.append({'status': status, 'count': count, 'pct': int((count / total) * 100)})
    return share


def journal_entries_owner_load(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    load: dict[str, int] = {}
    for row in rows:
        owner = journal_entries_owner_hint(row)
        load[owner] = load.get(owner, 0) + 1
    ranked = sorted(load.items(), key=lambda pair: pair[1], reverse=True)
    return [{'owner': name, 'count': count} for name, count in ranked]


def journal_entries_weekly_story(rows: list[dict[str, Any]]) -> list[str]:
    story = []
    briefing = journal_entries_briefing(rows)
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
    story.append('Journal Entries briefing is local-only and does not call an external network.')
    return story


def journal_entries_print_pack(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        'briefing': journal_entries_briefing(rows),
        'share': journal_entries_status_share(rows),
        'owners': journal_entries_owner_load(rows),
        'story': journal_entries_weekly_story(rows),
    }


class JournalEntriesReporter:
    """Builds operator-facing packs for Journal Entries."""

    def __init__(self, rows: list[dict[str, Any]] | None = None) -> None:
        self.rows = list(rows or [])

    def refresh(self, rows: list[dict[str, Any]]) -> None:
        self.rows = list(rows)

    def briefing(self) -> dict[str, Any]:
        return journal_entries_briefing(self.rows)

    def story(self) -> list[str]:
        return journal_entries_weekly_story(self.rows)

    def csv(self) -> str:
        return '\n'.join(journal_entries_csv_lines(self.rows)) + '\n'

    def pack(self) -> dict[str, Any]:
        return journal_entries_print_pack(self.rows)


def build_journal_entries_reporter(rows: list[dict[str, Any]]) -> JournalEntriesReporter:
    return JournalEntriesReporter(rows)

def journal_entries_report_by_entry_no(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Journal Entries by Entry No."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('entry_no') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'entry_no'} for label, count in ranked]


def journal_entries_report_by_memo(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Journal Entries by Memo."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('memo') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'memo'} for label, count in ranked]


def journal_entries_report_by_amount_cents(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Journal Entries by Amount Cents."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('amount_cents') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'amount_cents'} for label, count in ranked]


def journal_entries_outlier_amount_cents(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
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


def journal_entries_report_by_posted_on(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Journal Entries by Posted On."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('posted_on') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'posted_on'} for label, count in ranked]


def journal_entries_report_by_status(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Journal Entries by Status."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('status') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'status'} for label, count in ranked]


