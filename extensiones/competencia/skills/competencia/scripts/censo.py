"""El censo: por cada canal del universo del dueño (competencia y referentes), sus últimos videos largos, los enlaces de
cada descripción con la línea donde aparecen y su categoría, a dónde llegan (si se resuelven) y lo que pide en voz alta
(si hay subtítulos públicos). Escribe `$DATOS/censos/censo-<fecha>.json` y refresca suscriptores y foto del universo.

Límites que se dicen, no se esconden: la descripción es la de hoy (pudo editarse); no ve tarjetas, pantallas finales ni
el comentario fijado; un enlace presente no dice cuántos hicieron clic. Resolver un enlace abre la página pública:
no se registra, no compra, no envía nada.
"""
from __future__ import annotations

import collections
import concurrent.futures as cf
import html
import re
import urllib.parse

import alta
import comun
import youtube

ESQUEMA_CENSO = 'arbrain.competencia.censo/v1'
URL_RE = re.compile(r'(?:https?://|(?<![\w@./])www\.)[^\s)\]>"\'<]+')  # también «www.sitio.com/…» sin esquema
SOCIALES = ('instagram.com', 'x.com/', 'twitter.com', 'tiktok.com', 'linkedin.com', 'facebook.com', 'fb.com', 'threads.net',
            'spotify.com', 'podcasts.apple', 'twitch.tv', 'pinterest.', 'github.com/sponsors')
REGLAS = [  # (categoría, patrón sobre la URL en minúsculas); el orden importa
    ('otro_video', r'youtube\.com/(watch|playlist|@|c/|channel|shorts)|youtu\.be/'),
    ('red_social', '|'.join(re.escape(s) for s in SOCIALES)),
    ('mensajeria', r'wa\.me/|api\.whatsapp|chat\.whatsapp|whatsapp\.com/channel|t\.me/|telegram\.'),
    ('comunidad', r'skool\.com|discord\.(gg|com)|circle\.so|whop\.com|patreon\.com|mighty'),
    ('agenda', r'calendly\.com|cal\.com/|tidycal|savvycal|hubspot\.com/meetings|zcal|doctoralia|agenda'),
    ('cobro', r'stripe\.com|checkout|gumroad|hotmart|pay\.|lemonsqueezy|kajabi|teachable|thinkific|podia|stan\.store|buy\.|mpago\.la'),
    ('formulario', r'typeform|forms\.gle|docs\.google\.com/forms|tally\.so|jotform|fillout'),
    ('afiliado', r'[?&](ref|via|aff|fpr|affiliate|partner|coupon|code)=|/ref/|/aff/|geni\.us|amzn\.to|partnerstack|refer'),
    ('repo', r'github\.com|gitlab\.com|huggingface\.co'),
    ('newsletter', r'substack\.com|beehiiv|convertkit|kit\.com|mailchi|newsletter'),
    ('enlaces_bio', r'linktr\.ee|beacons\.ai|bio\.link|linkin\.bio|lnk\.bio|campsite\.bio'),
]
PALABRAS_CTA = {
    'es': r'comunidad|link|enlace|descripci[oó]n|gratis|gratuit|curso|mentor[ií]a|programa|agenda|cita|consulta|llamada|'
          r'[uú]nete|suscr[ií]b|newsletter|correo|plantilla|regalo|descarga|academia|membres[ií]a|coment[aá]|te dejo|abajo|whats',
    'en': r'community|link|description|free|course|program|book a call|join|subscribe|newsletter|email|template|'
          r'download|cohort|membership|comment|below|sign up|waitlist|grab|consult',
}
PRECIO = re.compile(r'(?:(?:US|MX)?\$|€|USD|EUR|MXN)\s?\d[\d.,]*(?:\s?(?:MXN|USD|EUR|COP|ARS|CLP|PEN))?(?:\s?(?:/|al |por |per |a )\s?(?:mes|month|mo|año|year|yr|trimestre))?'
                    r'|\d[\d.,]*\s?(?:€|USD|EUR|MXN|dólares|euros|pesos)(?:\s?(?:/|al |por |per )\s?(?:mes|month|mo|año|year))?', re.I)


def categoria(url: str) -> str:
    u = url.lower()
    for cat, pat in REGLAS:
        if re.search(pat, u):
            return cat
    return 'web'


