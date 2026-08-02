import test from 'node:test'
import assert from 'node:assert/strict'
import { formatBytes, formatDuration } from '../src/lib/formatters.js'

test('formatBytes renders API byte counters with truthful units', () => {
  assert.equal(formatBytes(1024), '1.0 KB')
  assert.equal(formatBytes(1073741824), '1.0 GB')
  assert.equal(formatBytes(null), '—')
})

test('formatDuration renders host uptime seconds', () => {
  assert.equal(formatDuration(90061), '1d 1h 1m')
  assert.equal(formatDuration(null), 'Uptime unavailable')
})
