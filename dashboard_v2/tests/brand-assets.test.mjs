import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'

const root = path.resolve(import.meta.dirname, '..')
const read = relativePath => fs.readFileSync(path.join(root, relativePath), 'utf8')

for (const asset of ['public/epicvm-mark.svg', 'public/favicon.svg']) {
  test(`${asset} is an accessible, compact EpicVM SVG mark`, () => {
    const source = read(asset)
    assert.match(source, /<svg\b/)
    assert.match(source, /<title[^>]*>EpicVM<\/title>/)
    assert.doesNotMatch(source, /<linearGradient|<radialGradient|url\(#/)
    assert.match(source, /(?:#02bdf3|#05a9e7|#80dcfa)/i)
  })
}

test('EpicVMMark component renders the shared mark with accessible sizing', () => {
  const source = read('src/components/EpicVMMark.jsx')
  assert.match(source, /function EpicVMMark|const EpicVMMark|export default function EpicVMMark/)
  assert.match(source, /<svg\b/)
  assert.match(source, /title = ['"]EpicVM['"]|<title[^>]*>\{title\}<\/title>/)
  assert.match(source, /width=\{size\}|width="\{size\}"/)
  assert.match(source, /height=\{size\}|height="\{size\}"/)
})

test('login and sidebar use the EpicVM mark without removing their brand labels', () => {
  for (const file of ['src/components/Login.jsx', 'src/components/Sidebar.jsx']) {
    const source = read(file)
    assert.match(source, /EpicVMMark/)
  }
  assert.match(read('src/components/Sidebar.jsx'), /collapsed/)
  assert.match(read('src/components/Login.jsx'), /MANAGER_NAME/)
})

test('document declares the EpicVM SVG favicon', () => {
  assert.match(read('index.html'), /<link[^>]+rel=["']icon["'][^>]+href=["']\/favicon\.svg["']/)
})
