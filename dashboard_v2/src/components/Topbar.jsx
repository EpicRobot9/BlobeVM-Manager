import React, { useState } from 'react'
import { useLocation } from 'react-router-dom'
import { List, TerminalWindow, Bell, Question, UserCircle, SignOut, Sun, Moon } from '@phosphor-icons/react'
import { useTheme } from '../lib/theme.jsx'
import { MANAGER_NAME } from '../brand'

const titles = {'/':'Home Overview','/vm':'VM Manager','/resources':'Resource Usage','/logs':'Logs Viewer','/optimizer':'Optimizer Control','/settings':'Settings','/users':'Users & Access','/api':'API & System Info','/tools':'Advanced Tools'}

export default function Topbar({onLogout, onToggleMobile}){
  const {theme,toggle} = useTheme(); const [open,setOpen] = useState(false); const location = useLocation()
  return <div className="topbar-inner">
    <div className="topbar-title"><button onClick={onToggleMobile} className="icon-button nav-trigger" aria-label="Open navigation"><List size={22}/></button><strong>{titles[location.pathname] || MANAGER_NAME}</strong></div>
    <div className="topbar-actions"><span className="host-online"><i/>Host Online</span><span className="topbar-divider"/><button className="icon-button" aria-label="Open terminal"><TerminalWindow size={20}/></button><button className="icon-button notification-button" aria-label="Notifications"><Bell size={20}/><b>3</b></button><button className="icon-button" aria-label="Help"><Question size={20}/></button><button className="icon-button" onClick={toggle} aria-label="Toggle color theme">{theme === 'dark' ? <Sun size={19}/> : <Moon size={19}/>}</button><div className="account-menu"><button className="account-trigger" onClick={()=>setOpen(v=>!v)} aria-expanded={open}><UserCircle size={21}/><span>admin</span></button>{open && <div className="menu-popover" role="menu"><button role="menuitem" onClick={onLogout}><SignOut size={18}/>Logout</button></div>}</div></div>
  </div>
}
