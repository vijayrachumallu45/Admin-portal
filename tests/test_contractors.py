from app.domains.contractors.engine import engine, STATUSES, DOMAIN_KEY


def test_contractors_validate_and_create():
    payload = engine.demo_payloads(1)[0]
    row, errors = engine.create(payload)
    assert errors == []
    assert row is not None
    assert row["status"] in STATUSES
    found = engine.get(row["id"])
    assert found is not None
    assert found['contractor_no'] == row['contractor_no']


def test_contractors_filters_and_kpis():
    engine.seed_demo(5)
    rows = engine.list_records({"q": DOMAIN_KEY})
    assert isinstance(rows, list)
    pack = engine.kpi_pack()
    assert "count" in pack
    assert pack["count"] >= 1


def test_contractors_policy_and_service():
    from app.domains.contractors.policies import policy
    from app.domains.contractors.services import service

    engine.seed_demo(3)
    rows = engine.list_records()
    assert rows
    card_ok = policy.allow_write(rows[0]) or isinstance(policy.collect(rows[0]), list)
    assert card_ok
    view = service.list_view()
    assert "rows" in view
    assert "kpis" in view
