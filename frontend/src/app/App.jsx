import { lazy, Suspense } from "react";
import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import Estructura from "@/app/Estructura";
import { Cargando } from "@/components/ui";
import { useSesion } from "@/lib/sesion";
import Entrar from "@/features/cuenta/Entrar";
import Inicio from "@/features/inicio/Inicio";
import MisTareas from "@/features/tareas/MisTareas";

// Las pantallas de supervisión y administración se cargan al abrirlas: la app del celular pesa menos.
const Validar = lazy(() => import("@/features/tareas/Validar"));
const Equipo = lazy(() => import("@/features/equipo/Equipo"));
const Desempeno = lazy(() => import("@/features/desempeno/Desempeno"));
const KpisDelMes = lazy(() => import("@/features/desempeno/KpisDelMes"));
const Organigrama = lazy(() => import("@/features/organizacion/Organigrama"));
const Puestos = lazy(() => import("@/features/organizacion/Puestos"));
const PuestoDetalle = lazy(() => import("@/features/organizacion/PuestoDetalle"));
const Personas = lazy(() => import("@/features/organizacion/Personas"));
const PlantillasKpi = lazy(() => import("@/features/kpis/PlantillasKpi"));
const Configuracion = lazy(() => import("@/features/desempeno/Configuracion"));
const MiCuenta = lazy(() => import("@/features/cuenta/MiCuenta"));
const Ordenes = lazy(() => import("@/features/ordenes/Ordenes"));
const OrdenDetalle = lazy(() => import("@/features/ordenes/OrdenDetalle"));
const Proyectos = lazy(() => import("@/features/proyectos/Proyectos"));
const ProyectoDetalle = lazy(() => import("@/features/proyectos/ProyectoDetalle"));
const Clientes = lazy(() => import("@/features/clientes/Clientes"));
const ClienteDetalle = lazy(() => import("@/features/clientes/ClienteDetalle"));
const MiTiempo = lazy(() => import("@/features/tiempo/MiTiempo"));
const Finanzas = lazy(() => import("@/features/finanzas/Finanzas"));
const Imprimir = lazy(() => import("@/features/finanzas/Imprimir"));
const Automatizaciones = lazy(() => import("@/features/automatizaciones/Automatizaciones"));

function Protegida({ children, admin, supervisor, finanzas }) {
  const { usuario, esAdmin, puedeValidar, esFinanzas } = useSesion();
  const location = useLocation();
  if (!usuario) return <Navigate to="/entrar" replace state={{ desde: location.pathname + location.search }} />;
  if ((admin && !esAdmin) || (supervisor && !puedeValidar) || (finanzas && !esFinanzas)) return <Navigate to="/" replace />;
  return children;
}

export default function App() {
  const { cargando, usuario } = useSesion();
  if (cargando) return <Cargando texto="Abriendo Adzone Team…" />;

  return (
    <Suspense fallback={<Cargando />}>
      <Routes>
        <Route path="/entrar" element={usuario ? <Navigate to="/" replace /> : <Entrar />} />
        <Route path="/login" element={<Navigate to="/entrar" replace />} />
        <Route path="/imprimir/:tipo/:id" element={<Protegida finanzas><Imprimir /></Protegida>} />
        <Route element={<Protegida><Estructura /></Protegida>}>
          <Route index element={<Inicio />} />
          <Route path="mis-tareas" element={<MisTareas />} />
          <Route path="organigrama" element={<Organigrama />} />
          <Route path="mi-cuenta" element={<MiCuenta />} />
          <Route path="ordenes" element={<Ordenes />} />
          <Route path="ordenes/:id" element={<OrdenDetalle />} />
          <Route path="proyectos" element={<Proyectos />} />
          <Route path="proyectos/:id" element={<ProyectoDetalle />} />
          <Route path="clientes" element={<Clientes />} />
          <Route path="clientes/:id" element={<ClienteDetalle />} />
          <Route path="tiempo" element={<MiTiempo />} />
          <Route path="finanzas" element={<Protegida finanzas><Finanzas /></Protegida>} />
          <Route path="automatizaciones" element={<Protegida admin><Automatizaciones /></Protegida>} />
          <Route path="validar" element={<Protegida supervisor><Validar /></Protegida>} />
          <Route path="equipo" element={<Protegida supervisor><Equipo /></Protegida>} />
          <Route path="desempeno" element={<Protegida admin><Desempeno /></Protegida>} />
          <Route path="kpis-del-mes" element={<Protegida admin><KpisDelMes /></Protegida>} />
          <Route path="puestos" element={<Protegida admin><Puestos /></Protegida>} />
          <Route path="puestos/:id" element={<Protegida admin><PuestoDetalle /></Protegida>} />
          <Route path="personas" element={<Protegida admin><Personas /></Protegida>} />
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
  );
}