def enlaces(desc: str) -> list[dict]:
    out, vistos = [], set()
    for ln in (desc or '').splitlines():
        for m in URL_RE.findall(ln):
            u = m.rstrip('.,;:!?')
            if not u.startswith('http'):
                u = 'https://' + u
            if u in vistos:
                continue
            vistos.add(u)
            etiqueta = ln.replace(m, '').strip(' -–—:|•→👉➡️🔗')[:140]
            out.append({'url': u, 'dominio': urllib.parse.urlsplit(u).netloc.lower().removeprefix('www.'),
                        'categoria': categoria(u), 'linea': etiqueta})
    return out


def texto_visible(h: str) -> str:
    h = re.sub(r'(?is)<(script|style|noscript|svg)[^>]*>.*?</\1>', ' ', h or '')
    h = re.sub(r'(?s)<[^>]+>', '\n', h)
    return re.sub(r'\n\s*\n+', '\n', html.unescape(h)).strip()


def precios_de(cuerpo: str) -> list[str]:
    return sorted({re.sub(r'\s+', '', m.group(0)) for m in PRECIO.finditer(texto_visible(cuerpo))})[:20]


def resolver(url: str) -> dict:
    r = comun.obtener(url, limite=300_000, timeout=15)
    if r.get('http') is None:
        return {'final': None, 'http': None, 'error': r.get('error')}
    t = re.search(r'<title[^>]*>(.*?)</title>', r.get('cuerpo') or '', re.S | re.I)
    return {'final': r.get('final'), 'http': r['http'],
            'titulo_pagina': html.unescape(re.sub(r'\s+', ' ', t.group(1))).strip()[:160] if t else None,
            'precios': precios_de(r.get('cuerpo') or '')}


def cta_hablado(vid: str, idioma: str | None) -> dict:
    segs, fuente = youtube.subtitulos(vid, idioma)
    if not segs:
        return {'transcript': fuente}
    fin = segs[-1][0]
    cierre = [s for s in segs if s[0] >= fin - 60]
    pat = re.compile(PALABRAS_CTA.get((idioma or 'es')[:2], PALABRAS_CTA['es']), re.I)
    fmt = lambda s: f'{s // 60}:{s % 60:02d}'  # noqa: E731
    menc = [{'min': fmt(s), 'texto': t} for s, t in segs if pat.search(t)]
    return {'transcript': fuente, 'cierre_desde': fmt(cierre[0][0]), 'cierre': ' '.join(t for _, t in cierre)[:900],
            'menciones': menc if len(menc) <= 12 else menc[:6] + [{'min': '…', 'texto': f'+{len(menc) - 12} más'}] + menc[-6:]}


def agregar(c: dict) -> dict:
    dom, cat, primero, ejemplos = collections.Counter(), collections.Counter(), collections.Counter(), {}
    for v in c['videos']:
        dom.update({e['dominio'] for e in v.get('enlaces', [])})
        cat.update({e['categoria'] for e in v.get('enlaces', [])})
        propios = [e for e in v.get('enlaces', []) if e['categoria'] not in ('red_social', 'otro_video')]
        if propios:
            primero[propios[0]['dominio']] += 1
        for e in v.get('enlaces', []):
            ejemplos.setdefault(e['dominio'], e)
    return {'videos': len(c['videos']), 'con_transcript': sum('cierre' in v.get('cta_hablado', {}) for v in c['videos']),
            'dominios': [{'dominio': d, 'en_videos': k, 'categoria': ejemplos[d]['categoria'], 'ejemplo': ejemplos[d]['url'],
                          'linea': ejemplos[d]['linea']} for d, k in dom.most_common()],
            'categorias': dict(cat.most_common()), 'primer_enlace_no_social': dict(primero.most_common())}


def objetivo(u: dict, quiero: set[str] | None) -> list[dict]:
    return [c for c in u['canales'] if set(c.get('capas') or [c.get('capa')]) & {'competencia', 'referente'}
            and (not quiero or c['slug'] in quiero)]


