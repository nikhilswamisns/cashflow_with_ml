import { useMemo, useState } from 'react'
import { Line } from 'react-chartjs-2'
import type { Chart, ChartData, Plugin, ScriptableContext } from 'chart.js'
import type { DashboardData } from '@/features/dashboard/types'
import { dlabel, fullDates, kfmt, usd } from '@/shared/format'
import { alpha, useChartTokens, type Tokens } from '@/shared/chart/tokens'
import { baseOptions, SANS } from '@/shared/chart/base'
import { assumptionPlugin, assumptionStart } from '@/features/dashboard/assumption'
import { actualValues, weekDates } from '@/features/dashboard/actual'
type View = 'both' | 'rules' | 'ml'
const RULES_IDX = 2

// small label on the lowest point of the rules line
const lowPointPlugin = (t: Tokens): Plugin<'line'> => ({
  id: 'lowPoint',
  afterDatasetsDraw(chart: Chart<'line'>) {
    const meta = chart.getDatasetMeta(RULES_IDX)
    const ds = chart.data.datasets[RULES_IDX]
    if (!ds || meta.hidden) return
    const data = ds.data as (number | null)[] // history weeks before the forecast are null
    const i = data.indexOf(Math.min(...data.filter((v): v is number => v != null)))
    const p = meta.data[i]
    if (!p) return
    const { ctx, chartArea } = chart
    const txt = `Lowest ${kfmt(data[i] as number)} · ${String(chart.data.labels?.[i] ?? '')}`
    ctx.save()
    ctx.font = `500 12px ${SANS}`
    const w = ctx.measureText(txt).width + 18,
      h = 24
    let x = p.x + 12,
      y = p.y + 10
    if (x + w > chartArea.right) x = p.x - w - 12
    if (y + h > chartArea.bottom) y = p.y - h - 10
    ctx.fillStyle = t.text
    ctx.beginPath()
    ctx.roundRect(x, y, w, h, 7)
    ctx.fill()
    ctx.fillStyle = t.bg
    ctx.textBaseline = 'middle'
    ctx.fillText(txt, x + 9, y + h / 2 + 0.5)
    ctx.fillStyle = t.cash
    ctx.strokeStyle = t.surface
    ctx.lineWidth = 2
    ctx.beginPath()
    ctx.arc(p.x, p.y, 5, 0, 7)
    ctx.fill()
    ctx.stroke()
    ctx.restore()
  },
})

