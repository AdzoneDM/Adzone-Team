import { Suspense } from "react";
import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import Estructura from "@/app/Estructura";
import LimiteDeErrores from "@/components/LimiteDeErrores";
import { Cargando } from "@/components/ui";
import { perezosa } from "@/lib/perezosa";
import { useSesion } from "@/lib/sesion";
import Entrar from "@/features/cuenta/Entrar";
import Inicio from "@/features/inicio/Inicio";
import MisTareas from "@/features/tareas/MisTareas";

// Las pantallas de supervisión y administración se cargan al abrirlas: la app del celular pesa menos.
const Validar = perezosa(() => import("@/features/tareas/Validar"));
const Equipo = perezosa(() => import("@/features/equipo/Equipo"));
const Colaboracion = perezosa(() => import("@/features/colaboracion/Colaboracion"));
const Desempeno = perezosa(() => import("@/features/desempeno/Desempeno"));
const KpisDelMes = perezosa(() => import("@/features/desempeno/KpisDelMes"));
const Organigrama = perezosa(() => import("@/features/organizacion/Organigrama"));
const Puestos = perezosa(() => import("@/features/organizacion/Puestos"));
const PuestoDetalle = perezosa(() => import("@/features/organizacion/PuestoDetalle"));
const Personas = perezosa(() => import("@/features/organizacion/Personas"));
const PlantillasKpi = perezosa(() => import("@/features/kpis/PlantillasKpi"));
const Configuracion = perezosa(() => import("@/features/desempeno/Configuracion"));
const MiCuenta = perezosa(() => import("@/features/cuenta/MiCuenta"));
const Ordenes = perezosa(() => import("@/features/ordenes/Ordenes"));
const OrdenDetalle = perezosa(() => import("@/features/ordenes/OrdenDetalle"));
const Proyectos = perezosa(() => import("@/features/proyectos/Proyectos"));
const ProyectoDetalle = perezosa(() => import("@/features/proyectos/ProyectoDetalle"));
const Clientes = perezosa(() => import("@/features/clientes/Clientes"));
const ClienteDetalle = perezosa(() => import("@/features/clientes/ClienteDetalle"));
const MiTiempo = perezosa(() => import("@/features/tiempo/MiTiempo"));
const Finanzas = perezosa(() => import("@/features/finanzas/Finanzas"));
const Imprimir = perezosa(() => import("@/features/finanzas/Imprimir"));
const Automatizaciones = perezosa(() => import("@/features/automatizaciones/Automatizaciones"));
const Accesos = perezosa(() => import("@/features/organizacion/Accesos"));
const MarcarQR = perezosa(() => import("@/features/asistencia/MarcarQR"));
const Portal = perezosa(() => import("@/features/portal/Portal"));
const PantallaQR = perezosa(() => import("@/features/asistencia/PantallaQR"));
const TableroDepartamento = perezosa(() => import("@/features/departamentos/TableroDepartamento"));
const ResumenSemanal = perezosa(() => import("@/features/desempeno/ResumenSemanal"));
const Respaldos = perezosa(() => import("@/features/organizacion/Respaldos"));
const DosPasosObligatoria = perezosa(() => import("@/features/cuenta/DosPasos").then((m) => ({ default: m.DosPasosObligatoria })));
const OrdenArea = perezosa(() => import("@/features/ordenes/OrdenArea"));
const Indicadores = perezosa(() => import("@/features/ordenes/Indicadores"));
const ImprimirFormato = perezosa(() => import("@/features/ordenes/ImprimirFormato"));
const AjustesProduccion = perezosa(() => import("@/features/ordenes/AjustesProduccion"));
const Almacen = perezosa(() => import("@/features/almacen/Almacen"));
const CallCenter = perezosa(() => import("@/features/callcenter/CallCenter"));
const Asistencia = perezosa(() => import("@/features/asistencia/Asistencia"));
const Monitoreo = perezosa(() => import("@/features/monitoreo/Monitoreo"));
const Ficha = perezosa(() => import("@/features/desempeno/Ficha"));
const Computadora = perezosa(() => import("@/features/monitoreo/Computadora"));
const Talento = perezosa(() => import("@/features/talento/Talento"));
const Politicas = perezosa(() => import("@/features/talento/Politicas"));
const Activos = perezosa(() => import("@/features/activos/Activos"));
const Constancia = perezosa(() => import("@/features/talento/Politicas").then((m) => ({ default: m.Constancia })));
const PanelGerencial = perezosa(() => import("@/features/desempeno/PanelGerencial"));

function Protegida({ children, admin, supervisor, asignar, finanzas, permiso }) {
  const { usuario, esAdmin, puedeValidar, puedeAsignar, esFinanzas, tiene } = useSesion();
  const location = useLocation();
  if (!usuario) return <Navigate to="/entrar" replace state={{ desde: location.pathname + location.search }} />;
  if (usuario.debe_activar_dos_pasos) return <DosPasosObligatoria />;
  if ((admin && !esAdmin) || (supervisor && !puedeValidar) || (asignar && !puedeValidar && !puedeAsignar) || (finanzas && !esFinanzas) || (permiso && !tiene(permiso))) return <Navigate to="/" replace />;
  return children;
}

/** Ya con sesión, la pantalla de entrada te devuelve a donde estabas (si la sesión venció, vuelves a esa misma pantalla) y no siempre al Inicio. */
function VolverDondeEstaba() {
  const location = useLocation();
  return <Navigate to={location.state?.desde || "/"} replace />;
}

