"""Read models and search helpers for Support Queue."""
from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

DOMAIN_KEY = 'support_tickets'
INDEX_FIELDS = ['ticket_no', 'subject', 'severity', 'requester', 'assignee', 'status']


def support_tickets_match(row: dict[str, Any], needle: str) -> bool:
    if not needle:
        return True
    blob = ' '.join(str(row.get(name, '')) for name in INDEX_FIELDS).lower()
    blob += ' ' + str(row.get('id') or '').lower()
    return needle.lower() in blob


def support_tickets_apply_filters(rows: list[dict[str, Any]], filters: dict[str, Any] | None) -> list[dict[str, Any]]:
    filters = filters or {}
    needle = str(filters.get('q') or '').strip()
    status = str(filters.get('status') or '').strip()
    selected = []
    for row in rows:
        if status and str(row.get('status') or '') != status:
            continue
        if not support_tickets_match(row, needle):
            continue
        selected.append(row)
    return selected


def support_tickets_sort_rows(rows: list[dict[str, Any]], field: str = 'updated_at', reverse: bool = True) -> list[dict[str, Any]]:
    def keyfn(row: dict[str, Any]) -> str:
        return str(row.get(field) or '')
    return sorted(rows, key=keyfn, reverse=reverse)


def support_tickets_page(rows: list[dict[str, Any]], offset: int = 0, limit: int = 50) -> list[dict[str, Any]]:
    if offset < 0:
        offset = 0
    if limit < 1:
        limit = 50
    if limit > 500:
        limit = 500
    return rows[offset: offset + limit]


