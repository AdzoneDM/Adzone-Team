"""Permiso «Personas» (personal.directorio): ve, crea y desactiva personas, sin correos, contraseñas ni accesos."""
from django.contrib.auth.models import Group, User
from django.test import TestCase
from rest_framework.test import APIClient

from apps.core.models import PermisosDePerfil
from apps.core.permisos import PERMISOS

URL = '/api/organizacion/usuarios/'
CLAVE = 'Clave-segura-2026-x'


def persona(username, *perfiles, **extra):
    u = User.objects.create_user(username, password=CLAVE, email=f'{username}@adzone.test', **extra)
    for nombre in perfiles:
        u.groups.add(Group.objects.get(name=nombre))
    return u


class DirectorioTests(TestCase):
    def setUp(self):
        g = Group.objects.create(name='Directorio')
        PermisosDePerfil.objects.create(grupo=g, descripcion='Solo directorio', permisos=['personal.directorio'], orden=5)
        self.rrhh = persona('rrhh', 'Directorio')
        self.colab = persona('colab', 'Colaborador')
        self.otro = persona('otro', 'Colaborador')
        self.sistema = persona('sistema', 'Administrador del sistema')   # tiene «Personas y accesos»
        self.c = APIClient()
        self.c.force_authenticate(self.rrhh)

    # ---- el permiso existe, es independiente y no toca al anterior
    def test_el_catalogo_trae_personas_y_conserva_personas_y_accesos(self):
        por_codigo = {p[0]: p for p in PERMISOS}
        nuevo, viejo = por_codigo['personal.directorio'], por_codigo['personal.usuarios']
        self.assertEqual((nuevo[1], nuevo[2], nuevo[3]), ('Personas', 'Empresa', 'empresa'))
        self.assertEqual(nuevo[4], 'Ver a todas las personas, crear usuarios nuevos y desactivar cuentas, sin poder modificar correos ni cambiar contraseñas.')
        self.assertEqual(viejo[1], 'Personas y accesos')

    def test_el_catalogo_de_la_pantalla_lo_muestra_en_la_seccion_de_empresa(self):
        c = APIClient()
        c.force_authenticate(self.sistema)
        permisos = c.get('/api/accesos/').json()['permisos']
        fila = next(p for p in permisos if p['codigo'] == 'personal.directorio')
        self.assertEqual(fila['nombre'], 'Personas')
        self.assertEqual(fila['alcance'], 'empresa')

    # ---- lo permitido
    def test_ve_el_directorio_completo(self):
        r = self.c.get(URL)
        self.assertEqual(r.status_code, 200)
        datos = r.json()
        self.assertGreaterEqual(len(datos['results'] if isinstance(datos, dict) else datos), 4)  # rrhh, colab, otro y sistema

    def test_quien_no_tiene_permiso_no_ve_el_directorio(self):
        c = APIClient()
        c.force_authenticate(self.colab)
        self.assertEqual(c.get(URL).status_code, 403)

    def test_crea_usuarios_nuevos_como_colaborador(self):
        r = self.c.post(URL, {'username': 'nuevo', 'first_name': 'Nuevo', 'password': 'Otra-clave-2026-z', 'roles_asignados': ['Colaborador']}, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(list(User.objects.get(username='nuevo').groups.values_list('name', flat=True)), ['Colaborador'])

    def test_no_crea_cuentas_con_perfiles_de_acceso_ni_puestos_adicionales(self):
        r = self.c.post(URL, {'username': 'jefe', 'first_name': 'Jefe', 'password': 'Otra-clave-2026-z', 'roles_asignados': ['Administrador']}, format='json')
        self.assertEqual(r.status_code, 403)
        self.assertFalse(User.objects.filter(username='jefe').exists())

    def test_desactiva_y_reactiva_cuentas(self):
        self.assertEqual(self.c.patch(f'{URL}{self.colab.pk}/', {'is_active': False}, format='json').status_code, 200)
        self.colab.refresh_from_db()
        self.assertFalse(self.colab.is_active)
        self.assertEqual(self.c.patch(f'{URL}{self.colab.pk}/', {'is_active': True}, format='json').status_code, 200)
        self.colab.refresh_from_db()
        self.assertTrue(self.colab.is_active)

    # ---- lo bloqueado en la API
    def test_no_cambia_correos(self):
        r = self.c.patch(f'{URL}{self.colab.pk}/', {'email': 'otro@correo.test'}, format='json')
        self.assertEqual(r.status_code, 403)
        self.colab.refresh_from_db()
        self.assertEqual(self.colab.email, 'colab@adzone.test')

    def test_no_cambia_contrasenas(self):
        r = self.c.patch(f'{URL}{self.colab.pk}/', {'password': 'Nueva-clave-2026-q'}, format='json')
        self.assertEqual(r.status_code, 403)
        self.colab.refresh_from_db()
        self.assertTrue(self.colab.check_password(CLAVE))

    def test_no_cambia_perfiles_de_acceso_ni_el_usuario_de_entrada(self):
        self.assertEqual(self.c.patch(f'{URL}{self.colab.pk}/', {'roles_asignados': ['Administrador']}, format='json').status_code, 403)
        self.assertEqual(self.c.patch(f'{URL}{self.colab.pk}/', {'username': 'otro-nombre'}, format='json').status_code, 403)
        self.assertEqual(list(self.colab.groups.values_list('name', flat=True)), ['Colaborador'])

    def test_enviar_los_mismos_valores_no_es_un_cambio(self):
        r = self.c.patch(f'{URL}{self.colab.pk}/', {'email': 'COLAB@adzone.test', 'username': 'colab', 'roles_asignados': ['Colaborador'], 'is_active': False}, format='json')
        self.assertEqual(r.status_code, 200, r.content)

    def test_no_borra_cuentas_solo_las_desactiva(self):
        self.assertEqual(self.c.delete(f'{URL}{self.otro.pk}/').status_code, 403)
        self.assertTrue(User.objects.filter(pk=self.otro.pk).exists())

    def test_no_entra_a_accesos_y_permisos(self):
        self.assertEqual(self.c.get('/api/accesos/personas/').status_code, 403)
        self.assertEqual(self.c.post('/api/accesos/excepciones/', {'usuario': self.colab.pk, 'permiso': 'direccion', 'conceder': True}, format='json').status_code, 403)

    # ---- mínimo privilegio sobre sí mismo
    def test_no_desactiva_su_propia_cuenta(self):
        r = self.c.patch(f'{URL}{self.rrhh.pk}/', {'is_active': False}, format='json')
        self.assertEqual(r.status_code, 400)
        self.rrhh.refresh_from_db()
        self.assertTrue(self.rrhh.is_active)

    def test_no_cambia_sus_propios_perfiles(self):
        self.assertEqual(self.c.patch(f'{URL}{self.rrhh.pk}/', {'roles_asignados': ['Administrador']}, format='json').status_code, 403)

    # ---- quien tiene «Personas y accesos» sigue haciendo todo
    def test_personas_y_accesos_conserva_todo(self):
        c = APIClient()
        c.force_authenticate(self.sistema)
        self.assertEqual(c.patch(f'{URL}{self.colab.pk}/', {'email': 'cambio@correo.test'}, format='json').status_code, 200)
        self.assertEqual(c.patch(f'{URL}{self.colab.pk}/', {'password': 'Nueva-clave-2026-q'}, format='json').status_code, 200)
        self.assertEqual(c.get('/api/accesos/personas/').status_code, 200)

    def test_quien_tiene_los_dos_permisos_no_queda_limitado(self):
        g = Group.objects.create(name='Ambos')
        PermisosDePerfil.objects.create(grupo=g, permisos=['personal.directorio', 'personal.usuarios'], orden=6)
        ambos = persona('ambos', 'Ambos')
        c = APIClient()
        c.force_authenticate(ambos)
        self.assertEqual(c.patch(f'{URL}{self.colab.pk}/', {'email': 'cambio2@correo.test'}, format='json').status_code, 200)
