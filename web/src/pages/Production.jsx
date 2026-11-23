import React, { useEffect, useMemo, useRef, useState } from 'react'
import { Link, NavLink, useParams } from 'react-router-dom'
import { api, useApi, useAct, Shell, Card, Btn, Badge, Tier, StateBadge, Planned, Empty, ErrorBox, Loading, Field, Line, Progress, Modal, fmtTime, fmtDur, fmtSize } from '../ui.jsx'

const TABS = [['research', 'Research'], ['strategy', 'Strategy'], ['script', 'Script'], ['storyboard', 'Storyboard'], ['produce', 'Scenes'], ['edit', 'Edit'], ['export', 'Export']]
const TREAT = { kinetic: 'Kinetic type', flow2d: '2D network flow', isometric: 'Isometric', cutaway: 'Cutaway', chart: 'Chart' }

function GateCard({ gate, title }) {
  if (!gate) return null
  return <Card title={title} right={<div className="row" style={{ gap: 8 }}><Badge tone={gate.passed ? 'ok' : 'danger'}>{gate.passed ? 'Passed' : 'Not passed'}</Badge><span className="muted">decided {gate.decided || 'automatically'}</span></div>}>
    <div>{gate.criteria.map((c, i) => <div className="line" key={i}><span>{c.name}{c.detail && <span className="muted"> · {c.detail}</span>}</span><Badge tone={c.passed ? 'ok' : 'danger'}>{c.passed ? 'Pass' : 'Fail'}</Badge></div>)}</div>
    {gate.role_output_by && <span className="muted">Role output written by: {gate.role_output_by}. The checks above ran on this machine.</span>}
  </Card>
}

function Waiting({ stage, p, run }) {
  const st = p.stages?.[stage] || {}
  const prov = useApi('/settings').data?.provider
  if (st.state === 'running') return <Empty title={`${stage[0].toUpperCase() + stage.slice(1)} is running`}>{p.jobs?.[0]?.message || 'Working…'}
    {prov?.provider === 'bridge' && <div className="muted" style={{ marginTop: 8 }}>The agent bridge is selected: the task waits for a coding agent or for you. <Link to="/renders">Open agent tasks</Link></div>}</Empty>
  if (st.state === 'failed') return <Empty title="This stage failed" action={<Btn kind="primary" onClick={() => run(stage)}>Run it again</Btn>}><span className="err">{st.error}</span></Empty>
  return <Empty title="Not produced yet" action={<Btn kind="primary" onClick={() => run(stage)}>Run from {stage}</Btn>}>This stage has not run. Earlier stages must pass first.</Empty>
}

// ------------------------------------------------------------------ Research
function Research({ p, run, reload }) {
  const [act, busy] = useAct()
  const f = p.facts
  const upload = e => { const file = e.target.files[0]; if (!file) return; const fd = new FormData(); fd.append('file', file); act('up', () => api(`/productions/${p.id}/uploads`, { method: 'POST', form: fd }), 'Document attached. Run research again to use it.').then(reload) }
  return <div className="pad">
    <div className="row between"><h2>Research and fact-checking</h2><div className="row" style={{ gap: 8 }}>
      <label className="btn">{busy === 'up' ? 'Uploading…' : 'Attach a text document'}<input type="file" accept=".txt,.md,.json,.yaml,.yml,.csv" hidden onChange={upload} /></label>
      <Btn onClick={() => run('research')}>Run research again</Btn></div></div>
    {p.uploads.length > 0 && <span className="muted">Attached: {p.uploads.join(', ')}</span>}
    {!f ? <Waiting stage="research" p={p} run={run} /> : <>
      <GateCard gate={p.gates.research} title="Research gate" />
      <Card title="The one arrangement this video depicts"><p>{f.arrangement}</p></Card>
      <Card title={`Facts (${f.claims.length})`}>{f.claims.map(c => <div className="line" key={c.id} style={{ alignItems: 'flex-start' }}>
        <div className="col" style={{ gap: 4 }}><div><span className="mono sec">{c.id}</span>&nbsp; {c.text}</div>
          <div className="muted">{c.sources.map((s, i) => <span key={i}>{i > 0 && ' · '}<a href={s.url} target="_blank" rel="noreferrer">{s.title}</a> ({s.kind})</span>)}{c.sources.length === 0 && 'No source'}</div></div></div>)}</Card>
      <div className="row"><Card title="System model: components" className="grow">{f.model.components.map(c => <Line key={c.id} k={<span className="mono">{c.id}</span>}>{c.label} <span className="muted">· {c.kind}</span></Line>)}</Card>
        <Card title="System model: ordered steps" className="grow">{f.model.steps.map(s => <div className="line" key={s.n}><span><b>{s.n}.</b> {s.text}</span><span className="mono muted">{s.components.join(' → ')}</span></div>)}</Card></div>
    </>}
  </div>
}

