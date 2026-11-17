import React, { useState } from 'react'
import { api, useApi, useAct, Shell, Card, Btn, Badge, Tier, Planned, Empty, ErrorBox, Loading, Field, Line, Modal } from '../ui.jsx'

const TIER_HELP = { verified: 'Measured on your own videos', preference: 'What you told the studio you want', observation: 'Seen in research or a reference; not proven', hypothesis: 'A creative idea, untested', experiment: 'Being tried in a production' }
const BLANK = { title: '', body: '', category: 'Storytelling frameworks', tier: 'hypothesis', source: '', applies: '', confidence: 'low', kind: 'note' }

export function Library() {
  const { data, error, loading, reload } = useApi('/knowledge')
  const [act, busy] = useAct()
  const [cat, setCat] = useState('')
  const [tier, setTier] = useState('')
  const [q, setQ] = useState('')
  const [edit, setEdit] = useState(null)
  const items = (data?.items || []).filter(i => (!cat || i.category === cat) && (!tier || i.tier === tier) && (!q || (i.title + ' ' + i.body + ' ' + i.applies).toLowerCase().includes(q.toLowerCase())))
  const count = c => (data?.items || []).filter(i => i.category === c && i.status !== 'retired').length
  const save = () => act('save', () => edit.id ? api('/knowledge/' + edit.id, { method: 'PUT', body: edit }) : api('/knowledge', { method: 'POST', body: edit }), 'Saved').then(r => { if (r) { setEdit(null); reload() } })
  return <Shell crumbs={['Creative library']} right={<Btn kind="primary" onClick={() => setEdit({ ...BLANK })}>Add an item</Btn>}>
    <div className="pad">
      <div><h1>Creative intelligence library</h1><span className="sec">What the Creative Director draws on. Every item says where it came from and how far to trust it.</span></div>
      <ErrorBox error={error} retry={reload} />
      <div className="row" style={{ gap: 8 }}>{Object.entries(TIER_HELP).map(([t, h]) => <button key={t} type="button" className={'choice ' + (tier === t ? 'on' : '')} style={{ flex: '1 1 180px' }} onClick={() => setTier(tier === t ? '' : t)}><Tier tier={t} /><span>{h}</span></button>)}</div>
      <div className="row" style={{ alignItems: 'flex-start' }}>
        <div className="col" style={{ flex: '0 1 260px', gap: 4 }}>
          <input type="search" placeholder="Search the library" value={q} onChange={e => setQ(e.target.value)} aria-label="Search the library" />
          <button className={'scene-item ' + (!cat ? 'on' : '')} onClick={() => setCat('')}><span>All categories</span><span className="mono muted">{data?.items.length || 0}</span></button>
          {(data?.categories || []).map(c => <button key={c} className={'scene-item ' + (cat === c ? 'on' : '')} onClick={() => setCat(c)}><span>{c}</span><span className="mono muted">{count(c)}</span></button>)}
        </div>
        <div className="col grow" style={{ flex: '999 1 520px' }}>
          {loading ? <Loading rows={5} /> : items.length === 0 ? <Empty title="Nothing matches">Clear the filters, or add an item.</Empty> : items.map(i => <Card key={i.id} style={{ opacity: i.status === 'retired' ? 0.55 : 1 }}
            title={i.title} right={<div className="row center" style={{ gap: 8 }}>{i.status === 'retired' && <Badge>Retired</Badge>}<Tier tier={i.tier} /></div>}>
            <p>{i.body}</p>
            <div className="row" style={{ gap: 16 }}><span className="muted">Category: {i.category}</span><span className="muted">Applies to: {i.applies || 'not stated'}</span><span className="muted">Confidence: {i.confidence || 'not stated'}</span><span className="muted">Date: {i.date}</span>{i.uses ? <span className="muted">Used {i.uses}×</span> : null}</div>
            <div className="row between"><span className="muted">Source: {i.source_url ? <a href={i.source_url} target="_blank" rel="noreferrer">{i.source || i.source_url}</a> : (i.source || 'none recorded')}</span>
              <div className="row" style={{ gap: 6 }}><Btn sm onClick={() => setEdit({ ...i })}>Edit</Btn>
                <Btn sm kind="ghost" onClick={() => act('r', () => api('/knowledge/' + i.id, { method: 'PUT', body: { status: i.status === 'retired' ? 'active' : 'retired' } }), i.status === 'retired' ? 'Restored' : 'Retired. The Creative Director no longer uses it.').then(reload)}>{i.status === 'retired' ? 'Restore' : 'Retire'}</Btn>
                <Btn sm kind="ghost danger" onClick={() => window.confirm('Delete this item permanently?') && act('d', () => api('/knowledge/' + i.id, { method: 'DELETE' }), 'Deleted').then(reload)}>Delete</Btn></div></div>
          </Card>)}
          <Card title="Learning from your results" right={<Planned />}><span className="sec">Promoting an item to “Verified” from your own channel's retention data needs the YouTube Analytics connection, which is not built. Until then you can add a verified item by hand, with the measurement as its source.</span></Card>
        </div>
      </div>
    </div>
    {edit && <Modal title={edit.id ? 'Edit item' : 'Add an item'} onClose={() => setEdit(null)} footer={<><Btn onClick={() => setEdit(null)}>Cancel</Btn><Btn kind="primary" busy={busy === 'save'} onClick={save}>Save</Btn></>}>
      <Field label="Title"><input type="text" value={edit.title} onChange={e => setEdit({ ...edit, title: e.target.value })} /></Field>
      <Field label="What it says"><textarea rows={4} value={edit.body} onChange={e => setEdit({ ...edit, body: e.target.value })} /></Field>
      <div className="row"><div className="grow"><Field label="Category"><input type="text" list="cats" value={edit.category} onChange={e => setEdit({ ...edit, category: e.target.value })} /><datalist id="cats">{(data?.categories || []).map(c => <option key={c} value={c} />)}</datalist></Field></div>
        <div className="grow"><Field label="Evidence level" hint={TIER_HELP[edit.tier]}><select value={edit.tier} onChange={e => setEdit({ ...edit, tier: e.target.value })}>{Object.keys(TIER_HELP).map(t => <option key={t}>{t}</option>)}</select></Field></div></div>
      <Field label="Source" hint="Required for a verified item: the measurement it rests on."><input type="text" value={edit.source || ''} onChange={e => setEdit({ ...edit, source: e.target.value })} /></Field>
      <div className="row"><div className="grow"><Field label="Applies to"><input type="text" value={edit.applies || ''} onChange={e => setEdit({ ...edit, applies: e.target.value })} /></Field></div>
        <div className="grow"><Field label="Confidence"><select value={edit.confidence || 'low'} onChange={e => setEdit({ ...edit, confidence: e.target.value })}><option>low</option><option>medium</option><option>high</option></select></Field></div></div>
    </Modal>}
  </Shell>
}

