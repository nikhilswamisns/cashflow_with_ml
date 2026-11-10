const RANGES = [13, 26, 52] // weeks, shortest first

/** The 13w / 26w / 52w selector shared by every weekly chart. */
export function RangeToggle({ value, onChange }: { value: number; onChange: (weeks: number) => void }) {
  return (
    <div className="seg" role="group" aria-label="Range">
      {RANGES.map((k) => (
        <button key={k} className={value === k ? 'on' : ''} aria-pressed={value === k} onClick={() => onChange(k)}>
          {k}w
        </button>
      ))}
    </div>
  )
}