// ------------------------------------------------------------------ Strategy
function Strategy({ p, run, reload }) {
  const [act] = useAct()
  const [ov, setOv] = useState(null)
  const s = p.strategy
  if (!s) return <div className="pad"><Waiting stage="strategy" p={p} run={run} /></div>
  return <>
    <div className="banner ok"><div><b>Strategy chosen by the Creative Director</b><div className="muted">{s.treatments.length} treatments were compared. Production continues without waiting; any decision below can be overridden.</div></div>
      <div className="row" style={{ gap: 8 }}><Btn onClick={() => run('strategy')}>Compare again</Btn><a className="btn" href={`/api/productions/${p.id}/file/strategy.md`}>Download strategy.md</a></div></div>
    <div className="pad">
      <div className="row"><Card title="Audience profile" className="grow"><p>{s.audience_profile}</p></Card><Card title="Learning objective" className="grow"><p>{s.learning_objective}</p></Card></div>
      <div className="row"><Card title="Creative concept" className="grow"><p>{s.creative_concept}</p></Card><Card title="Hook" className="grow"><p style={{ fontSize: 15, lineHeight: '24px' }}>{s.hook}</p></Card></div>
      <div className="col"><h2>Treatments compared</h2><div className="row">{s.treatments.map(t => <Card key={t.name} className="grow" style={{ flex: '1 1 260px', borderColor: t.name === s.chosen ? 'var(--accent)' : undefined, background: t.name === s.chosen ? 'var(--accent-tint)' : undefined }}
        title={t.name} right={t.name === s.chosen && <Badge tone="ok">Chosen</Badge>}>
        <p className="sec">{t.shape}</p><div><Line k="Engagement">{t.engagement}</Line><Line k="Teaching fit">{t.teaching_fit}</Line><Line k="Accuracy risk">{t.accuracy_risk}</Line><Line k="Feasibility">{t.feasibility}</Line></div><p>{t.verdict}</p></Card>)}</div></div>
      <div className="row" style={{ alignItems: 'flex-start' }}>
        <Card title="Decisions and reasons" style={{ flex: '999 1 560px' }}>{s.decisions.map(d => <div className="line" key={d.key} style={{ alignItems: 'flex-start' }}>
          <div style={{ flex: '0 0 150px' }} className="sec"><b style={{ fontWeight: 500 }}>{d.key}</b></div>
          <div className="grow"><div>{d.choice}</div><div className="muted">{d.reason}</div></div>
          <div className="row center" style={{ gap: 8, flexWrap: 'nowrap' }}><Tier tier={d.tier} /><Btn sm onClick={() => setOv({ key: d.key, choice: d.choice })}>Override</Btn></div></div>)}</Card>
        <div className="col" style={{ flex: '1 1 320px' }}>
          <Card title="Narrative and visual direction"><p>{s.narrative_structure}</p><p className="sec">{s.visual_direction}</p><p className="sec">{s.narration_approach}</p></Card>
          <Card title="Likely drop-off points" right={<span className="muted">hypotheses</span>}>{s.dropoff.map((d, i) => <div className="line" key={i}><div><div>{d.where}</div><div className="muted">{d.why} {d.countermeasure}</div></div></div>)}</Card>
          <Card title="Experiment and tools"><p>{s.experiment || 'No experiment in this video.'}</p><div className="row" style={{ gap: 6 }}>{s.tools.map(t => <Badge key={t}>{t}</Badge>)}</div></Card>
        </div>
      </div>
      <Card title="Scene breakdown"><div className="tablebox"><table><thead><tr><th>Scene</th><th>Treatment</th><th>Seconds</th><th>Purpose</th></tr></thead><tbody>
        {s.scene_breakdown.map((sc, i) => <tr key={i}><td>{sc.title}</td><td>{TREAT[sc.treatment] || sc.treatment}</td><td className="mono">{sc.seconds}</td><td className="sec">{sc.purpose}</td></tr>)}</tbody></table></div></Card>
    </div>
    {ov && <Modal title={`Override: ${ov.key}`} onClose={() => setOv(null)} footer={<><Btn onClick={() => setOv(null)}>Cancel</Btn>
      <Btn kind="primary" onClick={() => act('ov', () => api(`/productions/${p.id}/strategy/override`, { method: 'POST', body: ov }), r => r.note).then(() => { setOv(null); reload() })}>Record override</Btn></>}>
      <Field label="Your decision" hint="Recorded as your preference and kept in the library. Script and later stages are marked stale; run them again to apply it."><textarea rows={3} value={ov.choice} onChange={e => setOv({ ...ov, choice: e.target.value })} /></Field></Modal>}
  </>
}

function GateBanner({ p, stage, reload, label }) {
  const [act, busy] = useAct()
  const st = p.stages?.[stage] || {}
  const g = p.gates[stage]
  if (!g) return null
  if (st.state === 'awaiting_approval' || st.state === 'needs_you') return <div className="banner warn"><div><b>{label} {st.state === 'needs_you' ? 'did not pass its gate and needs you' : 'is waiting for your approval'}</b>
    <div className="muted">{g.criteria.filter(c => !c.passed).map(c => c.name + (c.detail ? ': ' + c.detail : '')).join(' · ') || 'All automatic checks passed.'}</div></div>
    <Btn kind="primary" busy={busy === 'ap'} onClick={() => act('ap', () => api(`/productions/${p.id}/gates/${stage}/approve`, { method: 'POST' }), 'Approved. Production continues.').then(reload)}>Approve and continue</Btn></div>
  return <div className={'banner ' + (g.passed ? 'ok' : 'danger')}><div><b>{label} gate {g.passed ? 'passed' : 'not passed'} {g.decided || 'automatically'}</b>
    <div className="muted">{g.criteria.length} checks{g.review?.skipped ? ' · independent model review did not run' : g.review ? ' · independent review included' : ' · code checks only'}{st.stale ? ' · stale: the strategy changed since' : ''}</div></div></div>
}

