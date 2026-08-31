"""Extra operational layers per domain: policy, query, report, and service modules."""
from __future__ import annotations

from typing import Any


def field_label(name: str) -> str:
    return name.replace("_", " ").title()


def emit_policies(domain: dict[str, Any]) -> str:
    key = domain["key"]
    title = domain["title"]
    statuses = domain["statuses"]
    fields = domain["fields"]
    accent = domain["accent"]
    lines: list[str] = [
        f'"""Policy engine for {title}.',
        "",
        f"{domain['desc']}",
        "Operators use these guards before a write is allowed to settle.",
        '"""',
        "from __future__ import annotations",
        "",
        "from datetime import date, datetime",
        "from typing import Any",
        "",
        f"DOMAIN_KEY = {key!r}",
        f"DOMAIN_TITLE = {title!r}",
        f"ACCENT = {accent!r}",
        f"STATUSES = {statuses!r}",
        f"SOFT_HOLD_STATUSES = {statuses[-2:]!r}",
        "",
        "",
        "def _as_int(value: Any, default: int = 0) -> int:",
        "    try:",
        "        if value in (None, ''):",
        "            return default",
        "        return int(value)",
        "    except (TypeError, ValueError):",
        "        return default",
        "",
        "",
        f"def {key}_policy_version() -> str:",
        f"    return '{key}.policy.4'",
        "",
        "",
        f"def {key}_is_terminal(status: str) -> bool:",
        f"    return status == {statuses[-1]!r}",
        "",
        "",
        f"def {key}_requires_dual_control(row: dict[str, Any]) -> bool:",
        "    status = str(row.get('status') or '')",
        "    if status in SOFT_HOLD_STATUSES:",
        "        return True",
        "    score = _as_int(row.get('health_score'))",
        "    return score < 35",
        "",
        "",
        f"class {''.join(p.title() for p in key.split('_'))}Policy:",
        f'    """Named checks that finance, people, and platform leads can quote."""',
        "",
        "    def __init__(self) -> None:",
        f"        self.domain = {key!r}",
        "        self.violations: list[str] = []",
        "",
        "    def reset(self) -> None:",
        "        self.violations = []",
        "",
        "    def collect(self, row: dict[str, Any]) -> list[str]:",
        "        self.reset()",
        "        self.check_status(row)",
        "        self.check_identity(row)",
        "        self.check_freshness(row)",
        "        self.check_numeric_bounds(row)",
        "        self.check_text_hygiene(row)",
        "        self.check_lifecycle(row)",
        "        return list(self.violations)",
        "",
        "    def check_status(self, row: dict[str, Any]) -> None:",
        "        status = str(row.get('status') or '')",
        "        if not status:",
        f"            self.violations.append('{title}: status is missing.')",
        "            return",
        "        if status not in STATUSES:",
        f"            self.violations.append('{title}: status is outside the published ladder.')",
        "",
        "    def check_identity(self, row: dict[str, Any]) -> None:",
        "        record_id = str(row.get('id') or '')",
        "        if record_id and ' ' in record_id:",
        f"            self.violations.append('{title}: record id cannot contain spaces.')",
        "",
        "    def check_freshness(self, row: dict[str, Any]) -> None:",
        "        stamp = str(row.get('updated_at') or '')",
        "        if not stamp:",
        "            return",
        "        try:",
        "            parsed = datetime.fromisoformat(stamp.replace('Z', ''))",
        "        except ValueError:",
        f"            self.violations.append('{title}: updated_at is not parseable.')",
        "            return",
        "        age = (datetime.utcnow() - parsed).days",
        "        if age > 800:",
        f"            self.violations.append('{title}: record is older than the archive window.')",
        "",
        "    def check_numeric_bounds(self, row: dict[str, Any]) -> None:",
        "        for name, value in row.items():",
        "            if not name.endswith('_cents') and name not in (",
        "                'health_score',",
        "                'seats',",
        "                'minutes',",
        "                'days',",
        "                'percent',",
        "                'score',",
        "                'cap',",
        "                'headcount',",
        "            ):",
        "                continue",
        "            number = _as_int(value, default=-1)",
        "            if number < 0:",
        f"                self.violations.append('{title}: ' + name + ' is out of bounds.')",
        "",
        "    def check_text_hygiene(self, row: dict[str, Any]) -> None:",
        "        for name, value in row.items():",
        "            if not isinstance(value, str):",
        "                continue",
        "            if '\\x00' in value:",
        f"                self.violations.append('{title}: ' + name + ' contains a null byte.')",
        "            if value != value.strip() and name not in ('comment',):",
        f"                self.violations.append('{title}: ' + name + ' has surrounding whitespace.')",
        "",
        "    def check_lifecycle(self, row: dict[str, Any]) -> None:",
        "        status = str(row.get('status') or '')",
        f"        if status == {statuses[-1]!r} and _as_int(row.get('health_score')) > 90:",
        f"            self.violations.append('{title}: terminal status with a high health score needs a note.')",
        "",
        "    def allow_write(self, row: dict[str, Any]) -> bool:",
        "        return not self.collect(row)",
        "",
        "",
        f"policy = {''.join(p.title() for p in key.split('_'))}Policy()",
        "",
        "",
        f"def {key}_gate_create(payload: dict[str, Any]) -> list[str]:",
        "    return policy.collect(payload)",
        "",
        "",
        f"def {key}_gate_transition(current: str, nxt: str) -> list[str]:",
        "    errors: list[str] = []",
        "    if nxt not in STATUSES:",
        f"        errors.append('{title} cannot move to an unknown status.')",
        f"    if current == {statuses[-1]!r} and nxt != current:",
        "        if nxt not in STATUSES[:1]:",
        f"            errors.append('{title} is sealed; only a reopen to the first status is modeled.')",
        "    return errors",
        "",
        "",
        f"def {key}_risk_band(row: dict[str, Any]) -> str:",
        "    score = _as_int(row.get('health_score'))",
        "    if score >= 80:",
        "        return 'calm'",
        "    if score >= 55:",
        "        return 'watch'",
        "    if score >= 30:",
        "        return 'elevated'",
        "    return 'critical'",
        "",
        "",
        f"def {key}_owner_hint(row: dict[str, Any]) -> str:",
        "    for candidate in ('owner', 'assignee', 'steward', 'manager', 'legal_owner', 'processor', 'host_name', 'sponsor'):",
        "        value = str(row.get(candidate) or '').strip()",
        "        if value:",
        "            return value",
        f"    return 'unassigned-{key}'",
        "",
        "",
        f"def {key}_sla_hours(row: dict[str, Any]) -> int:",
        f"    band = {key}_risk_band(row)",
        "    mapping = {'calm': 72, 'watch': 36, 'elevated': 12, 'critical': 4}",
        "    return mapping[band]",
        "",
        "",
        f"def {key}_escalation_copy(row: dict[str, Any]) -> str:",
        f"    band = {key}_risk_band(row)",
        f"    owner = {key}_owner_hint(row)",
        f"    hours = {key}_sla_hours(row)",
        f"    return DOMAIN_TITLE + ' ' + band + ' item assigned to ' + owner + ' must move within ' + str(hours) + ' hours.'",
        "",
        "",
        f"PLAYBOOK_{key.upper()} = [",
    ]
    verbs = [
        "Triage",
        "Confirm identifiers",
        "Check policy exceptions",
        "Notify the owner",
        "Capture evidence",
        "Propose a next status",
        "Record the decision",
        "Close the loop with finance",
        "File the audit crumb",
        "Schedule the next review",
    ]
    for index, verb in enumerate(verbs):
        lines.append(
            f"    {{'step': {index + 1}, 'title': {verb!r}, 'domain': {key!r}, 'hint': '{verb} for {title} before the shift ends.'}},"
        )
    lines += [
        "]",
        "",
        "",
        f"def {key}_playbook() -> list[dict[str, Any]]:",
        f"    return list(PLAYBOOK_{key.upper()})",
        "",
        "",
        f"def {key}_exception_needed(row: dict[str, Any]) -> bool:",
        f"    return {key}_risk_band(row) in ('elevated', 'critical')",
        "",
        "",
        f"def {key}_freeze_window(row: dict[str, Any]) -> bool:",
        "    status = str(row.get('status') or '')",
        f"    return status in {statuses[-2:]!r} and date.today().weekday() >= 5",
        "",
        "",
        f"def {key}_summary_line(row: dict[str, Any]) -> str:",
        "    ident = str(row.get('id') or 'new')",
        "    status = str(row.get('status') or 'n/a')",
        f"    band = {key}_risk_band(row)",
        "    return DOMAIN_TITLE + ' ' + ident + ' is ' + status + ' (' + band + ').'",
        "",
    ]
    for name, typ, req in fields:
        label = field_label(name)
        lines += [
            f"def {key}_check_{name}(value: Any) -> list[str]:",
            f'    """Field policy for {label} inside {title}."""',
            "    notes: list[str] = []",
            f"    if value in (None, '') and {req!r}:",
            f"        notes.append('{label} is required on {title}.')",
            "        return notes",
            f"    if {typ!r} == 'int':",
            "        number = _as_int(value, default=0)",
            f"        if {req!r} and number == 0:",
            f"            notes.append('{label} is zero; confirm the {title} case.')",
            "        if number > 9_000_000_000:",
            f"            notes.append('{label} exceeds the {title} ceiling.')",
            "        return notes",
            f"    if {typ!r} == 'date':",
            "        text = str(value or '').strip()",
            "        if text:",
            "            try:",
            "                date.fromisoformat(text)",
            "            except ValueError:",
            f"                notes.append('{label} must be YYYY-MM-DD for {title}.')",
            "        return notes",
            "    text = str(value or '').strip()",
            "    if len(text) > 240:",
            f"        notes.append('{label} is longer than the {title} ledger allows.')",
            f"    if text.lower() in ('n/a', 'todo', 'tbd') and {req!r}:",
            f"        notes.append('{label} placeholder values are not allowed on {title}.')",
            "    return notes",
            "",
            "",
            f"def {key}_normalize_{name}(value: Any) -> Any:",
            f"    if {typ!r} == 'int':",
            "        return _as_int(value)",
            f"    if {typ!r} == 'date':",
            "        return str(value or '').strip()",
            "    return str(value or '').strip()",
            "",
            "",
            f"def {key}_describe_{name}() -> str:",
            f"    required = 'required' if {req!r} else 'optional'",
            f"    return '{label} is a ' + required + ' {typ} field on {title} ({key}).'",
            "",
            "",
        ]
    lines += [
        f"FIELD_CHECKS_{key.upper()} = {{",
    ]
    for name, _typ, _req in fields:
        lines.append(f"    {name!r}: {key}_check_{name},")
    lines += [
        "}",
        "",
        "",
        f"def {key}_run_field_checks(row: dict[str, Any]) -> list[str]:",
        "    found: list[str] = []",
        f"    for name, checker in FIELD_CHECKS_{key.upper()}.items():",
        "        found.extend(checker(row.get(name)))",
        "    return found",
        "",
        "",
        f"def {key}_policy_card(row: dict[str, Any]) -> dict[str, Any]:",
        "    return {",
        "        'domain': DOMAIN_KEY,",
        "        'title': DOMAIN_TITLE,",
        "        'band': " + f"{key}_risk_band(row),",
        "        'owner': " + f"{key}_owner_hint(row),",
        "        'sla_hours': " + f"{key}_sla_hours(row),",
        "        'exceptions': " + f"{key}_exception_needed(row),",
        "        'freeze': " + f"{key}_freeze_window(row),",
        "        'violations': policy.collect(row) + " + f"{key}_run_field_checks(row),",
        "        'summary': " + f"{key}_summary_line(row),",
        "    }",
        "",
    ]
    return "\n".join(lines) + "\n"


