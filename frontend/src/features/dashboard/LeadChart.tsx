import { useMemo, useState } from 'react'
import { BlockLoading } from '@/shared/ui/Loading'
import { Line } from 'react-chartjs-2'
import type { Chart, ChartData, Plugin, ScriptableContext } from 'chart.js'
import type { DashboardData } from '@/features/dashboard/types'
import { dlabel, fullDates, kfmt, usd } from '@/shared/format'
import { alpha, useChartTokens, type Tokens } from '@/shared/chart/tokens'
import { baseOptions, SANS } from '@/shared/chart/base'
import { RangeToggle } from '@/features/dashboard/RangeToggle'
import { assumptionPlugin, assumptionStart } from '@/features/dashboard/assumption'
import { actualValues, buildSlots, latestPoint, onSlots, slotLabel, weekIsoDates } from '@/features/dashboard/actual'
type View = 'both' | 'rules' | 'ml'
const dates0 = (iso: string) => `${dlabel(iso.slice(5))}, ${iso.slice(0, 4)}`
const RULES_IDX = 2

// small label on the lowest point of the rules line
const lowPointPlugin = (t: Tokens): Plugin<'line'> => ({
  id: 'lowPoint',
  afterDatasetsDraw(chart: Chart<'line'>, _args, opts: { skip?: number }) {
    const skip = opts?.skip ?? 0
    const meta = chart.getDatasetMeta(RULES_IDX)
    const ds = chart.data.datasets[RULES_IDX]
    if (!ds || meta.hidden) return
    const data = ds.data as number[]
    const rest = data.slice(skip).filter((v) => v != null) // from today on: weeks already over are not part of the outlook
    const i = data.indexOf(Math.min(...rest), skip)
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

export function LeadChart({
  d,
  mlPending,
  mlFailed,
}: {
  d: DashboardData
  mlPending: boolean
  mlFailed: boolean
}) {
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
  const isoWeeks = useMemo(() => weekIsoDates(d.labels, d.kpis.as_of ?? ''), [d])
  const weeks = useMemo(() => isoWeeks.slice(0, n), [isoWeeks, n])
  // every line starts at today's actual cash (the shared start point); weeks already over are drawn faint before it
  const now = useMemo(() => (a ? latestPoint(a) : null), [a])
  const { dates: slotDays, todayIdx } = useMemo(() => buildSlots(weeks, now?.date ?? null), [weeks, now])
  const act = useMemo(() => (a ? actualValues(slotDays, a) : null), [a, slotDays])
  const data = useMemo(() => {
    const cut = (arr: number[]): (number | null)[] => onSlots(arr, slotDays, weeks, todayIdx, now?.balance ?? null)
    const over = (arr: number[]): (number | null)[] => cut(arr).map((v, i) => (todayIdx != null && i < todayIdx ? null : v)) // no band for weeks already over
    const past = (color: string, faint: string) => ({
      segment: { borderColor: (c: { p1DataIndex: number }) => (todayIdx != null && c.p1DataIndex <= todayIdx ? faint : color) },
    })
    const fillGradient = (ctx: ScriptableContext<'line'>) => {
      const area = ctx.chart.chartArea
      if (!area) return undefined
      const g = ctx.chart.ctx.createLinearGradient(0, area.top, 0, area.bottom)
      g.addColorStop(0, alpha(t.cash, 0.22))
      g.addColorStop(1, alpha(t.cash, 0))
      return g
    }
    const chartData: ChartData<'line'> = {
      labels: slotDays.map(slotLabel),
      datasets: [
        {
          label: 'Range low',
          data: over(d.ml?.p10 ?? []),
          borderColor: 'transparent',
          pointRadius: 0,
          fill: false,
          hideTip: true,
          hidden: !showM,
        },
        {
          label: 'Likely range (AI model)',
          data: over(d.ml?.p90 ?? []),
          borderColor: 'transparent',
          backgroundColor: alpha(t.ml, 0.14),
          pointRadius: 0,
          fill: '-1',
          hideTip: true,
          hidden: !showM,
        },
        {
          label: 'Our assumptions',
          data: cut(d.cash_rules),
          borderColor: t.cash,
          backgroundColor: fillGradient,
          borderWidth: 2.4,
          pointRadius: 0,
          pointHoverRadius: 5,
          tension: 0.3,
          fill: true,
          hidden: !showR,
          ...past(t.cash, alpha(t.cash, 0.3)),
        },
        {
          label: 'AI model',
          data: cut(d.ml?.cash_ml ?? []),
          borderColor: t.ml,
          borderWidth: 2.4,
          borderDash: [7, 5],
          pointRadius: 0,
          pointHoverRadius: 5,
          tension: 0.3,
          fill: false,
          hidden: !showM,
          ...past(t.ml, alpha(t.ml, 0.3)),
        },
        ...(floor == null
          ? []
          : [
              {
                label: 'Minimum cash floor',
                data: new Array(slotDays.length).fill(floor),
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
                data: act,
                borderColor: t.inC,
                backgroundColor: t.inC,
                borderWidth: 2.8,
                tension: 0.15,
                spanGaps: true,
                fill: false,
                order: -1, // drawn on top of the forecast lines
                pointRadius: act.map((v, i) => (v == null ? 0 : i === todayIdx ? 6 : 3.5)),
                pointBackgroundColor: act.map((_, i) => (i === todayIdx ? t.surface : t.inC)),
                pointBorderColor: t.inC,
                pointBorderWidth: 2,
                pointHoverRadius: 6,
              },
            ]
          : []),
      ],
    }
    return chartData
  }, [d, t, showR, showM, floor, slotDays, weeks, todayIdx, now, act])

  const options = useMemo(() => baseOptions(t, { yTicks: 9 }), [t])
  const assumeFrom = useMemo(() => assumptionStart(d), [d])
  const assumeSlot = assumeFrom == null ? null : slotDays.indexOf(weeks[assumeFrom] ?? '')
  // react-chartjs-2 reads `plugins` once, when the chart is created, but updates `options` on every render and animates
  // the change. So the plugins are fixed and get the changing values (zone start, first outlook slot) as plugin options.
  const plugins = useMemo(() => [assumptionPlugin(t), lowPointPlugin(t)], [t])
  const zone = assumeSlot == null || assumeSlot < 0 ? null : assumeSlot
  const chartOptions = useMemo(
    () =>
      ({
        ...options,
        plugins: { ...options.plugins, assumptionZone: { from: zone }, lowPoint: { skip: todayIdx ?? 0 } },
      }) as typeof options,
    [options, zone, todayIdx],
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
          <p className="sub">Weekly ending cash, costs included. Same documents, two views: our assumptions and the AI model.</p>
        </div>
        <div className="controls">
          {hasMl && (
            <div className="seg" role="group" aria-label="Timing">
              {(
                [
                  ['both', 'Both'],
                  ['rules', 'Our assumptions'],
                  ['ml', 'AI model'],
                ] as const
              ).map(([k, l]) => (
                <button key={k} className={view === k ? 'on' : ''} aria-pressed={view === k} onClick={() => setView(k)}>
                  {l}
                </button>
              ))}
            </div>
          )}
          <RangeToggle value={n} onChange={setN} />
        </div>
      </div>
      {mlPending ? (
        <BlockLoading tall />
      ) : (
        <div className="chart tall">
          <Line data={data} options={chartOptions} plugins={plugins} />
        </div>
      )}
      {mlFailed && (
        <p className="insight warn">
          The AI model is not available for this run. The blue line is the saved run, which may already include it.
        </p>
      )}
      <div className="legend">
        <span>
          <i style={{ background: t.cash }} />
          {hasMl ? 'Paid on due dates (our assumptions)' : 'Cash balance'}
        </span>
        {hasMl && (
          <span style={{ color: t.ml }}>
            <i className="dash" />
            <span style={{ color: 'var(--text-2)' }}>Paid when customers actually pay (AI model)</span>
          </span>
        )}
        {hasMl && (
          <span>
            <i className="box" style={{ background: alpha(t.ml, 0.35) }} />
            Likely range (AI model)
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
      {now && (
        <p className="fine">
          All lines start on {dates0(now.date)} at the actual cash in Zoho books. The faint line and green dots before it
          are weeks that have already ended: what was forecast against what happened.
        </p>
      )}
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
          {!mlFailed && ' by our assumptions'}, with the lowest point at <b>{usd(minRules)}</b> in the week ending{' '}
          {labels[minI]}.
          {d.ml && (
            <>
              {' '}
              The AI model puts the low at <b>{usd(mlMin)}</b> ({labels[mlMinI]})
              {mlMin > minRules ? ', because customers tend to pay earlier than the due date' : ''}.
            </>
          )}
        </p>
      )}
    </article>
  )
}