// ------------------------------------------------------------------ Script
function Script({ p, run, reload }) {
  const [act, busy] = useAct()
  const [draft, setDraft] = useState({})
  if (!p.script) return <div className="pad"><Waiting stage="script" p={p} run={run} /></div>
  const e = p.engagement
  const save = sid => act('s' + sid, () => api(`/productions/${p.id}/script/${sid}`, { method: 'PUT', body: { sentences: draft[sid].split('\n') } }), r => 'Saved. ' + r.summary).then(r => { if (r) { setDraft(d => { const x = { ...d }; delete x[sid]; return x }); reload() } })
  return <><GateBanner p={p} stage="script" reload={reload} label="Script" />
    <div className="pad"><div className="row" style={{ alignItems: 'flex-start' }}>
      <div className="col" style={{ flex: '999 1 520px' }}>
        <div className="row between"><h2>Script</h2><div className="row center" style={{ gap: 8 }}><span className="muted">{e.total_words} words · about {e.est_seconds} s for a {e.target_seconds} s target</span><Btn onClick={() => run('script')}>Write again</Btn></div></div>
        {p.script.scenes.map((sc, i) => { const text = draft[sc.id] ?? sc.sentences.map(s => s.text).join('\n'); const ps = e.per_scene.find(x => x.id === sc.id)
          return <Card key={sc.id} title={`${i + 1} · ${sc.title}`} right={<span className="mono muted">{ps?.words} words · ~{ps?.est_seconds}s</span>}>
            <textarea rows={Math.max(3, sc.sentences.length + 1)} style={{ fontSize: 15, lineHeight: '26px' }} value={text} onChange={ev => setDraft(d => ({ ...d, [sc.id]: ev.target.value }))} aria-label={`Narration of scene ${i + 1}, one sentence per line`} />
            <div className="row between"><span className="muted">One sentence per line. Claims cited: {[...new Set(sc.sentences.flatMap(s => s.claims))].join(', ') || 'none'}</span>
              {draft[sc.id] !== undefined && <div className="row" style={{ gap: 8 }}><Btn sm kind="ghost" onClick={() => setDraft(d => { const x = { ...d }; delete x[sc.id]; return x })}>Discard</Btn><Btn sm kind="primary" busy={busy === 's' + sc.id} onClick={() => save(sc.id)}>Save narration</Btn></div>}</div></Card> })}
        {p.plan?.rejoin && <Card className="raised"><div className="row between"><span>{p.plan.summary}</span><Link className="btn" to={`/p/${p.id}/produce`}>Review and rebuild</Link></div></Card>}
      </div>
      <div className="col" style={{ flex: '1 1 320px' }}>
        <GateCard gate={p.gates.script} title="Script gate" />
        <Card title="Engagement evaluation" right={<span className="muted">measured by code</span>}>
          <Line k="Opening poses a question or stake">{e.hook_has_question_or_stake ? 'Yes' : 'No'}</Line><Line k="Ending returns to the opening">{e.ending_echoes_opening ? 'Yes' : 'No'}</Line>
          {e.flags.length === 0 ? <span className="sec">No scene is flagged boring, repetitive, confusing or overloaded.</span> : e.flags.map((f, i) => <div key={i} className="card raised"><div className="row between"><b>{f.scene || 'Whole script'}: {f.label}</b></div><span className="sec">{f.why}</span><span className="muted">Suggested fix: {f.fix}</span></div>)}
          <span className="muted">Flags are prompts to look, not predictions of how the video will perform.</span></Card>
        {p.gates.script?.review && <Card title="Independent review"><p className="sec">{p.gates.script.review.summary}</p>{(p.gates.script.review.accuracy_issues || []).map((x, i) => <div className="err" key={i}>{x}</div>)}{(p.gates.script.review.engagement_notes || []).map((x, i) => <span className="muted" key={i}>{x}</span>)}</Card>}
      </div></div></div></>
}

// ------------------------------------------------------------------ Storyboard
function Still({ pid, sid, v, tall }) {
  const [bad, setBad] = useState(false)
  useEffect(() => setBad(false), [v])
  return bad ? <div className="thumb ph">Rendered when the scene is produced</div> : <img className={'thumb' + (tall ? ' tall' : '')} alt="" src={`/api/productions/${pid}/media/still/${sid}?v=${v}`} onError={() => setBad(true)} />
}
function Storyboard({ p, run, reload }) {
  if (!p.board) return <div className="pad"><Waiting stage="storyboard" p={p} run={run} /></div>
  return <><GateBanner p={p} stage="storyboard" reload={reload} label="Storyboard" />
    <div className="pad"><div className="row between"><h2>Storyboard</h2><Btn onClick={() => run('storyboard')}>Plan again</Btn></div>
      <div className="row">{p.board.scenes.map((s, i) => <Card key={s.id} style={{ flex: '1 1 340px' }}>
        <Still pid={p.id} sid={s.id} v={p.updated} tall={p.brief.format === '9:16'} />
        <div className="row between"><b style={{ fontWeight: 600 }}>{i + 1} · {s.title}</b><Badge tone="accent">{TREAT[s.treatment] || s.treatment}</Badge></div>
        <span className="sec">{s.objective}</span>
        <div><Line k="Elements">{(s.elements || []).length}</Line><Line k="Cues tied to words">{(s.cues || []).length + (s.lines || []).length}</Line></div>
        <div className="card raised" style={{ padding: 10 }}><div className="row between"><span className="label">Why this form</span><Tier tier={s.tier} /></div><span className="sec" style={{ fontSize: 12, lineHeight: '18px' }}>{s.reason}</span></div>
        <div className="row" style={{ gap: 6 }}>{(s.recipes || []).map(r => <span key={r} className="mono muted">{r}</span>)}</div>
        <Link className="btn sm" to={`/p/${p.id}/edit?scene=${s.id}`}>Open in editor</Link></Card>)}</div>
      <GateCard gate={p.gates.storyboard} title="Storyboard gate" /></div></>
}

