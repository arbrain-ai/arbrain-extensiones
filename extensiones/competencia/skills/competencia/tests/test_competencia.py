"""Pruebas de la extensión «Competencia» (20 nov 2026). Sin red: todo YouTube y toda página sale de `tests/fixture/`
(canales, videos, páginas y subtítulos inventados). Cada prueba usa un cerebro y una caché temporales.

    python3 -m unittest discover -s <extensión>/skills/competencia/tests
"""
from __future__ import annotations

import contextlib
import copy
import hashlib
import io
import json
import os
import shutil
import stat
import sys
import tempfile
import unittest
from pathlib import Path

AQUI = Path(__file__).resolve().parent
SKILL = AQUI.parent
sys.path.insert(0, str(SKILL / 'scripts'))

import alta  # noqa: E402
import censo  # noqa: E402
import comun  # noqa: E402
import competencia  # noqa: E402
import estudio  # noqa: E402
import fichas  # noqa: E402
import taxonomia  # noqa: E402
import validar  # noqa: E402

PLATO = 'UCnutriPlatoEjemplo00000'


def huella(d: Path) -> str:
    h = hashlib.sha256()
    for p in sorted(x for x in d.rglob('*') if x.is_file() and '__pycache__' not in x.parts):
        h.update(str(p.relative_to(d)).encode() + p.read_bytes())
    return h.hexdigest()[:16]


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix='competencia-'))
        self.cerebro = self.tmp / 'cerebro'
        (self.cerebro / '.claude' / 'memory').mkdir(parents=True)
        self.fx = self.tmp / 'fixture'
        shutil.copytree(AQUI / 'fixture', self.fx)
        self.env = {k: os.environ.get(k) for k in ('ARBRAIN_RAIZ', 'COMPETENCIA_DATOS', 'COMPETENCIA_FIXTURE', 'COMPETENCIA_HOY',
                                                    'ARBRAIN_LLAVES', 'YOUTUBE_DATA_API_KEY', 'CLAUDE_PLUGIN_DATA')}
        os.environ.update({'ARBRAIN_RAIZ': str(self.cerebro), 'COMPETENCIA_DATOS': str(self.tmp / 'datos'),
                           'COMPETENCIA_FIXTURE': str(self.fx), 'COMPETENCIA_HOY': '2026-11-20',
                           'ARBRAIN_LLAVES': str(self.tmp / 'llaves.env')})
        os.environ.pop('YOUTUBE_DATA_API_KEY', None)
        os.environ.pop('CLAUDE_PLUGIN_DATA', None)
        self.c = self.cerebro / '.claude' / 'memory' / 'extensiones' / 'competencia'

    def tearDown(self):
        for k, v in self.env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        shutil.rmtree(self.tmp, ignore_errors=True)

    def fixture(self, nombre, cambio):
        p = self.fx / nombre
        d = json.loads(p.read_text())
        cambio(d)
        p.write_text(json.dumps(d, ensure_ascii=False))

    def cli(self, *args) -> tuple[int, str]:
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = competencia.main(list(args))
        return code, out.getvalue() + err.getvalue()

    def alta_completa(self, curar=True):
        self.assertEqual(self.cli('alta', '--nicho', 'nutriólogas que atienden en línea en México', '--palabras',
                                  'nutrióloga, plan de alimentación', '--pais', 'MX')[0], 0)
        self.assertEqual(self.cli('buscar')[0], 0)
        for s in ('nutriplato-ejemplo', 'doctor-fit-ejemplo'):
            self.assertEqual(self.cli('marcar', s, '--capa', 'competencia')[0], 0)
        self.assertEqual(self.cli('marcar', 'cocina-sana-ejemplo', '--capa', 'referente')[0], 0)
        self.assertEqual(self.cli('censo', '--subs', '2')[0], 0)
        if curar:
            self.assertEqual(self.cli('paginas', '--abrir-sugeridas')[0], 0)
            (self.c / 'fichas').mkdir(exist_ok=True)
            shutil.copy(SKILL / 'references' / 'ficha-ejemplo.json', self.c / 'fichas' / 'nutriplato-ejemplo.json')


