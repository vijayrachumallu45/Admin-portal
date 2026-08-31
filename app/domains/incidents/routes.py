"""HTTP routes for Incident Room."""
from __future__ import annotations

from flask import Blueprint, flash, redirect, render_template, request, url_for, Response

from app.security import login_required
from app.domains.incidents.engine import DOMAIN_TITLE, STATUSES, engine, explain_incidents_score

bp = Blueprint('incidents', __name__, url_prefix='/incidents')


@bp.get('/')
@login_required
def list_incidents():
    filters = {'q': request.args.get('q', ''), 'status': request.args.get('status', '')}
    rows = engine.list_records(filters)
    kpis = engine.kpi_pack()
    return render_template(
        'incidents/list.html',
        title=DOMAIN_TITLE,
        rows=rows,
        kpis=kpis,
        statuses=STATUSES,
        filters=filters,
        domain_key='incidents',
    )


@bp.get('/new')
@login_required
def new_incidents():
    return render_template(
        'incidents/form.html',
        title='Create ' + DOMAIN_TITLE,
        record={},
        statuses=STATUSES,
        errors=[],
        domain_key='incidents',
    )


@bp.post('/new')
@login_required
def create_incidents():
    payload = request.form.to_dict()
    row, errors = engine.create(payload)
    if errors:
        return render_template(
            'incidents/form.html',
            title='Create ' + DOMAIN_TITLE,
            record=payload,
            statuses=STATUSES,
            errors=errors,
            domain_key='incidents',
        ), 400
    flash(DOMAIN_TITLE + ' record created', 'ok')
    return redirect(url_for('incidents.detail_incidents', record_id=row['id']))


@bp.get('/<record_id>')
@login_required
def detail_incidents(record_id: str):
    row = engine.get(record_id)
    if row is None:
        flash('Record not found', 'error')
        return redirect(url_for('incidents.list_incidents'))
    notes = explain_incidents_score(row)
    return render_template(
        'incidents/detail.html',
        title=DOMAIN_TITLE,
        record=row,
        notes=notes,
        statuses=STATUSES,
        domain_key='incidents',
    )


@bp.get('/<record_id>/edit')
@login_required
def edit_incidents(record_id: str):
    row = engine.get(record_id)
    if row is None:
        flash('Record not found', 'error')
        return redirect(url_for('incidents.list_incidents'))
    return render_template(
        'incidents/form.html',
        title='Edit ' + DOMAIN_TITLE,
        record=row,
        statuses=STATUSES,
        errors=[],
        domain_key='incidents',
    )


@bp.post('/<record_id>/edit')
@login_required
def update_incidents(record_id: str):
    payload = request.form.to_dict()
    row, errors = engine.update(record_id, payload)
    if errors:
        payload['id'] = record_id
        return render_template(
            'incidents/form.html',
            title='Edit ' + DOMAIN_TITLE,
            record=payload,
            statuses=STATUSES,
            errors=errors,
            domain_key='incidents',
        ), 400
    flash(DOMAIN_TITLE + ' record saved', 'ok')
    return redirect(url_for('incidents.detail_incidents', record_id=record_id))


@bp.post('/<record_id>/transition')
@login_required
def transition_incidents(record_id: str):
    new_status = request.form.get('status', '')
    row, errors = engine.transition(record_id, new_status)
    if errors:
        flash(errors[0], 'error')
    else:
        flash('Status moved to ' + new_status, 'ok')
    return redirect(url_for('incidents.detail_incidents', record_id=record_id))


@bp.post('/<record_id>/delete')
@login_required
def delete_incidents(record_id: str):
    engine.delete(record_id)
    flash('Record removed', 'ok')
    return redirect(url_for('incidents.list_incidents'))


@bp.get('/export.csv')
@login_required
def export_incidents():
    table = engine.export_rows()
    lines = [','.join(cell.replace(',', ' ') for cell in row) for row in table]
    body = '\n'.join(lines) + '\n'
    return Response(
        body,
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment; filename=incidents.csv'},
    )


@bp.get('/report')
@login_required
def report_incidents():
    aging = engine.aging_report()
    kpis = engine.kpi_pack()
    return render_template(
        'incidents/report.html',
        title=DOMAIN_TITLE + ' report',
        aging=aging,
        kpis=kpis,
        domain_key='incidents',
    )

