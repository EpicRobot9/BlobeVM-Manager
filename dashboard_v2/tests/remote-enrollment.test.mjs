import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'

const source = fs.readFileSync(new URL('../src/pages/VMManager.jsx', import.meta.url), 'utf8')

test('VM manager exposes authenticated RemoteVM token-file enrollment', () => {
  assert.match(source, /remote-hosts\/enroll/)
  assert.match(source, /FormData/)
  assert.match(source, /token_file/)
  assert.match(source, /RemoteVM host/)
  assert.doesNotMatch(source, /set[A-Za-z]*Token\(/)
})