class Rutas(Base):
    def test_el_cerebro_nunca_es_la_extension(self):
        self.assertEqual(comun.raiz(), self.cerebro.resolve())
        os.environ.pop('ARBRAIN_RAIZ')
        actual = os.getcwd()
        try:
            os.chdir(self.cerebro / '.claude' / 'memory')
            self.assertEqual(comun.raiz(), self.cerebro.resolve())
        finally:
            os.chdir(actual)
        self.assertNotIn('.claude-plugin', str(comun.carpeta()))

    def test_las_rutas_se_citan_sin_la_maquina(self):
        self.assertEqual(comun.rel(self.tmp / 'datos' / 'censos' / 'x.json'), '$DATOS/censos/x.json')
        self.assertEqual(comun.rel(self.c / 'universo.json'), '.claude/memory/extensiones/competencia/universo.json')


class Alta(Base):
    def test_alta_copia_la_taxonomia_y_arma_las_busquedas(self):
        self.cli('alta', '--nicho', 'nutriólogas en México', '--palabras', 'nutrióloga, plan de alimentación')
        u = json.loads((self.c / 'universo.json').read_text())
        self.assertEqual(u['esquema'], 'arbrain.universo-youtube/v1')
        self.assertEqual([q['q'] for q in u['consultas']], ['nutrióloga', 'plan de alimentación'])
        t = json.loads((self.c / 'taxonomia.json').read_text())
        self.assertEqual(len(t['modelos']), 7)

    def test_buscar_propone_y_nada_entra_sin_marca(self):
        self.cli('alta', '--nicho', 'nutriólogas', '--palabras', 'nutrióloga, plan de alimentación')
        code, out = self.cli('buscar')
        self.assertEqual(code, 0)
        cands = json.loads((self.c / 'candidatos.json').read_text())['candidatos']
        self.assertEqual([c['slug'] for c in cands], ['nutriplato-ejemplo', 'cocina-sana-ejemplo', 'doctor-fit-ejemplo'])
        self.assertEqual(cands[0]['apariciones'], 3)
        self.assertEqual(json.loads((self.c / 'universo.json').read_text())['canales'], [])
        self.assertEqual(json.loads((self.tmp / 'datos' / 'cuota' / '2026-11-20.json').read_text())['unidades'], 201)
        self.cli('marcar', 'nutriplato-ejemplo', '--capa', 'competencia')
        self.cli('marcar', 'doctor-fit-ejemplo', '--capa', 'ninguno')
        u = json.loads((self.c / 'universo.json').read_text())
        self.assertEqual([c['slug'] for c in u['canales']], ['nutriplato-ejemplo'])
        self.assertEqual(u['canales'][0]['suscriptores'], 182000)
        self.assertEqual([c['nombre'] for c in u['ignorados']], ['Doctor Fit (ejemplo)'])
        _, lista = self.cli('candidatos')
        self.assertIn('cocina-sana-ejemplo', lista)
        self.assertNotIn('doctor-fit-ejemplo', lista)

    def test_marcar_por_handle_y_su_canal(self):
        self.cli('alta', '--nicho', 'nutriólogas', '--palabras', 'nutrióloga', '--canal', '@cocinasana-ejemplo')
        u = json.loads((self.c / 'universo.json').read_text())
        self.assertEqual(u['dueno']['canal'], 'UCcocinaSanaEjemplo00000')
        self.assertEqual(u['canales'][0]['capa'], 'propio')
        code, out = self.cli('marcar', '@no-existe', '--capa', 'competencia')
        self.assertEqual(code, 2)
        self.assertIn('no encontré', out)

    def test_el_tope_de_cuota_frena(self):
        self.cli('alta', '--nicho', 'nutriólogas', '--palabras', 'nutrióloga, plan de alimentación', '--cuota', '150')
        code, out = self.cli('buscar')
        self.assertEqual(code, 5)
        self.assertIn('tope diario de 150', out)


