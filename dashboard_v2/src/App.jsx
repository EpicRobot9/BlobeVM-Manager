import React, { useState, useEffect } from 'react'
import { Routes, Route, Navigate, useNavigate, useLocation } from 'react-router-dom'
import Topbar from './components/Topbar'
import Sidebar from './components/Sidebar'
import ToastProvider from './components/ToastProvider'
import Login from './components/Login'
import Home from './pages/Home'
import VMManager from './pages/VMManager'
import ResourceUsage from './pages/ResourceUsage'
import Logs from './pages/Logs'
import Optimizer from './pages/Optimizer'
import Settings from './pages/Settings'
import APIInfo from './pages/APIInfo'
import AdvancedTools from './pages/AdvancedTools'
import Users from './pages/Users'
import { authStatus, logout } from './lib/fetchWrapper'

export default function App(){
  const [collapsed, setCollapsed] = useState(()=>{
    try{ return JSON.parse(localStorage.getItem('nbv2_sidebar_collapsed') || 'false') }catch(e){ return false }
  })
  const [mobileOpen, setMobileOpen] = useState(false)
  const [auth, setAuth] = useState({loading:true, allowed:false, required:true})
  const [animations, setAnimations] = useState(()=>localStorage.getItem('nbv2_animations') !== '0')
  const navigate = useNavigate()
  // Hooks must always run in the same order; location used to sit below the
  // login return and crashed immediately after a successful login.
  const location = useLocation()

  useEffect(()=>{
    if(import.meta.env.DEV && new URLSearchParams(window.location.search).get('preview') === '1'){
      setAuth({loading:false, allowed:true, required:false})
      return undefined
    }
    let live = true
    authStatus().then(result => {
      if(!live) return
      setAuth({loading:false, allowed: result.authRequired === false || result.ok === true, required: result.authRequired !== false, error: result.error})
    }).catch(() => live && setAuth({loading:false, allowed:false, required:true, error:'Unable to check dashboard session'}))
    return ()=>{ live = false }
  },[])

  useEffect(()=>{
    const refresh = () => setAnimations(localStorage.getItem('nbv2_animations') !== '0')
    window.addEventListener('nbv2:settings', refresh)
    return ()=>window.removeEventListener('nbv2:settings', refresh)
  }, [])

  if(auth.loading){
    return <div className="app-shell"><main className="main loading-screen" role="status">Checking dashboard session…</main></div>
  }

  if(!auth.allowed){
    return <div className="app-shell"><main className="main login-shell"><Login onLogin={()=>{ setAuth({loading:false, allowed:true, required:true}); navigate('/') }} />{auth.error && <p role="alert">{auth.error}</p>}</main></div>
  }

  return (
    <ToastProvider>
    <div className="app-shell" data-animations={animations ? 'on' : 'off'}>
      {mobileOpen && <button className="mobile-backdrop" aria-label="Close navigation" onClick={()=>setMobileOpen(false)} />}
      <aside className={`sidebar ${collapsed? 'collapsed':''} ${mobileOpen? 'mobile-open':''}`}>
        <Sidebar collapsed={collapsed} onCollapse={()=>{
          const next = !collapsed
          try{ localStorage.setItem('nbv2_sidebar_collapsed', JSON.stringify(next)) }catch(e){}
          setCollapsed(next)
        }} mobileOpen={mobileOpen} onMobileClose={()=>setMobileOpen(false)} />
      </aside>
      <div style={{flex:1,display:'flex',flexDirection:'column'}}>
        <div className="topbar"><Topbar collapsed={collapsed} onToggle={()=>{
          const next = !collapsed
          try{ localStorage.setItem('nbv2_sidebar_collapsed', JSON.stringify(next)) }catch(e){}
          setCollapsed(next)
        }} onToggleMobile={()=>setMobileOpen(v=>!v)} onLogout={async ()=>{ await logout(); setAuth({loading:false, allowed:false, required:true}); navigate('/login') }} /></div>
        <main className="main">
          <div key={location.pathname} className="page">
            <Routes>
              <Route path="/" element={<Home/>} />
              <Route path="/vm" element={<VMManager/>} />
              <Route path="/resources" element={<ResourceUsage/>} />
              <Route path="/logs" element={<Logs/>} />
              <Route path="/optimizer" element={<Optimizer/>} />
              <Route path="/settings" element={<Settings/>} />
              <Route path="/api" element={<APIInfo/>} />
              <Route path="/tools" element={<AdvancedTools/>} />
              <Route path="/users" element={<Users/>} />
              <Route path="/login" element={<Navigate to="/" replace />} />
            </Routes>
          </div>
        </main>
      </div>
    </div>
    </ToastProvider>
  )
}