def emit_queries(domain: dict[str, Any]) -> str:
    key = domain["key"]
    title = domain["title"]
    fields = domain["fields"]
    statuses = domain["statuses"]
    first = fields[0][0]
    lines = [
        f'"""Read models and search helpers for {title}."""',
        "from __future__ import annotations",
        "",
        "from collections import Counter, defaultdict",
        "from typing import Any",
        "",
        f"DOMAIN_KEY = {key!r}",
        f"INDEX_FIELDS = {[n for n, _t, _r in fields]!r}",
        "",
        "",
        f"def {key}_match(row: dict[str, Any], needle: str) -> bool:",
        "    if not needle:",
        "        return True",
        "    blob = ' '.join(str(row.get(name, '')) for name in INDEX_FIELDS).lower()",
        "    blob += ' ' + str(row.get('id') or '').lower()",
        "    return needle.lower() in blob",
        "",
        "",
        f"def {key}_apply_filters(rows: list[dict[str, Any]], filters: dict[str, Any] | None) -> list[dict[str, Any]]:",
        "    filters = filters or {}",
        "    needle = str(filters.get('q') or '').strip()",
        "    status = str(filters.get('status') or '').strip()",
        "    selected = []",
        "    for row in rows:",
        "        if status and str(row.get('status') or '') != status:",
        "            continue",
        f"        if not {key}_match(row, needle):",
        "            continue",
        "        selected.append(row)",
        "    return selected",
        "",
        "",
        f"def {key}_sort_rows(rows: list[dict[str, Any]], field: str = 'updated_at', reverse: bool = True) -> list[dict[str, Any]]:",
        "    def keyfn(row: dict[str, Any]) -> str:",
        "        return str(row.get(field) or '')",
        "    return sorted(rows, key=keyfn, reverse=reverse)",
        "",
        "",
        f"def {key}_page(rows: list[dict[str, Any]], offset: int = 0, limit: int = 50) -> list[dict[str, Any]]:",
        "    if offset < 0:",
        "        offset = 0",
        "    if limit < 1:",
        "        limit = 50",
        "    if limit > 500:",
        "        limit = 500",
        "    return rows[offset: offset + limit]",
        "",
        "",
        f"def {key}_group_status(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:",
        "    grouped: dict[str, list[dict[str, Any]]] = {name: [] for name in " + f"{statuses!r}" + "}",
        "    grouped['other'] = []",
        "    for row in rows:",
        "        status = str(row.get('status') or '')",
        "        if status in grouped:",
        "            grouped[status].append(row)",
        "        else:",
        "            grouped['other'].append(row)",
        "    return grouped",
        "",
        "",
        f"def {key}_histogram(rows: list[dict[str, Any]], field: str) -> list[tuple[str, int]]:",
        "    counter: Counter[str] = Counter()",
        "    for row in rows:",
        "        counter[str(row.get(field) or 'blank')] += 1",
        "    return counter.most_common()",
        "",
        "",
        f"def {key}_duplicates(rows: list[dict[str, Any]], field: str = {first!r}) -> list[str]:",
        "    seen: dict[str, int] = defaultdict(int)",
        "    for row in rows:",
        "        seen[str(row.get(field) or '')] += 1",
        "    return [key for key, count in seen.items() if key and count > 1]",
        "",
        "",
        f"def {key}_missing_required(rows: list[dict[str, Any]], required: list[str]) -> list[str]:",
        "    missing = []",
        "    for row in rows:",
        "        for name in required:",
        "            if not str(row.get(name) or '').strip():",
        "                missing.append(str(row.get('id') or '') + ':' + name)",
        "    return missing",
        "",
        "",
        f"def {key}_health_bands(rows: list[dict[str, Any]]) -> dict[str, int]:",
        "    bands = {'calm': 0, 'watch': 0, 'elevated': 0, 'critical': 0}",
        "    for row in rows:",
        "        score = int(row.get('health_score') or 0)",
        "        if score >= 80:",
        "            bands['calm'] += 1",
        "        elif score >= 55:",
        "            bands['watch'] += 1",
        "        elif score >= 30:",
        "            bands['elevated'] += 1",
        "        else:",
        "            bands['critical'] += 1",
        "    return bands",
        "",
        "",
        f"def {key}_search_tokens(row: dict[str, Any]) -> set[str]:",
        "    tokens: set[str] = set()",
        "    for name in INDEX_FIELDS:",
        "        value = str(row.get(name) or '').lower()",
        "        for part in value.replace('/', ' ').replace('-', ' ').split():",
        "            if len(part) >= 2:",
        "                tokens.add(part)",
        "    return tokens",
        "",
        "",
        f"def {key}_suggest(rows: list[dict[str, Any]], prefix: str, limit: int = 8) -> list[str]:",
        "    prefix = prefix.lower().strip()",
        "    hits: list[str] = []",
        "    if not prefix:",
        "        return hits",
        "    for row in rows:",
        f"        label = str(row.get({first!r}) or row.get('id') or '')",
        "        if prefix in label.lower() and label not in hits:",
        "            hits.append(label)",
        "        if len(hits) >= limit:",
        "            break",
        "    return hits",
        "",
        "",
        f"def {key}_export_map(row: dict[str, Any]) -> dict[str, str]:",
        "    payload = {'id': str(row.get('id') or '')}",
        "    for name in INDEX_FIELDS:",
        "        payload[name] = str(row.get(name) or '')",
        "    payload['health_score'] = str(row.get('health_score') or '')",
        "    payload['updated_at'] = str(row.get('updated_at') or '')",
        "    return payload",
        "",
        "",
        f"def {key}_diff(before: dict[str, Any], after: dict[str, Any]) -> list[dict[str, str]]:",
        "    changes = []",
        "    keys = set(before) | set(after)",
        "    for name in sorted(keys):",
        "        left = str(before.get(name) or '')",
        "        right = str(after.get(name) or '')",
        "        if left != right:",
        "            changes.append({'field': name, 'from': left, 'to': right})",
        "    return changes",
        "",
        "",
        f"def {key}_related_status(rows: list[dict[str, Any]], status: str) -> list[dict[str, Any]]:",
        "    return [row for row in rows if str(row.get('status') or '') == status]",
        "",
        "",
        f"def {key}_oldest(rows: list[dict[str, Any]], count: int = 5) -> list[dict[str, Any]]:",
        f"    ordered = {key}_sort_rows(rows, field='created_at', reverse=False)",
        "    return ordered[:count]",
        "",
        "",
        f"def {key}_newest(rows: list[dict[str, Any]], count: int = 5) -> list[dict[str, Any]]:",
        f"    ordered = {key}_sort_rows(rows, field='created_at', reverse=True)",
        "    return ordered[:count]",
        "",
        "",
        f"def {key}_attention_queue(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:",
        "    queue = [row for row in rows if int(row.get('health_score') or 0) < 50]",
        f"    return {key}_sort_rows(queue, field='health_score', reverse=False)",
        "",
        "",
        f"def {key}_completeness(row: dict[str, Any]) -> int:",
        "    filled = 0",
        "    for name in INDEX_FIELDS:",
        "        if str(row.get(name) or '').strip():",
        "            filled += 1",
        "    if not INDEX_FIELDS:",
        "        return 0",
        "    return int((filled / len(INDEX_FIELDS)) * 100)",
        "",
        "",
        f"def {key}_board(rows: list[dict[str, Any]]) -> dict[str, Any]:",
        "    return {",
        "        'total': len(rows),",
        f"        'bands': {key}_health_bands(rows),",
        f"        'attention': len({key}_attention_queue(rows)),",
        f"        'newest': {key}_newest(rows, 3),",
        f"        'oldest': {key}_oldest(rows, 3),",
        "    }",
        "",
    ]
    for name, typ, _req in fields:
        lines += [
            f"def {key}_values_{name}(rows: list[dict[str, Any]]) -> list[str]:",
            f'    """Distinct {field_label(name)} values used in {title}."""',
            "    values = []",
            "    seen: set[str] = set()",
            "    for row in rows:",
            f"        item = str(row.get({name!r}) or '')",
            "        if item and item not in seen:",
            "            seen.add(item)",
            "            values.append(item)",
            "    return values",
            "",
            "",
            f"def {key}_filter_{name}(rows: list[dict[str, Any]], expected: str) -> list[dict[str, Any]]:",
            f"    wanted = str(expected or '').strip()",
            "    if not wanted:",
            "        return list(rows)",
            f"    return [row for row in rows if str(row.get({name!r}) or '') == wanted]",
            "",
            "",
        ]
        if typ == "int":
            lines += [
                f"def {key}_sum_{name}(rows: list[dict[str, Any]]) -> int:",
                "    total = 0",
                "    for row in rows:",
                "        try:",
                f"            total += int(row.get({name!r}) or 0)",
                "        except (TypeError, ValueError):",
                "            continue",
                "    return total",
                "",
                "",
                f"def {key}_avg_{name}(rows: list[dict[str, Any]]) -> int:",
                f"    if not rows:",
                "        return 0",
                f"    return int({key}_sum_{name}(rows) / max(1, len(rows)))",
                "",
                "",
            ]
    return "\n".join(lines) + "\n"


