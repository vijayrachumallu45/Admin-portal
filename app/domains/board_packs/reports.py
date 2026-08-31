"""Period reports and operator briefings for Board Packs."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from app.domains.board_packs.queries import board_packs_group_status, board_packs_health_bands, board_packs_completeness
from app.domains.board_packs.policies import board_packs_risk_band, board_packs_sla_hours, board_packs_owner_hint

DOMAIN_TITLE = 'Board Packs'


def board_packs_age_days(row: dict[str, Any]) -> int:
    created = str(row.get('created_at') or '')
    try:
        parsed = datetime.fromisoformat(created.replace('Z', ''))
    except ValueError:
        return 0
    return max(0, (datetime.utcnow() - parsed).days)


def board_packs_bucket(days: int) -> str:
    if days < 3:
        return 'fresh'
    if days < 14:
        return 'current'
    if days < 45:
        return 'aging'
    return 'legacy'


def board_packs_line_item(row: dict[str, Any]) -> dict[str, Any]:
    days = board_packs_age_days(row)
    return {
        'id': row.get('id'),
        'title': row.get('pack_code'),
        'status': row.get('status'),
        'days': days,
        'bucket': board_packs_bucket(days),
        'band': board_packs_risk_band(row),
        'owner': board_packs_owner_hint(row),
        'sla_hours': board_packs_sla_hours(row),
        'completeness': board_packs_completeness(row),
        'health_score': row.get('health_score'),
    }


def board_packs_briefing(rows: list[dict[str, Any]]) -> dict[str, Any]:
    items = [board_packs_line_item(row) for row in rows]
    by_bucket = {'fresh': 0, 'current': 0, 'aging': 0, 'legacy': 0}
    for item in items:
        by_bucket[str(item['bucket'])] += 1
    return {
        'title': DOMAIN_TITLE,
        'generated_at': datetime.utcnow().replace(microsecond=0).isoformat() + 'Z',
        'count': len(items),
        'bands': board_packs_health_bands(rows),
        'buckets': by_bucket,
        'headline': board_packs_headline(rows),
        'items': items[:40],
    }


def board_packs_headline(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return 'Board Packs has no rows in the local ledger yet.'
    bands = board_packs_health_bands(rows)
    critical = bands.get('critical', 0)
    if critical:
        return f'Board Packs: {critical} critical records need a named owner this shift.'
    return f'Board Packs: {len(rows)} records are inside the operating range.'


def board_packs_csv_lines(rows: list[dict[str, Any]]) -> list[str]:
    header = ['id', 'title', 'status', 'days', 'bucket', 'band', 'owner', 'health_score']
    lines = [','.join(header)]
    for row in rows:
        item = board_packs_line_item(row)
        lines.append(','.join(str(item.get(col, '')).replace(',', ' ') for col in header))
    return lines


def board_packs_status_share(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped = board_packs_group_status(rows)
    total = max(1, len(rows))
    share = []
    for status in ['collecting', 'frozen', 'sent']:
        count = len(grouped.get(status, []))
        share.append({'status': status, 'count': count, 'pct': int((count / total) * 100)})
    return share


def board_packs_owner_load(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    load: dict[str, int] = {}
    for row in rows:
        owner = board_packs_owner_hint(row)
        load[owner] = load.get(owner, 0) + 1
    ranked = sorted(load.items(), key=lambda pair: pair[1], reverse=True)
    return [{'owner': name, 'count': count} for name, count in ranked]


def board_packs_weekly_story(rows: list[dict[str, Any]]) -> list[str]:
    story = []
    briefing = board_packs_briefing(rows)
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
    story.append('Board Packs briefing is local-only and does not call an external network.')
    return story


def board_packs_print_pack(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        'briefing': board_packs_briefing(rows),
        'share': board_packs_status_share(rows),
        'owners': board_packs_owner_load(rows),
        'story': board_packs_weekly_story(rows),
    }


class BoardPacksReporter:
    """Builds operator-facing packs for Board Packs."""

    def __init__(self, rows: list[dict[str, Any]] | None = None) -> None:
        self.rows = list(rows or [])

    def refresh(self, rows: list[dict[str, Any]]) -> None:
        self.rows = list(rows)

    def briefing(self) -> dict[str, Any]:
        return board_packs_briefing(self.rows)

    def story(self) -> list[str]:
        return board_packs_weekly_story(self.rows)

    def csv(self) -> str:
        return '\n'.join(board_packs_csv_lines(self.rows)) + '\n'

    def pack(self) -> dict[str, Any]:
        return board_packs_print_pack(self.rows)


def build_board_packs_reporter(rows: list[dict[str, Any]]) -> BoardPacksReporter:
    return BoardPacksReporter(rows)

def board_packs_report_by_pack_code(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Board Packs by Pack Code."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('pack_code') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'pack_code'} for label, count in ranked]


def board_packs_report_by_meeting_on(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Board Packs by Meeting On."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('meeting_on') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'meeting_on'} for label, count in ranked]


def board_packs_report_by_owner(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Board Packs by Owner."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('owner') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'owner'} for label, count in ranked]


def board_packs_report_by_page_count(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Board Packs by Page Count."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('page_count') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'page_count'} for label, count in ranked]


def board_packs_outlier_page_count(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    values = []
    for row in rows:
        try:
            values.append(int(row.get('page_count') or 0))
        except (TypeError, ValueError):
            values.append(0)
    if not values:
        return []
    avg = sum(values) / len(values)
    flagged = []
    for row, value in zip(rows, values):
        if value > avg * 3 and value > 0:
            flagged.append({'id': row.get('id'), 'field': 'page_count', 'value': value, 'avg': int(avg)})
    return flagged


def board_packs_report_by_status(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Slice Board Packs by Status."""
    buckets: dict[str, int] = {}
    for row in rows:
        label = str(row.get('status') or 'blank')
        buckets[label] = buckets.get(label, 0) + 1
    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)
    return [{'label': label, 'count': count, 'field': 'status'} for label, count in ranked]


