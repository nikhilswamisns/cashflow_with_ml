import { CHAT_ENABLED } from '@/features/chat/enabled'
import {
  Database,
  LayoutDashboard,
  ListChecks,
  MessageSquare,
  Scale,
  SlidersHorizontal,
  Table2,
  TrendingUp,
  type LucideIcon,
} from 'lucide-react'

export interface NavItem {
  to: string
  label: string
  icon: LucideIcon
}
export interface NavGroup {
  label: string
  items: NavItem[]
}

/** Add a page here and in app/App.tsx; the rail and the page title follow. */
export const NAV: NavGroup[] = [
  {
    label: 'Forecast',
    items: [
      { to: '/', label: 'Dashboard', icon: LayoutDashboard },
      { to: '/matrix', label: 'Cash forecast', icon: Table2 },
      { to: '/revenue', label: 'Revenue forecast', icon: TrendingUp },
      { to: '/actions', label: 'Actions', icon: ListChecks },
      { to: '/working-capital', label: 'Working capital', icon: Scale },
    ],
  },
  {
    label: 'Workspace',
    items: [
      { to: '/data', label: 'Data & sync', icon: Database },
      { to: '/assumptions', label: 'Assumptions', icon: SlidersHorizontal },
    ],
  },
  ...(CHAT_ENABLED ? [{ label: 'Assistant', items: [{ to: '/chat', label: 'Ask Gutster', icon: MessageSquare }] }] : []),
]
export const TITLES: Record<string, string> = Object.fromEntries(
  NAV.flatMap((g) => g.items.map((i) => [i.to, i.label])),
)
