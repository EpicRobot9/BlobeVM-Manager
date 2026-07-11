// Sessions are deliberately HttpOnly cookies. Never mirror them into browser
// storage where an injected script could steal an admin credential.
export function setToken(){ /* legacy no-op retained for import compatibility */ }
export function getToken(){ return '' }
export function isAuthenticated(){ return false }
