import React, { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, useApi, useAct, Shell, Card, Btn, Badge, StateBadge, Planned, Empty, ErrorBox, Loading, Field, Line, Progress, Modal, Seg, fmtTime } from '../ui.jsx'

function JobLog({ id, onClose }) {
  const { data } = useApi('/jobs/' + id, 2000)
  return <Modal title="Job log" onClose={onClose}>{!data ? <Loading /> : <>
    <Line k="State"><StateBadge state={data.state} /></Line><Line k="Message">{data.message}</Line>
    <pre className="mono" style={{ maxHeight: 360, overflow: 'auto', whiteSpace: 'pre-wrap', fontSize: 12, lineHeight: '18px', background: 'var(--bg-inset)', padding: 12, borderRadius: 6 }}>{(Array.isArray(data.log) ? data.log.join('\n') : data.log) || 'No log lines.'}</pre></>}</Modal>
}

export function Renders() {
  const jobs = useApi('/jobs?limit=60', 2000)
  const bridge = useApi('/bridge', 3000)
  const [act, busy] = useAct()
  const [log, setLog] = useState(null)
  const [task, setTask] = useState(null)
  const [answer, setAnswer] = useState('')
  const mem = jobs.data?.memory || {}
  const tasks = bridge.data || []
  const submit = () => act('ans', () => api('/bridge/' + task.id, { method: 'POST', body: { text: answer } }), 'Answer submitted. The role checks it against its schema.').then(r => { if (r) { setTask(null); setAnswer(''); bridge.reload() } })
  return <Shell crumbs={['Renders and agent tasks']}>
    <div className="pad">
      <div><h1>Renders and agent tasks</h1><span className="sec">One job runs at a time so the studio stays inside this machine's memory.</span></div>
      <ErrorBox error={jobs.error} retry={jobs.reload} />
      <div className="row">
        <Card title="Memory" style={{ flex: '1 1 240px' }}><Line k="In use on this computer">{mem.used_percent ?? '…'}%</Line><Progress value={(mem.used_percent || 0) / 100} /><Line k="Available">{mem.available_mb} of {mem.total_mb} MB</Line><Line k="Studio process">{mem.studio_mb} MB</Line></Card>
        <Card title="Processor" style={{ flex: '1 1 240px' }}><Line k="Cores">{mem.cpus}</Line><Line k="Load">{mem.cpu_percent}%</Line><span className="muted">Rendering uses the processor only. No graphics card is needed.</span></Card>
        <Card title="Cloud rendering" right={<Planned>Optional, paid · off</Planned>} style={{ flex: '1 1 240px' }}><span className="sec">Not built. The renderer takes a scene specification and returns a clip, so a remote worker can replace it later without changing productions.</span></Card>
      </div>
      <Card title={`Agent tasks (${tasks.length})`} right={<span className="muted">Used by the “agent bridge” provider</span>}>
        {tasks.length === 0 ? <span className="sec">No role is waiting for an answer.</span> : tasks.map(t => <div className="line" key={t.id}><span><b style={{ fontWeight: 500 }}>{t.role}</b> <span className="mono muted">{t.id}</span> <span className="muted">· waiting since {fmtTime(t.created)}</span></span><Btn sm onClick={() => { setTask(t); setAnswer('') }}>Open task</Btn></div>)}
        <span className="muted">Each task is a file in <span className="mono">data/bridge/tasks</span>. A coding agent can answer it by writing the result file named in the task, or you can paste an answer here. Nothing is made up while a task waits.</span>
      </Card>
      <Card title="Jobs">{jobs.loading ? <Loading /> : (jobs.data?.jobs || []).length === 0 ? <Empty title="No jobs yet" /> : <div className="tablebox"><table><thead><tr><th>Job</th><th>Production</th><th>State</th><th>Progress</th><th>Started</th><th>Took</th><th></th></tr></thead>
        <tbody>{jobs.data.jobs.map(j => <tr key={j.id}><td>{j.kind}</td><td>{j.production_id ? <Link to={`/p/${j.production_id}`}>{j.title || j.production_id}</Link> : <span className="muted">none</span>}</td><td><StateBadge state={j.state} /></td>
          <td style={{ minWidth: 220 }}>{j.state === 'running' ? <><Progress value={j.progress} /><span className="muted">{j.message}</span></> : <span className="muted">{j.message}</span>}</td>
          <td className="muted">{fmtTime(j.started || j.created)}</td><td className="mono muted">{j.finished && j.started ? Math.round(j.finished - j.started) + ' s' : ''}</td>
          <td><div className="row" style={{ gap: 6, flexWrap: 'nowrap' }}><Btn sm kind="ghost" onClick={() => setLog(j.id)}>Log</Btn>
            {j.state === 'queued' && <Btn sm kind="ghost danger" busy={busy === j.id} onClick={() => act(j.id, () => api(`/jobs/${j.id}/cancel`, { method: 'POST' }), 'Cancelled').then(jobs.reload)}>Cancel</Btn>}
            {j.state === 'running' && <span className="muted" title="A running job finishes; only queued jobs can be cancelled">cannot cancel</span>}</div></td></tr>)}</tbody></table></div>}</Card>
    </div>
    {log && <JobLog id={log} onClose={() => setLog(null)} />}
    {task && <Modal title={`Agent task: ${task.role}`} onClose={() => setTask(null)} footer={<><Btn onClick={() => navigator.clipboard?.writeText(task.system + '\n\n' + task.user)}>Copy instructions and input</Btn><Btn kind="primary" busy={busy === 'ans'} disabled={!answer.trim()} onClick={submit}>Submit answer</Btn></>}>
      <Field label="Instructions for the role"><textarea rows={6} readOnly className="mono" value={task.system} /></Field>
      <Field label="Input"><textarea rows={6} readOnly className="mono" value={task.user} /></Field>
      <Field label="Answer (JSON)" hint="Checked against the role's schema. If it does not fit, the role asks once more with the errors."><textarea rows={8} className="mono" value={answer} onChange={e => setAnswer(e.target.value)} /></Field>
    </Modal>}
  </Shell>
}

