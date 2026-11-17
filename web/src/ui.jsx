import React, { useCallback, useEffect, useRef, useState, createContext, useContext } from 'react'
import { NavLink } from 'react-router-dom'

// ---------------------------------------------------------------- API
export async function api(path, opts = {}) {
  const init = { method: opts.method || 'GET', headers: {} }
  if (opts.form) init.body = opts.form
  else if (opts.body !== undefined) { init.body = JSON.stringify(opts.body); init.headers['Content-Type'] = 'application/json' }
  const r = await fetch('/api' + path, init)
  if (!r.ok) {
    let msg = `Request failed (${r.status})`
    try { const j = await r.json(); msg = typeof j.detail === 'string' ? j.detail : JSON.stringify(j.detail) } catch { /* not JSON */ }
    throw new Error(msg)
  }
  return opts.blob ? r.blob() : r.json()
}

/** Loads a path, and reloads it every `every` ms while `every` is set. */
export function useApi(path, every = 0) {
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const alive = useRef(true)
  const load = useCallback(async () => {
    if (!path) return
    try { const d = await api(path); if (alive.current) { setData(d); setError('') } }
    catch (e) { if (alive.current) setError(e.message) }
    finally { if (alive.current) setLoading(false) }
  }, [path])
  useEffect(() => { alive.current = true; setLoading(true); load(); return () => { alive.current = false } }, [load])
  useEffect(() => { if (!every) return; const t = setInterval(load, every); return () => clearInterval(t) }, [every, load])
  return { data, error, loading, reload: load }
}

// ---------------------------------------------------------------- toasts
const ToastCtx = createContext(() => {})
export const useToast = () => useContext(ToastCtx)
export function ToastHost({ children }) {
  const [items, setItems] = useState([])
  const push = useCallback((text, kind = 'info') => {
    const id = Math.random().toString(36).slice(2)
    setItems(x => [...x, { id, text, kind }])
    setTimeout(() => setItems(x => x.filter(i => i.id !== id)), kind === 'error' ? 8000 : 4500)
  }, [])
  return <ToastCtx.Provider value={push}>{children}
    <div className="toasts" role="status" aria-live="polite">{items.map(i => <div key={i.id} className={'toast ' + i.kind}>{i.text}</div>)}</div>
  </ToastCtx.Provider>
}
/** Wraps an action: shows the error as a toast instead of failing silently. */
export function useAct() {
  const toast = useToast()
  const [busy, setBusy] = useState('')
  const act = useCallback(async (name, fn, okMsg) => {
    setBusy(name)
    try { const r = await fn(); if (okMsg) toast(typeof okMsg === 'function' ? okMsg(r) : okMsg); return r }
    catch (e) { toast(e.message, 'error'); return null }
    finally { setBusy('') }
  }, [toast])
  return [act, busy]
}

// ---------------------------------------------------------------- small pieces
const ICON = {
  home: <path d="M3 10l7-6 7 6v7H3z" />, projects: <><rect x="3" y="4" width="14" height="12" rx="2" /><path d="M8 8l4 2-4 2z" /></>,
  library: <path d="M4 4h4v12H4zM10 4h3v12h-3zM15 5l2 11" />, refs: <><rect x="3" y="4" width="14" height="10" rx="2" /><path d="M7 17h6M10 14v3" /></>,
  tools: <path d="M12 3a4 4 0 00-3.5 6L3 14.5 5.5 17l5.500-5.500A4 4 0 0017 8l-2.500 2.500L12 8l2.500-2.500A4 4 0 0012 3z" />,
  scout: <><circle cx="9" cy="9" r="5" /><path d="M13 13l4 4" /></>, renders: <><circle cx="10" cy="10" r="7" /><path d="M10 6v4l3 2" /></>,
  settings: <><circle cx="10" cy="10" r="3" /><path d="M10 2v3M10 15v3M2 10h3M15 10h3" /></>,
  empty: <><rect x="3" y="5" width="14" height="10" rx="2" /><path d="M3 9h14" /></>,
}
export const Icon = ({ name, size = 20 }) => <svg aria-hidden="true" width={size} height={size} viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">{ICON[name]}</svg>

const COLORS = { ok: 'var(--ok)', warn: 'var(--warn)', danger: 'var(--danger)', info: 'var(--info)', muted: 'var(--text-muted)', accent: 'var(--accent-400)', pink: 'var(--pink)' }
export const Badge = ({ tone = 'muted', children }) => <span className="badge"><i style={{ background: COLORS[tone] }} />{children}</span>
export const Planned = ({ children = 'Planned' }) => <span className="planned" title="Designed, not built yet">{children}</span>
const TIER = { verified: ['ok', 'Verified'], preference: ['accent', 'Preference'], observation: ['info', 'Observation'], hypothesis: ['warn', 'Hypothesis'], experiment: ['pink', 'Experiment'] }
export const Tier = ({ tier }) => <Badge tone={(TIER[tier] || TIER.hypothesis)[0]}>{(TIER[tier] || [0, tier])[1]}</Badge>
const STATE = { passed: ['ok', 'Passed'], running: ['info', 'Running'], pending: ['muted', 'Not started'], awaiting_approval: ['warn', 'Needs your approval'], needs_you: ['warn', 'Needs you'], failed: ['danger', 'Failed'],
  queued: ['muted', 'Queued'], done: ['ok', 'Done'], cancelled: ['muted', 'Cancelled'] }
