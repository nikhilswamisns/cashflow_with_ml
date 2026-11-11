import { useMemo, useState } from 'react'
import { Plus, Trash2 } from 'lucide-react'
import { saveConfig } from '@/features/config/api'
import {
  META,
  blankRow,
  humanize,
  leafBad,
  problems,
  titleOf,
  toDoc,
  toDraft,
  type Col,
  type Doc,
  type Draft,
  type Entry,
  type Leaf,
  type MapRow,
  type Row,
} from '@/features/config/configModel'
import type { ConfigTable } from '@/features/config/types'
import { useToast } from '@/shared/toast'

let rowId = 1_000_000 // ids for rows added in the form; the model hands out the saved ones

function LeafInput({ leaf, label, onChange }: { leaf: Leaf; label: string; onChange: (s: string) => void }) {
  const bad = leafBad(leaf)
  if (leaf.kind === 'text')
    return <input className="field" aria-label={label} value={leaf.s} onChange={(e) => onChange(e.target.value)} />
  if (leaf.kind === 'date')
    return (
      <input
        className="field"
        type="date"
        aria-label={label}
        aria-invalid={bad}
        value={leaf.s}
        onChange={(e) => onChange(e.target.value)}
      />
    )
  return (
    <input
      className="field num"
      inputMode="decimal"
      aria-label={label}
      aria-invalid={bad}
      value={leaf.s}
      onChange={(e) => onChange(e.target.value)}
    />
  )
}

function MapTable({ k, rows, onChange }: { k: string; rows: MapRow[]; onChange: (rows: MapRow[]) => void }) {
  const meta = META[k]
  const edit = (id: number, patch: Partial<MapRow>) => onChange(rows.map((r) => (r.id === id ? { ...r, ...patch } : r)))
  const names = rows.map((r) => r.key.trim())
  return (
    <>
      <div className="loans-wrap">
        <table className="loans-table cfg-table">
          <thead>
            <tr>
              <th>Item</th>
              <th>{meta?.unit && meta.unit !== '$' ? meta.unit : 'Amount ($)'}</th>
              {!meta?.fixed && <th />}
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => {
              const dup = r.key.trim() !== '' && names.filter((n) => n === r.key.trim()).length > 1
              return (
                <tr key={r.id}>
                  <td>
                    {r.isNew ? (
                      <input
                        className="field"
                        aria-label="Item name"
                        aria-invalid={r.key.trim() === '' || dup}
                        value={r.key}
                        onChange={(e) => edit(r.id, { key: e.target.value })}
                      />
                    ) : (
                      <span title={r.key}>{humanize(r.key)}</span>
                    )}
                  </td>
                  <td>
                    <LeafInput
                      leaf={r.v}
                      label={`${humanize(r.key) || 'New item'} value`}
                      onChange={(s) => edit(r.id, { v: { ...r.v, s } })}
                    />
                  </td>
                  {!meta?.fixed && (
                    <td>
                      <button
                        className="icon-btn"
                        aria-label={`Remove ${humanize(r.key) || 'row'}`}
                        data-tip="Remove"
                        onClick={() => onChange(rows.filter((x) => x.id !== r.id))}
                      >
                        <Trash2 size={16} />
                      </button>
                    </td>
                  )}
                </tr>
              )
            })}
            {rows.length === 0 && (
              <tr>
                <td colSpan={3} className="loans-empty">
                  Nothing here yet.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      {!meta?.fixed && (
        <div className="config-footer">
          <button
            className="btn"
            onClick={() =>
              onChange([...rows, { id: rowId++, key: '', v: { s: '', kind: meta?.kind ?? 'num' }, isNew: true }])
            }
          >
            <Plus size={16} /> Add a row
          </button>
        </div>
      )}
    </>
  )
}