export function Settings() {
  const { data, error, loading, reload } = useApi('/settings')
  const health = useApi('/health')
  const [act, busy] = useAct()
  const [s, setS] = useState(null)
  useEffect(() => { if (data) setS(data.settings) }, [data])
  if (error) return <Shell crumbs={['Settings']}><div className="pad"><ErrorBox error={error} retry={reload} /></div></Shell>
  if (loading || !s) return <Shell crumbs={['Settings']}><div className="pad"><Loading rows={6} /></div></Shell>
  const set = (k, v) => setS(x => ({ ...x, [k]: v }))
  const dirty = JSON.stringify(s) !== JSON.stringify(data.settings)
  const save = () => act('save', () => api('/settings', { method: 'PUT', body: s }), 'Settings saved').then(r => r && reload())
  const prov = data.providers.find(p => p.id === s.llm_provider)
  const h = health.data
  const Check = ({ k, children }) => <label className="row center" style={{ gap: 8 }}><input type="checkbox" checked={!!s[k]} onChange={e => set(k, e.target.checked)} /> {children}</label>
  return <Shell crumbs={['Settings']} right={<Btn kind="primary" busy={busy === 'save'} disabled={!dirty} onClick={save}>{dirty ? 'Save settings' : 'Saved'}</Btn>}>
    <div className="pad"><h1>Settings</h1>
      <div className="row" style={{ alignItems: 'flex-start' }}>
        <div className="col" style={{ flex: '1 1 460px' }}>
          <Card title="AI provider for the roles" right={<Badge tone={data.provider.ready ? 'ok' : 'warn'}>{data.provider.ready ? 'Ready' : 'Not ready'}</Badge>}>
            <Field label="Provider" hint={data.provider.note}><select value={s.llm_provider} onChange={e => set('llm_provider', e.target.value)}>{data.providers.map(p => <option key={p.id} value={p.id}>{p.name}{p.paid === true ? ' (paid)' : ''}</option>)}</select></Field>
            {prov?.id === 'bridge' && <span className="sec">Not unattended: a production pauses at each role until its task is answered.</span>}
            {prov?.id === 'claude_cli' && <span className="sec">Runs <span className="mono">claude -p</span> once per role. It uses your Claude plan and its usage limits; it is not unlimited, and a production stops with a clear message if a limit is reached.</span>}
            {['openai', 'anthropic'].includes(prov?.id) && <>
              {prov.id === 'openai' && <Field label="Address" hint="For a local Ollama: http://127.0.0.1:11434/v1. Local addresses are treated as free."><input type="text" value={s.llm_base_url || ''} onChange={e => set('llm_base_url', e.target.value)} /></Field>}
              <Field label="Model name"><input type="text" value={s.llm_model || ''} onChange={e => set('llm_model', e.target.value)} /></Field>
              <span className="sec">The key is read from <span className="mono">EXPOSIT_LLM_API_KEY</span> in <span className="mono">.env</span>; it is never stored by the app or shown here. Hosted providers charge per token: check the provider's current price list before raising the budget.</span></>}
            <Field label="Budget for paid services per production (US dollars)" hint="At 0, every paid provider is refused."><input type="number" min="0" step="0.5" value={s.budget_paid_usd} onChange={e => set('budget_paid_usd', +e.target.value)} /></Field>
            <Check k="independent_review">Ask the Quality Reviewer role for an independent review of script and storyboard</Check>
            <span className="label">Keys present in .env</span>{Object.entries(data.env).map(([k, v]) => <Line key={k} k={<span className="mono">{k}</span>}><Badge tone={v ? 'ok' : 'muted'}>{v ? 'Set' : 'Not set'}</Badge></Line>)}
          </Card>
          <Card title="Defaults for new productions">
            <Field label="Review mode"><Seg value={s.default_review_mode} onChange={v => set('default_review_mode', v)} options={[{ value: 'final_only', label: 'Final only' }, { value: 'every_gate', label: 'Every gate' }]} /></Field>
            <span className="muted">In both modes the final video waits for your approval, and nothing is published.</span></Card>
        </div>
        <div className="col" style={{ flex: '1 1 460px' }}>
          <Card title="Narration and sound">
            <Field label="Voice engine"><select value={s.voice_engine} disabled><option>{s.voice_engine}</option></select></Field>
            <div className="row"><div className="grow"><Field label="Default voice"><select value={s.voice} onChange={e => set('voice', e.target.value)}>{(data.voices.length ? data.voices : [s.voice]).map(v => <option key={v}>{v}</option>)}</select></Field></div>
              <div className="grow"><Field label={`Speed ${(+s.voice_speed).toFixed(2)}×`}><input type="range" min="0.8" max="1.3" step="0.02" value={s.voice_speed} onChange={e => set('voice_speed', +e.target.value)} /></Field></div></div>
            <Check k="burn_captions">Draw captions in the picture (subtitle files are always written)</Check>
            <Check k="music">Add the generated ambient music bed</Check><Check k="sfx">Add sound effects on visual cues</Check>
            <Line k="Urdu narration"><Planned /></Line><Line k="Premium cloud voices"><Planned>Optional, paid · off</Planned></Line><Line k="Licensed music library"><Planned /></Line></Card>
          <Card title="This machine">{!h ? <Loading rows={2} /> : <>
            <Line k="Version">{h.version}</Line><Line k="FFmpeg"><Badge tone={h.ffmpeg ? 'ok' : 'danger'}>{h.ffmpeg ? 'Found' : 'Missing'}</Badge></Line>
            {h.voice_engines.map(e => <Line key={e.id || e.name} k={`Voice: ${e.name || e.id}`}><Badge tone={e.available ? 'ok' : 'warn'}>{e.available ? 'Ready' : 'Not installed'}</Badge></Line>)}
            <Line k="Render size">{h.render.width}×{h.render.height} · {h.render.fps} fps</Line><Line k="Memory">{h.memory.available_mb} MB free of {h.memory.total_mb}</Line><Line k="Free disk">{h.disk_free_gb} GB</Line>
            <Line k="Treatments">{h.treatments.join(', ')}</Line><Line k="3D scenes"><Planned>Optional, not built</Planned></Line><Line k="Sign-in"><span className="muted">None. The studio listens on this computer only.</span></Line></>}</Card>
        </div>
      </div>
    </div>
  </Shell>
}
