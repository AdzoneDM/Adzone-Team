import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Award, CircleCheckBig, Trophy } from "lucide-react";
import { listarOrdenes, miResumen, resumenOrdenes, tablero } from "@/lib/api";
import { mesActual, nombreMes, plural, primerNombre, vencimiento } from "@/lib/formato";
import { useSesion } from "@/lib/sesion";
import { TarjetaOrden } from "@/features/ordenes/piezas";
import { useNavigate } from "react-router-dom";
import { Alerta, Avatar, Barra, Boton, Cargando, LeyendaTira, Panel, PrioridadTarea, Puntaje, TiraMes, cx } from "@/components/ui";

/** Cabecera azul: el mes de la persona hecho de tareas. */
export function MiMes({ resumen, nombre }) {
  const t = resumen.tareas;
  const pendientes = Math.max(0, t.por_hacer - t.vencidas);
  return (
    <section className="rounded-2xl bg-noche p-6 text-white md:p-7">
      <div className="flex flex-wrap items-start justify-between gap-6">
        <div>
          <p className="text-white/65 first-letter:uppercase">{nombreMes(resumen.periodo)}</p>
          <h1 className="mt-1 text-[28px] font-semibold text-white md:text-[32px]">Hola, {primerNombre(nombre)}</h1>
        </div>
        <div className="text-right">
          <p className="text-sm text-white/65">Puntaje del mes</p>
          <p className="font-display text-5xl font-semibold leading-none text-amarillo num">{resumen.puntaje == null ? "—" : Math.round(resumen.puntaje)}</p>
          {resumen.posicion && <p className="mt-1 text-sm text-white/70">Lugar {resumen.posicion} de {resumen.evaluados}</p>}
        </div>
      </div>
      <div className="mt-7">
        <div className="mb-2 flex flex-wrap items-baseline justify-between gap-2">
          <p className="text-[15px]"><span className="font-semibold num">{t.validadas} de {t.total}</span> <span className="text-white/70">tareas del mes validadas</span></p>
          <LeyendaTira oscuro />
        </div>
        <TiraMes validadas={t.validadas} revision={t.en_revision} vencidas={t.vencidas} pendientes={pendientes} oscuro />
      </div>
      {resumen.puntaje == null && t.total > 0 && (
        <p className="mt-4 text-sm text-white/70">Tu puntaje aparece cuando venza tu primera tarea del mes o te validen una entrega.</p>
      )}
    </section>
  );
}

function MuroDeHonor({ muro }) {
  const general = muro.filter((m) => !m.departamento);
  const deptos = muro.filter((m) => m.departamento);
  return (
    <Panel titulo="Muro de Honor" className="h-full">
      {muro.length === 0 ? (
        <div className="py-4 text-center">
          <Award className="mx-auto size-8 text-amarillo-600" aria-hidden />
          <p className="mt-2 text-sm text-gris">Al cerrar el mes, la dirección declara aquí al Empleado del Mes de la empresa y de cada departamento.</p>
        </div>
      ) : (
        <ul className="space-y-4">
          {general.map((m) => (
            <li key={m.id} className="rounded-xl bg-amarillo-50 p-4">
              <p className="text-sm text-[#7a5000] first-letter:uppercase">Empleado del Mes · {nombreMes(m.periodo)}</p>
              <div className="mt-2 flex items-center gap-3">
                <Avatar nombre={m.colaborador_nombre} tam="lg" className="bg-amarillo text-tinta" />
                <div className="min-w-0">
                  <p className="font-display text-lg font-semibold text-noche">{m.colaborador_nombre}</p>
                  <p className="text-sm text-gris">{m.puesto}</p>
                </div>
              </div>
              {m.motivo && <p className="mt-3 text-sm">{m.motivo}</p>}
              {m.beneficio && <p className="mt-1 text-sm text-gris">Reconocimiento: {m.beneficio}</p>}
            </li>
          ))}
          {deptos.map((m) => (
            <li key={m.id} className="flex items-center gap-3">
              <Avatar nombre={m.colaborador_nombre} tam="sm" />
              <div className="min-w-0">
                <p className="truncate text-sm font-medium">{m.colaborador_nombre}</p>
                <p className="truncate text-xs text-gris">{m.departamento_nombre}</p>
              </div>
            </li>
          ))}
        </ul>
      )}
    </Panel>
  );
}