def censar(n: int = 5, subs: int = 2, resolver_enlaces: bool = True, quiero: set[str] | None = None) -> dict:
    u = alta.universo()
    cuota = comun.Cuota(u.get('cuota_diaria'))
    canales = objetivo(u, quiero)
    if not canales:
        raise comun.Falta('el universo no tiene canales marcados como competencia o referente todavía')
    # suscriptores y foto al día (1 unidad por cada 50 canales)
    frescos = youtube.canales([c['channel_id'] for c in canales], cuota)
    for c in u['canales']:
        f = frescos.get(c['channel_id'])
        if f:
            c.update({k: f[k] for k in ('suscriptores', 'videos_total', 'miniatura_url') if f.get(k) is not None})
            # La foto como data URI chica, solo si cambió la URL o aún no la hay (una descarga por canal y foto nueva).
            if c.get('miniatura_url') and (c.get('miniatura_de') != c['miniatura_url'] or not c.get('miniatura')):
                foto = youtube.foto_data_uri(c['miniatura_url'])
                if foto:
                    c['miniatura'], c['miniatura_de'] = foto, c['miniatura_url']
            c['verificado'] = {'fecha': comun.hoy(), 'metodo': 'channels.list de la YouTube Data API (llave del dueño)'}
    res = []
    for c in canales:
        try:
            vs, origen = youtube.ultimos_largos(c['channel_id'], n, cuota)
            error = None
        except comun.TopeCuota:
            raise
        except Exception as e:  # noqa: BLE001
            vs, origen, error = [], None, f'{type(e).__name__}: {e}'[:200]
        idioma = c.get('idioma') or next((v['idioma'] for v in vs if v.get('idioma')), None)
        for i, v in enumerate(vs):
            v['enlaces'] = enlaces(v.get('descripcion', ''))
            v['cta_hablado'] = cta_hablado(v['id'], idioma) if i < subs else {'transcript': f'no se pidió (solo los {subs} más nuevos)'}
            if len(v.get('descripcion', '')) > 6000:
                v['descripcion'] = v['descripcion'][:6000] + ' …'
        if vs and vs[0].get('publicado'):
            c['ultimo_largo'] = vs[0]['publicado']
        res.append({'slug': c['slug'], 'nombre': c['nombre'], 'channel_id': c['channel_id'], 'idioma': idioma,
                    'lista_de': origen, 'error_lista': error, 'videos': vs})
        print(f"· {c['slug']:<36} {len(vs):>2} videos ({origen or 'sin lista'}){'  ERROR ' + error if error else ''}", flush=True)
    destinos = {}
    if resolver_enlaces:
        urls = sorted({e['url'] for r in res for v in r['videos'] for e in v['enlaces']
                       if e['categoria'] not in ('red_social', 'otro_video')})
        with cf.ThreadPoolExecutor(8) as ex:
            destinos = dict(zip(urls, ex.map(resolver, urls)))
        for r in res:
            for v in r['videos']:
                for e in v['enlaces']:
                    if e['url'] in destinos:
                        e['destino'] = destinos[e['url']]
    for r in res:
        r['resumen'] = agregar(r)
    alta.guardar(u)
    salida = comun.datos() / 'censos' / f'censo-{comun.hoy()}.json'
    previo = comun.leer(salida, {}) or {}
    nuevos = {r['slug'] for r in res}
    res = [c for c in previo.get('canales', []) if c['slug'] not in nuevos] + res  # un censo parcial no borra a los demás del día
    out = {'esquema': ESQUEMA_CENSO, 'generado': comun.ahora(), 'corte': comun.hoy(),
           'parametros': {'n': n, 'subs': subs, 'resolver': resolver_enlaces, 'ytdlp': youtube.hay_ytdlp()},
           'unidades_hoy': cuota.usadas, 'urls_resueltas': len(destinos), 'canales': res}
    comun.escribir(salida, out)
    print(f'\nEscrito {comun.rel(salida)} · {len(res)} canales · {cuota.usadas} unidades de YouTube hoy (tope {cuota.tope})')
    return out


def censo_fusionado() -> tuple[dict[str, dict], dict[str, str]]:
    """Por canal, su censo más reciente (con videos) entre todos los días: {slug: canal}, {slug: ruta citable}."""
    canales, de = {}, {}
    for p in sorted((comun.datos() / 'censos').glob('censo-*.json')):
        for c in (comun.leer(p) or {}).get('canales', []):
            if c.get('videos') or c['slug'] not in canales:
                canales[c['slug']], de[c['slug']] = c, comun.rel(p)
    return canales, de
