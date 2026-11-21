"""YouTube para la extensión «Competencia»: la Data API v3 con la llave del dueño (cuenta cada unidad contra su tope)
y, si está `yt-dlp`, los subtítulos públicos de un video para leer lo que pide en voz alta.

Con COMPETENCIA_FIXTURE=<carpeta> no sale a la red: responde desde `youtube.json` y `subs.json` de esa carpeta (las
pruebas y la corrida sin llave usan esto). Mismas unidades que la API real, para que el tope se pruebe igual.
"""
from __future__ import annotations

import datetime as dt
import json
import re
import shutil
import subprocess
import urllib.parse
import urllib.request

import comun

API = 'https://www.googleapis.com/youtube/v3/'


def _llamar(endpoint: str, cuota: comun.Cuota, **params) -> dict:
    cuota.gastar(endpoint)
    fx = comun.fixture()
    if fx:
        return _fixture(endpoint, params)
    params['key'] = comun.llave()
    url = API + endpoint + '?' + urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
    try:
        return comun.obtener_json(url)
    except Exception as e:  # noqa: BLE001  el mensaje de error de Google no trae la llave; la URL sí, así que no se cita
        cuerpo = ''
        try:
            cuerpo = json.loads(e.read().decode())['error']['message']  # type: ignore[attr-defined]
        except Exception:  # noqa: BLE001
            pass
        raise RuntimeError(f'YouTube {endpoint}: {type(e).__name__} {getattr(e, "code", "")} {cuerpo}'.strip()) from None


def _fixture(endpoint: str, p: dict) -> dict:
    fx = comun.leer(comun.fixture() / 'youtube.json', {}) or {}
    if endpoint == 'search':
        for r in fx.get('search', []):
            if r['q'].lower() == str(p.get('q', '')).lower():
                return {'items': r['items']}
        return {'items': []}
    if endpoint == 'channels':
        canales = fx.get('channels', {})
        if p.get('forHandle'):
            h = p['forHandle'].lstrip('@').lower()
            return {'items': [c for c in canales.values() if (c['snippet'].get('customUrl') or '').lstrip('@').lower() == h]}
        return {'items': [canales[i] for i in str(p.get('id', '')).split(',') if i in canales]}
    if endpoint == 'playlistItems':
        lista = fx.get('playlistItems', {}).get(p.get('playlistId'))
        if lista is None:
            raise RuntimeError('YouTube playlistItems: HTTPError 404 playlistNotFound')
        return {'items': lista[: int(p.get('maxResults', 50))]}
    if endpoint == 'videos':
        vs = fx.get('videos', {})
        return {'items': [vs[i] for i in str(p.get('id', '')).split(',') if i in vs]}
    return {'items': []}


# ───────────────────────── lo que usa la extensión ─────────────────────────

def buscar_videos(q: str, cuota, idioma=None, region=None, dias=180, n=25) -> list[dict]:
    """search.list (100 unidades): videos del tema publicados en la ventana; de ahí salen los canales candidatos."""
    desde = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=dias)).strftime('%Y-%m-%dT%H:%M:%SZ')
    r = _llamar('search', cuota, part='snippet', type='video', q=q, maxResults=n, order='relevance',
                relevanceLanguage=idioma, regionCode=region, publishedAfter=desde)
    return [{'video_id': it['id'].get('videoId'), 'channel_id': it['snippet']['channelId'],
             'canal': it['snippet'].get('channelTitle'), 'titulo': it['snippet'].get('title'),
             'publicado': (it['snippet'].get('publishedAt') or '')[:10]} for it in r.get('items', [])]


def _canal(it: dict) -> dict:
    sn, st = it.get('snippet', {}), it.get('statistics', {})
    th = sn.get('thumbnails', {})
    return {'channel_id': it['id'], 'nombre': sn.get('title'), 'handle': sn.get('customUrl'),
            'pais': sn.get('country'), 'idioma': (sn.get('defaultLanguage') or '')[:2] or None,
            'descripcion': (sn.get('description') or '')[:400],
            'suscriptores': int(st['subscriberCount']) if st.get('subscriberCount') and not st.get('hiddenSubscriberCount') else None,
            'videos_total': int(st['videoCount']) if st.get('videoCount') else None,
            'miniatura_url': (th.get('default') or th.get('medium') or {}).get('url')}


