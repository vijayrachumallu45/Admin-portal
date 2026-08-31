"""HTTP routes for Software Licenses."""
from __future__ import annotations

from flask import Blueprint, flash, redirect, render_template, request, url_for, Response

from app.security import login_required
from app.domains.software_licenses.engine import DOMAIN_TITLE, STATUSES, engine, explain_software_licenses_score

bp = Blueprint('software_licenses', __name__, url_prefix='/software_licenses')


@bp.get('/')
@login_required
def list_software_licenses():
    filters = {'q': request.args.get('q', ''), 'status': request.args.get('status', '')}
    rows = engine.list_records(filters)
    kpis = engine.kpi_pack()
    return render_template(
        'software_licenses/list.html',
        title=DOMAIN_TITLE,
        rows=rows,
        kpis=kpis,
        statuses=STATUSES,
        filters=filters,
        domain_key='software_licenses',
    )


@bp.get('/new')
@login_required
def new_software_licenses():
    return render_template(
        'software_licenses/form.html',
        title='Create ' + DOMAIN_TITLE,
        record={},
        statuses=STATUSES,
        errors=[],
        domain_key='software_licenses',
    )


@bp.post('/new')
@login_required
def create_software_licenses():
    payload = request.form.to_dict()
    row, errors = engine.create(payload)
    if errors:
        return render_template(
            'software_licenses/form.html',
            title='Create ' + DOMAIN_TITLE,
            record=payload,
            statuses=STATUSES,
            errors=errors,
            domain_key='software_licenses',
        ), 400
    flash(DOMAIN_TITLE + ' record created', 'ok')
    return redirect(url_for('software_licenses.detail_software_licenses', record_id=row['id']))


@bp.get('/<record_id>')
@login_required
def detail_software_licenses(record_id: str):
    row = engine.get(record_id)
    if row is None:
        flash('Record not found', 'error')
        return redirect(url_for('software_licenses.list_software_licenses'))
    notes = explain_software_licenses_score(row)
    return render_template(
        'software_licenses/detail.html',
        title=DOMAIN_TITLE,
        record=row,
        notes=notes,
        statuses=STATUSES,
        domain_key='software_licenses',
    )


@bp.get('/<record_id>/edit')
@login_required
def edit_software_licenses(record_id: str):
    row = engine.get(record_id)
    if row is None:
        flash('Record not found', 'error')
        return redirect(url_for('software_licenses.list_software_licenses'))
    return render_template(
        'software_licenses/form.html',
        title='Edit ' + DOMAIN_TITLE,
        record=row,
        statuses=STATUSES,
        errors=[],
        domain_key='software_licenses',
    )


@bp.post('/<record_id>/edit')
@login_required
def update_software_licenses(record_id: str):
    payload = request.form.to_dict()
    row, errors = engine.update(record_id, payload)
    if errors:
        payload['id'] = record_id
        return render_template(
            'software_licenses/form.html',
            title='Edit ' + DOMAIN_TITLE,
            record=payload,
            statuses=STATUSES,
            errors=errors,
            domain_key='software_licenses',
        ), 400
    flash(DOMAIN_TITLE + ' record saved', 'ok')
    return redirect(url_for('software_licenses.detail_software_licenses', record_id=record_id))


@bp.post('/<record_id>/transition')
@login_required
def transition_software_licenses(record_id: str):
    new_status = request.form.get('status', '')
    row, errors = engine.transition(record_id, new_status)
    if errors:
        flash(errors[0], 'error')
    else:
        flash('Status moved to ' + new_status, 'ok')
    return redirect(url_for('software_licenses.detail_software_licenses', record_id=record_id))


@bp.post('/<record_id>/delete')
@login_required
def delete_software_licenses(record_id: str):
    engine.delete(record_id)
    flash('Record removed', 'ok')
    return redirect(url_for('software_licenses.list_software_licenses'))


@bp.get('/export.csv')
@login_required
def export_software_licenses():
    table = engine.export_rows()
    lines = [','.join(cell.replace(',', ' ') for cell in row) for row in table]
    body = '\n'.join(lines) + '\n'
    return Response(
        body,
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment; filename=software_licenses.csv'},
    )


@bp.get('/report')
@login_required
def report_software_licenses():
    aging = engine.aging_report()
    kpis = engine.kpi_pack()
    return render_template(
        'software_licenses/report.html',
        title=DOMAIN_TITLE + ' report',
        aging=aging,
        kpis=kpis,
        domain_key='software_licenses',
    )