def emit_reports(domain: dict[str, Any]) -> str:
    key = domain["key"]
    title = domain["title"]
    statuses = domain["statuses"]
    fields = domain["fields"]
    first = fields[0][0]
    lines = [
        f'"""Period reports and operator briefings for {title}."""',
        "from __future__ import annotations",
        "",
        "from datetime import datetime",
        "from typing import Any",
        "",
        f"from app.domains.{key}.queries import {key}_group_status, {key}_health_bands, {key}_completeness",
        f"from app.domains.{key}.policies import {key}_risk_band, {key}_sla_hours, {key}_owner_hint",
        "",
        f"DOMAIN_TITLE = {title!r}",
        "",
        "",
        f"def {key}_age_days(row: dict[str, Any]) -> int:",
        "    created = str(row.get('created_at') or '')",
        "    try:",
        "        parsed = datetime.fromisoformat(created.replace('Z', ''))",
        "    except ValueError:",
        "        return 0",
        "    return max(0, (datetime.utcnow() - parsed).days)",
        "",
        "",
        f"def {key}_bucket(days: int) -> str:",
        "    if days < 3:",
        "        return 'fresh'",
        "    if days < 14:",
        "        return 'current'",
        "    if days < 45:",
        "        return 'aging'",
        "    return 'legacy'",
        "",
        "",
        f"def {key}_line_item(row: dict[str, Any]) -> dict[str, Any]:",
        f"    days = {key}_age_days(row)",
        "    return {",
        "        'id': row.get('id'),",
        f"        'title': row.get({first!r}),",
        "        'status': row.get('status'),",
        "        'days': days,",
        f"        'bucket': {key}_bucket(days),",
        f"        'band': {key}_risk_band(row),",
        f"        'owner': {key}_owner_hint(row),",
        f"        'sla_hours': {key}_sla_hours(row),",
        f"        'completeness': {key}_completeness(row),",
        "        'health_score': row.get('health_score'),",
        "    }",
        "",
        "",
        f"def {key}_briefing(rows: list[dict[str, Any]]) -> dict[str, Any]:",
        f"    items = [{key}_line_item(row) for row in rows]",
        "    by_bucket = {'fresh': 0, 'current': 0, 'aging': 0, 'legacy': 0}",
        "    for item in items:",
        "        by_bucket[str(item['bucket'])] += 1",
        "    return {",
        "        'title': DOMAIN_TITLE,",
        "        'generated_at': datetime.utcnow().replace(microsecond=0).isoformat() + 'Z',",
        "        'count': len(items),",
        f"        'bands': {key}_health_bands(rows),",
        "        'buckets': by_bucket,",
        "        'headline': " + f"{key}_headline(rows),",
        "        'items': items[:40],",
        "    }",
        "",
        "",
        f"def {key}_headline(rows: list[dict[str, Any]]) -> str:",
        "    if not rows:",
        f"        return '{title} has no rows in the local ledger yet.'",
        f"    bands = {key}_health_bands(rows)",
        "    critical = bands.get('critical', 0)",
        "    if critical:",
        f"        return f'{title}: {{critical}} critical records need a named owner this shift.'",
        f"    return f'{title}: {{len(rows)}} records are inside the operating range.'",
        "",
        "",
        f"def {key}_csv_lines(rows: list[dict[str, Any]]) -> list[str]:",
        "    header = ['id', 'title', 'status', 'days', 'bucket', 'band', 'owner', 'health_score']",
        "    lines = [','.join(header)]",
        "    for row in rows:",
        f"        item = {key}_line_item(row)",
        "        lines.append(','.join(str(item.get(col, '')).replace(',', ' ') for col in header))",
        "    return lines",
        "",
        "",
        f"def {key}_status_share(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:",
        f"    grouped = {key}_group_status(rows)",
        "    total = max(1, len(rows))",
        "    share = []",
        f"    for status in {statuses!r}:",
        "        count = len(grouped.get(status, []))",
        "        share.append({'status': status, 'count': count, 'pct': int((count / total) * 100)})",
        "    return share",
        "",
        "",
        f"def {key}_owner_load(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:",
        "    load: dict[str, int] = {}",
        "    for row in rows:",
        f"        owner = {key}_owner_hint(row)",
        "        load[owner] = load.get(owner, 0) + 1",
        "    ranked = sorted(load.items(), key=lambda pair: pair[1], reverse=True)",
        "    return [{'owner': name, 'count': count} for name, count in ranked]",
        "",
        "",
        f"def {key}_weekly_story(rows: list[dict[str, Any]]) -> list[str]:",
        "    story = []",
        f"    briefing = {key}_briefing(rows)",
        "    story.append(str(briefing['headline']))",
        "    story.append('Generated ' + str(briefing['generated_at']) + '.')",
        "    bands = briefing['bands']",
        "    story.append(",
        "        'Bands — calm {calm}, watch {watch}, elevated {elevated}, critical {critical}.'.format(",
        "            **bands",
        "        )",
        "    )",
        "    buckets = briefing['buckets']",
        "    story.append(",
        "        'Age — fresh {fresh}, current {current}, aging {aging}, legacy {legacy}.'.format(",
        "            **buckets",
        "        )",
        "    )",
        f"    story.append('{title} briefing is local-only and does not call an external network.')",
        "    return story",
        "",
        "",
        f"def {key}_print_pack(rows: list[dict[str, Any]]) -> dict[str, Any]:",
        "    return {",
        f"        'briefing': {key}_briefing(rows),",
        f"        'share': {key}_status_share(rows),",
        f"        'owners': {key}_owner_load(rows),",
        f"        'story': {key}_weekly_story(rows),",
        "    }",
        "",
        "",
        f"class {''.join(p.title() for p in key.split('_'))}Reporter:",
        f'    """Builds operator-facing packs for {title}."""',
        "",
        "    def __init__(self, rows: list[dict[str, Any]] | None = None) -> None:",
        "        self.rows = list(rows or [])",
        "",
        "    def refresh(self, rows: list[dict[str, Any]]) -> None:",
        "        self.rows = list(rows)",
        "",
        "    def briefing(self) -> dict[str, Any]:",
        f"        return {key}_briefing(self.rows)",
        "",
        "    def story(self) -> list[str]:",
        f"        return {key}_weekly_story(self.rows)",
        "",
        "    def csv(self) -> str:",
        f"        return '\\n'.join({key}_csv_lines(self.rows)) + '\\n'",
        "",
        "    def pack(self) -> dict[str, Any]:",
        f"        return {key}_print_pack(self.rows)",
        "",
        "",
        f"def build_{key}_reporter(rows: list[dict[str, Any]]) -> {''.join(p.title() for p in key.split('_'))}Reporter:",
        f"    return {''.join(p.title() for p in key.split('_'))}Reporter(rows)",
        "",
    ]
    for name, typ, _req in fields:
        lines += [
            f"def {key}_report_by_{name}(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:",
            f'    """Slice {title} by {field_label(name)}."""',
            "    buckets: dict[str, int] = {}",
            "    for row in rows:",
            f"        label = str(row.get({name!r}) or 'blank')",
            "        buckets[label] = buckets.get(label, 0) + 1",
            "    ranked = sorted(buckets.items(), key=lambda pair: pair[1], reverse=True)",
            "    return [{'label': label, 'count': count, 'field': " + repr(name) + "} for label, count in ranked]",
            "",
            "",
        ]
        if typ == "int":
            lines += [
                f"def {key}_outlier_{name}(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:",
                "    values = []",
                "    for row in rows:",
                "        try:",
                f"            values.append(int(row.get({name!r}) or 0))",
                "        except (TypeError, ValueError):",
                "            values.append(0)",
                "    if not values:",
                "        return []",
                "    avg = sum(values) / len(values)",
                "    flagged = []",
                "    for row, value in zip(rows, values):",
                "        if value > avg * 3 and value > 0:",
                f"            flagged.append({{'id': row.get('id'), 'field': {name!r}, 'value': value, 'avg': int(avg)}})",
                "    return flagged",
                "",
                "",
            ]
    return "\n".join(lines) + "\n"