class Censo(Base):
    def test_censo_enlaces_subtitulos_y_respaldo_de_lista(self):
        self.alta_completa(curar=False)
        d = json.loads(next((self.tmp / 'datos' / 'censos').glob('censo-*.json')).read_text())
        por = {c['slug']: c for c in d['canales']}
        ana = por['nutriplato-ejemplo']
        self.assertEqual(ana['lista_de'], 'UULF')
        cats = {e['dominio']: e['categoria'] for e in ana['videos'][0]['enlaces']}
        self.assertEqual(cats['skool.com'], 'comunidad')
        self.assertEqual(cats['amzn.to'], 'afiliado')
        self.assertEqual(cats['instagram.com'], 'red_social')
        self.assertIn('únete gratis a mi club', ana['videos'][0]['cta_hablado']['cierre'])
        self.assertEqual(ana['resumen']['con_transcript'], 1)
        doc = por['doctor-fit-ejemplo']
        self.assertEqual(doc['lista_de'], 'UU')  # sin lista de largos: subidas filtradas
        self.assertEqual([v['id'] for v in doc['videos']], ['CCCCCCCCCC2', 'CCCCCCCCCC3'])  # el de 45 s es un Short
        self.assertEqual({e['categoria'] for v in doc['videos'] for e in v['enlaces']}, {'mensajeria', 'web'})
        self.assertGreater(d['urls_resueltas'], 0)
        self.assertEqual([e['url'] for e in censo.enlaces('Agenda: www.ejemplo.mx/cita y correo hola@www.x.com')], ['https://www.ejemplo.mx/cita'])

    def test_la_foto_del_canal_viaja_como_data_uri_chica(self):
        self.alta_completa(curar=False)
        u = json.loads((self.c / 'universo.json').read_text())
        por = {c['slug']: c for c in u['canales']}
        foto = por['nutriplato-ejemplo'].get('miniatura') or ''
        self.assertTrue(foto.startswith('data:image/png;base64,'), foto[:40])
        self.assertLess(len(foto), 20_000)
        self.assertEqual(por['nutriplato-ejemplo']['miniatura_de'], por['nutriplato-ejemplo']['miniatura_url'])
        # Lo que no es imagen (o no está) se queda sin foto: el panel pinta iniciales.
        self.assertNotIn('miniatura', por['cocina-sana-ejemplo'])
        self.assertNotIn('miniatura', por['doctor-fit-ejemplo'])
        import youtube
        self.assertIsNone(youtube.foto_data_uri(None))
        os.environ.pop('COMPETENCIA_FIXTURE')
        try:  # fuera de los hosts de fotos de YouTube no sale a la red
            self.assertIsNone(youtube.foto_data_uri('https://ejemplo.invalid/foto.jpg'))
            self.assertIsNone(youtube.foto_data_uri('http://yt3.ggpht.com/foto.jpg'))
        finally:
            os.environ['COMPETENCIA_FIXTURE'] = str(self.fx)

    def test_un_censo_parcial_no_borra_a_los_demas(self):
        self.alta_completa(curar=False)
        self.cli('censo', '--canales', 'doctor-fit-ejemplo')
        d = json.loads(next((self.tmp / 'datos' / 'censos').glob('censo-*.json')).read_text())
        self.assertEqual(len(d['canales']), 3)


