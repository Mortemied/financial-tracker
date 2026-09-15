from datetime import date
from app.analytics import summarize
from app.services.periods import shift_month, month_end


def month_summary(records, start, end, today=None):
    today = today or date.today()
    elapsed = max(0, (min(today,end)-start).days+1)
    days = (end-start).days+1
    effective_end = min(today,end)
    current = summarize(records,start,end)
    actual_expenses = sum(r.amount_cents for r in records if r.type == 'expense' and start <= r.date <= effective_end)
    previous_start = shift_month(start,-1)
    previous = summarize(records,previous_start,month_end(previous_start))
    comparisons = {}
    for key in ('income','expenses'):
        base = previous[key]
        comparisons[key] = round((current[key]-base)/base*100,1) if base and previous['count'] else None
    return {'totals':current,'comparison':comparisons,'average':actual_expenses//elapsed if elapsed else 0,
            'days_remaining':max(0,days-elapsed),'estimated':round(actual_expenses*days/elapsed) if elapsed else None,
            'elapsed':elapsed,'days':days}
