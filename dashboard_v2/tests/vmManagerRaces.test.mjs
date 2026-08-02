import test from 'node:test'
import assert from 'node:assert/strict'
import {
  createEntitySetTracker,
  createInFlightDeduper,
  createLoadInFlightRunner,
  canCacheVmSettingsResponse,
  createLogSelectionTracker,
  clearRemovedVmState
} from '../src/lib/vmManagerRaces.js'

const deferred = () => {
  let resolve
  let reject
  const promise = new Promise((res, rej) => { resolve = res; reject = rej })
  return { promise, resolve, reject }
}

test('load runner shares one in-flight load with overlapping callers', async () => {
  const gate = deferred()
  let calls = 0
  const runner = createLoadInFlightRunner()
  const load = () => runner.run(async () => {
    calls += 1
    return gate.promise
  })

  const first = load()
  const second = load()
  assert.strictEqual(first, second)
  assert.equal(calls, 1)
  gate.resolve('loaded')
  assert.equal(await first, 'loaded')

  const third = load()
  assert.notStrictEqual(third, first)
  assert.equal(await third, 'loaded')
  assert.equal(calls, 2)
})

test('settings entity generations reject writes from removed or old VM sets', () => {
  const tracker = createEntitySetTracker()
  const firstGeneration = tracker.sync(['alpha', 'beta'])
  assert.equal(tracker.canCache('alpha', firstGeneration), true)

  const secondGeneration = tracker.sync(['alpha'])
  assert.equal(secondGeneration, firstGeneration + 1)
  assert.equal(tracker.canCache('beta', firstGeneration), false)
  assert.equal(tracker.canCache('alpha', firstGeneration), false)
  assert.equal(tracker.canCache('alpha', secondGeneration), true)
  assert.deepEqual(tracker.removed, ['beta'])
})

test('in-flight cleanup cannot remove a newer request for the same VM', async () => {
  const deduper = createInFlightDeduper()
  const firstGate = deferred()
  const secondGate = deferred()
  const first = deduper.run('alpha', () => firstGate.promise)
  deduper.clear('alpha', first)
  const second = deduper.run('alpha', () => secondGate.promise)
  firstGate.resolve('old')
  await first
  assert.strictEqual(deduper.get('alpha'), second)
  secondGate.resolve('new')
  assert.equal(await second, 'new')
})

test('manage response requires both request and settings generations to match', () => {
  assert.equal(canCacheVmSettingsResponse({ requestSequence: 4, currentSequence: 4, requestGeneration: 7, currentGeneration: 7, namePresent: true }), true)
  assert.equal(canCacheVmSettingsResponse({ requestSequence: 4, currentSequence: 4, requestGeneration: 7, currentGeneration: 8, namePresent: true }), false)
})

test('new VM selection invalidates its superseded log request and allows A to refresh after A to B to A', async () => {
  const tracker = createLogSelectionTracker()
  const aFirstGate = deferred()
  const bGate = deferred()
  const aFirst = tracker.select('alpha')
  const first = tracker.run('alpha', () => aFirstGate.promise)
  tracker.select('beta')
  const bSelection = tracker.selectionGeneration
  const second = tracker.run('beta', () => bGate.promise)
  tracker.select('alpha')
  const aSecondSelection = tracker.selectionGeneration
  const replacementGate = deferred()
  const replacement = tracker.run('alpha', () => replacementGate.promise)

  assert.notStrictEqual(replacement, first)
  assert.equal(tracker.isCurrent('alpha', aSecondSelection), true)
  assert.equal(tracker.isCurrent('beta', bSelection), false)

  aFirstGate.resolve('old alpha')
  bGate.resolve('beta')
  replacementGate.resolve('new alpha')
  assert.equal(await first, 'old alpha')
  assert.equal(await second, 'beta')
  assert.equal(await replacement, 'new alpha')
  assert.strictEqual(tracker.get('alpha'), undefined)
})

test('removed VM state cleanup clears alert baselines and announcement cooldowns', () => {
  const prevStats = { alpha: { cpu_percent: 10 }, beta: { cpu_percent: 20 } }
  const lastAnnounce = { alpha: 100, beta: 200 }
  clearRemovedVmState(prevStats, lastAnnounce, ['alpha'])
  assert.deepEqual(prevStats, { beta: { cpu_percent: 20 } })
  assert.deepEqual(lastAnnounce, { beta: 200 })
})