class Fichas(Base):
    def test_la_ficha_de_ejemplo_construye_un_embudo_valido(self):
        self.alta_completa()
        code, out = self.cli('construir')
        self.assertEqual(code, 0, out)
        e = json.loads((self.c / 'embudos.json').read_text())
        self.assertEqual(validar.validar(e), [])
        f = e['fichas'][0]
        self.assertEqual(f['cobertura'], {'estado': 'completa', 'faltan': []})
        self.assertEqual(f['cta_hablado'][0]['cita'],
                         'si quieres más recetas únete gratis a mi club el enlace está en la descripción nos vemos la próxima semana')
        roles = {d['rol']: d for d in f['destinos_video']}
        self.assertEqual(roles['comunidad_gratis']['nombre'], 'Club NutriPlato')
        self.assertEqual(roles['comunidad_gratis']['en_videos'], 3)
        self.assertIn('afiliado_o_patrocinio', roles)
        self.assertNotIn('linktr.ee', json.dumps(f['destinos_video']))  # «ignorar»
        self.assertEqual(f['oferta_pagada'][0]['dato']['respaldo'],
                         '.claude/memory/extensiones/competencia/evidencia/nutriplato-ejemplo__consulta.txt')
        self.assertNotIn('hola@nutriplato.example', (self.c / 'evidencia' / 'nutriplato-ejemplo__club-nutriplato.txt').read_text())
        self.assertNotIn(str(self.tmp), json.dumps(e))  # ninguna ruta de la máquina

    def test_la_evidencia_manda(self):
        self.alta_completa()
        f = json.loads((self.c / 'fichas' / 'nutriplato-ejemplo.json').read_text())

        def con(cambio):
            g = copy.deepcopy(f)
            cambio(g)
            (self.c / 'fichas' / 'nutriplato-ejemplo.json').write_text(json.dumps(g, ensure_ascii=False))
            return self.cli('construir')

        code, out = con(lambda g: g['promesa'][0].update(cita='Baja 10 kilos en un mes'))
        self.assertEqual(code, 2)
        self.assertIn('no aparece literal', out)
        code, out = con(lambda g: g['regalo_entrada'][0]['dato'].update(pagina='otra'))
        self.assertIn('no está abierta', out)
        code, out = con(lambda g: g['cta_hablado'][0].update(desde='0:10', hasta='0:20'))
        self.assertIn('no hay texto entre', out)
        code, out = con(lambda g: g['oferta_pagada'][0]['dato'].pop('nivel'))
        self.assertIn('no es precio_visto', out)
        code, out = con(lambda g: (g.pop('mecanismo'), g.update(vehiculo=['comunidad_gratis'])))
        self.assertIn('mecanismo» vacío sin', out)
        self.assertFalse((self.c / 'embudos.json').exists())  # nada inválido se escribe
        code, out = con(lambda g: (g.pop('mecanismo'), g.update(mecanismo_estado='no_visto: no lo explica')))
        self.assertEqual(code, 0, out)
        e = json.loads((self.c / 'embudos.json').read_text())
        self.assertEqual(e['fichas'][0]['cobertura']['faltan'], ['mecanismo'])

    def test_pendientes(self):
        self.alta_completa()
        self.cli('construir')
        _, out = self.cli('pendientes')
        self.assertRegex(out, r'nutriplato-ejemplo\s+completa')
        self.assertRegex(out, r'doctor-fit-ejemplo\s+sin ficha')


