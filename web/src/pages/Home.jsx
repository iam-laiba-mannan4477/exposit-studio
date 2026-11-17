import React, { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api, useApi, useAct, Shell, Card, Btn, Badge, StateBadge, Planned, Empty, ErrorBox, Loading, Field, Seg, Line, Progress, fmtTime, fmtDur } from '../ui.jsx'

const STAGES = ['research', 'strategy', 'script', 'storyboard', 'produce', 'export']
export const stageOf = p => {
  if (p.final === 'approved') return ['ok', 'Approved by you']
  if (p.final === 'awaiting_approval') return ['warn', 'Final video needs your approval']
  if (p.final === 'checks_failed') return ['danger', 'Final checks failed']
  for (const s of STAGES) { const st = p.stages?.[s]?.state; if (st && st !== 'passed') return [st === 'failed' ? 'danger' : st === 'running' ? 'info' : st === 'pending' ? 'muted' : 'warn', `${s[0].toUpperCase() + s.slice(1)}: ${st.replace('_', ' ')}`] }
  return ['muted', 'Not started']
}
export const nextTab = p => p.has_video ? 'export' : (STAGES.find(s => p.stages?.[s]?.state !== 'passed') || 'export')

function Thumb({ p }) {
  const [bad, setBad] = useState(false)
  if (bad) return <div className="thumb ph">No frame yet</div>
  return <img className="thumb" alt="" style={p.brief.format === '9:16' ? { objectFit: 'contain' } : undefined} src={`/api/productions/${p.id}/media/still/s3`} onError={() => setBad(true)} />
}

function StartButtons() {
  const nav = useNavigate()
  const [act, busy] = useAct()
  return <div className="row">
    <Btn kind="primary" onClick={() => nav('/new')}>New production</Btn>
    <Btn busy={busy === 'ex'} title="Builds the 60-second sample from prepared role outputs. Narration and rendering run on this machine."
      onClick={() => act('ex', () => api('/productions/from-example', { method: 'POST', body: { format: '16:9' } })).then(r => r && nav(`/p/${r.id}/produce`))}>Create from example</Btn>
    <Btn busy={busy === 'exv'} title="The same sample, laid out for Instagram Reels and YouTube Shorts (9:16)."
      onClick={() => act('exv', () => api('/productions/from-example', { method: 'POST', body: { format: '9:16' } })).then(r => r && nav(`/p/${r.id}/produce`))}>Vertical example</Btn>
  </div>
}

