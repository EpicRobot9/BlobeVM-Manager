import React from 'react'
import { NavLink } from 'react-router-dom'

const items = [
  {to:'/', label:'Home Overview'}, {to:'/vm', label:'VM Manager'}, {to:'/resources', label:'Resource Usage'},
  {to:'/logs', label:'Logs Viewer'}, {to:'/optimizer', label:'Optimizer Control'}, {to:'/settings', label:'Settings'},
  {to:'/users', label:'Users & Access'}, {to:'/api', label:'API & System Info'}, {to:'/tools', label:'Advanced Tools'}
]

export default function Sidebar({collapsed, onCollapse, mobileOpen, onMobileClose}){
  return <div style={{display:'flex',flexDirection:'column',height:'100%'}}>
    <div style={{display:'flex',alignItems:'center',justifyContent:'space-between',padding:'8px 6px'}}>
      <div className="nav-label" style={{fontWeight:700,color:'#cfe8ff'}}>BlobeVM</div>
      <div style={{display:'flex',gap:6,alignItems:'center'}}>
        {mobileOpen ? <button aria-label="Close navigation" onClick={onMobileClose} style={{background:'transparent',border:'none',color:'var(--muted)'}}>×</button> : null}
        <button aria-label={collapsed ? 'Expand navigation' : 'Collapse navigation'} onClick={onCollapse} className="collapse-btn" style={{background:'transparent',border:'none',color:'var(--muted)',transform:collapsed ? 'rotate(180deg)' : 'rotate(0)'}}>‹</button>
      </div>
    </div>
    <nav aria-label="Main navigation" style={{marginTop:8,display:'flex',flexDirection:'column',gap:6}}>
      {items.map(item => <NavLink key={item.to} to={item.to} title={collapsed ? item.label : undefined} onClick={()=>mobileOpen && onMobileClose?.()} className={({isActive})=>'nav-item' + (isActive ? ' active' : '')}>
        <span aria-hidden="true" style={{width:18,height:18,background:'linear-gradient(90deg,var(--blue-500),var(--blue-600))',borderRadius:6,display:'inline-block'}} />
        <span className="nav-label" style={{flex:1}}>{item.label}</span>
      </NavLink>)}
    </nav>
  </div>
}
