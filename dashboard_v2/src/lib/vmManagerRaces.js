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

export function canCacheVmSettingsResponse({ requestSequence, currentSequence, requestGeneration, currentGeneration, namePresent }){
  return requestSequence === currentSequence && requestGeneration === currentGeneration && namePresent
}

export function clearRemovedVmState(prevStats, lastAnnounce, removedNames){
  for(const name of removedNames){
    delete prevStats[name]
    delete lastAnnounce[name]
  }
}

export function createLogSelectionTracker(){
  let selectedName = null
  let selectionGeneration = 0
  const entries = new Map()
  return {
    select(name){
      if(selectedName !== name){
        if(selectedName !== null) entries.delete(selectedName)
        selectedName = name
        selectionGeneration += 1
      }
      return selectionGeneration
    },
    get selectionGeneration(){ return selectionGeneration },
    run(name, task){
      const existing = entries.get(name)
      if(existing) return existing
      const request = Promise.resolve().then(task)
      entries.set(name, request)
      request.finally(() => {
        if(entries.get(name) === request) entries.delete(name)
      }).catch(() => {})
      return request
    },
    get(name){ return entries.get(name) },
    isSelected(name){ return selectedName === name },
    isCurrent(name, requestGeneration){
      return selectedName === name && requestGeneration === selectionGeneration
    }
  }
}