# La foto del canal viaja DENTRO del universo como data URI chica (21 nov 2026): el panel vive con la CSP de las vistas
# de Arbrain (`img-src data: blob:`), así que una URL de YouTube no carga y pintaba iniciales. Solo la miniatura `default`
# (88 px, 2–6 KB), solo de los hosts de fotos de YouTube y con tope de bytes: lo demás se queda en iniciales.
HOSTS_FOTO = ('yt3.ggpht.com', 'yt3.googleusercontent.com', 'i.ytimg.com')
TOPE_FOTO = 16_000
FIRMAS_FOTO = ((b'\xff\xd8\xff', 'image/jpeg'), (b'\x89PNG\r\n\x1a\n', 'image/png'))


def tipo_foto(cuerpo: bytes) -> str | None:
    if cuerpo[:4] == b'RIFF' and cuerpo[8:12] == b'WEBP':
        return 'image/webp'
    return next((t for f, t in FIRMAS_FOTO if cuerpo.startswith(f)), None)


def foto_data_uri(url: str | None) -> str | None:
    """`miniatura_url` → `data:image/…;base64,…` (o None: sin URL, host ajeno, muy grande o no es imagen)."""
    import base64
    if not url or not isinstance(url, str):
        return None
    fx = comun.fixture()
    if fx:
        b64 = (comun.leer(fx / 'fotos.json', {}) or {}).get(url)
        cuerpo = base64.b64decode(b64) if b64 else b''
    else:
        u = urllib.parse.urlsplit(url)
        if u.scheme != 'https' or (u.hostname or '') not in HOSTS_FOTO:
            return None
        try:
            pedido = urllib.request.Request(url, headers={'User-Agent': 'arbrain-competencia/0.1'})
            with urllib.request.urlopen(pedido, timeout=15) as r:  # noqa: S310  host de la lista de arriba
                cuerpo = r.read(TOPE_FOTO + 1)
        except Exception:  # noqa: BLE001  sin foto no es error: el panel pinta iniciales
            return None
    tipo = tipo_foto(cuerpo) if cuerpo and len(cuerpo) <= TOPE_FOTO else None
    return f'data:{tipo};base64,{base64.b64encode(cuerpo).decode()}' if tipo else None


def canales(ids: list[str], cuota) -> dict[str, dict]:
    """channels.list (1 unidad por cada 50 ids)."""
    out = {}
    for i in range(0, len(ids), 50):
        r = _llamar('channels', cuota, part='snippet,statistics', id=','.join(ids[i:i + 50]), maxResults=50)
        for it in r.get('items', []):
            out[it['id']] = _canal(it)
    return out


def canal_por(ref: str, cuota) -> dict | None:
    """Un canal por @handle, URL o id (1 unidad)."""
    ref = ref.strip()
    m = re.search(r'(UC[\w-]{22})', ref)
    if m:
        return canales([m.group(1)], cuota).get(m.group(1))
    m = re.search(r'@([\w.\-]+)', ref)
    h = m.group(1) if m else ref.rstrip('/').rsplit('/', 1)[-1]
    r = _llamar('channels', cuota, part='snippet,statistics', forHandle='@' + h)
    its = r.get('items', [])
    return _canal(its[0]) if its else None


def _segundos(iso: str | None) -> int | None:
    m = re.fullmatch(r'P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', iso or '')
    if not m:
        return None
    d, h, mi, s = (int(x or 0) for x in m.groups())
    return d * 86400 + h * 3600 + mi * 60 + s


def ultimos_largos(channel_id: str, n: int, cuota) -> tuple[list[dict], str]:
    """Los últimos n videos LARGOS: la lista UULF del canal (sin Shorts ni directos). Si no existe, la de subidas (UU)
    filtrada por duración > 3 min. 1 unidad por lista + 1 por cada 50 videos."""
    origen = 'UULF'
    try:
        r = _llamar('playlistItems', cuota, part='contentDetails', playlistId='UULF' + channel_id[2:], maxResults=min(50, n))
    except RuntimeError:
        origen = 'UU'
        r = _llamar('playlistItems', cuota, part='contentDetails', playlistId='UU' + channel_id[2:], maxResults=50)
    ids = [it['contentDetails']['videoId'] for it in r.get('items', [])]
    vs = videos(ids, cuota)
    out = [vs[i] for i in ids if i in vs]
    if origen == 'UU':
        out = [v for v in out if (v['duracion_s'] or 0) > 180]
    return out[:n], origen