/** El agente de call center entra directo a su pantalla; el resto, al Inicio de siempre. */
function InicioSegunRol() {
  const { esAgente } = useSesion();
  return esAgente ? <Navigate to="/call-center" replace /> : <Inicio />;
}

export default function App() {
  const { cargando, usuario } = useSesion();
  const location = useLocation();
  if (cargando) return <Cargando texto="Abriendo Adzone Team…" />;

  return (
    <LimiteDeErrores claveReinicio={location.pathname}>
    <Suspense fallback={<Cargando />}>
      <Routes>
        <Route path="/entrar" element={usuario ? <VolverDondeEstaba /> : <Entrar />} />
        <Route path="/login" element={<Navigate to="/entrar" replace />} />
        <Route path="/pantalla-qr/:clave" element={<PantallaQR />} />
        <Route path="/portal/:token" element={<Portal />} />
        <Route path="/imprimir/ot/:id" element={<Protegida><ImprimirFormato tipo="ot" /></Protegida>} />
        <Route path="/imprimir/oa/:id" element={<Protegida><ImprimirFormato tipo="oa" /></Protegida>} />
        <Route path="/imprimir/acta/:id" element={<Protegida><ImprimirFormato tipo="acta" /></Protegida>} />
        <Route path="/imprimir/:tipo/:id" element={<Protegida finanzas><Imprimir /></Protegida>} />
        <Route element={<Protegida><Estructura /></Protegida>}>
          <Route index element={<InicioSegunRol />} />
          <Route path="call-center" element={<CallCenter />} />
          <Route path="mis-tareas" element={<MisTareas />} />
          <Route path="colaboracion" element={<Colaboracion />} />
          <Route path="organigrama" element={<Organigrama />} />
          <Route path="mi-cuenta" element={<MiCuenta />} />
          <Route path="ordenes" element={<Ordenes />} />
          <Route path="ordenes/indicadores" element={<Indicadores />} />
          <Route path="ordenes/:id" element={<OrdenDetalle />} />
          <Route path="ordenes/:id/areas/:oaId" element={<OrdenArea />} />
          <Route path="almacen" element={<Almacen />} />
          <Route path="produccion/ajustes" element={<AjustesProduccion />} />
          <Route path="proyectos" element={<Proyectos />} />
          <Route path="proyectos/:id" element={<ProyectoDetalle />} />
          <Route path="clientes" element={<Clientes />} />
          <Route path="clientes/:id" element={<ClienteDetalle />} />
          <Route path="tiempo" element={<MiTiempo />} />
          <Route path="asistencia" element={<Asistencia />} />
          <Route path="monitoreo" element={<Monitoreo />} />
          <Route path="monitoreo/computadoras/:id" element={<Computadora />} />
          <Route path="ficha" element={<Ficha />} />
          <Route path="talento" element={<Talento />} />
          <Route path="politicas" element={<Politicas />} />
          <Route path="activos" element={<Activos />} />
          <Route path="politicas/:id/constancia" element={<Constancia />} />
          <Route path="panel" element={<Protegida admin><PanelGerencial /></Protegida>} />
          <Route path="finanzas" element={<Protegida finanzas><Finanzas /></Protegida>} />
          <Route path="automatizaciones" element={<Protegida permiso="sistema.configurar"><Automatizaciones /></Protegida>} />
          <Route path="validar" element={<Protegida supervisor><Validar /></Protegida>} />
          <Route path="equipo" element={<Protegida asignar><Equipo /></Protegida>} />
          <Route path="desempeno" element={<Protegida admin><Desempeno /></Protegida>} />
          <Route path="kpis-del-mes" element={<Protegida admin><KpisDelMes /></Protegida>} />
          <Route path="puestos" element={<Protegida admin><Puestos /></Protegida>} />
          <Route path="puestos/:id" element={<Protegida admin><PuestoDetalle /></Protegida>} />
          <Route path="personas" element={<Protegida permiso="personal.usuarios"><Personas /></Protegida>} />
          <Route path="marcar" element={<MarcarQR />} />
          <Route path="departamentos/:id" element={<TableroDepartamento />} />
          <Route path="resumen-semanal" element={<Protegida admin><ResumenSemanal /></Protegida>} />
          <Route path="respaldos" element={<Protegida admin><Respaldos /></Protegida>} />
          <Route path="accesos" element={<Protegida permiso="personal.usuarios"><Accesos /></Protegida>} />
          <Route path="plantillas-kpi" element={<Protegida admin><PlantillasKpi /></Protegida>} />
          <Route path="configuracion" element={<Protegida admin><Configuracion /></Protegida>} />
          {/* Direcciones de la versión anterior */}
          <Route path="gestion-tareas" element={<Navigate to="/equipo" replace />} />
          <Route path="resultados-kpi" element={<Navigate to="/kpis-del-mes" replace />} />
          <Route path="gestion-usuarios" element={<Navigate to="/personas" replace />} />
          <Route path="gestion-puestos" element={<Navigate to="/puestos" replace />} />
          <Route path="departamentos" element={<Navigate to="/puestos" replace />} />
          <Route path="gestion-plantillas-kpi" element={<Navigate to="/plantillas-kpi" replace />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </Suspense>
    </LimiteDeErrores>
  );
}
