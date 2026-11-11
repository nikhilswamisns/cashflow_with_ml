import { useDashboard } from '@/features/dashboard/hooks'
import { useRun } from '@/features/runs/RunProvider'
import { Kpis } from '@/features/dashboard/Kpis'
import { FundingGap } from '@/features/dashboard/FundingGap'
import { LeadChart } from '@/features/dashboard/LeadChart'
import { ReceiptsChart } from '@/features/dashboard/ReceiptsChart'
import { ArApChart, InOutChart, StreamsChart } from '@/features/dashboard/OtherCharts'
export function DashboardPage() {
  const { runId, run } = useRun()
  const { data: d, error, mlPending, mlFailed, receiptsPending } = useDashboard(runId)
  if (error)
    return (
      <main className="page">
        <div className="card placeholder">
          <h2>This run could not be loaded</h2>
          <p>{error.message}</p>
        </div>
      </main>
    )
  if (!d)
    return (
      <main className="page">
        <div className="loading">Loading…</div>
      </main>
    )
  return (
    <main className="page">
      <Kpis d={d} syncedLabel={run?.syncedLabel} />
      <LeadChart d={d} mlPending={mlPending} mlFailed={mlFailed} />
      <FundingGap d={d} />
      <ReceiptsChart d={d} pending={receiptsPending} />
      <section className="grid2">
        <ArApChart d={d} />
        <InOutChart d={d} />
      </section>
      <StreamsChart d={d} />
    </main>
  )
}
