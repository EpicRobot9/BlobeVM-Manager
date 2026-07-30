export function formatBytes(value){
  if(value === null || value === undefined || value === '') return '—'
  const bytes = Number(value)
  if(!Number.isFinite(bytes) || bytes < 0) return '—'
  const units = ['B','KB','MB','GB','TB']; let amount = bytes; let index = 0
  while(amount >= 1024 && index < units.length - 1){ amount /= 1024; index += 1 }
  return `${amount >= 10 || index === 0 ? Math.round(amount) : amount.toFixed(1)} ${units[index]}`
}

export function formatDuration(seconds){
  if(seconds === null || seconds === undefined || seconds === '') return 'Uptime unavailable'
  const value = Number(seconds)
  if(!Number.isFinite(value) || value < 0) return 'Uptime unavailable'
  const days = Math.floor(value / 86400); const hours = Math.floor((value % 86400) / 3600); const minutes = Math.floor((value % 3600) / 60)
  return [days ? `${days}d` : '', hours ? `${hours}h` : '', `${minutes}m`].filter(Boolean).join(' ')
}
