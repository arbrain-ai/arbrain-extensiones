"""Piezas comunes de la extensión «Competencia» (20 nov 2026): dónde vive cada cosa, lectura y escritura segura,
la llave de YouTube del dueño, su tope de cuota y la red (real o de prueba).

Dónde vive cada cosa (contrato de extensiones, SPEC §1.3):
  CEREBRO = ARBRAIN_RAIZ, o el cerebro que contiene a este script si vive en <cerebro>/.claude/skills/…, o la carpeta de
            trabajo o la primera de sus madres con `.claude/`. Nunca la carpeta de la extensión (es de solo lectura).
  CARPETA = <cerebro>/.claude/memory/extensiones/competencia/   lo del dueño: su universo, sus fichas, su embudos.json,
            su taxonomía, la evidencia en texto y los cambios. Versionado en su rama.
  DATOS   = ${CLAUDE_PLUGIN_DATA} (o COMPETENCIA_DATOS)        lo que se regenera: censos crudos, HTML de páginas,
            subtítulos, huellas y el contador de cuota. Se pierde al desinstalar y no pasa nada.
Solo biblioteca estándar de Python 3.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import tempfile
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

UA = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130 Safari/537.36'
ID_EXT = 'competencia'


class Falta(Exception):
    """Falta algo que el dueño o Levy tienen que dar (código 2): la lista dice qué."""


class SinLlave(Exception):
    """No hay llave de YouTube (código 4). La tarea semanal se salta y avisa; no falla."""


class TopeCuota(Exception):
    """Se llegó al tope diario de unidades que el dueño fijó (código 5)."""


# ───────────────────────── rutas ─────────────────────────

def raiz() -> Path:
    if os.environ.get('ARBRAIN_RAIZ'):
        return Path(os.environ['ARBRAIN_RAIZ']).expanduser().resolve()
    aqui = Path(__file__).resolve()
    # <cerebro>/.claude/skills/competencia/scripts/comun.py → copia en la base
    if len(aqui.parents) > 4 and aqui.parents[2].name == 'skills' and aqui.parents[3].name == '.claude':
        return aqui.parents[4]
    for r in (Path.cwd(), *Path.cwd().parents):
        if (r / '.claude').is_dir():
            return r
    return Path.cwd()


def carpeta() -> Path:
    return raiz() / '.claude' / 'memory' / 'extensiones' / ID_EXT


def datos() -> Path:
    d = os.environ.get('COMPETENCIA_DATOS') or os.environ.get('CLAUDE_PLUGIN_DATA')
    if d and '${' not in d:
        return Path(d).expanduser()
    # Sin Claude Code (prueba a mano): caché fuera del cerebro, regenerable.
    return Path.home() / '.cache' / 'arbrain-extensiones' / ID_EXT


def extension() -> Path:
    """La carpeta de la extensión (solo lectura): de aquí salen la taxonomía por defecto y las referencias."""
    return Path(__file__).resolve().parents[1]


def rel(p: Path) -> str:
    """Cómo se cita una ruta en un dato: relativa al cerebro, o `$DATOS/…`. Nunca la ruta absoluta de la máquina."""
    p = Path(p).resolve()
    for base, nombre in ((datos().resolve(), '$DATOS'), (raiz(), None)):
        try:
            r = p.relative_to(base)
            return f'{nombre}/{r}' if nombre else str(r)
        except ValueError:
            pass
    return p.name


# ───────────────────────── archivos ─────────────────────────

def hoy() -> str:
    return os.environ.get('COMPETENCIA_HOY') or dt.date.today().isoformat()


def ahora() -> str:
    return dt.datetime.now().astimezone().isoformat(timespec='seconds')


def leer(p: Path, defecto=None):
    p = Path(p)
    if not p.exists():
        return defecto
    return json.loads(p.read_text(encoding='utf-8'))


def escribir(p: Path, obj, texto: bool = False) -> Path:
    """Escritura atómica (temporal + rename): un corte a medias nunca deja un JSON roto que el panel lea."""
    p = Path(p)
    p.parent.mkdir(parents=True, exist_ok=True)
    cuerpo = obj if texto else json.dumps(obj, ensure_ascii=False, indent=1) + '\n'
    fd, tmp = tempfile.mkstemp(dir=p.parent, prefix='.' + p.name, suffix='.tmp')
    with os.fdopen(fd, 'w', encoding='utf-8') as f:
        f.write(cuerpo)
    os.chmod(tmp, 0o644)  # mkstemp nace 0600; un archivo del cerebro se lee como cualquier otro
    os.replace(tmp, p)
    return p


def slug(texto: str) -> str:
    t = unicodedata.normalize('NFKD', texto or '').encode('ascii', 'ignore').decode().lower()
    t = re.sub(r'[^a-z0-9]+', '-', t).strip('-')
    return t[:48].strip('-') or 'canal'


# ───────────────────────── la llave del dueño ─────────────────────────

def archivo_llaves() -> Path:
    return Path(os.environ.get('ARBRAIN_LLAVES') or Path.home() / '.config' / 'arbrain' / 'extensiones' / 'llaves.env').expanduser()


def llave(clave: str = 'youtube_data_api_key') -> str:
    """La llave del dueño, nunca la del autor. Orden: el entorno (así la pasa Arbrain a sus tareas y a Levy, SPEC §4.3)
    y, mientras la tienda no la guarde en su cofre, `~/.config/arbrain/extensiones/llaves.env` (0600, fuera del
    cerebro y de git). Nunca se imprime."""
    var = clave.upper()
    if os.environ.get(var):
        return os.environ[var].strip()
    f = archivo_llaves()
    if f.exists():
        for ln in f.read_text(encoding='utf-8').splitlines():
            if ln.strip().startswith(var + '='):
                v = ln.split('=', 1)[1].strip().strip('"\'')
                if v:
                    return v
    if os.environ.get('COMPETENCIA_FIXTURE'):
        return 'llave-de-prueba'
    raise SinLlave(f'falta la llave {clave}: guárdala desde la tienda de Arbrain (Extensiones › Competencia) o con '
                   f'`competencia.py llave` (la lee de la entrada estándar, no del chat)')


def guardar_llave(valor: str, clave: str = 'youtube_data_api_key') -> Path:
    f = archivo_llaves()
    f.parent.mkdir(parents=True, exist_ok=True)
    var = clave.upper()
    lineas = [ln for ln in (f.read_text(encoding='utf-8').splitlines() if f.exists() else []) if not ln.startswith(var + '=')]
    lineas.append(f'{var}={valor.strip()}')
    fd = os.open(f, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, 'w', encoding='utf-8') as h:
        h.write('\n'.join(lineas) + '\n')
    os.chmod(f, 0o600)
    return f


# ───────────────────────── cuota de YouTube ─────────────────────────

COSTO = {'search': 100, 'channels': 1, 'playlistItems': 1, 'videos': 1}
TOPE_POR_DEFECTO = 2000  # de las 10,000 unidades diarias gratis de una llave nueva


class Cuota:
    """Cuenta las unidades que gasta la extensión hoy y frena antes del tope del dueño (universo.json › cuota_diaria)."""

    def __init__(self, tope: int | None = None):
        self.ruta = datos() / 'cuota' / f'{hoy()}.json'
        d = leer(self.ruta, {}) or {}
        self.usadas = int(d.get('unidades', 0))
        self.llamadas = dict(d.get('llamadas', {}))
        self.tope = int(tope or TOPE_POR_DEFECTO)

    def gastar(self, endpoint: str, veces: int = 1):
        u = COSTO.get(endpoint, 1) * veces
        if self.usadas + u > self.tope:
            raise TopeCuota(f'tope diario de {self.tope} unidades: hoy van {self.usadas} y {endpoint} cuesta {u}. '
                            f'Sube universo.json › cuota_diaria o espera a mañana.')
        self.usadas += u
        self.llamadas[endpoint] = self.llamadas.get(endpoint, 0) + veces
        escribir(self.ruta, {'fecha': hoy(), 'unidades': self.usadas, 'tope': self.tope, 'llamadas': self.llamadas})


# ───────────────────────── red (real o de prueba) ─────────────────────────

def fixture() -> Path | None:
    f = os.environ.get('COMPETENCIA_FIXTURE')
    return Path(f) if f else None


def obtener(url: str, limite: int = 3_000_000, timeout: int = 25) -> dict:
    """Un GET público, sin cookies ni sesión. → {http, final, cuerpo} o {http: None, error}."""
    fx = fixture()
    if fx:
        web = leer(fx / 'web.json', {}) or {}
        r = web.get(url)
        if r is None:
            return {'http': None, 'final': None, 'error': 'URLError: sin fixture'}
        return {'http': r.get('http', 200), 'final': r.get('final', url), 'cuerpo': r.get('html', '')}
    req = urllib.request.Request(url, headers={'User-Agent': UA, 'Accept-Language': 'es-MX,es;q=0.9,en;q=0.8'})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return {'http': r.status, 'final': r.geturl(), 'cuerpo': r.read(limite).decode('utf-8', 'replace')}
    except urllib.error.HTTPError as e:
        cuerpo = ''
        try:
            cuerpo = e.read(limite).decode('utf-8', 'replace') if e.fp else ''
        except Exception:  # noqa: BLE001
            pass
        return {'http': e.code, 'final': e.geturl() or url, 'cuerpo': cuerpo}
    except Exception as e:  # noqa: BLE001
        return {'http': None, 'final': None, 'error': f'{type(e).__name__}: {e}'[:160]}


def obtener_json(url: str, timeout: int = 25) -> dict:
    req = urllib.request.Request(url, headers={'User-Agent': UA, 'Accept': 'application/json'})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode('utf-8'))
