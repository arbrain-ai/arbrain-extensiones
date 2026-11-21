"""El estudio semanal (tarea `estudio-semanal` de la extensión): re-censa, saca la huella del embudo de cada canal, la
compara con la de la semana pasada y re-abre solo las páginas de quien cambió. No reescribe las fichas: deja
`cambios/cambios-<fecha>.md` y `estado-semanal.json` para que Levy y el dueño decidan qué ficha reabrir.

Huella (`competidores-embudos-huella/v1`), por canal: cada destino propio de sus descripciones (dominio, o dominio +
producto en Skool, Whop, Gumroad, Hotmart, bit.ly…) con en cuántos videos está, el primer enlace propio más común y,
por cada página citada en su ficha, su código HTTP, URL final, título, precios del texto y si su promesa sigue literal.
"""
from __future__ import annotations

import collections
import urllib.parse

import alta
import censo
import comun
import fichas
import paginas

ESQUEMA_HUELLA = 'competidores-embudos-huella/v1'
ESQUEMA_ESTADO = 'competidores-embudos-estado/v1'
CON_PRODUCTO = ('skool.com', 'whop.com', 'gumroad.com', 'hotmart.com', 'bit.ly', 'linktr.ee', 'calendly.com', 'stan.store',
                'beacons.ai', 'wa.me', 'pay.hotmart.com')


def clave_destino(url: str) -> str:
    p = urllib.parse.urlsplit(url)
    d = p.netloc.lower().removeprefix('www.')
    if any(d == x or d.endswith('.' + x) for x in CON_PRODUCTO):
        seg = [s for s in p.path.split('/') if s][:1]
        return f'{d}/{seg[0].lower()}' if seg else d
    return d


def huella_canal(c: dict, ficha: dict | None, textos: dict) -> dict:
    n, dest, primero = len(c.get('videos', [])), collections.Counter(), collections.Counter()
    for v in c.get('videos', []):
        propios = [e for e in v.get('enlaces', []) if e['categoria'] not in ('red_social', 'otro_video')]
        dest.update({clave_destino(e['url']) for e in propios})
        if propios:
            primero[clave_destino(propios[0]['url'])] += 1
    pags = {}
    for campo in ('regalo_entrada', 'oferta_pagada', 'promesa'):
        for x in (ficha or {}).get(campo, []):
            url = x.get('url') or (x.get('dato') or {}).get('fuente')
            if not url or not str(url).startswith('http') or url in pags:
                continue
            r = censo.resolver(url)
            h = {'http': r.get('http'), 'final': r.get('final'), 'titulo': r.get('titulo_pagina'), 'precios': r.get('precios', [])}
            if campo == 'promesa' and x.get('cita'):
                h['promesa_literal'] = fichas._norm(x['cita']) in fichas._norm(textos.get(url, ''))
            pags[url] = h
    return {'videos': n, 'destinos': dict(dest), 'primer_propio': primero.most_common(1)[0][0] if primero else None, 'paginas': pags}


def comparar(antes: dict | None, ahora: dict) -> list[str]:
    if not antes:
        return []
    m = []
    for d, k in ahora['destinos'].items():
        if k >= 2 and d not in antes.get('destinos', {}):
            m.append(f'nuevo destino en sus videos: {d} (en {k} de {ahora["videos"]})')
    for d, k in antes.get('destinos', {}).items():
        if k >= 2 and d not in ahora['destinos']:
            m.append(f'dejó de enlazar: {d} (estaba en {k} videos)')
    if antes.get('primer_propio') and ahora['primer_propio'] and antes['primer_propio'] != ahora['primer_propio']:
        m.append(f'su primer enlace cambió: {antes["primer_propio"]} → {ahora["primer_propio"]}')
    for url, h in ahora['paginas'].items():
        a = antes.get('paginas', {}).get(url)
        if not a:
            continue
        if a.get('http') != h.get('http'):
            m.append(f'{url}: respondía {a.get("http")}, hoy {h.get("http")}')
        if a.get('final') and h.get('final') and a['final'] != h['final']:
            m.append(f'{url}: ahora redirige a {h["final"]}')
        if a.get('precios') and h.get('precios') and a['precios'] != h['precios']:
            m.append(f'{url}: precios {", ".join(a["precios"][:4])} → {", ".join(h["precios"][:4])}')
        if a.get('promesa_literal') and h.get('promesa_literal') is False:
            m.append(f'{url}: su promesa ya no aparece literal')
    return m


def estudiar(n: int = 5, subs: int = 1) -> dict:
    try:
        comun.llave()
    except comun.SinLlave as e:
        print(f'salta: {e}')
        return {'saltado': str(e)}
    u = alta.universo()
    censo.censar(n=n, subs=subs, resolver_enlaces=True)
    canales, _ = censo.censo_fusionado()
    curadas = {f['slug']: f for f in (comun.leer(comun.carpeta() / 'embudos.json', {}) or {}).get('fichas', [])}
    abiertas = paginas.abiertas()
    textos = {}
    for (s, k), p in abiertas.items():
        ev = comun.raiz() / p['evidencia'] if p.get('evidencia') else None
        if ev and ev.exists():
            for url in {p.get('url'), p.get('final')} - {None}:
                textos[url] = ev.read_text(encoding='utf-8')
    hdir = comun.datos() / 'huellas'
    previa = sorted(hdir.glob('huella-*.json'))
    previa = [p for p in previa if p.stem != f'huella-{comun.hoy()}']
    antes = (comun.leer(previa[-1]) or {}).get('canales', {}) if previa else {}
    huella = {s: huella_canal(c, curadas.get(s), textos) for s, c in canales.items()
              if s in {x['slug'] for x in censo.objetivo(u, None)}}
    comun.escribir(hdir / f'huella-{comun.hoy()}.json', {'esquema': ESQUEMA_HUELLA, 'fecha': comun.hoy(), 'canales': huella})
    estado_ruta = comun.carpeta() / 'estado-semanal.json'
    estado = comun.leer(estado_ruta, {}) or {}
    previo = estado.get('canales', {})
    nuevo, lineas = {}, []
    for s, h in huella.items():
        motivos = comparar(antes.get(s), h)
        reinv = False
        if motivos:  # re-abrir solo las páginas de su ficha
            pedir = [{'slug': s, 'clave': k, 'url': p['url']} for (sl, k), p in abiertas.items() if sl == s]
            if pedir:
                paginas.abrir_todas(pedir)
                reinv = True
            lineas.append(f'## {s}\n' + '\n'.join(f'- {x}' for x in motivos) + '\n')
        nuevo[s] = {'revisado': comun.hoy(), 'reinvestigado': reinv,
                    'ultimo_cambio': comun.hoy() if motivos else (previo.get(s) or {}).get('ultimo_cambio'),
                    'motivos': motivos}
    out = {'esquema': ESQUEMA_ESTADO, 'generado': comun.ahora(), 'corte': comun.hoy(),
           'base': previa[-1].stem.removeprefix('huella-') if previa else None, 'canales': nuevo}
    comun.escribir(estado_ruta, out)
    cab = f'# Qué cambió en tus competidores · {comun.hoy()}\n\n'
    cuerpo = ('Primera huella: desde la próxima semana se compara contra esta.\n' if not previa else
              ('\n'.join(lineas) if lineas else f'Nada cambió desde el {out["base"]}.\n'))
    comun.escribir(comun.carpeta() / 'cambios' / f'cambios-{comun.hoy()}.md', cab + cuerpo, texto=True)
    print(cab + cuerpo)
    return out

