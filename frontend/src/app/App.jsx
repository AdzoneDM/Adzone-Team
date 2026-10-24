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

function Protegida({ children, admin, supervisor }) {
  const { usuario, esAdmin, puedeValidar } = useSesion();
  const location = useLocation();
  if (!usuario) return <Navigate to="/entrar" replace state={{ desde: location.pathname + location.search }} />;
  if ((admin && !esAdmin) || (supervisor && !puedeValidar)) return <Navigate to="/" replace />;
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
        <Route element={<Protegida><Estructura /></Protegida>}>
          <Route index element={<Inicio />} />
          <Route path="mis-tareas" element={<MisTareas />} />
          <Route path="organigrama" element={<Organigrama />} />
          <Route path="mi-cuenta" element={<MiCuenta />} />
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
