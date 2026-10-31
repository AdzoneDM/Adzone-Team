from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient

from apps.organizacion.models import PerfilUsuario, PuestoDeTrabajo
from .acceso import fijar_clave
from .models import Departamento


class EntradaPorEquipoTests(TestCase):
    """Clave general → directorio de áreas → contraseña de la persona."""

    def setUp(self):
        cache.clear()  # el límite de intentos se guarda en la caché
        self.c = APIClient()
        self.diseno = Departamento.objects.create(nombre="Marketing", orden=1)
        Departamento.objects.create(nombre="Call Center", orden=2)
        jefe = PuestoDeTrabajo.objects.create(nombre="Gerente de Marketing", departamento=self.diseno)
        disenador = PuestoDeTrabajo.objects.create(nombre="Diseñador", departamento=self.diseno, supervisor=jefe)
        self.ana = User.objects.create_user("ana", password="clave-ana-123", first_name="Ana", last_name="Ruiz")
        self.luis = User.objects.create_user("luis", password="clave-luis-123", first_name="Luis", last_name="Paz")
        PerfilUsuario.objects.update_or_create(user=self.ana, defaults={"puesto_trabajo": disenador})
        PerfilUsuario.objects.update_or_create(user=self.luis, defaults={"puesto_trabajo": jefe})
        inactivo = User.objects.create_user("ex", password="x", is_active=False)
        PerfilUsuario.objects.update_or_create(user=inactivo, defaults={"puesto_trabajo": disenador})

    def test_sin_clave_general_no_hay_directorio(self):
        r = self.c.get("/api/auth/directorio/")
        self.assertEqual(r.status_code, 403)
        self.assertFalse(r.data["configurada"])
        self.assertEqual(self.c.post("/api/auth/equipo/", {"clave": "lo-que-sea"}, format="json").status_code, 400)

    def test_clave_general_incorrecta(self):
        fijar_clave("equipo-adzone")
        self.assertEqual(self.c.post("/api/auth/equipo/", {"clave": "otra"}, format="json").status_code, 400)
        self.assertEqual(self.c.get("/api/auth/directorio/").status_code, 403)

    def test_directorio_ordenado_por_organigrama(self):
        fijar_clave("equipo-adzone")
        r = self.c.post("/api/auth/equipo/", {"clave": "equipo-adzone"}, format="json")
        self.assertEqual(r.status_code, 200)
        areas = {a["nombre"]: a for a in r.data["areas"]}
        self.assertEqual(list(areas), ["Marketing", "Call Center"])
        personas = areas["Marketing"]["personas"]
        self.assertEqual([p["nombre"] for p in personas], ["Luis Paz", "Ana Ruiz"])  # el inactivo no sale
        self.assertEqual(personas[1]["reporta_a"], "Gerente de Marketing")
        self.assertEqual(areas["Call Center"]["personas"], [])
        self.assertEqual(self.c.get("/api/auth/directorio/").status_code, 200)

    def test_entrar_eligiendo_persona(self):
        fijar_clave("equipo-adzone")
        # Sin la clave general no se puede entrar por la tarjeta de la persona.
        r = self.c.post("/api/auth/login/", {"user_id": self.ana.id, "password": "clave-ana-123"}, format="json")
        self.assertEqual(r.status_code, 403)
        self.c.post("/api/auth/equipo/", {"clave": "equipo-adzone"}, format="json")
        r = self.c.post("/api/auth/login/", {"user_id": self.ana.id, "password": "mala"}, format="json")
        self.assertEqual(r.status_code, 400)
        r = self.c.post("/api/auth/login/", {"user_id": self.ana.id, "password": "clave-ana-123"}, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["user"]["username"], "ana")
        # Al salir, el dispositivo sigue en el directorio.
        self.c.post("/api/auth/logout/")
        self.assertEqual(self.c.get("/api/auth/session/").data["isAuthenticated"], False)
        self.assertEqual(self.c.get("/api/auth/directorio/").status_code, 200)

    def test_entrada_clasica_sigue_funcionando(self):
        r = self.c.post("/api/auth/login/", {"username": "luis", "password": "clave-luis-123"}, format="json")
        self.assertEqual(r.status_code, 200)

    def test_solo_el_administrador_cambia_la_clave(self):
        self.c.force_authenticate(self.ana)
        self.assertEqual(self.c.post("/api/auth/clave-equipo/", {"nueva": "nueva-clave-1"}, format="json").status_code, 403)
        jefa = User.objects.create_superuser("jefa", password="x")
        self.c.force_authenticate(jefa)
        self.assertEqual(self.c.post("/api/auth/clave-equipo/", {"nueva": "corta"}, format="json").status_code, 400)
        self.assertEqual(self.c.post("/api/auth/clave-equipo/", {"nueva": "nueva-clave-1"}, format="json").status_code, 200)
        otro = APIClient()
        self.assertEqual(otro.post("/api/auth/equipo/", {"clave": "nueva-clave-1"}, format="json").status_code, 200)