class Validador(unittest.TestCase):
    def test_dice_que_no(self):
        f = {'slug': 'x', 'nombre': 'X', 'channel_id': 'UCmal', 'idioma': 'es', 'motivo': 'm', 'no_visto': [],
             'muestra': {'videos': 1, 'con_transcript': 0, 'censo': 'c'},
             'destinos_video': [{'rol': 'web_propia', 'url': 'https://a', 'en_videos': 3, 'de_videos': 2,
                                 'dato': {'fuente': '/' + 'home/alguien/x.json', 'fecha': '20 nov', 'nivel': 'visto'}}],
             'cta_hablado': [{'video_id': 'v', 'minuto': '90', 'cita': '', 'pide': 'p', 'dato': {'fuente': 'f', 'fecha': '2026-11-20', 'nivel': 'pagina_abierta'}}],
             'regalo_entrada': [], 'oferta_pagada': [{'nombre': 'o', 'url': 'u', 'precio': {'monto': '10', 'moneda': 'USD', 'recurrencia': 'semanal', 'texto': ''},
                                                       'dato': {'fuente': 'f', 'fecha': '2026-11-20', 'nivel': 'pagina_abierta'}}],
             'promesa': [], 'promesa_estado': 'no_visto', 'vehiculo': [], 'mecanismo': None,
             'cobertura': {'estado': 'completa', 'faltan': []}}
        errores = '\n'.join(validar.validar_fichas([f]))
        for esperado in ('channel_id no parece', 'en_videos > de_videos', 'ruta absoluta', 'fecha no es', 'nivel no permitido',
                         'minuto no es M:SS', 'cita vacía', 'dicho_en_video', '«regalo_entrada» vacío sin', 'recurrencia no permitida',
                         'no es precio_visto', 'vehiculo vacío', 'mecanismo» vacío', 'calculado parcial'):
            self.assertIn(esperado, errores)


class Estudio(Base):
    def test_primera_huella_y_luego_lo_que_cambio(self):
        self.alta_completa()
        self.cli('construir')
        r = estudio.estudiar()
        self.assertIsNone(r['base'])
        self.assertIn('Primera huella', (self.c / 'cambios' / 'cambios-2026-11-20.md').read_text())
        # una semana después: Doctor Fit manda a un Skool nuevo en sus videos y NutriPlato sube su consulta
        os.environ['COMPETENCIA_HOY'] = '2026-11-27'

        def cambiar_yt(d):
            for v in d['videos'].values():
                if v['snippet']['channelId'].startswith('UCdoctorFit'):
                    v['snippet']['description'] += '\nMi comunidad: https://www.skool.com/fit-90/about'
        self.fixture('youtube.json', cambiar_yt)
        self.fixture('web.json', lambda w: w['https://nutriplato.example/consulta'].update(
            html='<html><head><title>Consulta</title></head><body>Consulta de 50 min · $990 MXN</body></html>'))
        r = estudio.estudiar()
        self.assertEqual(r['base'], '2026-11-20')
        c = r['canales']
        self.assertTrue(any('skool.com/fit-90' in m for m in c['doctor-fit-ejemplo']['motivos']))
        self.assertTrue(any('$990MXN' in m for m in c['nutriplato-ejemplo']['motivos']))
        self.assertEqual(c['nutriplato-ejemplo']['ultimo_cambio'], '2026-11-27')
        self.assertTrue(c['nutriplato-ejemplo']['reinvestigado'])
        self.assertEqual(c['cocina-sana-ejemplo']['motivos'], [])
        self.assertIn('## doctor-fit-ejemplo', (self.c / 'cambios' / 'cambios-2026-11-27.md').read_text())

    def test_sin_llave_se_salta_y_no_falla(self):
        self.alta_completa(curar=False)
        os.environ.pop('COMPETENCIA_FIXTURE')
        code, out = self.cli('estudio')
        self.assertEqual(code, 0)
        self.assertIn('salta: falta la llave', out)


class Llave(Base):
    def test_se_guarda_fuera_del_cerebro_y_no_se_imprime(self):
        os.environ.pop('COMPETENCIA_FIXTURE')
        secreto = 'AIzaPrueba-0123456789abcdefghijklmno'
        viejo = sys.stdin
        sys.stdin = io.StringIO(secreto + '\n')
        try:
            code, out = self.cli('llave')
        finally:
            sys.stdin = viejo
        self.assertEqual(code, 0)
        self.assertNotIn(secreto, out)
        f = self.tmp / 'llaves.env'
        self.assertEqual(stat.S_IMODE(f.stat().st_mode), 0o600)
        self.assertEqual(comun.llave(), secreto)
        self.assertFalse(any(secreto in p.read_text(errors='ignore') for p in self.cerebro.rglob('*') if p.is_file()))


