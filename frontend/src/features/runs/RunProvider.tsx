import { createContext, useCallback, useContext, useMemo, type ReactNode } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'
import { useRuns } from '@/features/runs/hooks'
import type { RunInfo } from '@/features/runs/types'
interface RunContext {
  runs: RunInfo[]
  run: RunInfo | undefined
  runId: string
  selectRun: (id: string) => void
  /** Every way of creating a run ends here: refresh the list, select the new run, show its dashboard. */
  afterRun: (id: string) => Promise<void>
}
const Ctx = createContext<RunContext | null>(null)

/** The selected run lives in the URL (?run=<id>) so a page can be reloaded or shared. No ?run= means the newest run. */
export function RunProvider({ children }: { children: ReactNode }) {
  const { data: runs = [] } = useRuns()
  const [params, setParams] = useSearchParams()
  const qc = useQueryClient()
  const navigate = useNavigate()
  const wanted = params.get('run')
  const run = runs.find((r) => r.id === wanted) ?? runs[0]

  const selectRun = useCallback(
    (id: string) =>
      setParams((p) => {
        p.set('run', id)
        return p
      }),
    [setParams],
  )
  const afterRun = useCallback(
    async (id: string) => {
      await qc.invalidateQueries({ queryKey: ['runs'] })
      navigate({ pathname: '/', search: `?run=${id}` })
    },
    [qc, navigate],
  )

  const value = useMemo(
    () => ({ runs, run, runId: run?.id ?? '', selectRun, afterRun }),
    [runs, run, selectRun, afterRun],
  )
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>
}

export function useRun() {
  const v = useContext(Ctx)
  if (!v) throw new Error('useRun must be used inside <RunProvider>')
  return v
}
