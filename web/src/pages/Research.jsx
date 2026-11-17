import React, { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, useApi, useAct, Shell, Card, Btn, Badge, StateBadge, Planned, Empty, ErrorBox, Loading, Field, Line, fmtTime, fmtDur } from '../ui.jsx'

const ACC = { available: 'ok', 'needs key': 'warn', blocked: 'danger', planned: 'muted' }
const lines = v => (v || []).join('\n')
const unlines = s => s.split('\n').map(x => x.trim()).filter(Boolean)

export function Scout() {
  const { data, error, loading, reload } = useApi('/scout', 5000)
  const [act, busy] = useAct()
  const [kind, setKind] = useState('')
  const [cfg, setCfg] = useState(null)
  useEffect(() => { if (data && !cfg) setCfg({ g: lines(data.settings.scout_github_queries), f: lines(data.settings.scout_feeds), y: lines(data.settings.scout_youtube_channels), h: lines(data.settings.scout_hn_queries) }) }, [data])
  const s = data?.summary
  const items = (data?.items || []).filter(i => !kind || i.kind === kind)
  const last = data?.runs[0]
  const save = () => act('cfg', () => api('/settings', { method: 'PUT', body: { scout_github_queries: unlines(cfg.g), scout_feeds: unlines(cfg.f), scout_youtube_channels: unlines(cfg.y), scout_hn_queries: unlines(cfg.h) } }), 'Sources saved').then(reload)
  return <Shell crumbs={['Scout']} right={<Btn kind="primary" busy={busy === 'run'} onClick={() => act('run', () => api('/scout/run', { method: 'POST' }), 'Scout run queued. It waits for any render to finish.').then(reload)}>Run the Scout now</Btn>}>
    <div className="pad">
      <div><h1>Scout: trends and tool discovery</h1><span className="sec">Collects public signals once a day or on demand. It uses no AI model and costs nothing while idle.</span></div>
      <ErrorBox error={error} retry={reload} />
      {loading ? <Loading rows={4} /> : <>
        <div className="row" style={{ alignItems: 'flex-start' }}>
          <Card title="This week" style={{ flex: '1 1 300px' }}>
            <Line k="New items, last 7 days">{s.total}</Line>{Object.entries(s.counts).map(([k, n]) => <Line key={k} k={k}>{n}</Line>)}<Line k="Collection runs">{s.runs}</Line>
            <Line k="Last run">{last ? fmtTime(last.started) : 'never'}</Line>
            <span className="muted">{s.caveat}</span></Card>
          <Card title="Schedule" style={{ flex: '1 1 300px' }}>
            <label className="row center" style={{ gap: 8 }}><input type="checkbox" checked={!!data.settings.scout_daily_in_app} onChange={e => act('t', () => api('/settings', { method: 'PUT', body: { scout_daily_in_app: e.target.checked } }), 'Saved').then(reload)} /> Run once a day while the studio is open</label>
            <span className="muted">To run daily when the studio is closed, register the Windows scheduled task: <span className="mono">.\scripts\register-scout-task.ps1</span>. It starts a short process and exits.</span>
            {last && <><span className="label">Last run by source</span>{(last.summary.collectors || []).map(c => <div key={c.collector} className="col" style={{ gap: 2 }}><Line k={c.collector}>{c.new} new of {c.seen} seen</Line>{c.errors.map((e, i) => <span key={i} className="err" style={{ fontSize: 12 }}>{e}</span>)}</div>)}
              <span className="muted">No AI model was used; cost $0.</span></>}
          </Card>
          <Card title="What the Scout can and cannot see" style={{ flex: '1 1 380px' }}>{data.access.map(a => <div key={a.source} className="line" style={{ alignItems: 'flex-start' }}><div><div>{a.source}</div><div className="muted">{a.note}</div></div><Badge tone={ACC[a.status]}>{a.status}</Badge></div>)}</Card>
        </div>
        {(s.top_tools.length > 0 || s.top_discussions.length > 0) && <div className="row" style={{ alignItems: 'flex-start' }}>
          {s.top_tools.length > 0 && <Card title="Tools found this week, by stars" className="grow" right={<Link to="/tools" style={{ fontSize: 12 }}>Open the register</Link>}><div className="tablebox"><table><thead><tr><th>Repository</th><th>Stars</th><th>Licence</th><th>Maintenance</th><th>Hardware</th><th>Cost</th></tr></thead>
            <tbody>{s.top_tools.map(t => <tr key={t.url}><td><a href={t.url} target="_blank" rel="noreferrer">{t.title.slice(0, 70)}</a></td><td className="mono">{t.stars}</td><td>{t.licence} <span className="muted">{t.licence_class}</span></td><td className="sec">{t.maintenance}</td><td className="sec">{t.hardware}</td><td className="sec">{t.cost}</td></tr>)}</tbody></table></div>
            <span className="muted">Each one is in the register as “discovered”. None is installed.</span></Card>}
          {s.top_discussions.length > 0 && <Card title="Most discussed" style={{ flex: '1 1 320px' }}>{s.top_discussions.map(d => <Line key={d.url} k={<a href={d.url} target="_blank" rel="noreferrer">{d.title}</a>}>{d.points} points</Line>)}</Card>}
        </div>}
        <Card title="Collected items" right={<div className="row" style={{ gap: 6 }}>{['', 'tool', 'release', 'video', 'discussion', 'article'].map(k => <Btn key={k} sm kind={kind === k ? 'primary' : ''} onClick={() => setKind(k)}>{k || 'All'}</Btn>)}</div>}>
          {items.length === 0 ? <Empty title="Nothing collected yet">Run the Scout. It needs an internet connection; each source that fails is reported above, not hidden.</Empty> :
            <div className="tablebox"><table><thead><tr><th>Item</th><th>Kind</th><th>Source</th><th>Signal</th><th>Collected</th></tr></thead><tbody>{items.slice(0, 120).map(i => <tr key={i.id}><td><a href={i.url} target="_blank" rel="noreferrer">{i.title.slice(0, 110)}</a></td><td>{i.kind}</td><td className="sec">{i.source}</td><td className="sec">{i.signal_class}{i.views != null ? ` · ${i.views} views` : ''}{i.stars != null ? ` · ${i.stars} stars` : ''}</td><td className="muted">{fmtTime(i.fetched)}</td></tr>)}</tbody></table></div>}
        </Card>
        {cfg && <Card title="Sources" right={<Btn busy={busy === 'cfg'} onClick={save}>Save sources</Btn>}>
          <div className="row"><div className="grow"><Field label="GitHub searches, one per line"><textarea rows={5} className="mono" value={cfg.g} onChange={e => setCfg({ ...cfg, g: e.target.value })} /></Field></div>
            <div className="grow"><Field label="Release and blog feeds (Atom or RSS addresses)"><textarea rows={5} className="mono" value={cfg.f} onChange={e => setCfg({ ...cfg, f: e.target.value })} /></Field></div></div>
          <div className="row"><div className="grow"><Field label="YouTube channel ids (start with UC)" hint="Titles and dates from public feeds. View counts need your own free API key in .env."><textarea rows={4} className="mono" value={cfg.y} onChange={e => setCfg({ ...cfg, y: e.target.value })} /></Field></div>
            <div className="grow"><Field label="Hacker News searches"><textarea rows={4} className="mono" value={cfg.h} onChange={e => setCfg({ ...cfg, h: e.target.value })} /></Field></div></div>
        </Card>}
        <Card title="Written trend interpretation" right={<Planned />}><span className="sec">The weekly summary above is counts and links. A written interpretation by the Creative Director, labelled as hypothesis, is designed but not built.</span></Card>
      </>}
    </div>
  </Shell>
}

