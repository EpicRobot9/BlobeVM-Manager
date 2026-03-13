import { setToken as setTok, getToken } from './auth'

const API_BASE = '/dashboard/api'
const AUTH_BASE = '/Dashboard/api'

export async function apiFetch(path, opts={}){
  const headers = opts.headers || {}
  const token = getToken()
  if(token) headers['Authorization'] = 'Bearer ' + token
  opts.headers = headers
  const res = await fetch(API_BASE + path, { credentials:'same-origin', ...opts })
  if(res.status === 401){
    setTok('')
    try { window.location.href = '/Dashboard' } catch (_) {}
    throw new Error('Unauthorized')
  }
  return res
}

export async function login(password){
  const res = await fetch(AUTH_BASE + '/auth/login', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({password})})
  if(!res.ok) return false
  const j = await res.json().catch(()=>({}))
  if(j && j.token){ setTok(j.token); return true }
  return false
}

export default apiFetch