function ListTable({
  items,
  onChange,
}: {
  items: { id: number; leaf: Leaf }[]
  onChange: (items: { id: number; leaf: Leaf }[]) => void
}) {
  return (
    <>
      <div className="loans-wrap">
        <table className="loans-table cfg-table">
          <tbody>
            {items.map((it, i) => (
              <tr key={it.id}>
                <td>
                  <input
                    className="field"
                    aria-label={`Entry ${i + 1}`}
                    aria-invalid={it.leaf.s.trim() === ''}
                    value={it.leaf.s}
                    onChange={(e) =>
                      onChange(
                        items.map((x) => (x.id === it.id ? { ...x, leaf: { ...x.leaf, s: e.target.value } } : x)),
                      )
                    }
                  />
                </td>
                <td>
                  <button
                    className="icon-btn"
                    aria-label={`Remove entry ${i + 1}`}
                    data-tip="Remove"
                    onClick={() => onChange(items.filter((x) => x.id !== it.id))}
                  >
                    <Trash2 size={16} />
                  </button>
                </td>
              </tr>
            ))}
            {items.length === 0 && (
              <tr>
                <td colSpan={2} className="loans-empty">
                  Nothing here yet.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      <div className="config-footer">
        <button className="btn" onClick={() => onChange([...items, { id: rowId++, leaf: { s: '', kind: 'text' } }])}>
          <Plus size={16} /> Add an entry
        </button>
      </div>
    </>
  )
}

function RowsTable({ cols, rows, onChange }: { cols: Col[]; rows: Row[]; onChange: (rows: Row[]) => void }) {
  const set = (i: number, key: string, s: string) =>
    onChange(rows.map((r, n) => (n === i ? { ...r, [key]: { ...r[key], s } } : r)))
  return (
    <>
      <div className="loans-wrap">
        <table className="loans-table cfg-table">
          <thead>
            <tr>
              {cols.map((c) => (
                <th key={c.key}>{c.label}</th>
              ))}
              <th />
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={i}>
                {cols.map((c) => (
                  <td key={c.key}>
                    <LeafInput leaf={r[c.key]} label={`${c.label}, row ${i + 1}`} onChange={(s) => set(i, c.key, s)} />
                  </td>
                ))}
                <td>
                  <button
                    className="icon-btn"
                    aria-label={`Remove row ${i + 1}`}
                    data-tip="Remove"
                    onClick={() => onChange(rows.filter((_, n) => n !== i))}
                  >
                    <Trash2 size={16} />
                  </button>
                </td>
              </tr>
            ))}
            {rows.length === 0 && (
              <tr>
                <td colSpan={cols.length + 1} className="loans-empty">
                  Nothing here yet.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      <div className="config-footer">
        <button className="btn" onClick={() => onChange([...rows, blankRow(cols)])}>
          <Plus size={16} /> Add a row
        </button>
      </div>
    </>
  )
}

function Section({ k, e, onChange }: { k: string; e: Entry; onChange: (e: Entry) => void }) {
  const meta = META[k]
  return (
    <details className="cfg-sec" open>
      <summary>
        <b>{titleOf(k)}</b>
        {meta?.hint && <span className="fine">{meta.hint}</span>}
      </summary>
      {e.t === 'map' && <MapTable k={k} rows={e.rows} onChange={(rows) => onChange({ t: 'map', rows })} />}
      {e.t === 'list' && <ListTable items={e.items} onChange={(items) => onChange({ t: 'list', items })} />}
      {e.t === 'rows' && <RowsTable cols={e.cols} rows={e.rows} onChange={(rows) => onChange({ ...e, rows })} />}
      {e.t === 'groups' &&
        e.groups.map((g, gi) => (
          <div key={g.key} className="cfg-group">
            <h3>{meta?.groupTitles?.[g.key] ?? humanize(g.key)}</h3>
            <RowsTable
              cols={g.cols}
              rows={g.rows}
              onChange={(rows) => onChange({ ...e, groups: e.groups.map((x, n) => (n === gi ? { ...x, rows } : x)) })}
            />
          </div>
        ))}
      {e.t === 'other' && (
        <p className="fine">This setting has a layout the form cannot edit yet. Use the Raw JSON view for it.</p>
      )}
    </details>
  )
}

/** Mounted once the saved file is in (via key in the page), so everything starts from the server's copy. */
export function ConfigForm({ table, saved }: { table: ConfigTable; saved: Doc }) {
  const toast = useToast()
  const [base, setBase] = useState(() => JSON.stringify(toDoc(toDraft(saved))))
  const [draft, setDraft] = useState<Draft>(() => toDraft(saved))
  const [raw, setRaw] = useState<string | null>(null) // text while in the Raw JSON view
  const [saving, setSaving] = useState(false)
  const issues = useMemo(() => problems(draft), [draft])
  const dirty = raw !== null ? true : JSON.stringify(toDoc(draft)) !== base
  const scalars = Object.entries(draft).filter(([, e]) => e.t === 'scalar')
  const others = Object.entries(draft).filter(([, e]) => e.t !== 'scalar')
  const setEntry = (k: string, e: Entry) => setDraft((d) => ({ ...d, [k]: e }))

  function showRaw() {
    if (issues.length) {
      toast('Fix the highlighted values first: ' + issues[0], 'error', 6000)
      return
    }
    setRaw(JSON.stringify(toDoc(draft), null, 2))
  }
  function showForm() {
    try {
      setDraft(toDraft(JSON.parse(raw ?? '{}') as Doc))
      setRaw(null)
    } catch (e) {
      toast('The JSON has an error: ' + (e as Error).message, 'error', 8000)
    }
  }
  function revert() {
    setDraft(toDraft(JSON.parse(base) as Doc))
    setRaw(null)
  }

  async function save() {
    let doc: Doc
    if (raw !== null) {
      try {
        doc = JSON.parse(raw) as Doc
      } catch (e) {
        toast('Error saving config: ' + (e as Error).message, 'error', 8000)
        return
      }
    } else {
      if (issues.length) {
        toast(issues[0], 'error', 6000)
        return
      }
      doc = toDoc(draft)
    }
    setSaving(true)
    try {
      await saveConfig(table, doc)
      setBase(JSON.stringify(toDoc(toDraft(doc))))
      if (raw !== null) setDraft(toDraft(doc))
      toast('Configuration saved.', 'ok')
    } catch (e) {
      toast('Error saving config: ' + (e as Error).message, 'error', 8000)
    } finally {
      setSaving(false)
    }
  }

  return (
    <>
      <div className="cfg-bar">
        <div className="seg" role="group" aria-label="View">
          <button
            className={raw === null ? 'on' : ''}
            aria-pressed={raw === null}
            onClick={() => raw !== null && showForm()}
          >
            Form
          </button>
          <button
            className={raw !== null ? 'on' : ''}
            aria-pressed={raw !== null}
            onClick={() => raw === null && showRaw()}
          >
            Raw JSON
          </button>
        </div>
        {raw === null && dirty && <span className="fine">Unsaved changes</span>}
      </div>
      {raw !== null ? (
        <textarea
          className="json-editor"
          value={raw}
          onChange={(e) => setRaw(e.target.value)}
          spellCheck={false}
          aria-label="Configuration JSON"
          rows={24}
        />
      ) : (
        <>
          {scalars.length > 0 && (
            <div className="cfg-scalars">
              {scalars.map(([k, e]) =>
                e.t === 'scalar' ? (
                  <label key={k} className="cfg-scalar">
                    <span>{titleOf(k)}</span>
                    <span className="cfg-scalar-in">
                      <LeafInput
                        leaf={e.leaf}
                        label={titleOf(k)}
                        onChange={(s) => setEntry(k, { t: 'scalar', leaf: { ...e.leaf, s } })}
                      />
                      {META[k]?.unit && <i>{META[k].unit}</i>}
                    </span>
                    {META[k]?.hint && <small>{META[k].hint}</small>}
                  </label>
                ) : null,
              )}
            </div>
          )}
          {others.map(([k, e]) => (
            <Section key={k} k={k} e={e} onChange={(n) => setEntry(k, n)} />
          ))}
        </>
      )}
      {raw === null && issues.length > 0 && (
        <p className="insight warn">
          {issues.map((m) => (
            <span key={m} className="cfg-issue">
              {m}
            </span>
          ))}
        </p>
      )}
      <div className="config-footer">
        <button
          className="btn primary"
          onClick={() => void save()}
          disabled={saving || (raw === null && issues.length > 0)}
        >
          {saving ? 'Saving…' : 'Save & Invalidate Cache'}
        </button>
        <button className="btn" onClick={revert} disabled={!dirty || saving}>
          Revert changes
        </button>
        <span className="fine">Changes take effect immediately on the next run calculation.</span>
      </div>
    </>
  )
}