function Proximas({ tareas }) {
  return (
    <Panel titulo="Mis próximas tareas" accion={<Link to="/mis-tareas" className="text-sm font-medium text-azul hover:underline">Ver todas</Link>} cuerpo="p-0">
      {tareas.length === 0 ? (
        <p className="px-5 py-6 text-sm text-gris">No tienes tareas pendientes.</p>
      ) : (
        <ul>
          {tareas.map((t) => {
            const v = vencimiento(t.fecha_limite);
            return (
              <li key={t.id} className="flex items-center gap-3 border-b border-linea-suave px-5 py-3 last:border-0">
                <div className="min-w-0 flex-1">
                  <Link to={`/mis-tareas?tarea=${t.id}`} className="block truncate font-medium hover:text-azul">{t.titulo}</Link>
                  <p className={cx("text-sm", v.tono === "rojo" ? "text-rojo" : v.tono === "amarillo" ? "text-[#a86a00]" : "text-gris")}>{v.texto}</p>
                </div>
                <PrioridadTarea prioridad={t.prioridad} />
              </li>
            );
          })}
        </ul>
      )}
    </Panel>
  );
}

function Cifra({ etiqueta, valor, tono, a }) {
  const contenido = (
    <>
      <p className="text-sm text-gris">{etiqueta}</p>
      <p className={cx("mt-1 font-display text-3xl font-semibold num", tono === "rojo" && valor > 0 ? "text-rojo" : tono === "amarillo" && valor > 0 ? "text-[#a86a00]" : "text-noche")}>{valor}</p>
    </>
  );
  return a ? <Link to={a} className="rounded-xl border border-linea bg-white px-5 py-4 hover:border-azul/40">{contenido}</Link>
    : <div className="rounded-xl border border-linea bg-white px-5 py-4">{contenido}</div>;
}

