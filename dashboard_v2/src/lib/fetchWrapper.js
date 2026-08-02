const API_BASE = '/Dashboard/api'
const AUTH_BASE = '/Dashboard/api'

export async function apiFetch(path, opts={}){
  const res = await fetch(API_BASE + path, { credentials:'same-origin', ...opts })
  if(res.status === 401){
    throw new Error('Unauthorized')
  }
  return res
}

export async function login(username, password){
  const res = await fetch(AUTH_BASE + '/auth/login', {method:'POST', credentials:'same-origin', headers:{'Content-Type':'application/json'}, body: JSON.stringify({username, password})})
  if(!res.ok) return false
  const j = await res.json().catch(()=>({}))
  return !!(j && j.ok)
}

export async function authStatus(){
  const res = await fetch(AUTH_BASE + '/auth/status', {credentials:'same-origin'})
  const body = await res.json().catch(()=>({ok:false, authRequired:true}))
  return { httpOk: res.ok, ...body }
}

export async function logout(){
  await fetch(AUTH_BASE + '/auth/logout', {method:'POST', credentials:'same-origin'})
}

export default apiFetch
