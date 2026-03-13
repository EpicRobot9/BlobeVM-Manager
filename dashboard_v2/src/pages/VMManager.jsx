import React, { useEffect, useMemo, useRef, useState } from 'react'
import Button from '../components/Button'
import apiFetch from '../lib/fetchWrapper'
import Modal from '../components/Modal'
import VmExec from '../components/VmExec'
import { useToasts } from '../components/ToastProvider'

function toneFor(status){
  const s = (status || '').toLowerCase()
  if(s.includes('up') || s.includes('running') || s.includes('healthy')) return 'live'
  if(s.includes('rebuild') || s.includes('update')) return 'busy'
  return 'down'
}

function StatusBadge({ status }){
  const tone = toneFor(status)
  const colors = {
    live: ['#22c55e', '#14532d'],
    busy: ['#f59e0b', '#78350f'],
    down: ['#fb7185', '#4c0519']
  }
  const [dot, bg] = colors[tone]
  return (
    <div className="vm-status-badge" style={{ background:bg, color:'#fff' }}>
      <span style={{ width:10, height:10, borderRadius:999, background:dot, boxShadow:`0 0 14px ${dot}` }} />
      <span>{status || 'Unknown'}</span>
    </div>
  )
}

function StatMeter({ label, value, tone='cpu' }){
  const safe = Math.max(0, Math.min(100, Number(value || 0)))
  return (
    <div className="vm-meter">
      <div className="vm-meter-head">
        <span>{label}</span>
        <strong>{safe}%</strong>
      </div>
      <div className="vm-meter-track">
        <div className={`vm-meter-fill ${tone}`} style={{ width: `${safe}%` }} />
      </div>
    </div>
  )
}

function VmCard({ vm, onAction, onDetails, onProfileChange, onManage, profileBusy, busyAction, refreshing }){
  const tone = toneFor(vm.status)
  const profile = vm._profile || vm._optimizer?.profile || 'desktop'
  return (
    <div className={`vm-card vm-card-${tone}`}>
      <div className="vm-card-refresh" aria-hidden="true">
        {refreshing ? <span className="vm-mini-spinner" /> : <span className="vm-refresh-idle" />}
      </div>

      <div className="vm-card-top">
        <div>
          <div className="vm-card-name">{vm.name}</div>
          <div className="vm-card-url"><a href={vm.url} target="_blank" rel="noreferrer">{vm.url}</a></div>
          {vm._title ? <div style={{color:'var(--muted)', fontSize:13, marginTop:6}}>Tab title: {vm._title}</div> : null}
          {vm._hostOverride ? <div style={{color:'var(--muted)', fontSize:13, marginTop:4}}>Domain: {vm._hostOverride}</div> : null}
        </div>
        <StatusBadge status={vm.status || 'Unknown'} />
      </div>

      <div className="vm-card-stats">
        <StatMeter label="CPU" value={vm._stats?.cpu_percent ?? 0} tone="cpu" />
        <StatMeter label="RAM" value={vm._stats?.mem_percent ?? 0} tone="ram" />
      </div>

      <div className="vm-card-meta">
        <div className="vm-meta-chip">Port: {vm.port || '—'}</div>
        <div className="vm-meta-chip">Name: {vm.name}</div>
        <label className="vm-meta-chip" style={{ gap:8 }}>
          <span>Type</span>
          <select value={profile} disabled={profileBusy} onChange={e=>onProfileChange(vm.name, e.target.value)} style={{ background:'rgba(2,6,23,.8)', color:'#fff', border:'1px solid rgba(255,255,255,.12)', borderRadius:8, padding:'4px 8px' }}>
            <option value="light">light</option>
            <option value="desktop">desktop</option>
            <option value="interactive">interactive</option>
            <option value="gaming">gaming</option>
            <option value="background">background</option>
            <option value="disposable">disposable</option>
          </select>
        </label>
      </div>

      <div className="vm-card-actions">
        <Button disabled={busyAction} onClick={()=>onAction('start', vm.name)}>Start</Button>
        <Button disabled={busyAction} onClick={()=>onAction('stop', vm.name)}>Stop</Button>
        <Button disabled={busyAction} onClick={()=>onAction('restart', vm.name)}>Restart</Button>
        <Button disabled={busyAction} onClick={()=>onDetails(vm.name)}>Console</Button>
        <Button disabled={busyAction} onClick={()=>onManage(vm.name)}>Manage</Button>
      </div>
    </div>
  )
}

