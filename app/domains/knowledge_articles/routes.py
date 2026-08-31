"""HTTP routes for Knowledge Base."""
from __future__ import annotations

from flask import Blueprint, flash, redirect, render_template, request, url_for, Response

from app.security import login_required
from app.domains.knowledge_articles.engine import DOMAIN_TITLE, STATUSES, engine, explain_knowledge_articles_score

bp = Blueprint('knowledge_articles', __name__, url_prefix='/knowledge_articles')


@bp.get('/')
@login_required
def list_knowledge_articles():
    filters = {'q': request.args.get('q', ''), 'status': request.args.get('status', '')}
    rows = engine.list_records(filters)
    kpis = engine.kpi_pack()
    return render_template(
        'knowledge_articles/list.html',
        title=DOMAIN_TITLE,
        rows=rows,
        kpis=kpis,
        statuses=STATUSES,
        filters=filters,
        domain_key='knowledge_articles',
    )


@bp.get('/new')
@login_required
def new_knowledge_articles():
    return render_template(
        'knowledge_articles/form.html',
        title='Create ' + DOMAIN_TITLE,
        record={},
        statuses=STATUSES,
        errors=[],
        domain_key='knowledge_articles',
    )


@bp.post('/new')
@login_required
def create_knowledge_articles():
    payload = request.form.to_dict()
    row, errors = engine.create(payload)
    if errors:
        return render_template(
            'knowledge_articles/form.html',
            title='Create ' + DOMAIN_TITLE,
            record=payload,
            statuses=STATUSES,
            errors=errors,
            domain_key='knowledge_articles',
        ), 400
    flash(DOMAIN_TITLE + ' record created', 'ok')
    return redirect(url_for('knowledge_articles.detail_knowledge_articles', record_id=row['id']))


@bp.get('/<record_id>')
@login_required
def detail_knowledge_articles(record_id: str):
    row = engine.get(record_id)
    if row is None:
        flash('Record not found', 'error')
        return redirect(url_for('knowledge_articles.list_knowledge_articles'))
    notes = explain_knowledge_articles_score(row)
    return render_template(
        'knowledge_articles/detail.html',
        title=DOMAIN_TITLE,
        record=row,
        notes=notes,
        statuses=STATUSES,
        domain_key='knowledge_articles',
    )


@bp.get('/<record_id>/edit')
@login_required
def edit_knowledge_articles(record_id: str):
    row = engine.get(record_id)
    if row is None:
        flash('Record not found', 'error')
        return redirect(url_for('knowledge_articles.list_knowledge_articles'))
    return render_template(
        'knowledge_articles/form.html',
        title='Edit ' + DOMAIN_TITLE,
        record=row,
        statuses=STATUSES,
        errors=[],
        domain_key='knowledge_articles',
    )


@bp.post('/<record_id>/edit')
@login_required
def update_knowledge_articles(record_id: str):
    payload = request.form.to_dict()
    row, errors = engine.update(record_id, payload)
    if errors:
        payload['id'] = record_id
        return render_template(
            'knowledge_articles/form.html',
            title='Edit ' + DOMAIN_TITLE,
            record=payload,
            statuses=STATUSES,
            errors=errors,
            domain_key='knowledge_articles',
        ), 400
    flash(DOMAIN_TITLE + ' record saved', 'ok')
    return redirect(url_for('knowledge_articles.detail_knowledge_articles', record_id=record_id))


@bp.post('/<record_id>/transition')
@login_required
def transition_knowledge_articles(record_id: str):
    new_status = request.form.get('status', '')
    row, errors = engine.transition(record_id, new_status)
    if errors:
        flash(errors[0], 'error')
    else:
        flash('Status moved to ' + new_status, 'ok')
    return redirect(url_for('knowledge_articles.detail_knowledge_articles', record_id=record_id))


@bp.post('/<record_id>/delete')
@login_required
def delete_knowledge_articles(record_id: str):
    engine.delete(record_id)
    flash('Record removed', 'ok')
    return redirect(url_for('knowledge_articles.list_knowledge_articles'))


@bp.get('/export.csv')
@login_required
def export_knowledge_articles():
    table = engine.export_rows()
    lines = [','.join(cell.replace(',', ' ') for cell in row) for row in table]
    body = '\n'.join(lines) + '\n'
    return Response(
        body,
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment; filename=knowledge_articles.csv'},
    )


@bp.get('/report')
@login_required
def report_knowledge_articles():
    aging = engine.aging_report()
    kpis = engine.kpi_pack()
    return render_template(
        'knowledge_articles/report.html',
        title=DOMAIN_TITLE + ' report',
        aging=aging,
        kpis=kpis,
        domain_key='knowledge_articles',
    )

