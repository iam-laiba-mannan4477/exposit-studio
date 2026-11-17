import React from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import './styles.css'
import { ToastHost, Shell, Empty } from './ui.jsx'
import { Home, Productions, NewProduction } from './pages/Home.jsx'
import Production from './pages/Production.jsx'
import { Library, Tools } from './pages/Library.jsx'
import { Scout, References } from './pages/Research.jsx'
import { Renders, Settings } from './pages/System.jsx'

class Boundary extends React.Component {
  state = { error: null }
  static getDerivedStateFromError(error) { return { error } }
  render() {
    if (!this.state.error) return this.props.children
    return <div style={{ padding: 48 }}><div className="err">Something in the interface failed: {String(this.state.error.message)}. Reload the page; your productions are safe on disk.</div></div>
  }
}

createRoot(document.getElementById('root')).render(
  <Boundary><ToastHost><BrowserRouter>
    <Routes>
      <Route path="/" element={<Home />} />
      <Route path="/productions" element={<Productions />} />
      <Route path="/new" element={<NewProduction />} />
      <Route path="/p/:id" element={<Production />} />
      <Route path="/p/:id/:tab" element={<Production />} />
      <Route path="/library" element={<Library />} />
      <Route path="/references" element={<References />} />
      <Route path="/tools" element={<Tools />} />
      <Route path="/scout" element={<Scout />} />
      <Route path="/renders" element={<Renders />} />
      <Route path="/settings" element={<Settings />} />
      <Route path="*" element={<Shell crumbs={['Not found']}><Empty title="This page does not exist" /></Shell>} />
    </Routes>
  </BrowserRouter></ToastHost></Boundary>
)
