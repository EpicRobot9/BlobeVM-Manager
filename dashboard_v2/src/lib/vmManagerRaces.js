export function createLoadInFlightRunner(){
  let inFlight = null
  return {
    run(task){
      if(inFlight) return inFlight
      const request = task()
      inFlight = request
      request.finally(() => {
        if(inFlight === request) inFlight = null
      }).catch(() => {})
      return request
    },
    get(){ return inFlight }
  }
}

export function createEntitySetTracker(){
  let generation = 0
  let names = new Set()
  let removed = []
  return {
    sync(nextNames){
      const next = new Set(nextNames)
      removed = [...names].filter(name => !next.has(name))
      if([...names].sort().join('\0') !== [...next].sort().join('\0')) generation += 1
      names = next
      return generation
    },
    get generation(){ return generation },
    get removed(){ return removed },
    has(name){ return names.has(name) },
    canCache(name, requestGeneration){
      return requestGeneration === generation && names.has(name)
    }
  }
}

export function createInFlightDeduper(){
  const entries = new Map()
  return {
    run(key, task){
      const existing = entries.get(key)
      if(existing) return existing
      const request = Promise.resolve().then(task)
      entries.set(key, request)
      request.finally(() => {
        if(entries.get(key) === request) entries.delete(key)
      }).catch(() => {})
      return request
    },
    get(key){ return entries.get(key) },
    clear(key, request){
      if(entries.get(key) === request) entries.delete(key)
    }
  }
}