class Taxonomia(Base):
    def test_siete_por_defecto_y_editable(self):
        tax = taxonomia.cargar()
        f = {'vehiculo': ['agencia'], 'oferta_pagada': [{'precio': {'monto': 600, 'recurrencia': 'mensual'}}],
             'destinos_video': [{'rol': 'afiliado_o_patrocinio', 'en_videos': 2}, {'rol': 'comunidad_gratis', 'en_videos': 1}]}
        self.assertEqual(taxonomia.modelos_de(f, tax), ['comunidad_gratis', 'alto_ticket', 'agencia'])
        f['destinos_video'][0]['en_videos'] = 3
        self.assertIn('patrocinio', taxonomia.modelos_de(f, tax))
        tax['modelos'].append({'id': 'consulta', 'nombre': 'Consulta 1 a 1', 'vehiculos': ['consulta_individual'], 'roles': []})
        self.assertEqual(taxonomia.modelos_de({'vehiculo': ['consulta_individual']}, tax), ['consulta'])

    def test_completar_agrega_lo_nuevo_sin_tocar_lo_suyo(self):
        self.cli('alta', '--nicho', 'n', '--palabras', 'x')
        ruta = self.c / 'taxonomia.json'
        t = json.loads(ruta.read_text())
        t['modelos'][5]['nombre'] = 'Consulta o servicio'
        t['alto_ticket'] = {'mensual': 400, 'otro': 900}   # suyo y viejo: sin por_moneda ni trimestral
        ruta.write_text(json.dumps(t))
        self.assertEqual(taxonomia.por_completar(), ['alto_ticket.trimestral', 'alto_ticket.por_moneda', 'alto_ticket.nota'])
        code, out = self.cli('taxonomia', '--completar')
        t = json.loads(ruta.read_text())
        self.assertEqual((t['alto_ticket']['mensual'], t['alto_ticket']['otro'], t['modelos'][5]['nombre']), (400, 900, 'Consulta o servicio'))
        self.assertIn('MXN', t['alto_ticket']['por_moneda'])
        self.assertEqual(taxonomia.por_completar(), [])

    def test_alto_ticket_mira_la_moneda(self):
        tax = taxonomia.cargar()
        caro = lambda monto, moneda, rec='pago_unico': 'alto_ticket' in taxonomia.modelos_de(  # noqa: E731
            {'oferta_pagada': [{'precio': {'monto': monto, 'moneda': moneda, 'recurrencia': rec}}]}, tax)
        self.assertFalse(caro(1850, 'MXN'))   # ~100 USD: no es alto ticket
        self.assertTrue(caro(25000, 'MXN'))
        self.assertTrue(caro(1200, 'USD'))
        self.assertTrue(caro(1200, 'EUR'))
        self.assertFalse(caro(499, 'USD', 'mensual'))


class Extension(Base):
    def test_no_escribe_en_la_carpeta_de_la_extension(self):
        ext = SKILL.parents[1]
        antes = huella(ext)
        self.alta_completa()
        self.cli('construir')
        estudio.estudiar()
        self.assertEqual(huella(ext), antes)

    def test_estado(self):
        self.alta_completa()
        self.cli('construir')
        code, out = self.cli('estado')
        self.assertEqual(code, 0)
        e = json.loads(out)
        self.assertEqual((e['fichas'], e['completas'], e['censados']), (1, 1, 3))
        self.assertEqual([m['id'] for m in e['modelos']], ['comunidad_gratis', 'curso', 'agencia', 'patrocinio'])  # el afiliado está en sus 3 videos
        self.assertTrue(e['llave_youtube'])  # en la prueba, la del fixture


if __name__ == '__main__':
    unittest.main()
