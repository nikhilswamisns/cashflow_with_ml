import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from 'react'
import { useDismissToast, useToast } from '@/shared/toast'
import { useRun } from '@/features/runs/RunProvider'
import { syncZoho } from '@/features/sync/api'
interface SyncContext {
  sync: (runDate?: string) => Promise<void>
  syncing: boolean
}
const Ctx = createContext<SyncContext | null>(null)

/** One Zoho sync flow shared by the top-bar menu and the Data & sync page, so "syncing" is the same everywhere. */
export function SyncProvider({ children }: { children: ReactNode }) {
  const { afterRun } = useRun()
  const toast = useToast()
  const dismiss = useDismissToast()
  const [syncing, setSyncing] = useState(false)

  const sync = useCallback(
    async (runDate?: string) => {
      if (syncing) return
      setSyncing(true)
      const wait = toast('Syncing from Zoho… this can take a minute.', 'info', 0)
      try {
        const r = await syncZoho(runDate)
        await afterRun(r.run_id)
        toast(
          `Synced from Zoho. New run created${r.live_opening_cash ? ` (live bank $${Math.round(r.live_opening_cash).toLocaleString('en-US')})` : ''}.`,
          'ok',
        )
      } catch (e) {
        const msg = (e as Error).message
        toast(
          /\(500\)/.test(msg)
            ? 'Zoho sync failed on the server (500). Check the Zoho connection and the server log.'
            : 'Zoho sync: ' + msg,
          'error',
          8000,
        )
      } finally {
        dismiss(wait)
        setSyncing(false)
      }
    },
    [syncing, afterRun, toast, dismiss],
  )

  const value = useMemo(() => ({ sync, syncing }), [sync, syncing])
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>
}

export function useSync() {
  const v = useContext(Ctx)
  if (!v) throw new Error('useSync must be used inside <SyncProvider>')
  return v
}
