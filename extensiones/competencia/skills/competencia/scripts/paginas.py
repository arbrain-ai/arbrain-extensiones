"""Abre páginas PÚBLICAS de oferta o regalo (un GET, sin cookies, sin formularios) y deja evidencia.

  - Texto visible + cabecera (título y descripciones meta) en `<carpeta>/evidencia/<slug>__<clave>.txt` (versionado,
    sin correos), que es lo que respalda una ficha.
  - HTML crudo en `$DATOS/paginas/<slug>__<clave>.html` (se regenera).
  - Resumen en `<carpeta>/paginas-abiertas.json`: http, URL final, título, precios del texto con su contexto y, si es
    Skool, los campos públicos del grupo (miembros, privacidad, precios).
Límite: lo que la página pinta con JavaScript después de cargar no aparece; se dice «precio no visible», no se adivina.
"""
from __future__ import annotations

import collections
import concurrent.futures as cf
import html
import json
import re
import urllib.parse

import comun
import censo

CORREO = re.compile(r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}')
CLAVE = re.compile(r'^[a-z0-9][a-z0-9-]{0,40}$')


def cabecera(h: str) -> str:
    out = []
    t = re.search(r'<title[^>]*>(.*?)</title>', h, re.S | re.I)
    if t:
        out.append('[title] ' + html.unescape(re.sub(r'\s+', ' ', t.group(1))).strip())
    for k in ('description', 'og:description', 'twitter:description', 'og:title'):
        for m in re.finditer(r'<meta[^>]+(?:name|property)="' + re.escape(k) + r'"[^>]+content="([^"]*)"', h, re.I):
            v = html.unescape(m.group(1)).strip()
            if v and f'[{k}] {v}' not in out:
                out.append(f'[{k}] {v}')
    return '\n'.join(out)


def skool(h: str) -> dict | None:
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', h, re.S)
    if not m:
        return None
    try:
        d = json.loads(m.group(1))
    except Exception:  # noqa: BLE001
        return None
    pp = d.get('props', {}).get('pageProps', {})
    g = pp.get('currentGroup') or pp.get('group') or {}
    md = g.get('metadata') or {}
    out = {'nombre': md.get('displayName') or g.get('name'), 'miembros': md.get('totalMembers'),
           'privacidad': md.get('privacy'), 'descripcion': (md.get('description') or '')[:600]}
    hallados = []

    def recorre(x, ruta=''):
        if isinstance(x, dict):
            for k, v in x.items():
                if re.search(r'price|amount|interval|currency|tier|membership', k, re.I) and not isinstance(v, (dict, list)):
                    hallados.append(f'{ruta}.{k}={v}')
                recorre(v, f'{ruta}.{k}')
        elif isinstance(x, list):
            for i, v in enumerate(x[:20]):
                recorre(v, f'{ruta}[{i}]')
    recorre(g)
    out['campos_precio'] = hallados[:40]
    return out


def abrir(p: dict) -> dict:
    if not CLAVE.match(p.get('clave', '')) or not re.match(r'^https?://', p.get('url', '')):
        raise comun.Falta(f'página mal pedida: {p} (clave en minúsculas con guiones y URL http/https)')
    nombre = f"{p['slug']}__{p['clave']}"
    r = {**p, 'abierta': comun.ahora()}
    g = comun.obtener(p['url'])
    if g.get('http') is None:
        r.update(http=None, error=g.get('error'))
        return r
    h = g.get('cuerpo') or ''
    r.update(http=g['http'], final=g.get('final'))
    comun.escribir(comun.datos() / 'paginas' / f'{nombre}.html', h, texto=True)
    t = re.search(r'<title[^>]*>(.*?)</title>', h, re.S | re.I)
    r['titulo'] = html.unescape(re.sub(r'\s+', ' ', t.group(1))).strip()[:200] if t else None
    txt = censo.texto_visible(h)
    sk = skool(h) if 'skool.com' in (r.get('final') or p['url']) else None
    if sk:
        r['skool'] = sk
    precios = []
    for m in censo.PRECIO.finditer(txt):
        a, b = max(0, m.start() - 80), min(len(txt), m.end() + 60)
        precios.append({'precio': m.group(0).strip(), 'contexto': re.sub(r'\s+', ' ', txt[a:b])})
    r['precios_en_texto'] = precios[:25]
    r['chars_texto'] = len(txt)
    cab = cabecera(h)
    cuerpo = json.dumps(sk, ensure_ascii=False, indent=1) + '\n\n' + txt if sk else txt
    ev = comun.carpeta() / 'evidencia' / f'{nombre}.txt'
    comun.escribir(ev, CORREO.sub('[correo]', (cab + '\n\n' if cab else '') + cuerpo)[:400_000] + '\n', texto=True)
    r['evidencia'] = comun.rel(ev)
    return r


def abiertas() -> dict[tuple[str, str], dict]:
    return {(x['slug'], x['clave']): x for x in comun.leer(comun.carpeta() / 'paginas-abiertas.json', []) or []}


def abrir_todas(paginas: list[dict]) -> list[dict]:
    with cf.ThreadPoolExecutor(6) as ex:
        res = list(ex.map(abrir, paginas))
    previo = abiertas()
    for x in res:
        previo[(x['slug'], x['clave'])] = x
    comun.escribir(comun.carpeta() / 'paginas-abiertas.json', sorted(previo.values(), key=lambda x: (x['slug'], x['clave'])))
    return res


GENERICOS = {'about', 'es', 'en', 'p', 'go', 'link', 'links', 'www', 'index', 'home', 'inicio', 'l'}


def clave_de(url: str) -> str:
    """Una clave legible para una página: el primer tramo de la ruta que diga algo, o el dominio."""
    sp = urllib.parse.urlsplit(url)
    for seg in [x for x in sp.path.split('/') if x]:
        if seg.lower() not in GENERICOS and not seg.isdigit():
            return comun.slug(seg)[:40]
    d = sp.netloc.lower().removeprefix('www.')
    return comun.slug(d.split('.')[0] if d.count('.') <= 1 else d)[:40]


def sugeridas(por_canal: int = 3, quiero: set[str] | None = None) -> list[dict]:
    """Las páginas que conviene abrir según el censo: los enlaces propios más repetidos de cada canal (sin redes, otros
    videos, afiliados ni repos), uno por URL, con su destino final si se resolvió. Levy las revisa antes de abrirlas."""
    canales, _ = censo.censo_fusionado()
    out = []
    for s, c in canales.items():
        if quiero and s not in quiero:
            continue
        cuenta, ej = collections.Counter(), {}
        for v in c.get('videos', []):
            for e in v.get('enlaces', []):
                if e['categoria'] in ('red_social', 'otro_video', 'afiliado', 'repo', 'mensajeria'):
                    continue
                u = (e.get('destino') or {}).get('final') or e['url']
                if u not in ej:
                    ej[u] = e
                cuenta[u] += 1
        usadas = set()
        for u, k in cuenta.most_common():
            clave = clave_de(u)
            while clave in usadas:
                clave += '-2'
            usadas.add(clave)
            out.append({'slug': s, 'clave': clave, 'url': u, 'en_videos': k, 'categoria': ej[u]['categoria']})
            if len(usadas) >= por_canal:
                break
    return out
