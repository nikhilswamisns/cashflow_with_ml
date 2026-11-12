import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderApp, stubApi } from '@/test/utils'
import { ChatProvider } from '@/features/chat/ChatProvider'
import { ChatThread } from '@/features/chat/ChatThread'

const ndjson = (events: object[]) => new Response(events.map((e) => JSON.stringify(e)).join('\n') + '\n', { status: 200 })

describe('ChatThread', () => {
  it('shows starter questions only while the chat is empty, and streams the answer', async () => {
    window.HTMLElement.prototype.scrollIntoView = vi.fn()
    stubApi({
      'POST /chat': ndjson([
        { type: 'tool', tool: 'cash_outlook' },
        { type: 'delta', text: 'Cash ends at ' },
        { type: 'delta', text: '**negative $26,201**.' },
        { type: 'done', tools_used: [], run_date: null },
      ]),
    })
    renderApp(
      <ChatProvider>
        <ChatThread />
      </ChatProvider>,
    )
    const starter = screen.getByRole('button', { name: 'Where is our cash going?' })
    await userEvent.click(starter)
    await waitFor(() => expect(screen.getByText('negative $26,201')).toBeInTheDocument())
    expect(screen.queryByRole('button', { name: 'Where is our cash going?' })).not.toBeInTheDocument()
    expect(screen.getByText('Where is our cash going?')).toBeInTheDocument() // now only as the asked question
  })

  it('shows a readable message when the server has no chat route', async () => {
    window.HTMLElement.prototype.scrollIntoView = vi.fn()
    stubApi({})
    renderApp(
      <ChatProvider>
        <ChatThread />
      </ChatProvider>,
    )
    await userEvent.type(screen.getByLabelText('Ask a question'), 'hi{enter}')
    await waitFor(() => expect(screen.getByText(/not available on this server/i)).toBeInTheDocument())
  })

  it('disables the mic with a reason when the browser cannot record', () => {
    window.HTMLElement.prototype.scrollIntoView = vi.fn()
    stubApi({})
    renderApp(
      <ChatProvider>
        <ChatThread />
      </ChatProvider>,
    )
    const mic = screen.getByRole('button', { name: 'Speak your question' })
    expect(mic).toBeDisabled()
    expect(mic).toHaveAttribute('title', expect.stringMatching(/not supported/i))
  })
})
