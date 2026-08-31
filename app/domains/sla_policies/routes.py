"""HTTP routes for SLA Policies."""
from __future__ import annotations

from flask import Blueprint, flash, redirect, render_template, request, url_for, Response

from app.security import login_required
from app.domains.sla_policies.engine import DOMAIN_TITLE, STATUSES, engine, explain_sla_policies_score

bp = Blueprint('sla_policies', __name__, url_prefix='/sla_policies')


@bp.get('/')
@login_required
def list_sla_policies():
    filters = {'q': request.args.get('q', ''), 'status': request.args.get('status', '')}
    rows = engine.list_records(filters)
    kpis = engine.kpi_pack()
    return render_template(
        'sla_policies/list.html',
        title=DOMAIN_TITLE,
        rows=rows,
        kpis=kpis,
        statuses=STATUSES,
        filters=filters,
        domain_key='sla_policies',
    )


@bp.get('/new')
@login_required
def new_sla_policies():
    return render_template(
        'sla_policies/form.html',
        title='Create ' + DOMAIN_TITLE,
        record={},
        statuses=STATUSES,
        errors=[],
        domain_key='sla_policies',
    )


@bp.post('/new')
@login_required
def create_sla_policies():
    payload = request.form.to_dict()
    row, errors = engine.create(payload)
    if errors:
        return render_template(
            'sla_policies/form.html',
            title='Create ' + DOMAIN_TITLE,
            record=payload,
            statuses=STATUSES,
            errors=errors,
            domain_key='sla_policies',
        ), 400
    flash(DOMAIN_TITLE + ' record created', 'ok')
    return redirect(url_for('sla_policies.detail_sla_policies', record_id=row['id']))


@bp.get('/<record_id>')
@login_required
def detail_sla_policies(record_id: str):
    row = engine.get(record_id)
    if row is None:
        flash('Record not found', 'error')
        return redirect(url_for('sla_policies.list_sla_policies'))
    notes = explain_sla_policies_score(row)
    return render_template(
        'sla_policies/detail.html',
        title=DOMAIN_TITLE,
        record=row,
        notes=notes,
        statuses=STATUSES,
        domain_key='sla_policies',
    )


@bp.get('/<record_id>/edit')
@login_required
def edit_sla_policies(record_id: str):
    row = engine.get(record_id)
    if row is None:
        flash('Record not found', 'error')
        return redirect(url_for('sla_policies.list_sla_policies'))
    return render_template(
        'sla_policies/form.html',
        title='Edit ' + DOMAIN_TITLE,
        record=row,
        statuses=STATUSES,
        errors=[],
        domain_key='sla_policies',
    )


@bp.post('/<record_id>/edit')
@login_required
def update_sla_policies(record_id: str):
    payload = request.form.to_dict()
    row, errors = engine.update(record_id, payload)
    if errors:
        payload['id'] = record_id
        return render_template(
            'sla_policies/form.html',
            title='Edit ' + DOMAIN_TITLE,
            record=payload,
            statuses=STATUSES,
            errors=errors,
            domain_key='sla_policies',
        ), 400
    flash(DOMAIN_TITLE + ' record saved', 'ok')
    return redirect(url_for('sla_policies.detail_sla_policies', record_id=record_id))


@bp.post('/<record_id>/transition')
@login_required
def transition_sla_policies(record_id: str):
    new_status = request.form.get('status', '')
    row, errors = engine.transition(record_id, new_status)
    if errors:
        flash(errors[0], 'error')
    else:
        flash('Status moved to ' + new_status, 'ok')
    return redirect(url_for('sla_policies.detail_sla_policies', record_id=record_id))


@bp.post('/<record_id>/delete')
@login_required
def delete_sla_policies(record_id: str):
    engine.delete(record_id)
    flash('Record removed', 'ok')
    return redirect(url_for('sla_policies.list_sla_policies'))


@bp.get('/export.csv')
@login_required
def export_sla_policies():
    table = engine.export_rows()
    lines = [','.join(cell.replace(',', ' ') for cell in row) for row in table]
    body = '\n'.join(lines) + '\n'
    return Response(
        body,
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment; filename=sla_policies.csv'},
    )


@bp.get('/report')
@login_required
def report_sla_policies():
    aging = engine.aging_report()
    kpis = engine.kpi_pack()
    return render_template(
        'sla_policies/report.html',
        title=DOMAIN_TITLE + ' report',
        aging=aging,
        kpis=kpis,
        domain_key='sla_policies',
    )

