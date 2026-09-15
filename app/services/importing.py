"""CSV review is persistent; only an explicit confirmation commits one batch."""
import csv
import hashlib
import io
import json
import secrets
from datetime import datetime, timedelta, timezone
from flask import current_app
from app.extensions import db
from app.models import ImportBatch, Category, Transaction
from app.services.transactions import validate_transaction, ValidationError
from app.services.csv_transfer import FIELDS


def mapping_key(label, kind):
    return hashlib.sha256((kind+'\0'+label).encode()).hexdigest()[:20]


def parse_upload(raw):
    if len(raw) > 2*1024*1024:
        raise ValidationError('error.csv_size')
    try:
        text = raw.decode('utf-8-sig')
    except UnicodeDecodeError:
        raise ValidationError('error.csv_encoding') from None
    try:
        dialect = csv.Sniffer().sniff(text[:4096],delimiters=',;\t')
    except csv.Error:
        dialect = csv.excel
    reader = csv.DictReader(io.StringIO(text),dialect=dialect)
    if not reader.fieldnames or set(reader.fieldnames) != set(FIELDS) or len(reader.fieldnames) != len(FIELDS):
        raise ValidationError('error.csv_headers')
    rows = []
    try:
        for index, row in enumerate(reader,2):
            if index > 10001:
                raise ValidationError('error.csv_size')
            rows.append({'line':index,'date':row.get('Date') or '', 'type':row.get('Type') or '',
                         'category':row.get('Category') or '', 'description':row.get('Description') or '',
                         'amount':row.get('Amount') or '', 'malformed':None in row or any(value is None for value in row.values())})
    except csv.Error:
        raise ValidationError('error.csv_row') from None
    if not rows:
        raise ValidationError('error.csv_empty')
    return rows


def create_batch(raw):
    rows = parse_upload(raw)
    # Expired staging data is safe to discard; financial records are never removed.
    db.session.execute(db.delete(ImportBatch).where(ImportBatch.created_at < datetime.now(timezone.utc).replace(tzinfo=None)-timedelta(days=2)))
    batch = ImportBatch(id=secrets.token_hex(24),payload=json.dumps({'rows':rows,'mapping':{}},ensure_ascii=False))
    db.session.add(batch)
    db.session.commit()
    return batch


def review_batch(batch, mappings=None):
    if batch.completed_at or datetime.now(timezone.utc).replace(tzinfo=None)-batch.created_at > timedelta(hours=24):
        raise ValidationError('error.csv_expired')
    payload = json.loads(batch.payload)
    if mappings is not None:
        payload['mapping'].update({key[4:]:value for key,value in mappings.items() if key.startswith('map_') and value})
        batch.payload = json.dumps(payload,ensure_ascii=False)
        db.session.commit()
    categories = db.session.scalars(db.select(Category)).all()
    aliases = {}
    for category in categories:
        labels = [category.name] if category.name else [category.key] + [catalog.get('category.'+category.key) for catalog in current_app.extensions['catalogs'].values()]
        for label in labels:
            if label:
                aliases.setdefault((category.type,label.strip().casefold()),set()).add(category.id)
    existing = {(r.date.isoformat(),r.amount_cents,r.description.strip(),r.type) for r in db.session.scalars(db.select(Transaction).where(Transaction.deleted_at.is_(None)))}
    seen = set()
    reviewed, unknown = [], {}
    for raw in payload['rows']:
        row = dict(raw)
        key = mapping_key(row['category'],row['type'])
        matches = aliases.get((row['type'],row['category'].strip().casefold()),set())
        category_id = payload['mapping'].get(key) or (next(iter(matches)) if len(matches)==1 else None)
        row.update(status='ready',error=None,mapping_key=key,values=None,resolved_category=None)
        if not category_id:
            row['status'] = 'unknown'
            unknown[key] = {'label':row['category'],'type':row['type']}
        try:
            # Validate amount/date/type even if a category remains unmapped.
            from app.services.transactions import parse_money, parse_date
            parse_money(row['amount']); parse_date(row['date'])
            if row['malformed'] or row['type'] not in ('income','expense') or len(row['description']) > 250:
                raise ValidationError('error.csv_row')
            if category_id:
                row['values'] = validate_transaction({**row,'category_id':category_id})
                row['resolved_category'] = next(category for category in categories if category.id == row['values']['category_id'])
                values = row['values']
                identity = (values['date'].isoformat(),values['amount_cents'],values['description'],values['type'])
                if identity in existing or identity in seen:
                    row['status'] = 'duplicate'
                seen.add(identity)
        except ValidationError as error:
            row.update(status='invalid',error=error.key)
        reviewed.append(row)
    return {'rows':reviewed,'unknown':unknown,'categories':categories,
            'ready':sum(row['status'] in ('ready','duplicate') for row in reviewed)}


def commit_batch(batch, duplicate_action='skip'):
    if duplicate_action not in ('skip','import'):
        raise ValidationError('error.csv_row')
    review = review_batch(batch)
    if any(row['status'] in ('invalid','unknown') for row in review['rows']):
        raise ValidationError('error.csv_review')
    count = 0
    for row in review['rows']:
        if row['status'] == 'duplicate' and duplicate_action == 'skip':
            continue
        db.session.add(Transaction(**row['values']))
        count += 1
    batch.completed_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.session.commit()
    return count