// ------------------------------------------------------------------ Scene production
function PlanBox({ p, reload }) {
  const [act, busy] = useAct()
  const plan = p.plan
  if (!plan) return null
  const jobActive = p.jobs.length > 0
  return <Card className="raised" title="What a rebuild will do">
    <span>{plan.summary}</span>
    {plan.scenes.map(s => <Line key={s.scene} k={`${s.scene} · ${s.title}`}>{[s.narration && 'new narration', s.clip !== 'keep' && s.clip].filter(Boolean).join(', ')}</Line>)}
    <div className="row" style={{ gap: 8 }}><Btn kind="primary" busy={busy === 'rb'} disabled={jobActive || !plan.rejoin} title={jobActive ? 'A job is already running for this production' : !plan.rejoin ? 'Everything is up to date' : ''}
      onClick={() => act('rb', () => api(`/productions/${p.id}/rebuild`, { method: 'POST' }), 'Rebuild queued').then(reload)}>{plan.rejoin ? 'Rebuild now' : 'Up to date'}</Btn></div>
  </Card>
}
function Produce({ p, run, reload }) {
  if (!p.board) return <div className="pad"><Waiting stage="produce" p={p} run={run} /></div>
  const man = p.manifest
  const job = p.jobs[0]
  return <div className="pad">
    <div className="row between"><h2>Scene production</h2><span className="muted">Narration and rendering run on this machine, one scene at a time.</span></div>
    {job && <Card><div className="row between"><b>{job.message}</b><StateBadge state={job.state} /></div><Progress value={job.progress} /></Card>}
    <PlanBox p={p} reload={reload} />
    <div className="row">{p.board.scenes.map((s, i) => { const m = man?.scenes.find(x => x.id === s.id); const stale = p.plan?.scenes.find(x => x.scene === s.id)
      return <Card key={s.id} style={{ flex: '1 1 340px' }} title={`${i + 1} · ${s.title}`} right={<Badge tone={!m ? 'muted' : stale ? 'warn' : 'ok'}>{!m ? 'Not rendered' : stale ? 'Stale' : 'Rendered'}</Badge>}>
        {m ? <video className={'thumb' + (p.brief.format === '9:16' ? ' tall' : '')} controls preload="none" poster={`/api/productions/${p.id}/media/still/${s.id}?v=${p.updated}`} src={`/api/productions/${p.id}/media/clip/${s.id}?v=${m.clip_hash}`} /> : <div className="thumb ph">No clip yet</div>}
        <div><Line k="Treatment">{TREAT[s.treatment] || s.treatment}</Line><Line k="Duration">{m ? m.duration.toFixed(1) + ' s' : 'after narration'}</Line><Line k="Clip id"><span className="mono">{m?.clip_hash || 'none'}</span></Line></div>
        {m && <audio controls preload="none" src={`/api/productions/${p.id}/media/audio/${s.id}?v=${m.audio_hash}`} style={{ width: '100%' }} />}</Card> })}</div>
  </div>
}

