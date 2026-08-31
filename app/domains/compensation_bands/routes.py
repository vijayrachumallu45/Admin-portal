"""HTTP routes for Compensation Bands."""
from __future__ import annotations

from flask import Blueprint, flash, redirect, render_template, request, url_for, Response

from app.security import login_required
from app.domains.compensation_bands.engine import DOMAIN_TITLE, STATUSES, engine, explain_compensation_bands_score

bp = Blueprint('compensation_bands', __name__, url_prefix='/compensation_bands')


@bp.get('/')
@login_required
def list_compensation_bands():
    filters = {'q': request.args.get('q', ''), 'status': request.args.get('status', '')}
    rows = engine.list_records(filters)
    kpis = engine.kpi_pack()
    return render_template(
        'compensation_bands/list.html',
        title=DOMAIN_TITLE,
        rows=rows,
        kpis=kpis,
        statuses=STATUSES,
        filters=filters,
        domain_key='compensation_bands',
    )


@bp.get('/new')
@login_required
def new_compensation_bands():
    return render_template(
        'compensation_bands/form.html',
        title='Create ' + DOMAIN_TITLE,
        record={},
        statuses=STATUSES,
        errors=[],
        domain_key='compensation_bands',
    )


@bp.post('/new')
@login_required
def create_compensation_bands():
    payload = request.form.to_dict()
    row, errors = engine.create(payload)
    if errors:
        return render_template(
            'compensation_bands/form.html',
            title='Create ' + DOMAIN_TITLE,
            record=payload,
            statuses=STATUSES,
            errors=errors,
            domain_key='compensation_bands',
        ), 400
    flash(DOMAIN_TITLE + ' record created', 'ok')
    return redirect(url_for('compensation_bands.detail_compensation_bands', record_id=row['id']))


@bp.get('/<record_id>')
@login_required
def detail_compensation_bands(record_id: str):
    row = engine.get(record_id)
    if row is None:
        flash('Record not found', 'error')
        return redirect(url_for('compensation_bands.list_compensation_bands'))
    notes = explain_compensation_bands_score(row)
    return render_template(
        'compensation_bands/detail.html',
        title=DOMAIN_TITLE,
        record=row,
        notes=notes,
        statuses=STATUSES,
        domain_key='compensation_bands',
    )


@bp.get('/<record_id>/edit')
@login_required
def edit_compensation_bands(record_id: str):
    row = engine.get(record_id)
    if row is None:
        flash('Record not found', 'error')
        return redirect(url_for('compensation_bands.list_compensation_bands'))
    return render_template(
        'compensation_bands/form.html',
        title='Edit ' + DOMAIN_TITLE,
        record=row,
        statuses=STATUSES,
        errors=[],
        domain_key='compensation_bands',
    )


@bp.post('/<record_id>/edit')
@login_required
def update_compensation_bands(record_id: str):
    payload = request.form.to_dict()
    row, errors = engine.update(record_id, payload)
    if errors:
        payload['id'] = record_id
        return render_template(
            'compensation_bands/form.html',
            title='Edit ' + DOMAIN_TITLE,
            record=payload,
            statuses=STATUSES,
            errors=errors,
            domain_key='compensation_bands',
        ), 400
    flash(DOMAIN_TITLE + ' record saved', 'ok')
    return redirect(url_for('compensation_bands.detail_compensation_bands', record_id=record_id))


@bp.post('/<record_id>/transition')
@login_required
def transition_compensation_bands(record_id: str):
    new_status = request.form.get('status', '')
    row, errors = engine.transition(record_id, new_status)
    if errors:
        flash(errors[0], 'error')
    else:
        flash('Status moved to ' + new_status, 'ok')
    return redirect(url_for('compensation_bands.detail_compensation_bands', record_id=record_id))


@bp.post('/<record_id>/delete')
@login_required
def delete_compensation_bands(record_id: str):
    engine.delete(record_id)
    flash('Record removed', 'ok')
    return redirect(url_for('compensation_bands.list_compensation_bands'))


@bp.get('/export.csv')
@login_required
def export_compensation_bands():
    table = engine.export_rows()
    lines = [','.join(cell.replace(',', ' ') for cell in row) for row in table]
    body = '\n'.join(lines) + '\n'
    return Response(
        body,
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment; filename=compensation_bands.csv'},
    )


@bp.get('/report')
@login_required
def report_compensation_bands():
    aging = engine.aging_report()
    kpis = engine.kpi_pack()
    return render_template(
        'compensation_bands/report.html',
        title=DOMAIN_TITLE + ' report',
        aging=aging,
        kpis=kpis,
        domain_key='compensation_bands',
    )