export default function VMManager(){
  const { addToast } = useToasts()
  const [instances, setInstances] = useState([])
  const [initialLoading, setInitialLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [selected, setSelected] = useState(null)
  const [logs, setLogs] = useState('')
  const [logLoading, setLogLoading] = useState(false)
  const [announcement, setAnnouncement] = useState('')
  const [busyAction, setBusyAction] = useState('')
  const [optimizer, setOptimizer] = useState({ capacity:{}, vmStates:[], profiles:{} })
  const [profileBusy, setProfileBusy] = useState('')
  const [createName, setCreateName] = useState('')
  const [createBusy, setCreateBusy] = useState(false)
  const [manageVm, setManageVm] = useState(null)
  const [manageDraft, setManageDraft] = useState({ title:'', hostOverride:'', faviconUrl:'' })
  const [manageBusy, setManageBusy] = useState(false)
  const [faviconFile, setFaviconFile] = useState(null)
  const prevStatsRef = useRef({})
  const lastAnnounceRef = useRef({})
  const didLoadOnceRef = useRef(false)

  async function load({ silent = false } = {}){
    if(silent && didLoadOnceRef.current){
      setRefreshing(true)
    } else {
      setInitialLoading(true)
    }
    try{
      const [rList, rStats, rOpt, rSettings] = await Promise.all([
        apiFetch('/list'),
        apiFetch('/vm/stats').catch(()=>({ok:false})),
        apiFetch('/optimizer/v2/summary').catch(()=>({ok:false})),
        apiFetch('/settings').catch(()=>({ok:false}))
      ])
      const j = await rList.json().catch(()=>({instances:[]}))
      const statJ = rStats && rStats.ok ? await rStats.json().catch(()=>({vms:{}})) : (rStats && typeof rStats.json === 'function' ? await rStats.json().catch(()=>({vms:{}})) : {vms:{}})
      const optJ = rOpt && typeof rOpt.json === 'function' ? await rOpt.json().catch(()=>({ok:false})) : {ok:false}
      const settingsJ = rSettings && typeof rSettings.json === 'function' ? await rSettings.json().catch(()=>({})) : {}
      const statsMap = (statJ && statJ.vms) ? statJ.vms : {}
      const optimizerVmMap = Object.fromEntries(((optJ && optJ.vmStates) || []).map(v => [v.name, v]))
      const profileMap = (optJ && optJ.profiles) || {}
      const titleMap = (settingsJ && settingsJ.vm_titles) || {}

      const vmSettingsPairs = await Promise.all((j.instances || []).map(async (it) => {
        try{
          const resp = await apiFetch(`/vm-settings/${encodeURIComponent(it.name)}`)
          const data = await resp.json().catch(()=>({ ok:false }))
          return [it.name, data]
        }catch(_e){
          return [it.name, {}]
        }
      }))
      const vmSettingsMap = Object.fromEntries(vmSettingsPairs)

      const insts = (j.instances || []).map(it => ({
        ...it,
        _stats: statsMap[it.name] || statsMap[''+it.name] || statsMap[it.name],
        _optimizer: optimizerVmMap[it.name] || {},
        _profile: profileMap[it.name] || 'desktop',
        _title: vmSettingsMap[it.name]?.title || titleMap[it.name] || '',
        _hostOverride: vmSettingsMap[it.name]?.hostOverride || '',
        _faviconUrl: vmSettingsMap[it.name]?.faviconUrl || ''
      }))

      try{
        const prev = prevStatsRef.current || {}
        const now = Date.now()
        const cpuThresholdDelta = parseFloat(localStorage.getItem('nbv2_announce_cpu_delta') || '20')
        const memThresholdDelta = parseFloat(localStorage.getItem('nbv2_announce_mem_delta') || '25')
        const cpuAbsolute = parseFloat(localStorage.getItem('nbv2_announce_cpu_absolute') || '85')
        const memAbsolute = parseFloat(localStorage.getItem('nbv2_announce_mem_absolute') || '90')
        const announceCooldownMs = parseInt(localStorage.getItem('nbv2_announce_cooldown') || String(60*1000), 10)

        for(const [vm, s] of Object.entries(statsMap || {})){
          const cpu = (s && typeof s.cpu_percent === 'number') ? s.cpu_percent : null
          const mem = (s && typeof s.mem_percent === 'number') ? s.mem_percent : null
          const p = prev[vm] || {}
          const prevCpu = (p && typeof p.cpu_percent === 'number') ? p.cpu_percent : undefined
          const prevMem = (p && typeof p.mem_percent === 'number') ? p.mem_percent : undefined
          const lastAnn = lastAnnounceRef.current[vm] || 0

          if(prevCpu !== undefined && cpu !== null && ((((cpu - prevCpu) >= cpuThresholdDelta) && cpu >= 30) || (cpu >= cpuAbsolute && prevCpu < cpuAbsolute)) && now - lastAnn > announceCooldownMs){
            const msg = `Alert: VM ${vm} CPU ${cpu}% (was ${prevCpu}%)`
            setAnnouncement(msg)
            addToast({title:`VM ${vm} CPU`, message: `${cpu}% (was ${prevCpu}%)`, type:'warn', timeout:8000})
            lastAnnounceRef.current[vm] = now
            setTimeout(()=>setAnnouncement(''), 8000)
          }

          if(prevMem !== undefined && mem !== null && ((((mem - prevMem) >= memThresholdDelta) && mem >= 40) || (mem >= memAbsolute && prevMem < memAbsolute)) && now - lastAnn > announceCooldownMs){
            const msg = `Alert: VM ${vm} memory ${mem}% (was ${prevMem}%)`
            setAnnouncement(msg)
            addToast({title:`VM ${vm} Memory`, message: `${mem}% (was ${prevMem}%)`, type:'warn', timeout:8000})
            lastAnnounceRef.current[vm] = now
            setTimeout(()=>setAnnouncement(''), 8000)
          }
        }
      }catch(e){}

      prevStatsRef.current = statsMap || {}
      setInstances(insts)
      if(optJ && optJ.ok) setOptimizer(optJ)
      didLoadOnceRef.current = true
    }catch(e){
      console.error('load instances', e)
      addToast({ title:'Load failed', message:String(e), type:'error', timeout:8000 })
    }
    setInitialLoading(false)
    setRefreshing(false)
  }

  useEffect(()=>{
    let stopped = false
    async function tick(first = false){
      if(stopped) return
      await load({ silent: !first })
      const ivMs = parseInt(localStorage.getItem('nbv2_update_interval') || '3000', 10)
      await new Promise(r=>setTimeout(r, Math.max(800, ivMs)))
      if(!stopped) tick(false)
    }
    tick(true)
    return ()=>{ stopped = true }
  }, [])

  async function action(cmd, name, opts = {}){
    const key = `${cmd}:${name}`
    const force = !!opts.force
    setBusyAction(key)
    try{
      if(cmd === 'start'){
        await apiFetch(`/optimizer/activity/${encodeURIComponent(name)}`, { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ source: force ? 'force-start-click' : 'start-click' }) }).catch(()=>null)
        const admRes = await apiFetch(`/optimizer/admission/${encodeURIComponent(name)}${force ? '?force=1' : ''}`).catch(()=>null)
        const admBody = admRes && typeof admRes.json === 'function' ? await admRes.json().catch(()=>null) : null
        if(admBody && admBody.admission && admBody.admission.ok === false && !force){
          const proceed = window.confirm(`${admBody.admission.reason || 'Start blocked by optimizer admission control'}\n\nForce start anyway?`)
          if(proceed){
            setBusyAction('')
            return action(cmd, name, { force:true })
          }
          throw new Error(admBody.admission.reason || 'Start blocked by optimizer admission control')
        }
      }
      const startBody = cmd === 'start' && force ? new URLSearchParams({ force:'1' }) : undefined
      const res = await apiFetch(`/${cmd}/${encodeURIComponent(name)}`, {
        method:'POST',
        headers: startBody ? {'Content-Type':'application/x-www-form-urlencoded'} : undefined,
        body: startBody
      })
      const body = await res.json().catch(()=>({ ok:res.ok }))
      if(!res.ok || body.ok === false){
        throw new Error(body.error || body.message || `Failed to ${cmd} ${name}`)
      }
      addToast({ title:`${name}`, message:`${cmd} request sent successfully${force ? ' (forced)' : ''}`, type:'success', timeout:5000 })
    }catch(e){
      console.error('action error', e)
      addToast({ title:`${name}`, message:String(e), type:'error', timeout:8000 })
    }
    setBusyAction('')
    setTimeout(()=>load({ silent:true }), 800)
  }

  async function createVm(e){
    e?.preventDefault?.()
    const name = createName.trim().toLowerCase()
    if(!name) return
    setCreateBusy(true)
    try{
      const body = new URLSearchParams({ name })
      const res = await apiFetch('/create', { method:'POST', headers:{'Content-Type':'application/x-www-form-urlencoded'}, body })
      const j = await res.json().catch(()=>({ ok:res.ok }))
      if(!res.ok || j.ok === false) throw new Error(j.error || `Failed to create ${name}`)
      addToast({ title:'VM created', message:`${name} is being created`, type:'success', timeout:5000 })
      setCreateName('')
      setTimeout(()=>load({ silent:true }), 1000)
    }catch(err){
      addToast({ title:'Create failed', message:String(err), type:'error', timeout:8000 })
    }
    setCreateBusy(false)
  }

  async function setProfile(name, profile){
    setProfileBusy(name)
    try{
      const r = await apiFetch(`/optimizer/profile/${encodeURIComponent(name)}`, {
        method:'POST',
        headers:{'Content-Type':'application/json'},
        body: JSON.stringify({ profile })
      })
      const j = await r.json().catch(()=>({ ok:r.ok }))
      if(!r.ok || j.ok === false) throw new Error(j.error || `Failed to set profile for ${name}`)
      setInstances(items => items.map(vm => vm.name === name ? { ...vm, _profile: j.profile || profile } : vm))
      addToast({ title:name, message:`VM type set to ${j.profile || profile}`, type:'success', timeout:4000 })
      setTimeout(()=>load({ silent:true }), 500)
    }catch(e){
      addToast({ title:name, message:String(e), type:'error', timeout:8000 })
    }
    setProfileBusy('')
  }

  async function openDetails(name){
    setSelected(name)
    await apiFetch(`/optimizer/activity/${encodeURIComponent(name)}`, { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ source:'details-open' }) }).catch(()=>null)
    await fetchLogs(name)
  }

  async function fetchLogs(name){
    setLogLoading(true)
    try{
      const r = await apiFetch(`/vm/logs/${encodeURIComponent(name)}`)
      const j = await r.json().catch(()=>({ok:false, logs:''}))
      setLogs(j.logs || j.logs === '' ? (j.logs || '') : (j.error || ''))
    }catch(e){
      setLogs('Error loading logs: ' + String(e))
    }
    setLogLoading(false)
  }

  async function openManage(name){
    setManageVm(name)
    setManageBusy(true)
    setFaviconFile(null)
    try{
      const r = await apiFetch(`/vm-settings/${encodeURIComponent(name)}`)
      const j = await r.json().catch(()=>({}))
      setManageDraft({
        title: j.title || '',
        hostOverride: j.hostOverride || '',
        faviconUrl: j.faviconUrl || ''
      })
    }catch(e){
      addToast({ title:'Load failed', message:String(e), type:'error', timeout:7000 })
    }
    setManageBusy(false)
  }

  async function saveManageSettings(){
    if(!manageVm) return
    setManageBusy(true)
    try{
      const r = await apiFetch(`/vm-settings/${encodeURIComponent(manageVm)}`, {
        method:'POST',
        headers:{'Content-Type':'application/json'},
        body: JSON.stringify({ title: manageDraft.title, hostOverride: manageDraft.hostOverride })
      })
      const j = await r.json().catch(()=>({ ok:r.ok }))
      if(!r.ok || j.ok === false) throw new Error(j.error || 'Failed saving VM settings')

      if(faviconFile){
        const fd = new FormData()
        fd.append('file', faviconFile)
        const favRes = await apiFetch(`/upload-vm-favicon/${encodeURIComponent(manageVm)}`, { method:'POST', body: fd })
        const favJ = await favRes.json().catch(()=>({ ok:favRes.ok }))
        if(!favRes.ok || favJ.ok === false) throw new Error(favJ.error || 'Failed uploading favicon')
      }

      addToast({ title:manageVm, message:'VM settings updated', type:'success', timeout:5000 })
      setManageVm(null)
      setFaviconFile(null)
      setTimeout(()=>load({ silent:true }), 700)
    }catch(e){
      addToast({ title:manageVm || 'VM', message:String(e), type:'error', timeout:8000 })
    }
    setManageBusy(false)
  }

  async function deleteVm(name){
    const confirmed = window.prompt(`Delete ${name}? This removes the VM. Type DELETE to confirm.`)
    if(confirmed !== 'DELETE') return
    setBusyAction(`delete:${name}`)
    try{
      const res = await apiFetch(`/delete/${encodeURIComponent(name)}`, { method:'POST' })
      const j = await res.json().catch(()=>({ ok:res.ok }))
      if(!res.ok || j.ok === false) throw new Error(j.error || `Failed to delete ${name}`)
      addToast({ title:name, message:'VM deleted', type:'success', timeout:5000 })
      if(manageVm === name) setManageVm(null)
      setTimeout(()=>load({ silent:true }), 700)
    }catch(e){
      addToast({ title:name, message:String(e), type:'error', timeout:8000 })
    }
    setBusyAction('')
  }

  useEffect(()=>{
    let iv
    if(selected) iv = setInterval(()=>fetchLogs(selected), 2500)
    return ()=>{ if(iv) clearInterval(iv) }
  }, [selected])

  const summary = useMemo(()=>{
    const total = instances.length
    const live = instances.filter(x => toneFor(x.status) === 'live').length
    const down = instances.filter(x => toneFor(x.status) === 'down').length
    const busy = instances.filter(x => toneFor(x.status) === 'busy').length
    return { total, live, down, busy }
  }, [instances])

  return (
    <div>
      <div className="sr-only" role="status" aria-live="polite" aria-atomic="true">{announcement}</div>
      <div className="vm-page-hero glass-card">
        <div>
          <div className="eyebrow">Dashboard v2</div>
          <h1 style={{margin:'8px 0 10px'}}>VM Control Center</h1>
          <div style={{color:'var(--muted)', maxWidth:760}}>Create new VMs, manage running ones, open consoles, and edit per-VM presentation settings like custom domain, tab title, and favicon without touching the old dashboard.</div>
        </div>
        <div style={{display:'flex', alignItems:'center', gap:14, flexWrap:'wrap'}}>
          {refreshing && (
            <div className="vm-refresh-banner">
              <span className="vm-mini-spinner" />
              <span>Refreshing fleet…</span>
            </div>
          )}
          <div className="vm-summary-grid">
            <div className="summary-pill"><strong>{summary.total}</strong><span>Total</span></div>
            <div className="summary-pill live"><strong>{summary.live}</strong><span>Running</span></div>
            <div className="summary-pill warn"><strong>{summary.busy}</strong><span>Busy</span></div>
            <div className="summary-pill danger"><strong>{summary.down}</strong><span>Down</span></div>
          </div>
        </div>
      </div>

      <div className="glass-card" style={{marginTop:16}}>
        <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',gap:12, flexWrap:'wrap'}}>
          <div style={{color:'var(--muted)', maxWidth:640}}>Use the create form to spin up new VMs. Each VM card now also has a Manage flow for deleting the VM, changing its custom domain/host override, tab title, and favicon.</div>
          <Button onClick={()=>load({ silent:true })}>Refresh</Button>
        </div>

        <form onSubmit={createVm} style={{display:'flex', gap:10, flexWrap:'wrap', marginTop:18, alignItems:'center'}}>
          <input value={createName} onChange={e=>setCreateName(e.target.value)} placeholder="new vm name (e.g. alpha)" pattern="[a-z0-9][a-z0-9._-]{0,62}" style={{minWidth:260, background:'rgba(2,6,23,.7)', color:'#fff', border:'1px solid rgba(255,255,255,.12)', borderRadius:12, padding:'12px 14px'}} />
          <Button type="submit" disabled={createBusy}>{createBusy ? 'Creating…' : 'Create VM'}</Button>
        </form>

        <div style={{marginTop:18}}>
          {initialLoading && instances.length === 0 ? (
            <div className="vm-card-grid">
              {Array.from({ length:4 }).map((_, i)=><div key={i} className="skeleton" style={{height:220,borderRadius:20}} />)}
            </div>
          ) : instances.length === 0 ? (
            <div className="vm-empty-state">No VMs found. Incredible. A VM manager with nothing to manage.</div>
          ) : (
            <div className="vm-card-grid">
              {instances.map(vm => <VmCard key={vm.name} vm={vm} onAction={action} onDetails={openDetails} onManage={openManage} onProfileChange={setProfile} profileBusy={profileBusy === vm.name} busyAction={!!busyAction} refreshing={refreshing} />)}
            </div>
          )}
        </div>
      </div>

      <Modal open={!!selected} title={`VM: ${selected}`} onClose={()=>setSelected(null)} width={1180}>
        <div style={{display:'flex',gap:12, flexWrap:'wrap'}}>
          <div style={{flex:'1 1 620px'}}>
            <iframe title={`VM ${selected}`} src={`/dashboard/vm/${encodeURIComponent(selected)}/`} style={{width:'100%',height:360,border:'1px solid rgba(255,255,255,0.04)', background:'#020617'}} />
            <div style={{marginTop:12}}>
              <VmExec vmName={selected} />
            </div>
          </div>
          <div style={{width:420,maxWidth:'100%',display:'flex',flexDirection:'column',gap:8}}>
            <div style={{fontSize:13,color:'var(--muted)'}}>Console / Logs</div>
            <div style={{background:'#02040a',color:'#dff',padding:12,borderRadius:12,height:460,overflow:'auto',fontFamily:'monospace',fontSize:12,border:'1px solid rgba(255,255,255,0.04)'}}>
              {logLoading ? <div>Loading logs…</div> : <pre style={{whiteSpace:'pre-wrap',margin:0}}>{logs}</pre>}
            </div>
            <div style={{display:'flex',gap:8,flexWrap:'wrap'}}>
              <Button onClick={()=>fetchLogs(selected)}>Refresh Logs</Button>
              <a href={`/dashboard/vm/${encodeURIComponent(selected)}/`} target="_blank" rel="noreferrer"><Button>Open in new tab</Button></a>
            </div>
          </div>
        </div>
      </Modal>

      <Modal open={!!manageVm} title={`Manage VM: ${manageVm}`} onClose={()=>setManageVm(null)} width={760}>
        <div style={{display:'grid', gap:14}}>
          <div style={{color:'var(--muted)'}}>Edit the custom host/domain this VM uses, the browser tab title shown in the wrapper, and optionally upload a per-VM favicon.</div>
          <label style={{display:'grid', gap:6}}>
            <span>Custom domain / host override</span>
            <input value={manageDraft.hostOverride || ''} onChange={e=>setManageDraft(s => ({ ...s, hostOverride: e.target.value }))} placeholder="vm42.example.com (leave blank to use default)" style={{background:'rgba(2,6,23,.7)', color:'#fff', border:'1px solid rgba(255,255,255,.12)', borderRadius:12, padding:'12px 14px'}} />
          </label>
          <label style={{display:'grid', gap:6}}>
            <span>Browser tab title</span>
            <input value={manageDraft.title || ''} onChange={e=>setManageDraft(s => ({ ...s, title: e.target.value }))} placeholder="My Cool VM" style={{background:'rgba(2,6,23,.7)', color:'#fff', border:'1px solid rgba(255,255,255,.12)', borderRadius:12, padding:'12px 14px'}} />
          </label>
          <label style={{display:'grid', gap:6}}>
            <span>VM favicon / tab icon</span>
            <input type="file" accept=".ico,image/x-icon,image/png,image/webp,image/jpeg" onChange={e=>setFaviconFile(e.target.files?.[0] || null)} style={{background:'rgba(2,6,23,.7)', color:'#fff', border:'1px solid rgba(255,255,255,.12)', borderRadius:12, padding:'12px 14px'}} />
          </label>
          {manageDraft.faviconUrl ? (
            <div style={{display:'flex', alignItems:'center', gap:10, color:'var(--muted)'}}>
              <img src={`${manageDraft.faviconUrl}?v=${Date.now()}`} alt="VM favicon" style={{width:20,height:20,borderRadius:4}} />
              <span>Existing favicon detected for this VM.</span>
            </div>
          ) : null}
          <div style={{display:'flex', gap:10, flexWrap:'wrap'}}>
            <Button onClick={saveManageSettings} disabled={manageBusy}>{manageBusy ? 'Saving…' : 'Save VM settings'}</Button>
            <Button onClick={()=>deleteVm(manageVm)} disabled={manageBusy} style={{background:'linear-gradient(135deg,#ef4444,#b91c1c)', color:'#fff'}}>Delete VM</Button>
          </div>
        </div>
      </Modal>
    </div>
  )
}
