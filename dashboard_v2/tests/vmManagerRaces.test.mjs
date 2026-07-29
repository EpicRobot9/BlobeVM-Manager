import test from 'node:test'
import assert from 'node:assert/strict'
import {
  createEntitySetTracker,
  createInFlightDeduper,
  createLoadInFlightRunner
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