/** Órdenes de trabajo que me tocan hoy y, para quien gestiona, lo que espera aprobación o está vencido. */
function OperacionHoy({ gestiona }) {
  const navigate = useNavigate();
  const [mias, setMias] = useState(null);
  const [res, setRes] = useState(null);
  useEffect(() => {
    listarOrdenes({ mias: 1, abiertas: 1 }).then(setMias).catch(() => setMias([]));
    if (gestiona) resumenOrdenes().then(setRes).catch(() => {});
  }, [gestiona]);
  if (!mias || (!mias.length && !res?.por_aprobar && !res?.vencidas)) return null;
  const orden = [...mias].sort((a, b) => (a.fecha_compromiso || a.fecha_requerida || "9").localeCompare(b.fecha_compromiso || b.fecha_requerida || "9"));
  return (
    <section>
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-xl font-semibold">Órdenes de trabajo</h2>
        <Link to="/ordenes" className="text-sm font-medium text-azul hover:underline">Ver tablero</Link>
      </div>
      {res && (res.por_aprobar > 0 || res.vencidas > 0) && (
        <div className="mb-3 flex flex-wrap gap-2">
          {res.por_aprobar > 0 && <Link to="/ordenes" className="rounded-full bg-amarillo-50 px-3.5 py-1.5 text-sm font-medium text-[#7a5000] hover:bg-amarillo/30">{plural(res.por_aprobar, "orden espera", "órdenes esperan")} aprobación</Link>}
          {res.vencidas > 0 && <Link to="/ordenes?ver=tabla&vencidas=1" className="rounded-full bg-rojo-50 px-3.5 py-1.5 text-sm font-medium text-[#a3170f] hover:bg-rojo/15">{plural(res.vencidas, "orden vencida", "órdenes vencidas")}</Link>}
        </div>
      )}
      {orden.length > 0 && <ul className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">{orden.slice(0, 6).map((o) => <li key={o.id}><TarjetaOrden orden={o} onAbrir={() => navigate(`/ordenes/${o.id}`)} /></li>)}</ul>}
    </section>
  );
}

export default function Inicio() {
  const { usuario } = useSesion();
  const [datos, setDatos] = useState(null);
  const [resumen, setResumen] = useState(null);
  const [error, setError] = useState("");
  const mes = mesActual();

  useEffect(() => {
    Promise.all([tablero(mes), miResumen(mes)]).then(([t, r]) => { setDatos(t); setResumen(r); }).catch((e) => setError(e.message));
  }, [mes]);

  if (error) return <Alerta>{error}</Alerta>;
  if (!datos || !resumen) return <Cargando />;

  const eq = datos.equipo;
  const tieneTareas = resumen.tareas.total > 0 || datos.proximas.length > 0;

  return (
    <div className="space-y-6">
      <div className="grid gap-6 lg:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
        {tieneTareas || datos.rol === "colaborador" ? (
          <MiMes resumen={resumen} nombre={usuario.nombre} />
        ) : (
          <section className="rounded-2xl bg-noche p-6 text-white md:p-7">
            <p className="text-white/65 first-letter:uppercase">{nombreMes(mes)}</p>
            <h1 className="mt-1 text-[28px] font-semibold text-white md:text-[32px]">Hola, {primerNombre(usuario.nombre)}</h1>
            {eq && (
              <div className="mt-7">
                <p className="mb-2 text-[15px]"><span className="font-semibold num">{eq.validadas} de {eq.tareas}</span> <span className="text-white/70">tareas del equipo validadas este mes</span></p>
                <TiraMes validadas={eq.validadas} revision={eq.por_validar} vencidas={eq.vencidas} pendientes={eq.en_plazo} oscuro />
                <div className="mt-2"><LeyendaTira oscuro /></div>
              </div>
            )}
          </section>
        )}
        <MuroDeHonor muro={datos.muro} />
      </div>

      <OperacionHoy gestiona={!!usuario.gestiona} />

      {eq && (
        <>
          {eq.por_validar > 0 && (
            <Link to="/validar" className="flex items-center justify-between gap-4 rounded-xl border border-amarillo bg-amarillo-50 px-5 py-4 hover:bg-amarillo/20">
              <span className="flex items-center gap-3 font-medium text-[#5c3d00]">
                <CircleCheckBig className="size-5 shrink-0" />
                {plural(eq.por_validar, "entrega espera", "entregas esperan")} tu validación. Solo cuentan cuando las validas.
              </span>
              <Boton variante="acento" tam="sm" tabIndex={-1}>Revisar</Boton>
            </Link>
          )}

          <section>
            <h2 className="mb-3 text-xl font-semibold">{datos.rol === "administrador" ? "La empresa este mes" : "Tu equipo este mes"}</h2>
            <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
              <Cifra etiqueta="Personas" valor={eq.personas} />
              <Cifra etiqueta="Tareas del mes" valor={eq.tareas} a="/equipo" />
              <Cifra etiqueta="Por validar" valor={eq.por_validar} tono="amarillo" a="/validar" />
              <Cifra etiqueta="Vencidas sin entregar" valor={eq.vencidas} tono="rojo" a="/equipo?vencidas=1" />
            </div>
          </section>

          <div className="grid gap-6 lg:grid-cols-2">
            <Panel titulo="Necesitan atención" cuerpo="p-0">
              {datos.atencion.length === 0 ? (
                <p className="px-5 py-6 text-sm text-gris">Nadie tiene tareas vencidas sin entregar.</p>
              ) : (
                <ul>
                  {datos.atencion.map((a) => (
                    <li key={a.colaborador} className="flex items-center gap-3 border-b border-linea-suave px-5 py-3 last:border-0">
                      <Avatar nombre={a.nombre} tam="sm" />
                      <div className="min-w-0 flex-1"><p className="truncate font-medium">{a.nombre}</p><p className="truncate text-sm text-gris">{a.puesto}</p></div>
                      <Link to={`/equipo?colaborador=${a.colaborador}&vencidas=1`} className="whitespace-nowrap text-sm font-medium text-rojo hover:underline">{plural(a.vencidas, "vencida", "vencidas")}</Link>
                    </li>
                  ))}
                </ul>
              )}
            </Panel>
            <Panel titulo="Mejores puntajes del mes" cuerpo="p-0"
              accion={datos.rol === "administrador" && <Link to="/desempeno" className="text-sm font-medium text-azul hover:underline">Ranking completo</Link>}>
              {datos.top.length === 0 ? (
                <p className="px-5 py-6 text-sm text-gris">Todavía no hay puntajes: aparecen cuando vencen tareas o se validan entregas.</p>
              ) : (
                <ol>
                  {datos.top.map((p, i) => (
                    <li key={p.colaborador_id} className="flex items-center gap-3 border-b border-linea-suave px-5 py-3 last:border-0">
                      <span className={cx("flex size-7 items-center justify-center rounded-full text-sm font-semibold num", i === 0 ? "bg-amarillo text-tinta" : "bg-linea-suave text-gris")}>{i + 1}</span>
                      <div className="min-w-0 flex-1"><p className="truncate font-medium">{p.nombre}</p><p className="truncate text-sm text-gris">{p.puesto}</p></div>
                      <Puntaje valor={p.puntaje_total} className="text-xl" />
                    </li>
                  ))}
                </ol>
              )}
            </Panel>
          </div>

          {datos.departamentos && (
            <Panel titulo="Por departamento" cuerpo="p-0">
              <div className="overflow-x-auto">
                <table className="tabla">
                  <thead><tr><th>Departamento</th><th className="text-right">Personas</th><th className="text-right">Tareas</th><th>Validadas</th><th className="text-right">Vencidas</th><th className="text-right">Puntaje promedio</th></tr></thead>
                  <tbody>
                    {datos.departamentos.map((d) => (
                      <tr key={d.id}>
                        <td className="font-medium">{d.nombre}</td>
                        <td className="text-right num">{d.personas}</td>
                        <td className="text-right num">{d.tareas}</td>
                        <td className="min-w-40">{d.cumplimiento == null ? <span className="text-gris">Sin tareas</span> : (
                          <div className="flex items-center gap-3"><Barra valor={d.cumplimiento} className="w-24" /><span className="text-sm num">{d.cumplimiento}%</span></div>)}</td>
                        <td className={cx("text-right num", d.vencidas > 0 && "font-medium text-rojo")}>{d.vencidas}</td>
                        <td className="text-right"><Puntaje valor={d.puntaje_promedio} /></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {datos.sin_puesto > 0 && (
                <p className="border-t border-linea-suave px-5 py-3 text-sm text-gris">
                  {plural(datos.sin_puesto, "persona no tiene", "personas no tienen")} puesto asignado y no aparece en ningún departamento. <Link to="/personas" className="font-medium text-azul hover:underline">Asignar puesto</Link>
                </p>
              )}
            </Panel>
          )}
        </>
      )}

      {(datos.proximas.length > 0 || datos.rol === "colaborador") && <Proximas tareas={datos.proximas} />}

      {datos.rol === "colaborador" && resumen.kpis_del_puesto.length > 0 && (
        <Panel titulo="Los KPIs de tu puesto">
          <ul className="grid gap-3 sm:grid-cols-2">
            {resumen.kpis_del_puesto.map((k) => {
              const medido = resumen.kpis.find((m) => m.nombre === k.nombre);
              return (
                <li key={k.nombre} className="rounded-lg border border-linea-suave p-4">
                  <p className="font-medium">{k.nombre}</p>
                  <p className="mt-0.5 text-sm text-gris">Meta: {k.meta || "—"} · Peso {k.ponderacion}% · {k.automatico ? "se llena con tus tareas validadas" : "lo anota la administración"}</p>
                  {medido ? <div className="mt-3 flex items-center gap-3"><Barra valor={medido.cumplimiento} /><span className="text-sm font-medium num">{Math.round(medido.cumplimiento)}%</span></div>
                    : <p className="mt-3 text-sm text-gris">Sin resultado este mes todavía.</p>}
                </li>
              );
            })}
          </ul>
        </Panel>
      )}
      {datos.rol !== "colaborador" && !usuario.puesto && (
        <p className="text-sm text-gris"><Trophy className="mr-1 inline size-4" />Tu usuario no tiene puesto, por eso no tienes puntaje propio. Se asigna en Personas.</p>
      )}
    </div>
  );
}
