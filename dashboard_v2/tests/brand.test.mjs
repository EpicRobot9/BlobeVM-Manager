import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'

const root = path.resolve(import.meta.dirname, '..')
const brandSource = fs.readFileSync(path.join(root, 'src/brand.js'), 'utf8')

test('brand constants define the EpicVM public identity', () => {
  assert.match(brandSource, /PRODUCT_NAME\s*=\s*['"]EpicVM['"]/)
  assert.match(brandSource, /DASHBOARD_TITLE\s*=\s*['"]EpicVM Dashboard['"]/)
  assert.match(brandSource, /MANAGER_NAME\s*=\s*['"]EpicVM Manager['"]/)
  assert.match(brandSource, /BRAND_TAGLINE\s*=\s*['"]Virtual desktops, managed your way\.[ '"]/)
})

test('visible React surfaces consume centralized brand constants', () => {
  for (const file of ['Login.jsx', 'Sidebar.jsx', 'Topbar.jsx']) {
    const source = fs.readFileSync(path.join(root, 'src/components', file), 'utf8')
    assert.ok(source.includes("from '../brand'"), `${file} should import brand constants`)
    assert.doesNotMatch(source, /BlobeVM/)
  }

  const index = fs.readFileSync(path.join(root, 'index.html'), 'utf8')
  assert.match(index, /EpicVM Dashboard/)
  assert.doesNotMatch(index, /BlobeVM/)
})
