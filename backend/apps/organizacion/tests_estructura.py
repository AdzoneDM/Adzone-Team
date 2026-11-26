"""Organigrama 2026: unidad estructural ↔ cargo, coordinación operativa, matriz de reporte, registro de cambios y versiones."""
from openpyxl import load_workbook
from io import BytesIO

from apps.desempeno.tests_mejoras import Base

from .models import CambioOrganigrama, PuestoDeTrabajo, VersionOrganigrama

API = '/api/organizacion'


class EstructuraTests(Base):
    def test_cambios_quedan_registrados_y_la_direccion_aprueba_la_version(self):
        self.como(self.osiris)
        r = self.c.patch(f'{API}/puestos-trabajo/{self.p_gerente.id}/', {'unidad': 'Gerencia de Marketing y Audiovisuales',
                                                                         'coordina_con': [self.p_cm.id]}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        campos = set(CambioOrganigrama.objects.filter(version__isnull=True).values_list('campo', flat=True))
        self.assertEqual(campos, {'unidad', 'coordina_con'})
        o = self.c.get(f'{API}/organigrama/').json()
        self.assertEqual(o['cambios_pendientes'], 2)
        self.assertIsNone(o['version'])
        r = self.c.post(f'{API}/organigrama/versiones/', {'vigente_desde': '2026-12-01', 'notas': 'Organigrama 2026'}, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        o = self.c.get(f'{API}/organigrama/').json()
        self.assertEqual((o['version']['numero'], o['version']['vigente_desde'], o['cambios_pendientes']), (1, '2026-12-01', 0))
        self.assertEqual(VersionOrganigrama.objects.get().cambios.count(), 2)

    def test_solo_direccion_cambia_y_aprueba(self):
        self.como(self.ashley)
        self.assertEqual(self.c.patch(f'{API}/puestos-trabajo/{self.p_gerente.id}/', {'unidad': 'X'}, format='json').status_code, 403)
        self.assertEqual(self.c.post(f'{API}/organigrama/versiones/', {}, format='json').status_code, 403)
        self.assertEqual(self.c.get(f'{API}/organigrama/matriz/').status_code, 200)   # consultar sí: ¿a quién reporto?

    def test_no_se_forma_un_circulo_ni_se_coordina_consigo_mismo(self):
        self.como(self.osiris)
        r = self.c.patch(f'{API}/puestos-trabajo/{self.p_gerente.id}/', {'supervisor': self.p_cm.id}, format='json')
        self.assertEqual(r.status_code, 400)
        r = self.c.patch(f'{API}/puestos-trabajo/{self.p_cm.id}/', {'coordina_con': [self.p_cm.id]}, format='json')
        self.assertEqual(r.status_code, 400)

    def test_matriz_superior_coordinacion_escalamiento_y_excel(self):
        self.como(self.osiris)
        self.c.patch(f'{API}/puestos-trabajo/{self.p_gerente.id}/', {'coordina_con': [self.p_cm.id]}, format='json')
        m = self.c.get(f'{API}/organigrama/matriz/').json()
        cm = next(f for f in m['filas'] if f['id'] == self.p_cm.id)
        self.assertEqual(cm['superior'], PuestoDeTrabajo.objects.get(pk=self.p_cm.id).supervisor.nombre)
        self.assertEqual(cm['coordinado_por'], [self.p_gerente.nombre])
        self.assertTrue(cm['escalamiento'])
        self.assertTrue(any(a['tipo'] == 'unidad' for a in m['revision']))   # aún no tienen unidad
        r = self.c.get(f'{API}/organigrama/matriz/?formato=xlsx')
        self.assertEqual(r.status_code, 200)
        wb = load_workbook(BytesIO(r.content))
        self.assertEqual(wb.sheetnames, ['Matriz de reporte', 'Registro de cambios'])
        self.assertEqual(wb['Matriz de reporte']['D3'].value, 'Superior directo')