// ------------------------------------------------------------------ Editor
function Editor({ p, reload }) {
  const [act, busy] = useAct()
  const params = new URLSearchParams(window.location.search)
  const [sel, setSel] = useState(params.get('scene') || p.board?.scenes[0]?.id)
  const [mode, setMode] = useState('video')
  const [t, setT] = useState(0)
  const [tab, setTab] = useState('scene')
  const [instruction, setInstruction] = useState('')
  const [proposal, setProposal] = useState(null)
  const [raw, setRaw] = useState(null)
  const [versions, setVersions] = useState(false)
  const vid = useRef(null)
  const man = p.manifest
  if (!p.board) return <div className="pad"><Empty title="Nothing to edit yet">The editor opens once the storyboard exists.</Empty></div>
  const spec = p.board.scenes.find(s => s.id === sel) || p.board.scenes[0]
  const script = p.script.scenes.find(s => s.id === spec.id)
  const total = man?.duration || 60
  const ms = man?.scenes.find(s => s.id === spec.id)
  const stale = p.plan?.scenes.find(x => x.scene === spec.id)
  const patch = (pt, label) => act('patch', () => api(`/productions/${p.id}/scenes/${spec.id}`, { method: 'PUT', body: { patch: pt, label } }), r => r.summary).then(r => r && reload())
  const seek = sec => { setMode('video'); setT(sec); setTimeout(() => { if (vid.current) vid.current.currentTime = sec }, 60) }
  const pick = id => { setSel(id); setProposal(null); setRaw(null); const m = man?.scenes.find(s => s.id === id); if (m && mode === 'video') seek(m.start + 0.05) }
  const idx = p.board.scenes.findIndex(s => s.id === spec.id)
  const move = d => { const ids = p.board.scenes.map(s => s.id); const j = idx + d; if (j < 0 || j >= ids.length) return;[ids[idx], ids[j]] = [ids[j], ids[idx]]; act('mv', () => api(`/productions/${p.id}/reorder`, { method: 'POST', body: { ids } }), r => r.summary).then(reload) }
  const ask = () => act('ask', async () => { const r = await api(`/productions/${p.id}/scenes/${spec.id}/instruct`, { method: 'POST', body: { instruction } })
    for (let i = 0; i < 900; i++) { await new Promise(z => setTimeout(z, 1500)); const j = await api('/jobs/' + r.job); if (j.state === 'done') return api(`/productions/${p.id}/scenes/${spec.id}/proposal`); if (j.state === 'failed') throw new Error(j.message) } throw new Error('No answer yet. Check Renders → Agent tasks.') }).then(r => r && setProposal(r))
  const abs = mode === 'video' ? t : (ms ? ms.start + t : 0)
  const src = mode === 'video' ? (p.has_video ? `/api/productions/${p.id}/media/video?v=${man?.final_hash}` : '') : (ms ? `/api/productions/${p.id}/media/clip/${spec.id}?v=${ms.clip_hash}` : '')
  const pct = s => `${(s / total) * 100}%`
  const click = e => { const r = e.currentTarget.getBoundingClientRect(); seek(Math.max(0, Math.min(total, (e.clientX - r.left) / r.width * total))) }
  return <div className="editor">
    <div className="editor-top">
      <aside className="scenes" aria-label="Scenes"><span className="label">Scenes</span>
        {p.board.scenes.map((s, i) => { const m = man?.scenes.find(x => x.id === s.id); return <button key={s.id} className={'scene-item ' + (s.id === spec.id ? 'on' : '')} onClick={() => pick(s.id)}>
          <span><span className="mono muted">{i + 1}</span>&nbsp; {s.title}</span><span className="mono muted">{m ? fmtDur(m.start) : ''}</span></button> })}
        {man?.scenes.filter(m => m.end_slide).map(m => <button key={m.id} className="scene-item locked" title="Added at export. Change it on the Settings page." onClick={() => seek(m.start + 0.05)}>
          <span><span className="mono muted">🔒</span>&nbsp; End slide</span><span className="mono muted">{fmtDur(m.start)}</span></button>)}
        <div className="row" style={{ gap: 6, marginTop: 8 }}><Btn sm disabled={idx === 0} onClick={() => move(-1)}>Move up</Btn><Btn sm disabled={idx === p.board.scenes.length - 1} onClick={() => move(1)}>Move down</Btn></div>
        <span className="muted" style={{ marginTop: 8 }}>Split and merge scenes <Planned /></span>
      </aside>
      <div className="stagebox">
        {src ? <video ref={vid} key={src} className={p.brief.format === '9:16' ? 'tall' : ''} controls preload="metadata" poster={`/api/productions/${p.id}/media/still/${spec.id}?v=${p.updated}`} src={src} onTimeUpdate={e => setT(e.target.currentTime)} /> : <div className="novideo">{mode === 'video' ? 'The video appears here after the first export' : 'This scene has not been rendered yet'}</div>}
        <div className="row between" style={{ width: '100%', maxWidth: 860 }}>
          <div className="seg" style={{ width: 260 }}><button className={mode === 'video' ? 'on' : ''} onClick={() => { setMode('video'); setT(0) }}>Whole video</button><button className={mode === 'scene' ? 'on' : ''} onClick={() => { setMode('scene'); setT(0) }}>This scene</button></div>
          <span className="mono">{fmtDur(abs)} / {fmtDur(total)}</span>
          <Badge tone={!ms ? 'muted' : stale ? 'warn' : 'ok'}>{!ms ? 'Not rendered' : stale ? 'Edited: needs rebuild' : 'Showing the latest render'}</Badge></div>
      </div>
      <aside className="inspector" aria-label="Inspector">
        <div className="seg">{[['scene', 'Scene'], ['style', 'Style'], ['cues', 'Cues'], ['json', 'Data']].map(([k, l]) => <button key={k} className={tab === k ? 'on' : ''} onClick={() => setTab(k)}>{l}</button>)}</div>
        <h3>{idx + 1} · {spec.title}</h3>
        {tab === 'scene' && <>
          <div><Line k="Treatment">{TREAT[spec.treatment] || spec.treatment}</Line><Line k="Duration">{ms ? ms.duration.toFixed(1) + ' s' : 'set by narration'}</Line><Line k="Engine">Skia scene renderer</Line></div>
          <div className="card raised" style={{ padding: 10 }}><div className="row between"><span className="label">Why the Creative Director chose this</span><Tier tier={spec.tier} /></div><span className="sec" style={{ fontSize: 12, lineHeight: '18px' }}>{spec.reason || 'No reason recorded.'}</span></div>
          <Field label={`Animation speed: ${(1 / (spec.motion_scale || 1)).toFixed(2)}×`} hint="Slower holds each movement longer. Narration is unchanged.">
            <div className="row" style={{ gap: 8 }}><Btn sm onClick={() => patch({ motion_scale: +(Math.min(2.5, (spec.motion_scale || 1) * 1.25)).toFixed(2) }, 'Slower animation')}>Slower</Btn><Btn sm onClick={() => patch({ motion_scale: +(Math.max(0.5, (spec.motion_scale || 1) / 1.25)).toFixed(2) }, 'Faster animation')}>Faster</Btn></div></Field>
          <div className="row"><div className="grow"><Field label="Pause before (s)"><input type="number" step="0.1" min="0" max="3" defaultValue={spec.pad_start ?? 0.4} key={spec.id + 'a' + p.hpos} onBlur={e => +e.target.value !== (spec.pad_start ?? 0.4) && patch({ pad_start: +e.target.value }, 'Changed pause before')} /></Field></div>
            <div className="grow"><Field label="Hold after (s)"><input type="number" step="0.1" min="0" max="5" defaultValue={spec.pad_end ?? 0.5} key={spec.id + 'b' + p.hpos} onBlur={e => +e.target.value !== (spec.pad_end ?? 0.5) && patch({ pad_end: +e.target.value }, 'Changed hold after')} /></Field></div></div>
          <Field label="Transition in"><select value={spec.camera?.enter || ''} onChange={e => patch({ camera: { ...spec.camera, enter: e.target.value || undefined } }, 'Changed transition in')}><option value="">Fade</option><option value="zoom_out">Pull back into the scene</option></select></Field>
          <Field label="Transition out"><select value={spec.camera?.exit || ''} onChange={e => patch({ camera: { ...spec.camera, exit: e.target.value || undefined } }, 'Changed transition out')}><option value="">Fade</option><option value="push_in">Push in</option></select></Field>
          <Field label="Narration" hint={<>Edit the words on the <Link to={`/p/${p.id}/script`}>Script</Link> tab; that re-records this scene only.</>}><div className="sec" style={{ fontSize: 12, lineHeight: '18px' }}>{script?.sentences.map(s => s.text).join(' ')}</div></Field>
          <Field label="Describe a change to this scene" hint="Needs an AI provider. Nothing is applied until you accept the proposal.">
            <textarea rows={3} value={instruction} onChange={e => setInstruction(e.target.value)} placeholder="For example: keep the load balancer highlighted until the node is chosen" /></Field>
          <Btn busy={busy === 'ask'} disabled={!instruction.trim()} onClick={ask}>Propose a change</Btn>
          {proposal?.spec && <div className="card raised"><b>Proposed change</b><span className="sec">Fields changed: {proposal.changed.join(', ') || 'none'}</span>
            <div className="row" style={{ gap: 8 }}><Btn sm kind="primary" onClick={() => act('ap', () => api(`/productions/${p.id}/scenes/${spec.id}/proposal/apply`, { method: 'POST' }), r => r.summary).then(() => { setProposal(null); setInstruction(''); reload() })}>Accept</Btn><Btn sm onClick={() => setProposal(null)}>Discard</Btn></div></div>}
        </>}
        {tab === 'style' && <>
          <Field label="Template for this scene" hint="Empty uses the production template."><select value={spec.theme || ''} onChange={e => patch({ theme: e.target.value || null }, 'Changed scene template')}><option value="">Production template ({p.brief.theme})</option><option>premium-technical</option><option>noir-network</option><option>paper</option><option>blueprint</option><option>sketch</option><option>midnight-blue</option><option>minimal-mono</option></select></Field>
          <Field label="Small heading"><input type="text" defaultValue={spec.heading || ''} key={spec.id + 'h' + p.hpos} onBlur={e => e.target.value !== (spec.heading || '') && patch({ heading: e.target.value || null }, 'Changed heading')} /></Field>
          <span className="label">Labels</span>
          {(spec.elements || []).map((el, i) => <div className="row" key={el.id} style={{ gap: 8, flexWrap: 'nowrap', alignItems: 'center' }}><span className="mono muted" style={{ flex: '0 0 56px' }}>{el.id}</span>
            <input type="text" defaultValue={el.label} key={spec.id + el.id + p.hpos} onBlur={e => { if (e.target.value !== el.label) { const els = spec.elements.map((x, j) => j === i ? { ...x, label: e.target.value } : x); patch({ elements: els }, `Renamed ${el.id}`) } }} /></div>)}
          {(spec.elements || []).length === 0 && <span className="sec">This treatment has no labelled elements.</span>}
          <span className="muted">Colour grading, masking and motion tracking apply to filmed footage and are not part of this editor.</span>
        </>}
        {tab === 'cues' && <>{[...(spec.lines || []).map(l => ({ action: 'line', at: l.at, text: l.text })), ...(spec.cues || [])].map((c, i) => <div className="line" key={i}><span><b style={{ fontWeight: 500 }}>{c.action}</b> <span className="muted">{c.target || c.text || (c.from && `${c.from} → ${c.to}`) || ''}</span></span>
          <span className="mono muted">{typeof c.at === 'number' ? c.at + ' s' : c.at?.word ? `“${c.at.word}”` : c.at?.sentence !== undefined ? `sentence ${c.at.sentence + 1}` : 'start'}</span></div>)}
          <span className="muted">Each cue fires on a spoken word. Edit them under Data.</span></>}
        {tab === 'json' && <><Field label="Scene specification (JSON)" hint="Validated against the schema when you save."><textarea rows={18} className="mono" value={raw ?? JSON.stringify(spec, null, 1)} onChange={e => setRaw(e.target.value)} /></Field>
          <Btn disabled={raw === null} onClick={() => { let o; try { o = JSON.parse(raw) } catch (e) { return act('x', () => { throw new Error('Not valid JSON: ' + e.message) }) } patch(o, 'Edited specification').then(() => setRaw(null)) }}>Save specification</Btn></>}
        {p.plan?.rejoin && <PlanBox p={p} reload={reload} />}
      </aside>
    </div>
    <section className="timeline" aria-label="Timeline">
      <div className="row between" style={{ padding: '6px 12px' }}>
        <div className="row center" style={{ gap: 4 }}>
          <Btn sm kind="ghost" disabled={p.hpos <= 0} onClick={() => act('u', () => api(`/productions/${p.id}/undo`, { method: 'POST' }), r => 'Undone. ' + r.summary).then(reload)}>Undo</Btn>
          <Btn sm kind="ghost" disabled={p.hpos >= p.history.length - 1} onClick={() => act('r', () => api(`/productions/${p.id}/redo`, { method: 'POST' }), r => 'Redone. ' + r.summary).then(reload)}>Redo</Btn>
          <Btn sm onClick={() => setVersions(true)}>Versions ({p.versions.length})</Btn>
          <span className="muted">{p.history[p.hpos]?.label}</span></div>
        <span className="muted">Click the timeline to move the playhead. Scene length follows its narration.</span></div>
      <div className="tl-scroll"><div className="tl-inner">
        <div className="lane"><div className="head" /><div className="ruler" style={{ flex: 1 }}>{Array.from({ length: Math.floor(total / 10) + 1 }).map((_, i) => <span key={i} style={{ left: pct(i * 10) }}>{fmtDur(i * 10)}</span>)}</div></div>
        <div className="lane"><div className="head">Visual</div><div className="body" onClick={click}>{man?.scenes.map((s, i) => s.end_slide
          ? <div key={s.id} className="clip scene locked" title="End slide: locked, edit it in Settings" style={{ left: pct(s.start), width: `calc(${pct(s.duration)} - 2px)` }} onClick={e => { e.stopPropagation(); seek(s.start + 0.05) }}>🔒 End slide</div>
          : <div key={s.id} className={'clip scene ' + (s.id === spec.id ? 'on' : '')} style={{ left: pct(s.start), width: `calc(${pct(s.duration)} - 2px)` }} onClick={e => { e.stopPropagation(); pick(s.id) }}>{i + 1} · {s.title}</div>)}</div></div>
        <div className="lane small"><div className="head">Narration</div><div className="body" onClick={click}>{man?.scenes.map(s => <div key={s.id} className="clip voice" style={{ left: pct(s.start + s.pad_start), width: `calc(${pct(Math.max(0.2, s.duration - s.pad_start - 0.5))} - 2px)` }} />)}</div></div>
        <div className="lane small"><div className="head">Captions</div><div className="body" onClick={click}>{man?.scenes.map(s => <div key={s.id} className="clip cap" style={{ left: pct(s.start + s.pad_start), width: `calc(${pct(Math.max(0.2, s.duration - s.pad_start - 0.5))} - 2px)` }} />)}</div></div>
        <div className="lane small"><div className="head">Cues</div><div className="body" onClick={click}>{man?.scenes.flatMap(s => s.events.map((e, i) => <div key={s.id + i} className="cue" title={e.action} style={{ left: pct(s.start + e.t) }} />))}</div></div>
        <div className="lane small"><div className="head">Music <span className="muted">bed</span></div><div className="body" onClick={click}>{man?.settings.music && <div className="clip" style={{ left: 0, right: 0, borderColor: 'rgba(228,106,166,.6)', background: 'rgba(228,106,166,.18)' }}>Generated ambient bed, ducked under the voice</div>}</div></div>
        {man && <div className="playhead" style={{ left: `calc(120px + (100% - 120px) * ${Math.min(1, abs / total)})` }} />}
      </div></div>
    </section>
    {versions && <Modal title="Versions" onClose={() => setVersions(false)} footer={<Btn kind="primary" onClick={() => { const label = window.prompt('Name this version'); if (label) act('v', () => api(`/productions/${p.id}/versions`, { method: 'POST', body: { label } }), 'Version saved').then(reload) }}>Save current as a version</Btn>}>
      {p.versions.length === 0 ? <span className="sec">No versions yet. One is saved automatically at each export.</span> : [...p.versions].reverse().map(v => <div className="line" key={v.id}><span>{v.label} <span className="muted">· {fmtTime(v.at)}{v.auto ? ' · automatic' : ''}</span></span>
        <Btn sm onClick={() => act('rv', () => api(`/productions/${p.id}/versions/${v.id}/restore`, { method: 'POST' }), r => 'Restored. ' + r.summary).then(() => { setVersions(false); reload() })}>Restore</Btn></div>)}
      <span className="muted">Restoring never deletes later versions. Clips that were already rendered are reused, not rendered again.</span></Modal>}
  </div>
}

