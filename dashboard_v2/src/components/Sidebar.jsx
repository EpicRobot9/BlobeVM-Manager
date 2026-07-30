import React from 'react'
import { NavLink } from 'react-router-dom'
import { House, DesktopTower, ChartBar, FileText, SlidersHorizontal, Gear, Users, Code, Wrench, CaretLeft, X, CubeTransparent } from '@phosphor-icons/react'
import { PRODUCT_NAME, MANAGER_NAME } from '../brand'

const items = [
  {to:'/', label:'Home Overview', icon:House}, {to:'/vm', label:'VM Manager', icon:DesktopTower},
  {to:'/resources', label:'Resource Usage', icon:ChartBar}, {to:'/logs', label:'Logs Viewer', icon:FileText},
  {to:'/optimizer', label:'Optimizer Control', icon:SlidersHorizontal}, {to:'/settings', label:'Settings', icon:Gear},
  {to:'/users', label:'Users & Access', icon:Users}, {to:'/api', label:'API & System Info', icon:Code},
  {to:'/tools', label:'Advanced Tools', icon:Wrench}
]

function BrandMark(){ return <CubeTransparent className="brand-mark" size={38} weight="duotone" aria-hidden="true"/> }

export default function Sidebar({collapsed, onCollapse, mobileOpen, onMobileClose}){
  return <div className="sidebar-inner">
    <div className="brand-row"><BrandMark /><div className="nav-label brand-copy"><strong>{PRODUCT_NAME}</strong><span>{MANAGER_NAME.split(' ').slice(1).join(' ')}</span></div>{mobileOpen && <button className="icon-button mobile-close" aria-label="Close navigation" onClick={onMobileClose}><X size={20}/></button>}</div>
    <nav aria-label="Main navigation" className="nav-list">
      {items.map(({to,label,icon:Icon}) => <NavLink key={to} to={to} title={collapsed ? label : undefined} onClick={()=>mobileOpen && onMobileClose?.()} className={({isActive})=>'nav-item' + (isActive ? ' active' : '')}><Icon size={21} aria-hidden="true" /><span className="nav-label">{label}</span></NavLink>)}
    </nav>
    <button className="collapse-control" onClick={onCollapse} aria-label={collapsed ? 'Expand navigation' : 'Collapse navigation'}><CaretLeft size={19} className={collapsed ? 'rotated' : ''}/><span className="nav-label">Collapse</span></button>
  </div>
}
