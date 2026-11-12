import { act, fireEvent, render, screen } from '@testing-library/react'
import { KpiCard, resetKpiSync } from './KpiCard'

const slides = [
  { view: 'Our assumptions', value: '−$195,383', tone: 'neg', note: 'Week ending Dec 25, 2026 · our assumptions' },
  { view: 'AI model', value: '−$81,331', tone: 'neg', note: 'Week ending Nov 20, 2026 · AI model' },
]

describe('KpiCard', () => {
  beforeEach(() => {
    resetKpiSync()
    vi.useFakeTimers()
  })
  afterEach(() => vi.useRealTimers())

  it('shows a single number with no swapping or dots when there is one view', () => {
    render(<KpiCard label="Lowest cash ahead" slides={[slides[0]]} />)
    expect(screen.getByText('−$195,383')).toBeInTheDocument()
    expect(screen.queryByRole('button')).toBeNull()
  })

  it('swaps to the AI model number every 3 seconds and labels which view is showing', () => {
    render(<KpiCard label="Lowest cash ahead" slides={slides} />)
    const chip = () => document.querySelector('.kpi-view')?.textContent
    expect(chip()).toBe('Our assumptions')
    act(() => void vi.advanceTimersByTime(3000))
    expect(chip()).toBe('AI model')
    act(() => void vi.advanceTimersByTime(3000))
    expect(chip()).toBe('Our assumptions')
  })

  it('pauses while hovered, and the dots pick a view', () => {
    render(<KpiCard label="Lowest cash ahead" slides={slides} />)
    const card = document.querySelector('.kpi-swap') as HTMLElement
    fireEvent.mouseEnter(card)
    act(() => void vi.advanceTimersByTime(9000))
    expect(document.querySelector('.kpi-view')?.textContent).toBe('Our assumptions')
    fireEvent.click(screen.getByRole('button', { name: 'AI model' }))
    expect(document.querySelector('.kpi-view')?.textContent).toBe('AI model')
  })

  it('keeps every card on the same view: the timer moves them together and a dot on one card moves all', () => {
    render(
      <>
        <KpiCard label="Lowest cash ahead" slides={slides} />
        <KpiCard label="Weeks below zero" slides={[{ ...slides[0], value: '10' }, { ...slides[1], value: '4' }]} />
      </>,
    )
    const chips = () => [...document.querySelectorAll('.kpi-view')].map((e) => e.textContent)
    expect(chips()).toEqual(['Our assumptions', 'Our assumptions'])
    act(() => void vi.advanceTimersByTime(3000))
    expect(chips()).toEqual(['AI model', 'AI model'])
    fireEvent.click(screen.getAllByRole('button', { name: 'Our assumptions' })[1])
    expect(chips()).toEqual(['Our assumptions', 'Our assumptions'])
    fireEvent.mouseEnter(document.querySelectorAll('.kpi-swap')[1])   // hovering one card pauses all of them
    act(() => void vi.advanceTimersByTime(9000))
    expect(chips()).toEqual(['Our assumptions', 'Our assumptions'])
  })

  it('shows both numbers stacked, with no swapping, when the user prefers reduced motion', () => {
    vi.stubGlobal('matchMedia', () => ({ matches: true, addEventListener() {}, removeEventListener() {} }))
    render(<KpiCard label="Lowest cash ahead" slides={slides} />)
    expect(screen.getByText('−$195,383')).toBeInTheDocument()
    expect(screen.getByText('−$81,331')).toBeInTheDocument()
    vi.unstubAllGlobals()
  })
})
