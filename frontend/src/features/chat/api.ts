import type { Answer } from '@/features/chat/types'
// Placeholder until the AI backend exists (separate track).
export async function askQuestion(_runId: string, _q: string): Promise<Answer> {
  return {
    html: 'In the real build this runs a lookup on the payment history and answers with the figures and the run it used. This sample only has the first answer.',
    source: 'Sample reply',
  }
}