export function Home() {
  const prods = useApi('/productions', 4000)
  const jobs = useApi('/jobs?limit=8', 2500)
  const health = useApi('/health')
  const scout = useApi('/scout')
  const list = prods.data || []
  const last = list[0]
  const active = (jobs.data?.jobs || []).filter(j => ['running', 'queued'].includes(j.state))
  const h = health.data
  return <Shell crumbs={['Home']}>
    <div className="pad">
      <div className="row between"><h1>Home</h1><StartButtons /></div>
      <ErrorBox error={prods.error} retry={prods.reload} />
      {h && (!h.voice_engines[0].available || !h.ffmpeg) && <div className="err">Setup is incomplete: {!h.ffmpeg && 'FFmpeg was not found. '}{!h.voice_engines[0].available && h.voice_engines[0].note} See the README.</div>}
      <div className="row">
        <Card className="grow" style={{ flex: '2 1 560px' }}>
          {prods.loading ? <Loading rows={2} /> : !last ? <Empty title="No productions yet">Start with a topic, or build the 60-second example to check that narration and rendering work on this machine.</Empty> :
            <div className="row" style={{ alignItems: 'flex-start' }}>
              <div style={{ flex: '0 1 280px', minWidth: 200 }}><Thumb p={last} /></div>
              <div className="col grow">
                <span className="label">Continue</span>
                <div style={{ fontSize: 20, lineHeight: '28px', fontWeight: 600 }}>{last.title}</div>
                <span className="muted">{last.brief.format === '9:16' ? '9:16 vertical' : '16:9'} · {last.brief.quality} · {last.brief.duration} seconds · English · Review mode: {last.brief.review_mode === 'final_only' ? 'final only' : 'every gate'}</span>
                <div className="row" style={{ gap: 8 }}><Badge tone={stageOf(last)[0]}>{stageOf(last)[1]}</Badge>{last.duration && <Badge>{fmtDur(last.duration)} rendered</Badge>}</div>
                <div className="row" style={{ gap: 8 }}><Link className="btn primary" to={`/p/${last.id}/${nextTab(last)}`}>Open</Link><Link className="btn" to={`/p/${last.id}/strategy`}>See the strategy</Link></div>
              </div>
            </div>}
        </Card>
        <Card title="Render queue" right={<Link to="/renders" style={{ fontSize: 12 }}>All jobs and agent tasks</Link>} style={{ flex: '1 1 320px' }}>
          {active.length === 0 ? <span className="sec">Nothing is running.</span> : active.map(j => <div key={j.id} className="col" style={{ gap: 6 }}>
            <div className="row between"><span>{j.title || j.kind}</span><StateBadge state={j.state} /></div>
            <span className="muted">{j.message}</span>{j.state === 'running' && <Progress value={j.progress} />}</div>)}
          <span className="muted">One job runs at a time on this machine. Paid services: none in use.</span>
        </Card>
      </div>
      <div className="col">
        <div className="row between"><h2>Recent productions</h2><Link to="/productions" style={{ fontSize: 12 }}>All productions</Link></div>
        <div className="row">{list.slice(0, 3).map(p => <Link key={p.id} to={`/p/${p.id}/${nextTab(p)}`} className="card" style={{ flex: '1 1 280px', maxWidth: 440, color: 'inherit' }}>
          <Thumb p={p} /><b style={{ fontWeight: 600 }}>{p.title}</b><div className="row between"><Badge tone={stageOf(p)[0]}>{stageOf(p)[1]}</Badge><span className="muted">{fmtTime(p.updated)}</span></div></Link>)}
          {!prods.loading && list.length === 0 && <span className="sec">Productions you create appear here.</span>}</div>
      </div>
      <div className="row" style={{ alignItems: 'flex-start' }}>
        <Card title="Trend intelligence" right={<Link to="/scout" style={{ fontSize: 12 }}>Open Scout</Link>} style={{ flex: '1 1 320px' }}>
          {scout.data ? <>
            <Line k="New items in the last 7 days">{scout.data.summary.total}</Line>
            <Line k="Collection runs this week">{scout.data.summary.runs}</Line>
            <Line k="Daily run inside the studio">{scout.data.settings.scout_daily_in_app ? 'On' : 'Off'}</Line>
            <span className="muted">Public signals only. The Scout never claims to know another creator's retention.</span></> : <Loading rows={2} />}
        </Card>
        <Card title="This machine" style={{ flex: '1 1 320px' }}>
          {h ? <><Line k="AI provider">{h.provider.provider}{h.provider.paid ? ' (paid)' : ' (no API cost)'}</Line>
            <Line k="Voice">{h.voice_engines[0].available ? 'Kokoro, local' : 'Not installed'}</Line>
            <Line k="Memory available">{h.memory.available_mb} of {h.memory.total_mb} MB</Line>
            <Line k="Free disk">{h.disk_free_gb} GB</Line></> : <Loading rows={2} />}
        </Card>
        <Card title="Not built yet" style={{ flex: '1 1 320px' }}>
          <Line k="Square 1:1 format"><Planned /></Line><Line k="Publishing to a channel"><Planned /></Line>
          <Line k="Cloud rendering"><Planned>Optional, paid · off</Planned></Line><Line k="Brand kits"><Planned /></Line>
        </Card>
      </div>
    </div>
  </Shell>
}

export function Productions() {
  const { data, error, loading, reload } = useApi('/productions', 4000)
  const [act] = useAct()
  return <Shell crumbs={['Productions']}>
    <div className="pad">
      <div className="row between"><h1>Productions</h1><StartButtons /></div>
      <ErrorBox error={error} retry={reload} />
      {loading ? <Loading /> : !data?.length ? <Empty title="No productions yet">Create one from a topic, or build the example.</Empty> :
        <Card><div className="tablebox"><table><thead><tr><th>Title</th><th>Status</th><th>Length</th><th>Format · review</th><th>Updated</th><th></th></tr></thead>
          <tbody>{data.map(p => <tr key={p.id}><td><Link to={`/p/${p.id}/${nextTab(p)}`}>{p.title}</Link></td><td><Badge tone={stageOf(p)[0]}>{stageOf(p)[1]}</Badge></td>
            <td className="mono">{p.duration ? fmtDur(p.duration) : `${p.brief.duration}s target`}</td><td>{p.brief.format === '9:16' ? '9:16 vertical' : '16:9'} · {p.brief.review_mode === 'final_only' ? 'final only' : 'every gate'}</td><td className="muted">{fmtTime(p.updated)}</td>
            <td><Btn sm kind="ghost danger" onClick={() => window.confirm(`Delete "${p.title}" and all of its files? This cannot be undone.`) && act('d', () => api(`/productions/${p.id}`, { method: 'DELETE' }), 'Production deleted').then(reload)}>Delete</Btn></td></tr>)}</tbody></table></div></Card>}
    </div>
  </Shell>
}

export function NewProduction() {
  const nav = useNavigate()
  const settings = useApi('/settings')
  const health = useApi('/health')
  const [act, busy] = useAct()
  const [f, setF] = useState({ topic: '', title: '', audience: 'decide', duration: 60, format: '16:9', quality: '1080p', theme: 'premium-technical', voice: '', voice_speed: 1.0, review_mode: 'final_only', objective: '' })
  const [audio, setAudio] = useState('')
  const set = (k, v) => setF(x => ({ ...x, [k]: v }))
  const s = settings.data
  const voice = f.voice || s?.settings.voice || 'am_michael'
  const prov = s?.provider
  const preview = () => act('pv', async () => { const b = await api('/voices/preview', { method: 'POST', body: { voice, speed: f.voice_speed }, blob: true }); setAudio(URL.createObjectURL(b)) })
  const create = () => act('create', () => api('/productions', { method: 'POST', body: { ...f, voice } })).then(r => r && nav(`/p/${r.id}/research`))
  return <Shell crumbs={['Productions', 'New production']} right={<Btn onClick={() => nav('/')}>Cancel</Btn>}>
    <div className="pad"><div className="row" style={{ alignItems: 'flex-start', gap: 24 }}>
      <div className="col grow" style={{ flex: '999 1 520px', gap: 16 }}>
        <h1>New production</h1>
        <Card title="1. Topic">
          <Field label="What should the video explain?"><textarea rows={3} value={f.topic} onChange={e => set('topic', e.target.value)} placeholder="For example: how a Kubernetes rolling update replaces pods without downtime" /></Field>
          <div className="row"><div className="grow"><Field label="Title (optional)"><input type="text" value={f.title} onChange={e => set('title', e.target.value)} /></Field></div>
            <div className="grow"><Field label="Learning objective (optional)" hint="Leave empty and the Creative Director states one."><input type="text" value={f.objective} onChange={e => set('objective', e.target.value)} /></Field></div></div>
          <span className="muted">You can attach text documents for research on the Research tab after creating the production. Reference videos are analysed under Reference analysis.</span>
        </Card>
        <Card title="2. Audience and length">
          <div className="row"><div style={{ flex: '2 1 320px' }}><Field label="Audience level" hint="“Let it decide” leaves this to the Creative Director, who records what it assumed and why.">
            <Seg value={f.audience} onChange={v => set('audience', v)} options={[{ value: 'decide', label: 'Let it decide' }, { value: 'beginner', label: 'Beginner' }, { value: 'intermediate', label: 'Intermediate' }, { value: 'advanced', label: 'Advanced' }]} /></Field></div>
            <div style={{ flex: '1 1 160px' }}><Field label="Length"><select value={f.duration} onChange={e => set('duration', +e.target.value)}>{[30, 45, 60, 90, 120].map(d => <option key={d} value={d}>{d} seconds</option>)}</select></Field></div></div>
        </Card>
        <Card title="3. Format and look">
          <span className="label">Format</span>
          <div className="row"><button type="button" className={'choice ' + (f.format === '16:9' ? 'on' : '')} onClick={() => set('format', '16:9')}><b>16:9 landscape</b><span>YouTube, courses, presentations</span></button>
            <button type="button" className={'choice ' + (f.format === '9:16' ? 'on' : '')} onClick={() => set('format', '9:16')}><b>9:16 vertical</b><span>Instagram Reels, YouTube Shorts, TikTok</span></button>
            <button type="button" className="choice" disabled><div className="row between"><b>1:1 square</b><Planned /></div><span>Social feeds</span></button></div>
          <div className="row"><div className="grow"><Field label="Resolution" hint="4K is not offered: it is impractical on this hardware.">
            <Seg value={f.quality} onChange={v => set('quality', v)} options={[{ value: '1080p', label: '1080p' }, { value: '720p', label: '720p, faster' }, { value: '540p', label: '540p, draft' }]} /></Field></div>
            <div className="grow"><Field label="Theme" hint="Animation style per scene is chosen by the Creative Director and can be overridden."><select value={f.theme} onChange={e => set('theme', e.target.value)}>{(health.data?.themes || ['premium-technical']).map(t => <option key={t}>{t}</option>)}</select></Field></div></div>
        </Card>
        <Card title="4. Narration">
          <div className="row" style={{ alignItems: 'flex-end' }}>
            <div className="grow"><Field label="Language"><select disabled><option>English</option></select></Field></div>
            <div className="grow"><Field label="Voice (Kokoro, runs on this machine)"><select value={voice} onChange={e => set('voice', e.target.value)}>{(s?.voices?.length ? s.voices : [voice]).map(v => <option key={v}>{v}</option>)}</select></Field></div>
            <div className="grow"><Field label={`Speed ${f.voice_speed.toFixed(2)}×`}><input type="range" min="0.8" max="1.3" step="0.02" value={f.voice_speed} onChange={e => set('voice_speed', +e.target.value)} /></Field></div>
            <Btn busy={busy === 'pv'} onClick={preview}>Preview voice</Btn></div>
          {audio && <audio controls autoPlay src={audio} style={{ width: '100%' }} />}
          <div className="row between"><span className="sec">Urdu and other languages</span><Planned /></div>
        </Card>
        <Card title="5. Review and budget">
          <span className="label">Review mode</span>
          <div className="row">
            <button type="button" className={'choice ' + (f.review_mode === 'final_only' ? 'on' : '')} onClick={() => set('review_mode', 'final_only')}><b>Final only</b><span>Research, script and storyboard pass by themselves when their quality gates pass. You approve the final video.</span></button>
            <button type="button" className={'choice ' + (f.review_mode === 'every_gate' ? 'on' : '')} onClick={() => set('review_mode', 'every_gate')}><b>Every gate</b><span>Stops for you at script, storyboard and the final video.</span></button></div>
          <Line k="Paid services for this production"><Badge tone="ok">None · $0</Badge></Line>
          <Line k="Premium voices, cloud rendering, generated media"><Planned>Optional, paid · off</Planned></Line>
          <span className="muted">Publishing is never automatic.</span>
        </Card>
      </div>
      <div style={{ flex: '1 1 300px', position: 'sticky', top: 0 }}>
        <Card title="Summary">
          <Line k="Audience">{f.audience === 'decide' ? 'Creative Director decides' : f.audience}</Line><Line k="Length">{f.duration} seconds</Line>
          <Line k="Format">{f.format} · {f.quality} · 30 fps</Line><Line k="Narration">English · {voice}</Line>
          <Line k="Review mode">{f.review_mode === 'final_only' ? 'Final only' : 'Every gate'}</Line>
          <Line k="AI provider">{prov ? prov.provider : '…'}</Line>
          {prov && <span className="muted">{prov.ready ? prov.note : 'Not ready: ' + prov.note}</span>}
          {prov?.provider === 'bridge' && <span className="muted">With the agent bridge, each role's task waits under Renders → Agent tasks until a coding agent or you answer it. Nothing is invented while it waits.</span>}
          <Btn kind="primary" busy={busy === 'create'} disabled={!f.topic.trim()} onClick={create}>Create production</Btn>
        </Card>
      </div>
    </div></div>
  </Shell>
}