function RefDetail({ id, onChange }) {
  const { data: r, error, reload } = useApi('/references/' + id, 3000)
  const [act, busy] = useAct()
  if (error) return <ErrorBox error={error} retry={reload} />
  if (!r) return <Loading />
  const a = r.analysis
  return <div className="col">
    <div className="row between"><h2>{r.title}</h2><div className="row" style={{ gap: 8 }}>
      <Btn busy={busy === 'lib'} disabled={!a} onClick={() => act('lib', () => api(`/references/${id}/to-library`, { method: 'POST' }), x => `${x.created.length} observations added to the library`)}>Add measurements to the library</Btn>
      <Btn kind="ghost danger" onClick={() => window.confirm('Delete this reference and its file?') && act('d', () => api('/references/' + id, { method: 'DELETE' }), 'Deleted').then(onChange)}>Delete</Btn></div></div>
    {!a ? <Empty title={r.state === 'failed' ? 'Analysis failed' : 'Analysis is queued or running'}>It waits for any render to finish. See Renders for progress.</Empty> : <>
      {a.notes.map((n, i) => <span key={i} className="muted">{n}</span>)}
      <div className="row" style={{ alignItems: 'flex-start' }}>
        {a.metadata && <Card title="File" style={{ flex: '1 1 240px' }}><Line k="Length">{fmtDur(a.metadata.duration)}</Line><Line k="Picture">{a.metadata.width}×{a.metadata.height} · {a.metadata.fps} fps</Line><Line k="Codecs">{a.metadata.vcodec} / {a.metadata.acodec || 'no audio'}</Line></Card>}
        {a.rhythm && <Card title="Editing rhythm" style={{ flex: '1 1 260px' }}><Line k="Shots">{a.rhythm.shot_count}</Line><Line k="Hard cuts / fades">{a.rhythm.hard_cuts ?? 'n/a'} / {a.rhythm.fades ?? 'n/a'}</Line><Line k="Changes a minute">{a.rhythm.cuts_per_minute}</Line><Line k="Median shot">{a.rhythm.median_shot_s} s</Line><Line k="Shortest / longest">{a.rhythm.shortest_shot_s} / {a.rhythm.longest_shot_s} s</Line><Line k="Time in motion">{a.rhythm.share_of_time_in_motion != null ? Math.round(a.rhythm.share_of_time_in_motion * 100) + '%' : 'n/a'}</Line><span className="muted">{a.rhythm.note}</span></Card>}
        {a.audio && <Card title="Audio" style={{ flex: '1 1 240px' }}>{a.audio.has_audio ? <><Line k="Pauses over 0.35 s">{a.audio.pauses}</Line><Line k="Total pause">{a.audio.pause_total_s} s</Line><Line k="Longest pause">{a.audio.longest_pause_s} s</Line><Line k="Mean / peak level">{a.audio.mean_volume_db} / {a.audio.peak_db} dB</Line></> : <span className="sec">No audio track.</span>}</Card>}
        {a.narration && <Card title="Narration" style={{ flex: '1 1 240px' }}><Line k="Words">{a.narration.words}</Line><Line k="Sentences">{a.narration.sentences}</Line><Line k="Median sentence">{a.narration.median_sentence_words} words</Line>{a.narration.words_per_minute && <Line k="Pace">{a.narration.words_per_minute} words a minute</Line>}<Line k="Questions">{a.narration.questions}</Line><span className="muted">{a.narration.note}</span></Card>}
        {a.image && <Card title="Image" style={{ flex: '1 1 240px' }}><Line k="Size">{a.image.width}×{a.image.height}</Line><div className="row" style={{ gap: 4 }}>{a.image.palette.map(c => <span key={c} className="swatch" title={c} style={{ background: c }} />)}</div></Card>}
      </div>
      {a.transcript && !a.transcript.text && <span className="muted">Transcript: {a.transcript.note || 'not available'}</span>}
      {a.shots?.length > 0 && <Card title={`Shots (${a.shots.length})`}><div className="row">{a.shots.slice(0, 60).map(s => <div key={s.n} className="col" style={{ flex: '0 0 172px', gap: 4 }}>
        {s.frame ? <img className="thumb" alt="" loading="lazy" src={`/api/references/${id}/frames/${s.frame}`} /> : <div className="thumb ph">no frame</div>}
        <div className="row between"><span className="mono muted">{fmtDur(s.start)} · {s.length.toFixed(1)}s</span><span className="muted">{s.begins_with === 'fade' ? 'fade · ' : s.begins_with === 'cut' ? 'cut · ' : ''}{s.motion_level}</span></div>
        <div className="row" style={{ gap: 2 }}>{(s.palette || []).map(c => <span key={c} className="swatch" title={c} style={{ background: c }} />)}</div></div>)}</div></Card>}
    </>}
  </div>
}