def support_tickets_group_status(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {name: [] for name in ['new', 'open', 'pending', 'resolved', 'closed']}
    grouped['other'] = []
    for row in rows:
        status = str(row.get('status') or '')
        if status in grouped:
            grouped[status].append(row)
        else:
            grouped['other'].append(row)
    return grouped


def support_tickets_histogram(rows: list[dict[str, Any]], field: str) -> list[tuple[str, int]]:
    counter: Counter[str] = Counter()
    for row in rows:
        counter[str(row.get(field) or 'blank')] += 1
    return counter.most_common()


def support_tickets_duplicates(rows: list[dict[str, Any]], field: str = 'ticket_no') -> list[str]:
    seen: dict[str, int] = defaultdict(int)
    for row in rows:
        seen[str(row.get(field) or '')] += 1
    return [key for key, count in seen.items() if key and count > 1]


def support_tickets_missing_required(rows: list[dict[str, Any]], required: list[str]) -> list[str]:
    missing = []
    for row in rows:
        for name in required:
            if not str(row.get(name) or '').strip():
                missing.append(str(row.get('id') or '') + ':' + name)
    return missing


def support_tickets_health_bands(rows: list[dict[str, Any]]) -> dict[str, int]:
    bands = {'calm': 0, 'watch': 0, 'elevated': 0, 'critical': 0}
    for row in rows:
        score = int(row.get('health_score') or 0)
        if score >= 80:
            bands['calm'] += 1
        elif score >= 55:
            bands['watch'] += 1
        elif score >= 30:
            bands['elevated'] += 1
        else:
            bands['critical'] += 1
    return bands


def support_tickets_search_tokens(row: dict[str, Any]) -> set[str]:
    tokens: set[str] = set()
    for name in INDEX_FIELDS:
        value = str(row.get(name) or '').lower()
        for part in value.replace('/', ' ').replace('-', ' ').split():
            if len(part) >= 2:
                tokens.add(part)
    return tokens


def support_tickets_suggest(rows: list[dict[str, Any]], prefix: str, limit: int = 8) -> list[str]:
    prefix = prefix.lower().strip()
    hits: list[str] = []
    if not prefix:
        return hits
    for row in rows:
        label = str(row.get('ticket_no') or row.get('id') or '')
        if prefix in label.lower() and label not in hits:
            hits.append(label)
        if len(hits) >= limit:
            break
    return hits


def support_tickets_export_map(row: dict[str, Any]) -> dict[str, str]:
    payload = {'id': str(row.get('id') or '')}
    for name in INDEX_FIELDS:
        payload[name] = str(row.get(name) or '')
    payload['health_score'] = str(row.get('health_score') or '')
    payload['updated_at'] = str(row.get('updated_at') or '')
    return payload


def support_tickets_diff(before: dict[str, Any], after: dict[str, Any]) -> list[dict[str, str]]:
    changes = []
    keys = set(before) | set(after)
    for name in sorted(keys):
        left = str(before.get(name) or '')
        right = str(after.get(name) or '')
        if left != right:
            changes.append({'field': name, 'from': left, 'to': right})
    return changes


def support_tickets_related_status(rows: list[dict[str, Any]], status: str) -> list[dict[str, Any]]:
    return [row for row in rows if str(row.get('status') or '') == status]


def support_tickets_oldest(rows: list[dict[str, Any]], count: int = 5) -> list[dict[str, Any]]:
    ordered = support_tickets_sort_rows(rows, field='created_at', reverse=False)
    return ordered[:count]


def support_tickets_newest(rows: list[dict[str, Any]], count: int = 5) -> list[dict[str, Any]]:
    ordered = support_tickets_sort_rows(rows, field='created_at', reverse=True)
    return ordered[:count]


def support_tickets_attention_queue(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    queue = [row for row in rows if int(row.get('health_score') or 0) < 50]
    return support_tickets_sort_rows(queue, field='health_score', reverse=False)


def support_tickets_completeness(row: dict[str, Any]) -> int:
    filled = 0
    for name in INDEX_FIELDS:
        if str(row.get(name) or '').strip():
            filled += 1
    if not INDEX_FIELDS:
        return 0
    return int((filled / len(INDEX_FIELDS)) * 100)


def support_tickets_board(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        'total': len(rows),
        'bands': support_tickets_health_bands(rows),
        'attention': len(support_tickets_attention_queue(rows)),
        'newest': support_tickets_newest(rows, 3),
        'oldest': support_tickets_oldest(rows, 3),
    }

def support_tickets_values_ticket_no(rows: list[dict[str, Any]]) -> list[str]:
    """Distinct Ticket No values used in Support Queue."""
    values = []
    seen: set[str] = set()
    for row in rows:
        item = str(row.get('ticket_no') or '')
        if item and item not in seen:
            seen.add(item)
            values.append(item)
    return values


def support_tickets_filter_ticket_no(rows: list[dict[str, Any]], expected: str) -> list[dict[str, Any]]:
    wanted = str(expected or '').strip()
    if not wanted:
        return list(rows)
    return [row for row in rows if str(row.get('ticket_no') or '') == wanted]


def support_tickets_values_subject(rows: list[dict[str, Any]]) -> list[str]:
    """Distinct Subject values used in Support Queue."""
    values = []
    seen: set[str] = set()
    for row in rows:
        item = str(row.get('subject') or '')
        if item and item not in seen:
            seen.add(item)
            values.append(item)
    return values


def support_tickets_filter_subject(rows: list[dict[str, Any]], expected: str) -> list[dict[str, Any]]:
    wanted = str(expected or '').strip()
    if not wanted:
        return list(rows)
    return [row for row in rows if str(row.get('subject') or '') == wanted]


def support_tickets_values_severity(rows: list[dict[str, Any]]) -> list[str]:
    """Distinct Severity values used in Support Queue."""
    values = []
    seen: set[str] = set()
    for row in rows:
        item = str(row.get('severity') or '')
        if item and item not in seen:
            seen.add(item)
            values.append(item)
    return values


def support_tickets_filter_severity(rows: list[dict[str, Any]], expected: str) -> list[dict[str, Any]]:
    wanted = str(expected or '').strip()
    if not wanted:
        return list(rows)
    return [row for row in rows if str(row.get('severity') or '') == wanted]


def support_tickets_values_requester(rows: list[dict[str, Any]]) -> list[str]:
    """Distinct Requester values used in Support Queue."""
    values = []
    seen: set[str] = set()
    for row in rows:
        item = str(row.get('requester') or '')
        if item and item not in seen:
            seen.add(item)
            values.append(item)
    return values


def support_tickets_filter_requester(rows: list[dict[str, Any]], expected: str) -> list[dict[str, Any]]:
    wanted = str(expected or '').strip()
    if not wanted:
        return list(rows)
    return [row for row in rows if str(row.get('requester') or '') == wanted]


def support_tickets_values_assignee(rows: list[dict[str, Any]]) -> list[str]:
    """Distinct Assignee values used in Support Queue."""
    values = []
    seen: set[str] = set()
    for row in rows:
        item = str(row.get('assignee') or '')
        if item and item not in seen:
            seen.add(item)
            values.append(item)
    return values


def support_tickets_filter_assignee(rows: list[dict[str, Any]], expected: str) -> list[dict[str, Any]]:
    wanted = str(expected or '').strip()
    if not wanted:
        return list(rows)
    return [row for row in rows if str(row.get('assignee') or '') == wanted]


def support_tickets_values_status(rows: list[dict[str, Any]]) -> list[str]:
    """Distinct Status values used in Support Queue."""
    values = []
    seen: set[str] = set()
    for row in rows:
        item = str(row.get('status') or '')
        if item and item not in seen:
            seen.add(item)
            values.append(item)
    return values


def support_tickets_filter_status(rows: list[dict[str, Any]], expected: str) -> list[dict[str, Any]]:
    wanted = str(expected or '').strip()
    if not wanted:
        return list(rows)
    return [row for row in rows if str(row.get('status') or '') == wanted]


