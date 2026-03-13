import React, { useEffect, useMemo, useState } from 'react'
import apiFetch from '../lib/fetchWrapper'
import Button from '../components/Button'

function pressureTone(level){
  switch((level || '').toLowerCase()){
    case 'critical': return 'danger'
    case 'pressured': return 'warn'
    case 'warm': return 'warm'
    default: return 'ok'
  }
}

function SettingField({ label, value, onChange, type='number', min, step }){
  return (
    <label className="optimizer-setting-field">
      <span>{label}</span>
      <input type={type} value={value} min={min} step={step} onChange={onChange} />
    </label>
  )
}

export default function Optimizer(){
  const [summary, setSummary] = useState({ hostPressure:{ level:'healthy', reasons:[] }, capacity:{}, reliefCandidates:[], recommendations:[], vmStates:[], cfg:{}, history:{ events:[] }, trends:{ points:[] }, densityProfiles:{} })
  const [logs, setLogs] = useState('')
  const [running, setRunning] = useState(false)
  const [saving, setSaving] = useState(false)
  const [applyingDensity, setApplyingDensity] = useState(false)
  const [settingsDraft, setSettingsDraft] = useState({})

  async function loadStatus(){
    try{
      const r = await apiFetch('/optimizer/v2/summary')
      const j = await r.json().catch(()=>({}))
      if(j && j.ok){
        setSummary(j)
        setSettingsDraft({
          densityProfile: j.cfg?.densityProfile ?? 'single-user',
          hostCpuSoftLimit: j.cfg?.hostCpuSoftLimit ?? 75,
          hostCpuHardLimit: j.cfg?.hostCpuHardLimit ?? 90,
          minAvailableMemoryMb: j.cfg?.minAvailableMemoryMb ?? 2048,
          maxSwapPercent: j.cfg?.maxSwapPercent ?? 10,
          activityWindowSeconds: j.cfg?.activityWindowSeconds ?? 300,
          gamingVmCpuBudgetPercent: j.cfg?.gamingVmCpuBudgetPercent ?? 30,
          interactiveVmCpuBudgetPercent: j.cfg?.interactiveVmCpuBudgetPercent ?? 20,
          gamingVmMemoryMb: j.cfg?.gamingVmMemoryMb ?? 3072,
          interactiveVmMemoryMb: j.cfg?.interactiveVmMemoryMb ?? 2048,
          protectActiveVms: !!j.cfg?.protectActiveVms,
          blockStartsOnPressure: !!j.cfg?.blockStartsOnPressure,
        })
      }
    }catch(e){ console.error('optimizer status', e) }
  }

  async function runOnce(){
    try{
      setRunning(true)
      const r = await apiFetch('/optimizer/run-once', {method:'POST'})
      if(!r.ok) throw new Error('Failed to start optimizer run')
    }catch(e){ console.error('run once', e) }
    setRunning(false)
    setTimeout(()=>loadStatus(), 1200)
  }

  async function tailLogs(){
    try{
      const r = await apiFetch('/optimizer/logs')
      const text = await r.text()
      setLogs(text || '')
    }catch(e){ setLogs('Error: '+String(e)) }
  }

  async function saveSettings(){
    setSaving(true)
    try{
      const entries = [
        ['densityProfile', 'custom'],
        ['hostCpuSoftLimit', Number(settingsDraft.hostCpuSoftLimit || 75)],
        ['hostCpuHardLimit', Number(settingsDraft.hostCpuHardLimit || 90)],
        ['minAvailableMemoryMb', Number(settingsDraft.minAvailableMemoryMb || 2048)],
        ['maxSwapPercent', Number(settingsDraft.maxSwapPercent || 10)],
        ['activityWindowSeconds', Number(settingsDraft.activityWindowSeconds || 300)],
        ['gamingVmCpuBudgetPercent', Number(settingsDraft.gamingVmCpuBudgetPercent || 30)],
        ['interactiveVmCpuBudgetPercent', Number(settingsDraft.interactiveVmCpuBudgetPercent || 20)],
        ['gamingVmMemoryMb', Number(settingsDraft.gamingVmMemoryMb || 3072)],
        ['interactiveVmMemoryMb', Number(settingsDraft.interactiveVmMemoryMb || 2048)],
        ['protectActiveVms', !!settingsDraft.protectActiveVms],
        ['blockStartsOnPressure', !!settingsDraft.blockStartsOnPressure],
      ]
      for(const [key, val] of entries){
        const r = await apiFetch('/optimizer/set', {
          method:'POST',
          headers:{'Content-Type':'application/json'},
          body: JSON.stringify({ key, val })
        })
        const j = await r.json().catch(()=>({ ok:r.ok }))
        if(!r.ok || j.ok === false) throw new Error(j.error || `Failed to set ${key}`)
      }
      await loadStatus()
    }catch(e){
      console.error('save optimizer settings', e)
      alert(String(e))
    }
    setSaving(false)
  }

  async function applyDensityProfile(profile){
    if(!profile) return
    if(profile === 'custom'){
      setSettingsDraft(s => ({ ...s, densityProfile: 'custom' }))
      return
    }
    setApplyingDensity(true)
    try{
      const r = await apiFetch('/optimizer/density-profile', {
        method:'POST',
        headers:{'Content-Type':'application/json'},
        body: JSON.stringify({ profile })
      })
      const j = await r.json().catch(()=>({ ok:r.ok }))
      if(!r.ok || j.ok === false) throw new Error(j.error || `Failed to apply ${profile}`)
      await loadStatus()
    }catch(e){
      console.error('apply density profile', e)
      alert(String(e))
    }
    setApplyingDensity(false)
  }

  useEffect(()=>{
    loadStatus()
    tailLogs()
  }, [])

  const hostPressure = summary.hostPressure || { level:'healthy', reasons:[] }
  const capacity = summary.capacity || {}
  const recentEvents = (summary.history?.events || []).slice(-8).reverse()
  const recommendations = summary.recommendations || []
  const reliefCandidates = (summary.reliefCandidates || []).slice(0, 6)
  const vmStates = summary.vmStates || []
  const protectedCount = useMemo(()=>vmStates.filter(v => v.protected).length, [vmStates])
  const unstableCount = useMemo(()=>vmStates.filter(v => v.unstable).length, [vmStates])

  return (
    <div>
      <h1 style={{marginTop:0}}>Optimizer Control</h1>
      <div className="optimizer-grid">
        <div className="glass-card optimizer-card">
          <div className="optimizer-card-label">Host pressure</div>
          <div className={`optimizer-pressure pressure-${pressureTone(hostPressure.level)}`}>{hostPressure.level || 'healthy'}</div>
          <div className="optimizer-pressure-stats">
            <div><strong>{Math.round(hostPressure.vmCpuTotal || 0)}%</strong><span>VM CPU total</span></div>
            <div><strong>{hostPressure.availableMemoryMb || 0} MB</strong><span>Available RAM</span></div>
            <div><strong>{hostPressure.swapPercent || 0}%</strong><span>Swap</span></div>
          </div>
          <div className="optimizer-reason-list">
            {(hostPressure.reasons || []).length ? hostPressure.reasons.map((reason, idx)=><div key={idx}>{reason}</div>) : <div>No host pressure warnings.</div>}
          </div>
        </div>

        <div className="glass-card optimizer-card">
          <div className="optimizer-card-label">Capacity</div>
          <div className={`optimizer-pressure pressure-${capacity.gamingSuitability === 'poor' ? 'danger' : capacity.gamingSuitability === 'tight' ? 'warn' : 'ok'}`}>{capacity.gamingSuitability || 'good'}</div>
          <div className="optimizer-pressure-stats">
            <div><strong>{capacity.estimatedAdditionalGamingSlots ?? 0}</strong><span>Gaming slots</span></div>
            <div><strong>{capacity.estimatedAdditionalInteractiveSlots ?? 0}</strong><span>Interactive slots</span></div>
            <div><strong>{Math.round(capacity.cpuHeadroomPercent ?? 0)}%</strong><span>CPU headroom</span></div>
          </div>
          <div className="optimizer-reason-list">
            <div>Protected VMs: {protectedCount}</div>
            <div>Unstable VMs: {unstableCount}</div>
            <div>Relief candidates: {reliefCandidates.length}</div>
          </div>
        </div>

        <div className="glass-card optimizer-card optimizer-card-wide">
          <div className="optimizer-card-label">Controls</div>
          <div className="optimizer-policy-actions">
            <Button onClick={runOnce} disabled={running}>{running ? 'Running…' : 'Run once'}</Button>
            <Button onClick={tailLogs}>Refresh logs</Button>
            <Button onClick={loadStatus}>Refresh summary</Button>
          </div>
        </div>
      </div>

      <div className="glass-card" style={{marginTop:16}}>
        <div className="optimizer-card-label">Policy settings</div>
        <div style={{display:'grid', gap:12, marginTop:12}}>
          <label className="optimizer-setting-field">
            <span>Density profile</span>
            <select value={settingsDraft.densityProfile ?? 'single-user'} disabled={applyingDensity} onChange={e=>applyDensityProfile(e.target.value)}>
              <option value="single-user">Single user / low density</option>
              <option value="small-group">Small group / balanced</option>
              <option value="multi-user">Multi-user / higher density</option>
              <option value="custom">Custom</option>
            </select>
          </label>
          <div className="optimizer-reason-list" style={{marginTop:0}}>
            <div>Current profile: <strong>{summary.capacity?.densityProfile || summary.cfg?.densityProfile || 'single-user'}</strong></div>
            <div>Gaming budget per VM: {summary.capacity?.gamingVmCpuBudgetPercent ?? settingsDraft.gamingVmCpuBudgetPercent ?? 30}% CPU / {summary.capacity?.gamingVmMemoryMb ?? settingsDraft.gamingVmMemoryMb ?? 3072} MB RAM</div>
            <div>Interactive budget per VM: {summary.capacity?.interactiveVmCpuBudgetPercent ?? settingsDraft.interactiveVmCpuBudgetPercent ?? 20}% CPU / {summary.capacity?.interactiveVmMemoryMb ?? settingsDraft.interactiveVmMemoryMb ?? 2048} MB RAM</div>
          </div>
        </div>
        <div className="optimizer-settings-grid" style={{marginTop:12}}>
          <SettingField label="Host CPU soft limit" value={settingsDraft.hostCpuSoftLimit ?? ''} min={1} step={1} onChange={e=>setSettingsDraft(s => ({ ...s, densityProfile:'custom', hostCpuSoftLimit: e.target.value }))} />
          <SettingField label="Host CPU hard limit" value={settingsDraft.hostCpuHardLimit ?? ''} min={1} step={1} onChange={e=>setSettingsDraft(s => ({ ...s, densityProfile:'custom', hostCpuHardLimit: e.target.value }))} />
          <SettingField label="Minimum available RAM (MB)" value={settingsDraft.minAvailableMemoryMb ?? ''} min={128} step={128} onChange={e=>setSettingsDraft(s => ({ ...s, densityProfile:'custom', minAvailableMemoryMb: e.target.value }))} />
          <SettingField label="Max swap percent" value={settingsDraft.maxSwapPercent ?? ''} min={0} step={1} onChange={e=>setSettingsDraft(s => ({ ...s, densityProfile:'custom', maxSwapPercent: e.target.value }))} />
          <SettingField label="Activity window (seconds)" value={settingsDraft.activityWindowSeconds ?? ''} min={30} step={30} onChange={e=>setSettingsDraft(s => ({ ...s, densityProfile:'custom', activityWindowSeconds: e.target.value }))} />
          <SettingField label="Gaming VM CPU budget (%)" value={settingsDraft.gamingVmCpuBudgetPercent ?? ''} min={1} step={1} onChange={e=>setSettingsDraft(s => ({ ...s, densityProfile:'custom', gamingVmCpuBudgetPercent: e.target.value }))} />
          <SettingField label="Interactive VM CPU budget (%)" value={settingsDraft.interactiveVmCpuBudgetPercent ?? ''} min={1} step={1} onChange={e=>setSettingsDraft(s => ({ ...s, densityProfile:'custom', interactiveVmCpuBudgetPercent: e.target.value }))} />
          <SettingField label="Gaming VM RAM budget (MB)" value={settingsDraft.gamingVmMemoryMb ?? ''} min={256} step={128} onChange={e=>setSettingsDraft(s => ({ ...s, densityProfile:'custom', gamingVmMemoryMb: e.target.value }))} />
          <SettingField label="Interactive VM RAM budget (MB)" value={settingsDraft.interactiveVmMemoryMb ?? ''} min={256} step={128} onChange={e=>setSettingsDraft(s => ({ ...s, densityProfile:'custom', interactiveVmMemoryMb: e.target.value }))} />
          <label className="optimizer-toggle-field"><input type="checkbox" checked={!!settingsDraft.protectActiveVms} onChange={e=>setSettingsDraft(s => ({ ...s, densityProfile:'custom', protectActiveVms: e.target.checked }))} /><span>Protect active VMs from disruptive recovery</span></label>
          <label className="optimizer-toggle-field"><input type="checkbox" checked={!!settingsDraft.blockStartsOnPressure} onChange={e=>setSettingsDraft(s => ({ ...s, densityProfile:'custom', blockStartsOnPressure: e.target.checked }))} /><span>Block new starts under pressure</span></label>
        </div>
        <div className="optimizer-settings-actions">
          <Button onClick={saveSettings} disabled={saving || applyingDensity}>{saving ? 'Saving…' : 'Save custom settings'}</Button>
        </div>
      </div>

      <div className="optimizer-grid" style={{marginTop:16}}>
        <div className="glass-card optimizer-card optimizer-card-wide">
          <div className="optimizer-card-label">Recommendations</div>
          <div className="optimizer-recommendations">
            {recommendations.length ? recommendations.map((rec, idx)=>(
              <div key={idx} className={`optimizer-rec rec-${rec.level || 'info'}`}>
                <strong>{rec.title}</strong>
                <span>{rec.detail}</span>
              </div>
            )) : <div className="optimizer-event-empty">No optimizer recommendations right now.</div>}
          </div>
        </div>

        <div className="glass-card optimizer-card optimizer-card-wide">
          <div className="optimizer-card-label">Pressure relief ranking</div>
          <div className="optimizer-event-list">
            {reliefCandidates.length ? reliefCandidates.map((cand, idx)=>(
              <div key={idx} className="optimizer-event-item">
                <strong>#{idx + 1} · {cand.name}</strong>
                <span>{cand.profile} · score {cand.score} · CPU {Math.round(cand.cpuPercent || 0)}% · RAM {Math.round(cand.memPercent || 0)}%</span>
                <span>{(cand.reasons || []).join(' · ')}</span>
              </div>
            )) : <div className="optimizer-event-empty">No ranked relief candidates right now.</div>}
          </div>
        </div>
      </div>

      <div className="optimizer-grid" style={{marginTop:16}}>
        <div className="glass-card optimizer-card optimizer-card-wide">
          <div className="optimizer-card-label">Recent optimizer actions</div>
          <div className="optimizer-event-list">
            {recentEvents.length ? recentEvents.map((ev, idx)=>(
              <div key={idx} className="optimizer-event-item">
                <strong>{ev.vm || ev.name || ev.container || 'host'}</strong>
                <span>{ev.action || ev.reason || 'event'}{ev.reason ? ` · ${ev.reason}` : ''}</span>
              </div>
            )) : <div className="optimizer-event-empty">No recent optimizer actions recorded yet.</div>}
          </div>
        </div>

        <div className="glass-card optimizer-card optimizer-card-wide">
          <div className="optimizer-card-label">Optimizer logs</div>
          <div style={{background:'#02040a',color:'#dff',padding:8,borderRadius:8,height:260,overflow:'auto',fontFamily:'monospace',fontSize:12}}>
            <pre style={{whiteSpace:'pre-wrap',margin:0}}>{logs || 'No logs yet.'}</pre>
          </div>
        </div>
      </div>
    </div>
  )
}