def videos(ids: list[str], cuota) -> dict[str, dict]:
    out = {}
    for i in range(0, len(ids), 50):
        r = _llamar('videos', cuota, part='snippet,contentDetails,statistics', id=','.join(ids[i:i + 50]), maxResults=50)
        for it in r.get('items', []):
            sn, st = it.get('snippet', {}), it.get('statistics', {})
            out[it['id']] = {'id': it['id'], 'titulo': sn.get('title'), 'publicado': (sn.get('publishedAt') or '')[:10],
                             'duracion_s': _segundos(it.get('contentDetails', {}).get('duration')),
                             'vistas': int(st['viewCount']) if st.get('viewCount') else None,
                             'idioma': (sn.get('defaultAudioLanguage') or sn.get('defaultLanguage') or '')[:2] or None,
                             'descripcion': sn.get('description') or '', 'descripcion_de': 'youtube-data-api'}
    return out


# ───────────────────────── subtítulos públicos (yt-dlp, opcional) ─────────────────────────

def hay_ytdlp() -> bool:
    return bool(shutil.which('yt-dlp'))


def parse_vtt(txt: str) -> list[tuple[int, str]]:
    segs, t, ultimo = [], None, None
    for ln in txt.splitlines():
        m = re.match(r'^(?:(\d+):)?(\d{2}):(\d{2})\.\d{3} --> ', ln)
        if m:
            h, mi, s = int(m.group(1) or 0), int(m.group(2)), int(m.group(3))
            t = h * 3600 + mi * 60 + s
            continue
        if t is None or not ln.strip() or ln.startswith(('WEBVTT', 'Kind:', 'Language:', 'NOTE')):
            continue
        limpio = re.sub(r'<[^>]+>', '', ln).strip()
        if limpio and limpio != ultimo:
            segs.append((t, limpio))
            ultimo = limpio
    return segs


def subtitulos(vid: str, idioma: str | None) -> tuple[list[tuple[int, str]] | None, str]:
    """(segmentos, fuente). Solo la pista ORIGINAL del video (nunca una traducción automática). Caché en $DATOS/subs/."""
    cache = comun.datos() / 'subs' / f'{vid}.json'
    if cache.exists():
        d = comun.leer(cache)
        return [tuple(x) for x in d['segs']], f"subtítulos {d['pista']} ($DATOS/subs/{vid}.json)"
    fx = comun.fixture()
    if fx:
        segs = (comun.leer(fx / 'subs.json', {}) or {}).get(vid)
        if not segs:
            return None, 'sin subtítulos en la prueba'
        comun.escribir(cache, {'id': vid, 'pista': f'{idioma or "?"} (prueba)', 'bajado': comun.ahora(), 'segs': segs})
        return [tuple(x) for x in segs], f'subtítulos {idioma or "?"} (prueba) ($DATOS/subs/{vid}.json)'
    if not hay_ytdlp():
        return None, 'sin yt-dlp: no se leyó lo que dice en voz alta'
    try:
        p = subprocess.run(['yt-dlp', '-J', '--skip-download', '--no-warnings', f'https://www.youtube.com/watch?v={vid}'],
                           capture_output=True, text=True, timeout=90)
        info = json.loads(p.stdout or '{}')
    except Exception as e:  # noqa: BLE001
        return None, f'yt-dlp: {type(e).__name__}'
    if not info:
        return None, 'yt-dlp no devolvió datos (¿YouTube pidió verificación?)'
    lang = (info.get('language') or idioma or '')[:2]
    pista, url = None, None
    for fuente, claves in ((info.get('subtitles') or {}, [lang]), (info.get('automatic_captions') or {}, [f'{lang}-orig', lang])):
        for k in claves:
            for f in fuente.get(k, []) or []:
                if f.get('ext') == 'vtt':
                    pista, url = ('manual ' if fuente is info.get('subtitles') else 'automática ') + k, f['url']
                    break
            if url:
                break
        if url:
            break
    if not url:
        return None, 'sin pista de subtítulos original'
    r = comun.obtener(url, limite=5_000_000, timeout=40)
    segs = parse_vtt(r.get('cuerpo') or '')
    if not segs:
        return None, f'subtítulos vacíos (http {r.get("http")})'
    comun.escribir(cache, {'id': vid, 'pista': pista, 'bajado': comun.ahora(), 'segs': segs})
    return segs, f'subtítulos {pista} ($DATOS/subs/{vid}.json)'
