"""HTTP routes for OKR Board."""
from __future__ import annotations

from flask import Blueprint, flash, redirect, render_template, request, url_for, Response

from app.security import login_required
from app.domains.okrs.engine import DOMAIN_TITLE, STATUSES, engine, explain_okrs_score

bp = Blueprint('okrs', __name__, url_prefix='/okrs')


@bp.get('/')
@login_required
def list_okrs():
    filters = {'q': request.args.get('q', ''), 'status': request.args.get('status', '')}
    rows = engine.list_records(filters)
    kpis = engine.kpi_pack()
    return render_template(
        'okrs/list.html',
        title=DOMAIN_TITLE,
        rows=rows,
        kpis=kpis,
        statuses=STATUSES,
        filters=filters,
        domain_key='okrs',
    )


@bp.get('/new')
@login_required
def new_okrs():
    return render_template(
        'okrs/form.html',
        title='Create ' + DOMAIN_TITLE,
        record={},
        statuses=STATUSES,
        errors=[],
        domain_key='okrs',
    )


@bp.post('/new')
@login_required
def create_okrs():
    payload = request.form.to_dict()
    row, errors = engine.create(payload)
    if errors:
        return render_template(
            'okrs/form.html',
            title='Create ' + DOMAIN_TITLE,
            record=payload,
            statuses=STATUSES,
            errors=errors,
            domain_key='okrs',
        ), 400
    flash(DOMAIN_TITLE + ' record created', 'ok')
    return redirect(url_for('okrs.detail_okrs', record_id=row['id']))


@bp.get('/<record_id>')
@login_required
def detail_okrs(record_id: str):
    row = engine.get(record_id)
    if row is None:
        flash('Record not found', 'error')
        return redirect(url_for('okrs.list_okrs'))
    notes = explain_okrs_score(row)
    return render_template(
        'okrs/detail.html',
        title=DOMAIN_TITLE,
        record=row,
        notes=notes,
        statuses=STATUSES,
        domain_key='okrs',
    )


@bp.get('/<record_id>/edit')
@login_required
def edit_okrs(record_id: str):
    row = engine.get(record_id)
    if row is None:
        flash('Record not found', 'error')
        return redirect(url_for('okrs.list_okrs'))
    return render_template(
        'okrs/form.html',
        title='Edit ' + DOMAIN_TITLE,
        record=row,
        statuses=STATUSES,
        errors=[],
        domain_key='okrs',
    )


@bp.post('/<record_id>/edit')
@login_required
def update_okrs(record_id: str):
    payload = request.form.to_dict()
    row, errors = engine.update(record_id, payload)
    if errors:
        payload['id'] = record_id
        return render_template(
            'okrs/form.html',
            title='Edit ' + DOMAIN_TITLE,
            record=payload,
            statuses=STATUSES,
            errors=errors,
            domain_key='okrs',
        ), 400
    flash(DOMAIN_TITLE + ' record saved', 'ok')
    return redirect(url_for('okrs.detail_okrs', record_id=record_id))


@bp.post('/<record_id>/transition')
@login_required
def transition_okrs(record_id: str):
    new_status = request.form.get('status', '')
    row, errors = engine.transition(record_id, new_status)
    if errors:
        flash(errors[0], 'error')
    else:
        flash('Status moved to ' + new_status, 'ok')
    return redirect(url_for('okrs.detail_okrs', record_id=record_id))


@bp.post('/<record_id>/delete')
@login_required
def delete_okrs(record_id: str):
    engine.delete(record_id)
    flash('Record removed', 'ok')
    return redirect(url_for('okrs.list_okrs'))


@bp.get('/export.csv')
@login_required
def export_okrs():
    table = engine.export_rows()
    lines = [','.join(cell.replace(',', ' ') for cell in row) for row in table]
    body = '\n'.join(lines) + '\n'
    return Response(
        body,
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment; filename=okrs.csv'},
    )


@bp.get('/report')
@login_required
def report_okrs():
    aging = engine.aging_report()
    kpis = engine.kpi_pack()
    return render_template(
        'okrs/report.html',
        title=DOMAIN_TITLE + ' report',
        aging=aging,
        kpis=kpis,
        domain_key='okrs',
    )

