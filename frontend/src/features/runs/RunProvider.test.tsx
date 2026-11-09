import { screen, waitFor } from '@testing-library/react'
import { RunProvider, useRun } from './RunProvider'
import { renderApp, stubApi } from '@/test/utils'

const runs = [
  { run_id: 'new', run_date: '2026-10-30', created_at: '2026-10-28T11:06:00Z' },
  { run_id: 'old', run_date: '2026-10-23', created_at: '2026-10-27T13:06:00Z' },
]
function Probe() {
  const { run, runId } = useRun()
  return <p>{run ? `${runId}|${run.label}` : 'none'}</p>
}
afterEach(() => vi.unstubAllGlobals())

describe('RunProvider', () => {
  it('selects the newest run when the URL has no ?run=', async () => {
    stubApi({ 'GET /runs': runs })
    renderApp(
      <RunProvider>
        <Probe />
      </RunProvider>,
    )
    await waitFor(() => expect(screen.getByText(/^new\|/)).toBeInTheDocument())
  })
  it('selects the run named in ?run=', async () => {
    stubApi({ 'GET /runs': runs })
    renderApp(
      <RunProvider>
        <Probe />
      </RunProvider>,
      { route: '/matrix?run=old' },
    )
    await waitFor(() => expect(screen.getByText(/^old\|Oct 23, 2026$/)).toBeInTheDocument())
  })
  it('ignores an unknown ?run= and uses the newest', async () => {
    stubApi({ 'GET /runs': runs })
    renderApp(
      <RunProvider>
        <Probe />
      </RunProvider>,
      { route: '/?run=gone' },
    )
    await waitFor(() => expect(screen.getByText(/^new\|/)).toBeInTheDocument())
  })
})