export function References() {
  const { data, error, loading, reload } = useApi('/references', 4000)
  const [act, busy] = useAct()
  const [sel, setSel] = useState(null)
  const [f, setF] = useState({ title: '', transcript: '', url: '', file: null })
  const add = () => { const fd = new FormData(); fd.append('title', f.title); fd.append('transcript', f.transcript); fd.append('url', f.url); if (f.file) fd.append('file', f.file)
    act('add', () => api('/references', { method: 'POST', form: fd }), 'Reference added. Analysis is queued.').then(r => { if (r) { setF({ title: '', transcript: '', url: '', file: null }); setSel(r.id); reload() } }) }
  const refs = data?.references || []
  return <Shell crumbs={['Reference analysis']}>
    <div className="pad">
      <div><h1>Reference analysis</h1><span className="sec">Measures how a reference is built: rhythm, motion, palette, pauses and narration pace. It stores numbers and structure, never footage or wording to copy.</span></div>
      <ErrorBox error={error} retry={reload} />
      <div className="row" style={{ alignItems: 'flex-start' }}>
        <div className="col" style={{ flex: '1 1 340px' }}>
          <Card title="Add a reference">
            <Field label="Title"><input type="text" value={f.title} onChange={e => setF({ ...f, title: e.target.value })} /></Field>
            <Field label="File" hint="A video (mp4, mov, mkv, webm), a screenshot or image, or a text transcript. Upload only material you are allowed to use."><input type="file" accept=".mp4,.mov,.mkv,.webm,.png,.jpg,.jpeg,.webp,.txt,.md" onChange={e => setF({ ...f, file: e.target.files[0] || null })} /></Field>
            <Field label="Transcript (optional)"><textarea rows={3} value={f.transcript} onChange={e => setF({ ...f, transcript: e.target.value })} /></Field>
            <Field label="Web address (optional)" hint="Recorded as a link only. Exposit does not download videos from platforms."><input type="url" value={f.url} onChange={e => setF({ ...f, url: e.target.value })} /></Field>
            <Btn kind="primary" busy={busy === 'add'} disabled={!f.file && !f.transcript.trim() && !f.url.trim()} onClick={add}>Add and analyse</Btn></Card>
          <Card title="References">{loading ? <Loading rows={2} /> : refs.length === 0 ? <span className="sec">None yet.</span> : refs.map(r => <button key={r.id} className={'scene-item ' + (sel === r.id ? 'on' : '')} onClick={() => setSel(r.id)}><span>{r.title}</span><StateBadge state={r.state} /></button>)}</Card>
          <Card title="Not supported">{(data?.unsupported || []).map(u => <div className="line" key={u.capability} style={{ alignItems: 'flex-start' }}><div><div>{u.capability}</div><div className="muted">{u.why}</div></div><Planned>Not built</Planned></div>)}</Card>
        </div>
        <div style={{ flex: '999 1 560px' }}>{sel ? <RefDetail key={sel} id={sel} onChange={() => { setSel(null); reload() }} /> : <Empty title="Choose or add a reference">The analysis appears here.</Empty>}</div>
      </div>
    </div>
  </Shell>
}
