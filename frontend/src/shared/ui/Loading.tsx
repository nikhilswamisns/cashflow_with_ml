/** The one loading look for the whole app: grey shapes where the content will be, with a light band sweeping across.
 *  No words on screen (screen readers still hear "Loading"). */

/** A single placeholder for one chart, card or table. */
export function BlockLoading({ tall }: { tall?: boolean }) {
  return <div className={`skel skel-block ${tall ? 'tall' : ''}`} role="status" aria-label="Loading" />
}

/** A whole page: four number cards, one large chart, two smaller ones. Used while a page's data or code is on its way. */
export function PageLoading() {
  return (
    <main className="page" aria-busy="true">
      <div className="kpis" role="status" aria-label="Loading">
        {[0, 1, 2, 3].map((i) => (
          <div key={i} className="skel skel-kpi" />
        ))}
      </div>
      <div className="skel skel-block tall" />
      <div className="skel-pair">
        <div className="skel skel-block" />
        <div className="skel skel-block" />
      </div>
    </main>
  )
}
