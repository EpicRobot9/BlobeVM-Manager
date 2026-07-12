import React, { useState } from 'react'
import { CubeTransparent, LockKey, User } from '@phosphor-icons/react'
import { login } from '../lib/fetchWrapper'
import Button from './Button'

export default function Login({onLogin}){
  const [username,setUsername]=useState(''); const [pw,setPw]=useState(''); const [err,setErr]=useState(''); const [loading,setLoading]=useState(false)
  async function submit(e){e?.preventDefault();setErr('');setLoading(true);try{const ok=await login(username,pw);setLoading(false);if(ok){onLogin?.();return}setErr('Invalid credentials')}catch{setErr('Unable to reach the dashboard service')}setLoading(false)}
  return <div className="glass-card login-panel"><div className="login-brand"><CubeTransparent size={42} weight="duotone"/><div><strong>BlobeVM</strong><span>Manager</span></div></div><div className="login-heading"><h2>Welcome back</h2><p>Sign in to manage your virtual machine fleet.</p></div><form onSubmit={submit}>
    <label htmlFor="dashboard-username">Admin username</label><div className="input-with-icon"><User size={18}/><input id="dashboard-username" autoFocus autoComplete="username" value={username} onChange={e=>setUsername(e.target.value)}/></div>
    <label htmlFor="dashboard-password">Admin password</label><div className="input-with-icon"><LockKey size={18}/><input id="dashboard-password" autoComplete="current-password" type="password" value={pw} onChange={e=>setPw(e.target.value)}/></div>
    <Button type="submit" disabled={loading}>{loading?'Signing in…':'Sign in'}</Button>{err&&<div className="login-error" role="alert">{err}</div>}
  </form></div>
}