export function LeadChart({ d, mlPending, mlFailed }: { d: DashboardData; mlPending: boolean; mlFailed: boolean }) {
  const t = useChartTokens()
  const [view, setView] = useState<View>('both')
  const [n, setN] = useState(13)
  const labels = useMemo(() => d.labels.map(dlabel), [d])
  const dates = useMemo(() => fullDates(d.labels, d.kpis.as_of ?? ''), [d])
  const hasMl = !!d.ml
  const showR = !hasMl || view !== 'ml',
    showM = hasMl && view !== 'rules'
  const floor = d.floor
  const a = d.actuals
  const pad = a ? a.historyWeeks : 0 // actual weeks shown before the forecast starts (context only)
  const weeks = useMemo(() => (a ? weekDates(a.firstWeek, a.historyWeeks, n) : []), [a, n])
  const act = useMemo(() => (a ? actualValues(weeks, a) : null), [a, weeks])

  const data = useMemo(() => {
    const cut = (arr: number[]): (number | null)[] => [...Array<null>(pad).fill(null), ...arr.slice(0, n)]
    const fillGradient = (ctx: ScriptableContext<'line'>) => {
      const area = ctx.chart.chartArea
      if (!area) return undefined
      const g = ctx.chart.ctx.createLinearGradient(0, area.top, 0, area.bottom)
      g.addColorStop(0, alpha(t.cash, 0.22))
      g.addColorStop(1, alpha(t.cash, 0))
      return g
    }
    const chartData: ChartData<'line'> = {
      labels: a ? weeks.map((w) => dlabel(w.slice(5))) : labels.slice(0, n),
      datasets: [
        {
          label: 'Range low',
          data: cut(d.ml?.p10 ?? []),
          borderColor: 'transparent',
          pointRadius: 0,
          fill: false,
          hideTip: true,
          hidden: !showM,
        },
        {
          label: 'Likely range (ML timing)',
          data: cut(d.ml?.p90 ?? []),
          borderColor: 'transparent',
          backgroundColor: alpha(t.ml, 0.14),
          pointRadius: 0,
          fill: '-1',
          hideTip: true,
          hidden: !showM,
        },
        {
          label: 'Rules timing',
          data: cut(d.cash_rules),
          borderColor: t.cash,
          backgroundColor: fillGradient,
          borderWidth: 2.4,
          pointRadius: 0,
          pointHoverRadius: 5,
          tension: 0.3,
          fill: true,
          hidden: !showR,
        },
        {
          label: 'ML timing',
          data: cut(d.ml?.cash_ml ?? []),
          borderColor: t.ml,
          borderWidth: 2.4,
          borderDash: [7, 5],
          pointRadius: 0,
          pointHoverRadius: 5,
          tension: 0.3,
          fill: false,
          hidden: !showM,
        },
        ...(floor == null
          ? []
          : [
              {
                label: 'Minimum cash floor',
                data: new Array(pad + n).fill(floor),
                borderColor: t.floor,
                borderWidth: 1.4,
                borderDash: [3, 4],
                pointRadius: 0,
                fill: false,
                hideTip: true,
              },
            ]),
        ...(act
          ? [
              {
                label: 'Actual cash (Zoho books)',
                data: act.values,
                borderColor: t.inC,
                backgroundColor: t.inC,
                borderWidth: 2.8,
                tension: 0.15,
                spanGaps: false,
                fill: false,
                order: -1, // drawn on top of the forecast lines
                pointRadius: act.values.map((v, i) => (v == null ? 0 : i === act.todayIdx ? 6 : 3.5)),
                pointBackgroundColor: act.values.map((_, i) => (i === act.todayIdx ? t.surface : t.inC)),
                pointBorderColor: t.inC,
                pointBorderWidth: 2,
                pointHoverRadius: 6,
              },
            ]
          : []),
      ],
    }
    return chartData
  }, [d, t, n, labels, showR, showM, floor, a, weeks, act, pad])

  const options = useMemo(() => baseOptions(t, { yTicks: 9 }), [t])
  const assumeFrom = useMemo(() => assumptionStart(d), [d])
  const plugins = useMemo(
    () => [assumptionPlugin(t, assumeFrom == null ? null : assumeFrom + pad), lowPointPlugin(t)],
    [t, assumeFrom, pad],
  )

  const minRules = Math.min(...d.cash_rules)
  const minI = d.cash_rules.indexOf(minRules)
  const limit = floor ?? 0
  const below = d.cash_rules.filter((v) => v < limit).length
  const mlMin = d.ml ? Math.min(...d.ml.cash_ml) : 0
  const mlMinI = d.ml ? d.ml.cash_ml.indexOf(mlMin) : 0

  return (
    <article className="card lead-chart">
      <div className="card-head">
        <div>
          <h2>Cash position</h2>
          <p className="sub">Weekly ending cash, costs included. Same documents, two payment-timing assumptions.</p>
        </div>
        <div className="controls">
          {hasMl && (
            <div className="seg" role="group" aria-label="Timing">
              {(
                [
                  ['both', 'Both'],
                  ['rules', 'Rules'],
                  ['ml', 'ML timing'],
                ] as const
              ).map(([k, l]) => (
                <button key={k} className={view === k ? 'on' : ''} aria-pressed={view === k} onClick={() => setView(k)}>
                  {l}
                </button>
              ))}
            </div>
          )}
          <div className="seg" role="group" aria-label="Range">
            {[13, 26, 52].map((k) => (
              <button key={k} className={n === k ? 'on' : ''} aria-pressed={n === k} onClick={() => setN(k)}>
                {k}w
              </button>
            ))}
          </div>
        </div>
      </div>
      {mlPending ? (
        <div className="chart tall chart-wait">
          <span>Loading the ML timing line…</span>
        </div>
      ) : (
        <div className="chart tall">
          <Line data={data} options={options} plugins={plugins} />
        </div>
      )}
      {mlFailed && (
        <p className="insight warn">
          ML timing is not available for this run. The blue line is the saved run, which may already include ML timing.
        </p>
      )}
      <div className="legend">
        <span>
          <i style={{ background: t.cash }} />
          {hasMl ? 'Paid on rule dates' : 'Cash balance'}
        </span>
        {hasMl && (
          <span style={{ color: t.ml }}>
            <i className="dash" />
            <span style={{ color: 'var(--text-2)' }}>Paid when customers actually pay (ML timing)</span>
          </span>
        )}
        {hasMl && (
          <span>
            <i className="box" style={{ background: alpha(t.ml, 0.35) }} />
            Likely range (p10 to p90)
          </span>
        )}
        {act && (
          <span>
            <i style={{ background: t.inC }} />
            Actual cash (Zoho books); the hollow dot is today
          </span>
        )}
        {floor != null && (
          <span style={{ color: t.floor }}>
            <i className="dash" />
            <span style={{ color: 'var(--text-2)' }}>Minimum cash floor {usd(floor)}</span>
          </span>
        )}
      </div>
      {assumeFrom != null && assumeFrom < n && (
        <p className="insight">
          From the week ending <b>{dates[assumeFrom]}</b> no known invoice or bill is left, so both lines use the same
          flat run-rate. Treat the grey weeks as an assumption.
        </p>
      )}
      {!mlPending && (
        <p className="insight">
          Cash is{' '}
          <b>
            {below === 0
              ? `never below ${usd(limit)}`
              : `below ${usd(limit)} for ${below} of ${d.cash_rules.length} weeks`}
          </b>
          {!mlFailed && ' on the rules'}, with the lowest point at <b>{usd(minRules)}</b> in the week ending{' '}
          {labels[minI]}.
          {d.ml && (
            <>
              {' '}
              With ML timing the low is <b>{usd(mlMin)}</b> ({labels[mlMinI]})
              {mlMin > minRules ? ', because customers tend to pay earlier than the due date' : ''}.
            </>
          )}
        </p>
      )}
    </article>
  )
}