const ST_TONE = { adopted: 'ok', 'approved for trial': 'info', evaluated: 'accent', discovered: 'muted', optional: 'muted', watching: 'warn', rejected: 'danger' }
export function Tools() {
  const { data, error, loading, reload } = useApi('/registry')
  const [act] = useAct()
  const [f, setF] = useState('')
  const [open, setOpen] = useState(null)
  const tools = (data?.tools || []).filter(t => !f || t.status === f)
  return <Shell crumbs={['Tools and skills']}>
    <div className="pad">
      <div><h1>Tools, skills, plugins and MCP servers</h1><span className="sec">A register of what the studio uses and what the Scout has found. Changing a status records your decision; it does not install anything.</span></div>
      <div className="banner info" style={{ borderRadius: 8, border: 0 }}><div><b>Exposit never installs or runs a discovered tool.</b><div className="muted">Evaluate the source yourself, try it in a sandbox without keys, then record the outcome here. Evaluations from the Scout rest on public repository metadata only.</div></div></div>
      <ErrorBox error={error} retry={reload} />
      <div className="row" style={{ gap: 6 }}><Btn sm kind={!f ? 'primary' : ''} onClick={() => setF('')}>All ({data?.tools.length || 0})</Btn>{(data?.statuses || []).map(s => { const n = (data?.tools || []).filter(t => t.status === s).length; return n ? <Btn key={s} sm kind={f === s ? 'primary' : ''} onClick={() => setF(s)}>{s} ({n})</Btn> : null })}</div>
      {loading ? <Loading /> : tools.length === 0 ? <Empty title="No tools with this status" /> : <Card><div className="tablebox"><table>
        <thead><tr><th>Tool</th><th>Category</th><th>Licence</th><th>Maintenance</th><th>Cost</th><th>Hardware</th><th>Status</th><th></th></tr></thead>
        <tbody>{tools.map(t => <React.Fragment key={t.id}><tr>
          <td>{t.url ? <a href={t.url} target="_blank" rel="noreferrer">{t.name}</a> : t.name}</td><td className="sec">{t.category}</td><td className="sec">{t.licence}</td><td className="sec">{t.maintenance}</td><td className="sec">{t.cost}</td><td className="sec">{t.hardware}</td>
          <td><select aria-label={`Status of ${t.name}`} value={t.status} onChange={e => act('s', () => api(`/registry/${encodeURIComponent(t.id)}/status`, { method: 'POST', body: { status: e.target.value } }), r => r.note).then(reload)} style={{ minWidth: 150 }}>{data.statuses.map(s => <option key={s}>{s}</option>)}</select></td>
          <td><Btn sm kind="ghost" onClick={() => setOpen(open === t.id ? null : t.id)}>{open === t.id ? 'Hide' : 'Details'}</Btn></td></tr>
          {open === t.id && <tr><td colSpan={8} style={{ background: 'var(--bg-raised)' }}><div className="col" style={{ gap: 4, padding: 8 }}>
            <div className="row center" style={{ gap: 8 }}><Badge tone={ST_TONE[t.status]}>{t.status}</Badge>{t.stars != null && <span className="muted">{t.stars} stars</span>}{t.interface && <span className="muted">Interface: {t.interface}</span>}</div>
            {t.recommended_use && <Line k="Recommended use">{t.recommended_use}</Line>}{t.risks && <Line k="Risks">{t.risks}</Line>}{t.security && <Line k="Security">{t.security}</Line>}
            {(t.evaluation || t.basis) && <Line k="Basis of this entry">{t.evaluation || t.basis}</Line>}{t.licence_class && <Line k="Licence class">{t.licence_class}</Line>}</div></td></tr>}
        </React.Fragment>)}</tbody></table></div></Card>}
    </div>
  </Shell>
}