export const StateBadge = ({ state }) => <Badge tone={(STATE[state] || STATE.pending)[0]}>{(STATE[state] || [0, state])[1]}</Badge>

export function Btn({ kind = '', sm, busy, children, ...p }) {
  return <button type="button" className={`btn ${kind} ${sm ? 'sm' : ''}`} {...p} disabled={p.disabled || busy}>{busy ? 'Working…' : children}</button>
}
export const Card = ({ title, right, children, className = '', style }) => <section className={'card ' + className} style={style}>
  {(title || right) && <div className="row between"><h3>{title}</h3>{right}</div>}{children}</section>
export const Field = ({ label, hint, children }) => <label className="field"><span className="label">{label}</span>{children}{hint && <span className="muted">{hint}</span>}</label>
export const Line = ({ k, children }) => <div className="line"><span className="sec">{k}</span><span style={{ textAlign: 'right' }}>{children}</span></div>
export const Empty = ({ title, children, action }) => <div className="empty"><Icon name="empty" size={28} /><b>{title}</b>{children && <div style={{ maxWidth: 520 }}>{children}</div>}{action}</div>
export const ErrorBox = ({ error, retry }) => error ? <div className="err" role="alert">{error} {retry && <Btn sm kind="ghost" onClick={retry}>Try again</Btn>}</div> : null
export const Loading = ({ rows = 3 }) => <div className="col" aria-busy="true">{Array.from({ length: rows }).map((_, i) => <div key={i} className="skeleton" style={{ height: 44 }} />)}</div>
export const Progress = ({ value }) => <div className="progress" role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round((value || 0) * 100)}><div style={{ width: `${Math.round((value || 0) * 100)}%` }} /></div>
export function Seg({ value, onChange, options }) {
  return <div className="seg" role="radiogroup">{options.map(o => <button key={o.value} type="button" role="radio" aria-checked={value === o.value} disabled={o.disabled}
    title={o.title} className={value === o.value ? 'on' : ''} onClick={() => onChange(o.value)}>{o.label}</button>)}</div>
}
export function Modal({ title, onClose, children, footer }) {
  useEffect(() => { const h = e => e.key === 'Escape' && onClose(); window.addEventListener('keydown', h); return () => window.removeEventListener('keydown', h) }, [onClose])
  return <div className="overlay" onMouseDown={e => e.target === e.currentTarget && onClose()}>
    <div className="dialog" role="dialog" aria-modal="true" aria-label={title}>
      <div className="row between"><h2>{title}</h2><Btn kind="ghost" sm onClick={onClose} aria-label="Close">Close</Btn></div>
      {children}{footer && <div className="row" style={{ justifyContent: 'flex-end' }}>{footer}</div>}
    </div></div>
}
export const fmtTime = t => t ? new Date(t * 1000).toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' }) : ''
export const fmtDur = s => { if (s == null) return ''; const m = Math.floor(s / 60); return `${m}:${String(Math.floor(s % 60)).padStart(2, '0')}` }
export const fmtSize = b => b > 1e6 ? (b / 1e6).toFixed(1) + ' MB' : Math.max(1, Math.round(b / 1e3)) + ' KB'

// ---------------------------------------------------------------- shell
const NAV = [['/', 'home', 'Home'], ['/productions', 'projects', 'Productions'], ['/library', 'library', 'Creative library'], ['/references', 'refs', 'Reference analysis'],
  ['/tools', 'tools', 'Tools and skills'], ['/scout', 'scout', 'Scout: trends'], ['/renders', 'renders', 'Renders and agent tasks'], ['/settings', 'settings', 'Settings']]

export function Shell({ crumbs = [], right, children }) {
  const { data } = useApi('/jobs?limit=12', 2500)
  const active = (data?.jobs || []).filter(j => j.state === 'running' || j.state === 'queued')
  const running = active.find(j => j.state === 'running')
  const mem = data?.memory || {}
  return <div className="shell">
    <nav className="rail" aria-label="Main">
      <div className="logo" aria-hidden="true"><svg width="12" height="12" viewBox="0 0 14 14"><path d="M3 1l10 6-10 6z" fill="#fff" /></svg></div>
      {NAV.map(([to, icon, label]) => <NavLink key={to} to={to} end={to === '/'} className={({ isActive }) => isActive ? 'on' : ''} aria-label={label}><Icon name={icon} /><span className="tip">{label}</span></NavLink>)}
    </nav>
    <div className="main">
      <header className="topbar">
        <div className="crumbs">{crumbs.map((c, i) => <React.Fragment key={i}>{i > 0 && <span className="sep">/</span>}<span className={i < crumbs.length - 1 ? 'sec' : ''}>{c}</span></React.Fragment>)}</div>
        <div className="row center" style={{ gap: 12, flexWrap: 'nowrap' }}>
          {right}
          {mem.total_mb && <span className="muted" title="Memory in use on this computer. The studio runs one job at a time to stay inside it.">RAM {mem.used_percent}% · studio {mem.studio_mb} MB</span>}
          <NavLink to="/renders" className="btn sm" title={running ? running.message : 'No job is running'}>
            <span className={'dot ' + (running ? 'running' : '')} />{running ? `${Math.round((running.progress || 0) * 100)}% · ${running.kind}` : 'Idle'}{active.length > 1 ? ` · ${active.length - 1} queued` : ''}
          </NavLink>
        </div>
      </header>
      <div className="page">{children}</div>
    </div>
  </div>
}
