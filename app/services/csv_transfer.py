"""Stable CSV contract and a side-effect-free import preview boundary."""
import csv
import io
from app.services.transactions import validate_transaction, ValidationError

FIELDS = ('Date', 'Type', 'Category', 'Description', 'Amount')


def safe_cell(value):
    value = str(value)
    # Prevent spreadsheet formula execution, including leading whitespace.
    if value.lstrip().startswith(('=', '+', '-', '@')) or value.startswith(('\t', '\r', '\n')):
        return "'" + value
    return value


def export_csv(records, category_label):
    output = io.StringIO(newline='')
    writer = csv.writer(output)
    writer.writerow(FIELDS)
    for row in records:
        writer.writerow([row.date.isoformat(), row.type, safe_cell(category_label(row.category)),
                         safe_cell(row.description), format(row.amount, '.2f')])
    return '\ufeff' + output.getvalue()


def preview_import(text, category_resolver):
    """Compatibility API: validated rows, no writes; parsing shared with the UI."""
    from app.services.importing import parse_upload
    valid, errors = [], []
    for row in parse_upload(text.encode('utf-8')):
        try:
            if row['malformed']:
                raise ValidationError('error.csv_row')
            values = validate_transaction({**row, 'category_id':category_resolver(row['category'],row['type'])})
            valid.append(values)
        except (ValidationError, TypeError, KeyError) as error:
            errors.append({'row':row['line'],'key':getattr(error,'key','error.csv_row')})
    return {'rows':valid,'errors':errors}