def emit_services(domain: dict[str, Any]) -> str:
    key = domain["key"]
    title = domain["title"]
    class_name = "".join(p.title() for p in key.split("_"))
    statuses = domain["statuses"]
    fields = domain["fields"]
    lines = [
        f'"""Application service for {title} writes and operator actions."""',
        "from __future__ import annotations",
        "",
        "from copy import deepcopy",
        "from typing import Any",
        "",
        f"from app.domains.{key}.engine import engine",
        f"from app.domains.{key}.policies import {key}_gate_transition, {key}_policy_card, {key}_run_field_checks",
        f"from app.domains.{key}.queries import {key}_diff, {key}_export_map",
        f"from app.domains.{key}.reports import build_{key}_reporter",
        "",
        "",
        f"class {class_name}Service:",
        f'    """Coordinates validation, policy, persistence, and briefings for {title}."""',
        "",
        "    def list_view(self, filters: dict[str, Any] | None = None) -> dict[str, Any]:",
        "        rows = engine.list_records(filters)",
        "        reporter = " + f"build_{key}_reporter(rows)",
        "        return {",
        "            'rows': rows,",
        "            'kpis': engine.kpi_pack(),",
        "            'pack': reporter.pack(),",
        "        }",
        "",
        "    def detail_view(self, record_id: str) -> dict[str, Any] | None:",
        "        row = engine.get(record_id)",
        "        if row is None:",
        "            return None",
        f"        card = {key}_policy_card(row)",
        "        return {'record': row, 'policy': card}",
        "",
        "    def create_from_form(self, payload: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:",
        f"        field_errors = {key}_run_field_checks(payload)",
        "        if field_errors:",
        "            return None, field_errors",
        "        return engine.create(payload)",
        "",
        "    def update_from_form(self, record_id: str, payload: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:",
        "        current = engine.get(record_id)",
        "        if current is None:",
        "            return None, ['missing record']",
        "        merged = deepcopy(current)",
        "        merged.update(payload)",
        f"        field_errors = {key}_run_field_checks(merged)",
        "        if field_errors:",
        "            return None, field_errors",
        "        row, errors = engine.update(record_id, payload)",
        "        if row:",
        f"            row['_diff'] = {key}_diff(current, row)",
        "        return row, errors",
        "",
        "    def move_status(self, record_id: str, new_status: str) -> tuple[dict[str, Any] | None, list[str]]:",
        "        current = engine.get(record_id)",
        "        if current is None:",
        "            return None, ['missing record']",
        f"        errors = {key}_gate_transition(str(current.get('status') or ''), new_status)",
        "        if errors:",
        "            return None, errors",
        "        return engine.transition(record_id, new_status)",
        "",
        "    def export_maps(self) -> list[dict[str, str]]:",
        f"        return [{key}_export_map(row) for row in engine.list_records()]",
        "",
        "    def seed_if_empty(self, count: int = 10) -> int:",
        "        return engine.seed_demo(count)",
        "",
        "",
        f"service = {class_name}Service()",
        "",
        "",
        f"def {key}_safe_payload(form: dict[str, Any]) -> dict[str, Any]:",
        "    allowed = {name for name in " + repr([n for n, _t, _r in fields]) + "}",
        "    clean = {}",
        "    for name, value in form.items():",
        "        if name in allowed or name in {'id', 'status'}:",
        "            clean[name] = value",
        "    return clean",
        "",
        "",
        f"def {key}_can_delete(row: dict[str, Any]) -> bool:",
        "    status = str(row.get('status') or '')",
        f"    if status == {statuses[0]!r}:",
        "        return True",
        "    return int(row.get('health_score') or 0) < 20",
        "",
        "",
        f"def {key}_next_statuses(current: str) -> list[str]:",
        "    if current not in " + f"{statuses!r}" + ":",
        f"        return list({statuses!r})",
        f"    index = {statuses!r}.index(current)",
        "    options = [current]",
        "    if index + 1 < len(" + f"{statuses!r}" + "):",
        f"        options.append({statuses!r}[index + 1])",
        "    if index > 0:",
        f"        options.append({statuses!r}[index - 1])",
        "    unique = []",
        "    for item in options:",
        "        if item not in unique:",
        "            unique.append(item)",
        "    return unique",
        "",
        "",
        f"def {key}_operator_actions(row: dict[str, Any]) -> list[dict[str, str]]:",
        "    actions = [{'code': 'edit', 'label': 'Edit record'}]",
        f"    for status in {key}_next_statuses(str(row.get('status') or '')):",
        "        actions.append({'code': 'status:' + status, 'label': 'Move to ' + status})",
        f"    if {key}_can_delete(row):",
        "        actions.append({'code': 'delete', 'label': 'Remove record'})",
        "    return actions",
        "",
        "",
        f"def {key}_toast(action: str, ok: bool) -> str:",
        "    if ok:",
        f"        return f'{title} {{action}} completed.'",
        f"    return f'{title} {{action}} was blocked by policy.'",
        "",
        "",
        f"def {key}_dashboard_chip(rows: list[dict[str, Any]]) -> dict[str, Any]:",
        "    return {",
        "        'key': " + repr(key) + ",",
        "        'title': " + repr(title) + ",",
        "        'count': len(rows),",
        "        'hot': len([row for row in rows if int(row.get('health_score') or 0) < 45]),",
        "    }",
        "",
    ]
    for name, _typ, _req in fields:
        lines += [
            f"def {key}_form_help_{name}() -> str:",
            f"    return 'Enter {field_label(name)} for {title}. Local validation runs on save.'",
            "",
            "",
        ]
    lines += [
        f"FORM_HELP_{key.upper()} = {{",
    ]
    for name, _typ, _req in fields:
        lines.append(f"    {name!r}: {key}_form_help_{name}(),")
    lines += [
        "}",
        "",
        "",
        f"def {key}_form_help() -> dict[str, str]:",
        f"    return dict(FORM_HELP_{key.upper()})",
        "",
    ]
    return "\n".join(lines) + "\n"


