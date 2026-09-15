'use strict';
(() => {
  const config = document.getElementById('chart-config');
  if (!config) return;
  const data = JSON.parse(config.dataset.chart);
  const locale = config.dataset.locale;
  const money = new Intl.NumberFormat(locale, { style: 'currency', currency: config.dataset.currency, maximumFractionDigits: 2 });
  const compact = new Intl.NumberFormat(locale, { notation: 'compact', maximumFractionDigits: 1 });
  const css = getComputedStyle(document.documentElement);
  const muted = css.getPropertyValue('--muted').trim();
  const line = css.getPropertyValue('--line').trim();
  const green = '#10c59a', red = '#fa7d89', blue = '#3989fb';
  const fmtMonth = label => new Intl.DateTimeFormat(locale, { month: 'short' }).format(new Date(label + '-01T12:00:00'));
  const fmtDay = label => new Intl.DateTimeFormat(locale, { day: 'numeric', month: 'short' }).format(new Date(label + 'T12:00:00'));
  const dataset = (label, values, color, extra = {}) => ({ label, data: values, backgroundColor: color, borderColor: color, borderWidth: 0, borderRadius: 4, maxBarThickness: 17, ...extra });

  function render(id, type, labels, datasets, formatter = x => x) {
    const canvas = document.getElementById(id);
    if (!canvas) return;
    const card = canvas.closest('.chart-card');
    // A keyboard-accessible data table supplies the same information as each canvas.
    const table = document.createElement('table');
    const header = document.createElement('tr');
    ['', ...datasets.map(s => s.label)].forEach(label => {
      const th = document.createElement('th'); th.textContent = label; header.append(th);
    });
    const thead = document.createElement('thead'); thead.append(header); table.append(thead);
    const tbody = document.createElement('tbody');
    labels.forEach((label, index) => {
      const row = document.createElement('tr');
      const title = document.createElement('th'); title.scope = 'row'; title.textContent = formatter(label); row.append(title);
      datasets.forEach(series => { const td = document.createElement('td'); td.textContent = money.format(series.data[index]); row.append(td); });
      tbody.append(row);
    });
    table.append(tbody);
    card.querySelector('.chart-data-table').append(table);
    if (!labels.length || !datasets.some(series => series.data.some(value => value !== 0))) {
      canvas.hidden = true; card.querySelector('.chart-empty').hidden = false; return;
    }
    if (!window.Chart) {
      canvas.hidden = true;
      const empty = card.querySelector('.chart-empty'); empty.textContent = data.text.chart_unavailable; empty.hidden = false;
      return;
    }
    const doughnut = type === 'doughnut';
    new Chart(canvas, {
      type, data: { labels: labels.map(formatter), datasets },
      options: {
        responsive: true, maintainAspectRatio: false, animation: false,
        interaction: { intersect: false, mode: doughnut ? 'nearest' : 'index' },
        cutout: doughnut ? '73%' : undefined,
        layout: { padding: { top: 5, right: 5, bottom: 0 } },
        plugins: {
          legend: { display: doughnut || id === 'comparison', position: doughnut ? 'right' : 'top', align: doughnut ? 'center' : 'end',
            labels: { color: muted, boxWidth: 8, boxHeight: 8, usePointStyle: true, pointStyle: 'rectRounded', padding: doughnut ? 13 : 18, font: { size: 12, family: 'Inter' } } },
          tooltip: { padding: 12, cornerRadius: 9, titleFont: { size: 13 }, bodyFont: { size: 13 }, callbacks: {
            label: context => {
              const value = doughnut ? context.parsed : context.parsed.y;
              const total = doughnut ? context.dataset.data.reduce((sum, item) => sum + item, 0) : 0;
              const share = total ? ` · ${new Intl.NumberFormat(locale, { style: 'percent', maximumFractionDigits: 1 }).format(value / total)}` : '';
              return `${doughnut ? context.label : context.dataset.label}: ${money.format(value)}${share}`;
            }
          } },
        },
        scales: doughnut ? {} : {
          x: { grid: { display: false }, border: { display: false }, ticks: { color: muted, font: { size: 11, family: 'Inter' }, maxTicksLimit: 7, maxRotation: 0 } },
          y: { beginAtZero: id !== 'balance', border: { display: false }, grid: { color: line, tickLength: 0 }, ticks: { color: muted, padding: 10, maxTicksLimit: 5, font: { size: 11, family: 'Inter' }, callback: value => compact.format(value) } },
        },
      },
      plugins: doughnut ? [{
        id: 'centerTotal', afterDraw(chart) {
          const meta = chart.getDatasetMeta(0);
          if (!meta.data.length) return;
          const { x, y } = meta.data[0];
          const total = chart.data.datasets[0].data.reduce((sum, value, index) => chart.getDataVisibility(index) ? sum + value : sum, 0);
          const ctx = chart.ctx;
          ctx.save(); ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
          ctx.fillStyle = css.getPropertyValue('--text').trim(); ctx.font = '600 18px Inter, sans-serif';
          ctx.fillText(new Intl.NumberFormat(locale, { maximumFractionDigits: 0 }).format(total), x, y - 6);
          ctx.fillStyle = muted; ctx.font = '10px Inter, sans-serif'; ctx.fillText(config.dataset.currency, x, y + 14); ctx.restore();
        },
      }] : [],
    });
  }
  render('breakdown', 'doughnut', data.breakdown.labels, [dataset(data.text.expense, data.breakdown.values, data.breakdown.colors, { borderWidth: 0, borderRadius: 0, hoverOffset: 4 })]);
  render('comparison', 'bar', data.monthly.labels, [dataset(data.text.income, data.monthly.income, green), dataset(data.text.expense, data.monthly.expense, red)], fmtMonth);
  function lineSeries(label, values, color) {
    return dataset(label, values, color, { borderWidth: 2, tension: .32, pointRadius: values.length > 40 ? 0 : 2.5, pointHoverRadius: 4, fill: true, backgroundColor: color + '16' });
  }
  render('balance', 'line', data.balance.labels, [lineSeries(data.text.balance, data.balance.values, green)], fmtDay);
  render('trend', 'line', data.trend.labels, [lineSeries(data.text.expense, data.trend.values, blue)], fmtDay);
  render('savings', 'bar', data.monthly.labels, [dataset(data.text.savings, data.monthly.savings, data.monthly.savings.map(value => value < 0 ? red : green))], fmtMonth);
})();