// ------------------------------------------------------------------ Export
function Export({ p, reload }) {
  const [act, busy] = useAct()
  const g = p.gates.final
  const job = p.jobs[0]
  const setBrief = b => act('b', () => api(`/productions/${p.id}/brief`, { method: 'PUT', body: b }), r => r.plan ? r.plan.summary : 'Saved').then(reload)
  return <div className="pad">
    <div className="row between"><div><h1>Export</h1><span className="sec">The final video is always yours to approve. Nothing is published from here.</span></div>
      <div className="row" style={{ gap: 8 }}><Link className="btn" to={`/p/${p.id}/edit`}>Back to editor</Link>
        <Btn kind="primary" busy={busy === 'ok'} disabled={!['awaiting_approval', 'checks_failed'].includes(p.final)} title={p.final === 'approved' ? 'Already approved' : !p.has_video ? 'Render the video first' : ''}
          onClick={() => act('ok', () => api(`/productions/${p.id}/final/approve`, { method: 'POST' }), 'Final video approved').then(reload)}>{p.final === 'approved' ? 'Approved' : 'Approve final video'}</Btn></div></div>
    {job && <Card><div className="row between"><b>{job.message}</b><StateBadge state={job.state} /></div><Progress value={job.progress} /></Card>}
    {p.final === 'approved' && <div className="banner ok" style={{ borderRadius: 8, border: 0 }}><b>You approved this video on {fmtTime(p.approved_at)}.</b></div>}
    <div className="row" style={{ alignItems: 'flex-start' }}>
      <div className="col" style={{ flex: '2 1 520px' }}>
        {p.has_video ? <video className={'thumb' + (p.brief.format === '9:16' ? ' tall' : '')} controls preload="metadata" poster={`/api/productions/${p.id}/media/still/${p.board?.scenes[2]?.id || 's1'}`} src={`/api/productions/${p.id}/media/video?v=${p.manifest?.final_hash}`} /> : <div className="thumb ph">No video yet. Run production from the Scenes tab.</div>}
        {g ? <GateCard gate={g} title="Automated checks on the final video" /> : <Card title="Automated checks"><span className="sec">Checks run after the video is encoded.</span></Card>}
      </div>
      <div className="col" style={{ flex: '1 1 320px' }}>
        <Card title="Output settings">
          <Field label="Resolution" hint="Changing this re-renders every clip."><select value={p.brief.quality} onChange={e => setBrief({ quality: e.target.value })}><option>1080p</option><option>720p</option><option>540p</option></select></Field>
          <Field label="Template" hint="Re-renders the pictures only. Narration and the AI's work are kept."><select value={p.brief.theme} onChange={e => setBrief({ theme: e.target.value })}><option value="auto">Creative Director's choice{p.strategy?.template ? ` (${p.strategy.template})` : ''}</option><option>noir-network</option><option>paper</option><option>blueprint</option><option>sketch</option><option>premium-technical</option><option>midnight-blue</option><option>minimal-mono</option></select></Field>
          <Field label="Format" hint="Switching re-renders every scene in the new shape. Narration and the AI's work are reused; no new tasks.">
            <select value={p.brief.format || '16:9'} onChange={e => setBrief({ format: e.target.value })}>
              <option value="16:9">16:9 landscape: YouTube, courses</option>
              <option value="9:16">9:16 vertical: Instagram Reels, YouTube Shorts, TikTok</option>
            </select></Field>
          <Line k="1:1 square"><Planned /></Line><Line k="Frame rate">30 fps</Line><Line k="Subtitles">SRT and VTT files; also drawn in the picture if enabled in Settings</Line>
          <Line k="Render on this machine"><Badge tone="ok">In use · $0</Badge></Line><Line k="Cloud rendering"><Planned>Optional, paid · off</Planned></Line>
        </Card>
        <PlanBox p={p} reload={reload} />
        <Card title="Cover">
          {p.exports.some(f => f.name === 'cover.png')
            ? <img alt="Cover" src={`/api/productions/${p.id}/file/cover.png?v=${p.updated}`} style={{ width: '100%', maxWidth: p.brief.format === '9:16' ? 220 : 360, borderRadius: 8, display: 'block' }} />
            : <span className="sec">The cover is written with every export, in the video's style.</span>}
          <Field label="Cover headline" hint="Empty uses the production title. Regenerate to apply it; only the cover is re-rendered.">
            <input defaultValue={p.brief.cover_headline || ''} placeholder={p.title} key={'ch' + p.updated}
              onBlur={e => e.target.value !== (p.brief.cover_headline || '') && setBrief({ cover_headline: e.target.value })} /></Field>
          <div className="row" style={{ gap: 8 }}>
            <Btn sm busy={busy === 'cov'} onClick={() => act('cov', () => api(`/productions/${p.id}/cover`, { method: 'POST' }), 'Cover regenerated').then(reload)}>Regenerate cover</Btn>
            {p.exports.some(f => f.name === 'cover.png') && <a className="btn sm" href={`/api/productions/${p.id}/file/cover.png`}>Download cover</a>}
          </div>
        </Card>
        <Card title="Files">{p.exports.length === 0 ? <span className="sec">Files appear here as they are written.</span> : p.exports.map(f => <div className="line" key={f.name}><span><span className="mono">{f.name}</span> <span className="muted">· {fmtSize(f.size)}</span></span><a className="btn sm" href={`/api/productions/${p.id}/file/${f.name}`}>Download</a></div>)}
          <span className="muted">project.zip holds the editable production: brief, facts, strategy, script, scene specifications, narration and subtitles.</span></Card>
        <Card title="Publishing" right={<Planned />}><span className="sec">Uploading to a channel is not built. When it is, every upload will ask you first.</span></Card>
      </div></div></div>
}

// ------------------------------------------------------------------ frame
export default function Production() {
  const { id, tab = 'research' } = useParams()
  const [poll, setPoll] = useState(2000)
  const { data: p, error, loading, reload } = useApi(`/productions/${id}`, poll)
  const [act] = useAct()
  useEffect(() => { if (p) setPoll(p.jobs.length ? 1500 : 6000) }, [p])
  const run = stage => act('run', () => api(`/productions/${id}/run`, { method: 'POST', body: { start: stage } }), `Queued from ${stage}`).then(reload)
  const body = useMemo(() => {
    if (!p) return null
    const props = { p, run, reload }
    return { research: <Research {...props} />, strategy: <Strategy {...props} />, script: <Script {...props} />, storyboard: <Storyboard {...props} />, produce: <Produce {...props} />, edit: <Editor {...props} />, export: <Export {...props} /> }[tab] || <div className="pad"><Empty title="Unknown tab" /></div>
  }, [p, tab])
  const stState = s => { if (!p) return ''; if (s === 'edit') return p.plan?.rejoin && p.manifest ? 'stale' : p.manifest ? 'passed' : ''; if (s === 'export') return p.final === 'approved' ? 'passed' : p.final === 'awaiting_approval' ? 'awaiting_approval' : (p.stages.export?.state || ''); const st = p.stages[s] || {}; return st.stale ? 'stale' : st.state }
  return <Shell crumbs={['Productions', p?.title || '…']} right={p && <span className="muted">Review mode: {p.brief.review_mode === 'final_only' ? 'final only' : 'every gate'}</span>}>
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <nav className="tabs" aria-label="Stages">{TABS.map(([k, l]) => <NavLink key={k} to={`/p/${id}/${k}`} className={tab === k ? 'on' : ''}><span className={'dot ' + stState(k)} />{l}</NavLink>)}</nav>
      <div style={{ flex: 1, minHeight: 0, overflow: tab === 'edit' ? 'hidden' : 'auto' }}>
        {error ? <div className="pad"><ErrorBox error={error} retry={reload} /></div> : loading && !p ? <div className="pad"><Loading rows={5} /></div> : body}
      </div></div>
  </Shell>
}