def emit_css_extra(domain: dict[str, Any]) -> str:
    key = domain["key"]
    accent = domain["accent"]
    title = domain["title"]
    parts = [
        f"/* Extended skin for {title} — {key} */",
    ]
    for i in range(1, 28):
        parts.append(
            f""".{key}-tone-{i} {{
  --tone: {accent};
  opacity: {round(0.35 + (i % 6) * 0.1, 2)};
  border-radius: {4 + (i % 8)}px;
  letter-spacing: {round(0.01 * (i % 5), 2)}em;
}}"""
        )
    parts.append(
        f""".{key}-canvas {{
  background:
    radial-gradient(circle at {10 + (len(key) % 40)}% {20 + (len(title) % 30)}%, {accent}40, transparent 42%),
    radial-gradient(circle at {70 + (len(key) % 20)}% {80 - (len(title) % 25)}%, #09111fcc, transparent 45%),
    linear-gradient(160deg, #070b16, #101a33 55%, #0b1528);
}}
.{key}-ribbon {{
  height: 4px;
  background: linear-gradient(90deg, transparent, {accent}, transparent);
}}
.{key}-pill {{
  border: 1px solid {accent}66;
  color: {accent};
  padding: 0.2rem 0.7rem;
  border-radius: 999px;
  font-size: 0.75rem;
}}
.{key}-stat {{
  font-variant-numeric: tabular-nums;
  color: {accent};
}}
.{key}-panel-head {{
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: 1rem;
}}
.{key}-empty {{
  padding: 2.5rem 1rem;
  text-align: center;
  color: #9fb0d0;
}}
.{key}-empty strong {{
  display: block;
  color: {accent};
  margin-bottom: 0.35rem;
}}
.{key}-timeline li {{
  border-left: 2px solid {accent}55;
  padding: 0.35rem 0 0.35rem 0.9rem;
}}
.{key}-kbd {{
  font-family: "IBM Plex Mono", monospace;
  font-size: 0.78rem;
  color: {accent};
}}
.{key}-form .field input,
.{key}-form .field select {{
  background: rgba(6, 12, 24, 0.72);
}}
.{key}-hero.is-ready {{
  animation: {key}-rise 640ms ease both;
}}
@keyframes {key}-rise {{
  from {{ transform: translateY(8px); opacity: 0.4; }}
  to {{ transform: translateY(0); opacity: 1; }}
}}
.{key}-table.is-hot,
.{key}-table tr.is-hot {{
  box-shadow: inset 3px 0 0 {accent};
}}
.{key}-watermark {{
  position: absolute;
  right: 1.2rem;
  bottom: 0.8rem;
  font-size: 0.7rem;
  letter-spacing: 0.2em;
  text-transform: uppercase;
  color: {accent}55;
}}
"""
    )
    return "\n".join(parts)


def emit_js_extra(domain: dict[str, Any]) -> str:
    key = domain["key"]
    title = domain["title"]
    return f"""(function (global) {{
  const ns = (global.NexusModules = global.NexusModules || {{}});
  const current = ns[{key!r}] || {{}};
  current.filterHint = function (value) {{
    const q = String(value || "").toLowerCase();
    document.querySelectorAll(".{key}-table tbody tr").forEach(function (row) {{
      const hay = (row.textContent || "").toLowerCase();
      row.style.display = !q || hay.indexOf(q) >= 0 ? "" : "none";
    }});
  }};
  current.highlightStatus = function () {{
    document.querySelectorAll(".{key}-table tbody tr").forEach(function (row) {{
      const text = row.textContent || "";
      if (/expired|failed|rejected|lost|critical/i.test(text)) {{
        row.classList.add("is-hot");
      }}
    }});
  }};
  current.title = {title!r};
  current.readyAt = Date.now();
  ns[{key!r}] = current;
  current.highlightStatus();
}})(window);
"""
