// Oportunidades comerciales (Marketing): posibles clientes y clientes, del primer contacto a la contratación, con su seguimiento,
// su valor potencial y sus servicios por departamento. Flujo: Nueva oportunidad → Contactado → En negociación → Propuesta enviada →
// Ganada / Perdida. Al ganar con un posible cliente, se convierte en cliente sin duplicarlo.
// Pestaña «Solicitudes de servicio»: cada departamento ve y atiende solo las suyas.
import { useCallback, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { AlarmClock, Briefcase, Plus, Search } from "lucide-react";
import { listarOportunidades, listarSolicitudes, resumenOportunidades } from "@/lib/api";
import { dinero, fechaCorta } from "@/lib/formato";
import { useRecurso } from "@/lib/recursos";
import { useSesion } from "@/lib/sesion";
import { Alerta, Boton, Cabecera, Cargando, Insignia, Pestanas, Vacio, cx } from "@/components/ui";
import {
  DetalleOportunidad, DetalleSolicitud, ESTADOS_OP_FLUJO, ESTADOS_SOL, EstadoOp, EstadoSol, FLUJO_OP, FormOportunidad, SERVICIOS,
} from "./piezas";

const VISTAS = [
  { valor: "pendientes", etiqueta: "Pendientes" }, { valor: "seguimiento", etiqueta: "Por atender hoy" },
  { valor: "ganadas", etiqueta: "Ganadas" }, { valor: "perdidas", etiqueta: "Perdidas" }, { valor: "todas", etiqueta: "Todas" },
];
const nombreServicio = (codigo) => SERVICIOS.find((s) => s[0] === codigo)?.[1] || codigo;

function Filtros({ f, setF, estados, conResponsable = true, conTipo = false }) {
  const [deptos] = useRecurso("departamentos");
  const [gente] = useRecurso("directorio");
  const cambiar = (k) => (e) => setF({ ...f, [k]: e.target.value });
  return (
    <div className="flex flex-wrap gap-2 [&>*]:min-w-[11rem] [&>*]:flex-1">
      <label className="relative !min-w-[16rem] !flex-[2]">
        <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-gris" aria-hidden />
        <input className="campo pl-9" value={f.q || ""} onChange={cambiar("q")} placeholder={conTipo ? "Buscar cliente, posible cliente, código o título" : "Buscar cliente, código o título"} aria-label="Buscar" />
      </label>
      {conTipo && (
        <select className="campo" value={f.tipo || ""} onChange={cambiar("tipo")} aria-label="Cliente o posible cliente">
          <option value="">Clientes y posibles clientes</option>
          <option value="prospecto">Solo posibles clientes</option>
          <option value="cliente">Solo clientes registrados</option>
        </select>
      )}
      <select className="campo" value={f.estado || ""} onChange={cambiar("estado")} aria-label="Estado">
        <option value="">Todos los estados</option>
        {Object.entries(estados).map(([k, [n]]) => <option key={k} value={k}>{n}</option>)}
      </select>
      {conResponsable && (
        <select className="campo" value={f.responsable || ""} onChange={cambiar("responsable")} aria-label="Responsable">
          <option value="">Cualquier responsable</option>
          {(gente || []).map((g) => <option key={g.id} value={g.id}>{g.nombre}</option>)}
        </select>
      )}
      <select className="campo" value={f.departamento || ""} onChange={cambiar("departamento")} aria-label="Departamento">
        <option value="">Todos los departamentos</option>
        {(deptos || []).map((d) => <option key={d.id} value={d.id}>{d.nombre}</option>)}
      </select>
      <div className="flex gap-2 !min-w-[18rem]">
        <label className="flex flex-1 items-center gap-1.5 text-sm text-gris">Desde<input type="date" className="campo" value={f.desde || ""} onChange={cambiar("desde")} aria-label="Registradas desde" /></label>
        <label className="flex flex-1 items-center gap-1.5 text-sm text-gris">Hasta<input type="date" className="campo" value={f.hasta || ""} onChange={cambiar("hasta")} aria-label="Registradas hasta" /></label>
      </div>
    </div>
  );
}

const limpio = (o) => Object.fromEntries(Object.entries(o).filter(([, v]) => v !== "" && v != null));

function TabOportunidades({ abrirOp, version, refrescar }) {
  const [vista, setVista] = useState("pendientes");
  const [f, setF] = useState({});
  const [lista, setLista] = useState(null);
  const [resumen, setResumen] = useState(null);
  const [error, setError] = useState("");
  const [nueva, setNueva] = useState(false);
  const filtros = useMemo(() => limpio(f), [f]);
  useEffect(() => {
    const t = setTimeout(() => {
      listarOportunidades({ ...filtros, ...(vista !== "todas" ? { vista } : {}) }).then((r) => setLista(r.results || r)).catch((e) => setError(e.message));
      resumenOportunidades(filtros).then(setResumen).catch(() => {});
    }, 250);
    return () => clearTimeout(t);
  }, [filtros, vista, version]);
  const cuentas = { pendientes: resumen?.pendientes, seguimiento: resumen?.seguimiento_vencido, ganadas: resumen?.ganadas, perdidas: resumen?.perdidas };
  const opciones = VISTAS.map((v) => ({ ...v, cuenta: cuentas[v.valor] }));
  return (
    <div className="space-y-4">
      <div className="flex flex-col-reverse gap-3 sm:flex-row sm:items-center">
        <Pestanas opciones={opciones} valor={vista} onCambio={setVista} className="min-w-0 flex-1" />
        <Boton icono={Plus} onClick={() => setNueva(true)} className="shrink-0">Nueva oportunidad</Boton>
      </div>
      {resumen && (
        <>
          <div className="grid grid-cols-2 gap-2 lg:grid-cols-4">
            {[
              ["pendientes", "Pendientes", resumen.pendientes, resumen.prospectos ? `${resumen.prospectos} con posibles clientes` : "En seguimiento", "text-tinta"],
              ["valor", "Valor potencial abierto", dinero(resumen.valor_abierto), "Suma de las pendientes", "text-azul"],
              ["ganadas", "Ganadas", resumen.ganadas, resumen.valor_ganado ? dinero(resumen.valor_ganado) : "Negocios cerrados", "text-verde"],
              ["perdidas", "Perdidas", resumen.perdidas, "No se concretaron", "text-rojo"],
            ].map(([clave, titulo, valor, nota, color]) => (
              <button key={clave} type="button" onClick={() => { setVista(clave === "valor" ? "pendientes" : clave); setF({ ...f, estado: "" }); }}
                className={cx("rounded-xl border bg-white px-3 py-2.5 text-left hover:border-azul", vista === clave ? "border-azul" : "border-linea")}>
                <span className="block text-xs text-gris">{titulo}</span>
                <span className={cx("num block text-xl font-semibold", color)}>{valor}</span>
                <span className="block truncate text-xs text-gris">{nota}</span>
              </button>
            ))}
          </div>
          <div className="flex snap-x gap-2 overflow-x-auto pb-1 [scrollbar-width:none]" aria-label="Oportunidades por estado">
            {resumen.estados.map((e) => {
              const paso = FLUJO_OP.indexOf(e.codigo);
              return (
                <button key={e.codigo} type="button" onClick={() => { setVista("todas"); setF({ ...f, estado: f.estado === e.codigo ? "" : e.codigo }); }}
                  className={cx("min-w-32 shrink-0 snap-start rounded-xl border px-3 py-2 text-left", f.estado === e.codigo ? "border-azul bg-azul/5" : "border-linea bg-white")}>
                  <span className="block text-xs text-gris">{paso >= 0 && <span className="num">{paso + 1}. </span>}{e.nombre}</span><span className="num text-xl font-semibold">{e.total}</span>
                </button>
              );
            })}
          </div>
        </>
      )}
      <Filtros f={f} setF={setF} estados={ESTADOS_OP_FLUJO} conTipo />
      {error ? <Alerta>{error}</Alerta> : !lista ? <Cargando /> : !lista.length ? (
        <Vacio icono={Briefcase} titulo="No hay oportunidades con estos filtros" accion={<Boton icono={Plus} onClick={() => setNueva(true)}>Registrar la primera</Boton>}>
          Registra cada posible cliente desde el primer contacto (aunque todavía no sea cliente) para que nadie se quede sin atención.
        </Vacio>
      ) : (
        <ul className="grid gap-2">
          {lista.map((o) => (
            <li key={o.id}>
              <button type="button" onClick={() => abrirOp(o.id)} className={cx("w-full rounded-xl border bg-white px-4 py-3 text-left hover:border-azul", o.seguimiento_vencido ? "border-rojo/40" : "border-linea")}>
                <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
                  <span className="font-semibold">{o.cliente_nombre}</span>
                  {o.es_prospecto && <Insignia tono="amarillo">Posible cliente</Insignia>}
                  <span className="text-sm text-gris">{o.codigo} · {o.titulo}</span>
                  <span className="ml-auto flex items-center gap-2">
                    {o.seguimiento_vencido && <span className="flex items-center gap-1 text-xs font-medium text-rojo"><AlarmClock className="size-3.5" aria-hidden />Seguimiento {fechaCorta(o.proximo_seguimiento)}</span>}
                    <EstadoOp estado={o.estado} />
                  </span>
                </div>
                <div className="mt-1 flex flex-wrap gap-x-4 gap-y-1 text-sm text-gris">
                  <span>{o.responsable_nombre || "Sin responsable"}</span>
                  {o.valor_estimado != null && <span className="num font-medium text-tinta">{dinero(o.valor_estimado)}</span>}
                  {o.departamento_nombre && <span>{o.departamento_nombre}</span>}
                  <span>Registrada {fechaCorta(o.fecha_creacion)}</span>
                  {!o.seguimiento_vencido && o.proximo_seguimiento && o.estado !== "APROBADA" && o.estado !== "NO_CONCRETADA" && <span>Seguimiento {fechaCorta(o.proximo_seguimiento)}</span>}
                </div>
                {o.servicios.length > 0 ? (
                  <div className="mt-2 flex flex-wrap gap-1.5">
                    {o.servicios.map((s) => <span key={s.id} className="rounded-full bg-fondo px-2 py-0.5 text-xs">{s.servicio} · <span className="text-gris">{s.estado_nombre}</span></span>)}
                  </div>
                ) : o.servicios_interes?.length > 0 && (
                  <div className="mt-2 flex flex-wrap gap-1.5">
                    {o.servicios_interes.map((c) => <span key={c} className="rounded-full bg-fondo px-2 py-0.5 text-xs">{nombreServicio(c)} · <span className="text-gris">le interesa</span></span>)}
                  </div>
                )}
              </button>
            </li>
          ))}
        </ul>
      )}
      <FormOportunidad abierto={nueva} onCerrar={() => setNueva(false)} onGuardado={(o) => { setNueva(false); refrescar(); abrirOp(o.id); }} />
    </div>
  );
}

function TabSolicitudes({ abrirSol, version }) {
  const [f, setF] = useState({ vista: "abiertas" });
  const [lista, setLista] = useState(null);
  const [error, setError] = useState("");
  const filtros = useMemo(() => limpio(f), [f]);
  useEffect(() => {
    const t = setTimeout(() => listarSolicitudes(filtros).then((r) => setLista(r.results || r)).catch((e) => setError(e.message)), 250);
    return () => clearTimeout(t);
  }, [filtros, version]);
  return (
    <div className="space-y-4">
      <Pestanas opciones={[{ valor: "abiertas", etiqueta: "Abiertas" }, { valor: "", etiqueta: "Todas" }]} valor={f.vista} onCambio={(v) => setF({ ...f, vista: v })} />
      <Filtros f={f} setF={setF} estados={ESTADOS_SOL} />
      {error ? <Alerta>{error}</Alerta> : !lista ? <Cargando /> : !lista.length ? (
        <Vacio icono={Briefcase} titulo="No hay solicitudes con estos filtros">Aquí llegan los servicios que Marketing registra para tu departamento.</Vacio>
      ) : (
        <ul className="grid gap-2">
          {lista.map((s) => (
            <li key={s.id}>
              <button type="button" onClick={() => abrirSol(s.id)} className="w-full rounded-xl border border-linea bg-white px-4 py-3 text-left hover:border-azul">
                <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
                  <span className="font-semibold">{s.servicio_nombre}</span>
                  <span className="text-sm text-gris">{s.codigo} · {s.cliente_nombre}</span>
                  <span className="ml-auto"><EstadoSol estado={s.estado} /></span>
                </div>
                <div className="mt-1 flex flex-wrap gap-x-4 gap-y-1 text-sm text-gris">
                  <span>{s.departamento_nombre}</span><span>{s.responsable_nombre || "Sin responsable"}</span><span>Registrada {fechaCorta(s.fecha_creacion)}</span>
                  {(s.proyecto_codigo || s.orden_codigo) && <span className="text-verde">{s.proyecto_codigo || s.orden_codigo}</span>}
                </div>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export default function Oportunidades() {
  const { usuario } = useSesion();
  const comercial = !!usuario.es_comercial;
  const [params, setParams] = useSearchParams();
  const [tab, setTab] = useState(comercial && !params.get("solicitud") ? "oportunidades" : "solicitudes");
  const [version, setVersion] = useState(0);
  const refrescar = useCallback(() => setVersion((v) => v + 1), []);
  const op = params.get("oportunidad");
  const sol = params.get("solicitud");
  const abrir = (clave, id) => { const p = new URLSearchParams(params); p.delete("oportunidad"); p.delete("solicitud"); if (id) p.set(clave, id); setParams(p); };
  useEffect(() => { if (params.get("nuevo") === "1") setTab("oportunidades"); }, [params]);
  return (
    <div className="space-y-5">
      <Cabecera titulo={comercial ? "Oportunidades comerciales" : "Solicitudes de servicio"}
        descripcion={comercial ? "Marketing: posibles clientes y clientes, del primer contacto al negocio ganado. Anota cada llamada, reunión y propuesta; al ganar, se convierte en cliente y cada servicio pasa a su departamento."
          : "Servicios que Marketing registró para tu departamento. Cambia su estado, asigna responsable y, cuando el cliente apruebe, conviértela en proyecto u orden."} />
      {comercial && <Pestanas opciones={[{ valor: "oportunidades", etiqueta: "Oportunidades" }, { valor: "solicitudes", etiqueta: "Solicitudes de servicio" }]} valor={tab} onCambio={setTab} />}
      {tab === "oportunidades" && comercial
        ? <TabOportunidades abrirOp={(id) => abrir("oportunidad", id)} version={version} refrescar={refrescar} />
        : <TabSolicitudes abrirSol={(id) => abrir("solicitud", id)} version={version} />}
      {comercial && <DetalleOportunidad id={op} onCerrar={() => abrir()} onCambio={refrescar} onAbrirSolicitud={(id) => abrir("solicitud", id)} />}
      <DetalleSolicitud id={sol} onCerrar={() => abrir()} onCambio={refrescar} />
    </div>
  );
}
