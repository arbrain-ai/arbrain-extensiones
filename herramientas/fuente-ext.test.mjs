// La fuente `ext:` niega todo lo que la extensión no declara (20 nov 2026).   node --test herramientas/fuente-ext.test.mjs
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { mkdirSync, mkdtempSync, symlinkSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { resolverFuente, textoDeAccion } from './fuente-ext.mjs'

const raiz = mkdtempSync(join(tmpdir(), 'fuente-ext-'))
const cerebro = join(raiz, 'cerebro'), datos = join(raiz, 'datos')
mkdirSync(join(cerebro, '.claude/memory/extensiones/x'), { recursive: true })
mkdirSync(join(cerebro, '.claude/memory/project'), { recursive: true })
mkdirSync(datos, { recursive: true })
writeFileSync(join(cerebro, '.claude/memory/extensiones/x/a.json'), '{"ok":1}')
writeFileSync(join(cerebro, '.claude/memory/extensiones/x/roto.json'), '{')
writeFileSync(join(cerebro, '.claude/memory/project/secreto.json'), '{"no":1}')
writeFileSync(join(datos, 'c.json'), '[1]')
symlinkSync(join(cerebro, '.claude/memory/project/secreto.json'), join(cerebro, '.claude/memory/extensiones/x/enlace.json'))
const M = {
  permisos: { lee: ['.claude/memory/extensiones/x/'] },
  panel: {
    datos: ['$CEREBRO/.claude/memory/extensiones/x/a.json', '$CEREBRO/.claude/memory/extensiones/x/roto.json', '$CEREBRO/.claude/memory/extensiones/x/falta.json',
      '$CEREBRO/.claude/memory/extensiones/x/enlace.json', '$CEREBRO/.claude/memory/project/secreto.json', '$DATOS/c.json', '$CEREBRO/.claude/memory/extensiones/x/../../project/secreto.json'],
    acciones: [{ id: 'censar', pide: 'Corre el censo' }],
  },
}
const r = f => resolverFuente(f, M, { cerebro, datos })

test('lo declarado y dentro de permisos.lee se lee; lo que falta es vacío, no cero', () => {
  assert.deepEqual([r('ext:$CEREBRO/.claude/memory/extensiones/x/a.json').estado, r('ext:$CEREBRO/.claude/memory/extensiones/x/a.json').valor], ['ok', { ok: 1 }])
  assert.equal(r('ext:$DATOS/c.json').estado, 'ok')
  assert.equal(r('ext:$CEREBRO/.claude/memory/extensiones/x/falta.json').estado, 'vacio')
  assert.equal(r('ext:$CEREBRO/.claude/memory/extensiones/x/roto.json').error, 'JSON roto')
})

test('todo lo demás se niega', () => {
  for (const f of ['ext:$CEREBRO/.claude/memory/extensiones/x/otro.json',           // no declarado
    'ext:$CEREBRO/.claude/memory/project/secreto.json',                              // declarado pero fuera de permisos.lee
    'ext:$CEREBRO/.claude/memory/extensiones/x/../../project/secreto.json',          // sale con ..
    'ext:$CEREBRO/.claude/memory/extensiones/x/enlace.json',                         // enlace que escapa
    'pulso:venta', 'ext:/etc/passwd', null]) assert.equal(r(f).estado, 'negado', String(f))
})

test('una acción es texto declarado para Levy, nunca un comando', () => {
  assert.equal(textoDeAccion('chat:censar', M), 'Corre el censo')
  assert.equal(textoDeAccion('chat:rm-rf', M), null)
  assert.equal(textoDeAccion('url:https://a.example', M), null)
})
