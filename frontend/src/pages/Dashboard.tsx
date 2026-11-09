import { useOutletContext } from 'react-router-dom'
import { useDashboard } from '../data/hooks'
import type { ShellCtx } from '../components/Shell'
import { Kpis } from '../components/Kpis'
import { LeadChart } from '../charts/LeadChart'
import { ReceiptsChart } from '../charts/ReceiptsChart'
import { ArApChart, InOutChart, StreamsChart } from '../charts/OtherCharts'

export function Dashboard() {
  const { runId } = useOutletContext<ShellCtx>()
  const { data: d, error, mlPending, mlFailed, receiptsPending } = useDashboard(runId)
  if (error) return <main className="page"><div className="card placeholder"><h2>This run could not be loaded</h2><p>{error.message}</p></div></main>
  if (!d) return <main className="page"><div className="loading">Loading…</div></main>
  return (
    <main className="page">
      <Kpis d={d} />
      <LeadChart d={d} mlPending={mlPending} mlFailed={mlFailed} />
      <ReceiptsChart d={d} pending={receiptsPending} />
      <section className="grid2"><ArApChart d={d} /><InOutChart d={d} /></section>
      <StreamsChart d={d} />
    </main>
  )
}
