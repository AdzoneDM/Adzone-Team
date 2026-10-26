// OT Maestra (F-01): Comercial la llena y la entrega a Coordinación. Coordinación la numera al liberarla (G0).
import { useEffect, useState } from "react";
import { ArrowDown, ArrowUp, Calculator, ChevronDown, Plus, Trash2 } from "lucide-react";
import { calcularCompromiso, guardarOrden, listarProyectos } from "@/lib/api";
import { PRIORIDADES_OTM, dinero, fechaCorta, hoyISO, sumarDias } from "@/lib/formato";
import { useRecurso } from "@/lib/recursos";
import { useSesion } from "@/lib/sesion";
import { SelectorCliente, SelectorPersona } from "@/components/Selectores";
import { Alerta, Boton, Campo, Cargando, Modal, cx } from "@/components/ui";
import { Anticipacion, AreaChip, CampoFormato, Checklist } from "./piezas";

const ANTICIPO = "Anticipo confirmado por Administración";

function Seccion({ numero, titulo, ayuda, children }) {
  return (
    <section className="rounded-xl border border-linea p-4">
      <h3 className="mb-0.5 flex items-center gap-2 text-base font-semibold"><span className="flex size-6 items-center justify-center rounded-full bg-noche text-xs text-white num">{numero}</span>{titulo}</h3>
      {ayuda && <p className="mb-3 text-sm text-gris">{ayuda}</p>}
      <div className={cx(!ayuda && "mt-3")}>{children}</div>
    </section>
  );
}

function FilaArea({ fila, i, total, catalogo, tiempos, onCambio, onQuitar, onMover }) {
  const [abierta, setAbierta] = useState(false);
  const area = catalogo.areas.find((a) => a.codigo === fila.area);
  const sugeridos = tiempos.filter((t) => t.area === fila.area);
  const poner = (k) => (v) => onCambio({ ...fila, [k]: v });
  const elegirTrabajo = (trabajo, cantidad) => {
    const t = sugeridos.find((x) => x.trabajo === trabajo);
    if (!t) return onCambio({ ...fila, trabajo: "", cantidad });
    const horas = Number(t.horas || Number(t.dias) * 8) * cantidad;
    // Lo que dura en horas se reparte en días de 8 h; lo que se mide en días se suma por pieza.
    const dias = Math.round((t.horas && Number(t.horas) < 8 ? horas / 8 : Number(t.dias) * cantidad) * 100) / 100;
    onCambio({ ...fila, trabajo, cantidad, horas_estimadas: horas, tiempo_estandar_dias: dias,
      que_produce: fila.que_produce || (cantidad > 1 ? `${cantidad} × ${t.trabajo}` : t.trabajo) });
  };
  return (
    <li className="rounded-xl border border-linea bg-white p-3">
      {sugeridos.length > 0 && (
        <div className="mb-3 grid gap-3 md:grid-cols-[minmax(0,1fr)_110px]">
          <Campo etiqueta="Tipo de trabajo (cronograma de producción)" ayuda="Pone las horas y los días estándar; se pueden ajustar.">{(id) => (
            <select id={id} className="campo" value={fila.trabajo || ""} onChange={(e) => elegirTrabajo(e.target.value, fila.cantidad || 1)}>
              <option value="">Otro / a mano</option>
              {sugeridos.map((t) => <option key={t.id} value={t.trabajo}>{t.trabajo} · {t.referencia || `${Number(t.dias)} d`}</option>)}
            </select>
          )}</Campo>
          <Campo etiqueta="Cantidad">{(id) => <input id={id} type="number" min={1} className="campo" value={fila.cantidad || 1}
            onChange={(e) => elegirTrabajo(fila.trabajo, Math.max(1, Number(e.target.value) || 1))} />}</Campo>
        </div>
      )}
      <div className="grid gap-3 md:grid-cols-[minmax(0,180px)_80px_minmax(0,1fr)_120px_auto]">
        <Campo etiqueta="Área">{(id) => (
          <select id={id} className="campo" value={fila.area || ""} onChange={(e) => onCambio({ ...fila, area: e.target.value, especificacion: {} })}>
            <option value="">Elige…</option>
            {catalogo.areas.map((a) => <option key={a.codigo} value={a.codigo}>{a.codigo} · {a.nombre}</option>)}
          </select>
        )}</Campo>
        <Campo etiqueta="Orden" ayuda="Igual = a la vez">{(id) => <input id={id} type="number" min={1} max={20} className="campo" value={fila.secuencia ?? i + 1} onChange={(e) => poner("secuencia")(e.target.value)} />}</Campo>
        <Campo etiqueta="Qué produce">{(id) => <input id={id} className="campo" value={fila.que_produce || ""} onChange={(e) => poner("que_produce")(e.target.value)} placeholder="Ej.: arte final de 4 lonas" maxLength={255} />}</Campo>
        <Campo etiqueta="Días estándar" ayuda={fila.horas_estimadas ? `${Number(fila.horas_estimadas)} h de trabajo` : undefined}>{(id) => (
          <input id={id} type="number" min={0} step="any" className="campo" value={fila.tiempo_estandar_dias ?? ""} onChange={(e) => poner("tiempo_estandar_dias")(e.target.value)} />
        )}</Campo>
        <div className="flex items-end gap-1">
          <button type="button" aria-label="Subir" disabled={i === 0} onClick={() => onMover(-1)} className="flex size-11 items-center justify-center rounded-lg border border-linea disabled:opacity-30"><ArrowUp className="size-4" /></button>
          <button type="button" aria-label="Bajar" disabled={i === total - 1} onClick={() => onMover(1)} className="flex size-11 items-center justify-center rounded-lg border border-linea disabled:opacity-30"><ArrowDown className="size-4" /></button>
          <button type="button" aria-label="Quitar área" onClick={onQuitar} className="flex size-11 items-center justify-center rounded-lg border border-linea text-rojo"><Trash2 className="size-4" /></button>
        </div>
      </div>
      {area && (
        <div className="mt-2">
          <button type="button" onClick={() => setAbierta(!abierta)} aria-expanded={abierta} className="inline-flex items-center gap-1 text-sm font-medium text-azul">
            <ChevronDown className={cx("size-4 transition", abierta && "rotate-180")} />Especificación de {area.formato} (opcional, la completa el área)
          </button>
          {abierta && (
            <div className="mt-3 grid gap-4 rounded-lg bg-fondo/60 p-3 sm:grid-cols-2">
              {area.especificacion.map((c) => <CampoFormato key={c.clave} campo={c} valor={fila.especificacion?.[c.clave]}
                onCambio={(v) => onCambio({ ...fila, especificacion: { ...(fila.especificacion || {}), [c.clave]: v } })} />)}
            </div>
          )}
        </div>
      )}
    </li>
  );
}

export default function FormOrden({ abierto, onCerrar, inicial, onGuardada }) {
  const { usuario, esFinanzas } = useSesion();
  const [catalogo] = useRecurso("catalogo");
  const [f, setF] = useState({});
  const [proyectos, setProyectos] = useState([]);
  const [calculo, setCalculo] = useState(null);
  const [error, setError] = useState("");
  const [guardando, setGuardando] = useState(false);
  const editando = !!inicial?.id;

  useEffect(() => {
    if (!abierto) return;
    setError(""); setCalculo(null);
    if (editando) {
      setF({ ...inicial, cliente: String(inicial.cliente), proyecto: inicial.proyecto ? String(inicial.proyecto) : "",
        asesor_comercial: inicial.asesor_comercial ? String(inicial.asesor_comercial) : "", plan_areas: inicial.plan_areas?.length ? inicial.plan_areas : [{}],
        g0: { ...inicial.g0 }, monto: inicial.monto ?? "", anticipo_requerido: inicial.anticipo_requerido ?? "" });
    } else {
      setF({ titulo: "", descripcion: "", exclusiones: "", cliente: inicial?.cliente ? String(inicial.cliente) : "", proyecto: inicial?.proyecto ? String(inicial.proyecto) : "",
        contacto: "", telefono: "", correo: "", direccion_entrega: "", tipo_cliente: "RECURRENTE", asesor_comercial: String(usuario.id),
        numero_cotizacion: "", prioridad: "N", rondas_incluidas: 2, fecha_requerida: sumarDias(hoyISO(), 7), monto: "", anticipo_requerido: "",
        plan_areas: [{ area: "", secuencia: 1, que_produce: "" }], g0: {} });
    }
  }, [abierto, inicial, editando, usuario]);

  useEffect(() => {
    if (!f.cliente) { setProyectos([]); return; }
    listarProyectos({ cliente: f.cliente, activos: 1 }).then(setProyectos).catch(() => setProyectos([]));
  }, [f.cliente]);

  const poner = (k) => (e) => setF({ ...f, [k]: e?.target ? e.target.value : e });
  const plan = f.plan_areas || [];
  const ponerPlan = (lista) => { setF({ ...f, plan_areas: lista }); setCalculo(null); };
  const filasValidas = () => plan.filter((p) => p.area).map((p, i) => ({ ...p, secuencia: Number(p.secuencia || i + 1),
    tiempo_estandar_dias: p.tiempo_estandar_dias === "" || p.tiempo_estandar_dias == null ? undefined : Number(p.tiempo_estandar_dias),
    horas_estimadas: p.horas_estimadas === "" || p.horas_estimadas == null ? undefined : Number(p.horas_estimadas) }));

  const calcular = async () => {
    setError("");
    try { setCalculo(await calcularCompromiso({ plan_areas: filasValidas(), prioridad: f.prioridad, rondas_incluidas: f.rondas_incluidas, fecha_requerida: f.fecha_requerida || null })); }
    catch (e) { setError(e.message); }
  };

  const guardar = async (e) => {
    e.preventDefault();
    setError("");
    if (!f.titulo?.trim()) return setError("Escribe el nombre del proyecto o trabajo.");
    if (!f.cliente) return setError("Elige el cliente (para trabajos internos, «ADZONE Digital Marketing»).");
    const filas = filasValidas();
    if (!filas.length) return setError("Agrega al menos un área (sección 3).");
    if (filas.some((x) => !x.que_produce?.trim())) return setError("Anota qué produce cada área.");
    setGuardando(true);
    try {
      const datos = {
        id: f.id, titulo: f.titulo.trim(), descripcion: f.descripcion || "", exclusiones: f.exclusiones || "", cliente: Number(f.cliente),
        proyecto: f.proyecto ? Number(f.proyecto) : null, contacto: f.contacto || "", telefono: f.telefono || "", correo: f.correo || "",
        direccion_entrega: f.direccion_entrega || "", tipo_cliente: f.tipo_cliente, asesor_comercial: f.asesor_comercial ? Number(f.asesor_comercial) : null,
        numero_cotizacion: f.numero_cotizacion || "", prioridad: f.prioridad, rondas_incluidas: Number(f.rondas_incluidas) || 2,
        fecha_requerida: f.fecha_requerida || null, plan_areas: filas, g0: f.g0 || {},
        monto: f.monto === "" ? null : f.monto, anticipo_requerido: f.anticipo_requerido === "" ? null : f.anticipo_requerido,
      };
      const o = await guardarOrden(datos);
      onGuardada(o, editando);
    } catch (err) { setError(err.message); }
    setGuardando(false);
  };

  const g0Items = (catalogo?.g0 || []).map((x) => x.texto);
  const despuesDeLiberar = editando && !["SOLICITADA", "DEVUELTA"].includes(inicial.estado);
  return (
    <Modal abierto={abierto} onCerrar={onCerrar} ancho="md:max-w-4xl" titulo={editando ? `Editar ${inicial.codigo}` : "Nueva OT Maestra (F-01)"}
      descripcion={editando ? inicial.titulo : "Comercial la entrega completa a Coordinación de Producción, que la revisa (G0) y le asigna el número."}
      pie={<><Boton variante="secundario" onClick={onCerrar}>Cancelar</Boton>
        <Boton type="submit" form="form-orden" cargando={guardando}>{editando ? "Guardar cambios" : "Entregar a Coordinación"}</Boton></>}>
      {!catalogo ? <Cargando /> : (
        <form id="form-orden" onSubmit={guardar} className="space-y-4">
          {error && <Alerta>{error}</Alerta>}
          <Seccion numero="1" titulo="Datos del cliente">
            <div className="grid gap-4 sm:grid-cols-2">
              <SelectorCliente valor={f.cliente} onCambio={(v) => setF({ ...f, cliente: v, proyecto: "" })} />
              <Campo etiqueta="Tipo de cliente">{(id) => (
                <select id={id} className="campo" value={f.tipo_cliente || "RECURRENTE"} onChange={poner("tipo_cliente")}>
                  {catalogo.tipos_cliente.map((t) => <option key={t.valor} value={t.valor}>{t.nombre}</option>)}
                </select>
              )}</Campo>
              <Campo etiqueta="Persona de contacto">{(id) => <input id={id} className="campo" value={f.contacto || ""} onChange={poner("contacto")} maxLength={150} />}</Campo>
              <Campo etiqueta="Teléfono / WhatsApp">{(id) => <input id={id} className="campo" inputMode="tel" value={f.telefono || ""} onChange={poner("telefono")} maxLength={40} />}</Campo>
              <Campo etiqueta="Correo (opcional)">{(id) => <input id={id} type="email" className="campo" value={f.correo || ""} onChange={poner("correo")} />}</Campo>
              <Campo etiqueta="Dirección de entrega / instalación">{(id) => <input id={id} className="campo" value={f.direccion_entrega || ""} onChange={poner("direccion_entrega")} maxLength={255} />}</Campo>
              <SelectorPersona etiqueta="Asesor comercial" valor={f.asesor_comercial} onCambio={(v) => setF({ ...f, asesor_comercial: v })} />
              <Campo etiqueta="Proyecto (opcional)">{(id) => (
                <select id={id} className="campo" value={f.proyecto || ""} onChange={poner("proyecto")} disabled={!proyectos.length}>
                  <option value="">{f.cliente && !proyectos.length ? "Sin proyectos activos" : "Ninguno"}</option>
                  {proyectos.map((p) => <option key={p.id} value={p.id}>{p.codigo} · {p.nombre}</option>)}
                </select>
              )}</Campo>
            </div>
          </Seccion>

          <Seccion numero="2" titulo="Alcance del trabajo" ayuda="Descripción, cantidades, piezas y resultado esperado. Lo que no está aquí no está incluido.">
            <div className="grid gap-4">
              <Campo etiqueta="Nombre del proyecto / trabajo">{(id) => <input id={id} className="campo" value={f.titulo || ""} onChange={poner("titulo")} maxLength={200} placeholder="Ej.: Lonas 3×2 del Torneo Superior" />}</Campo>
              <Campo etiqueta="Alcance">{(id) => <textarea id={id} rows={4} className="campo" value={f.descripcion || ""} onChange={poner("descripcion")} />}</Campo>
              <Campo etiqueta="Exclusiones (opcional)" ayuda="Lo que NO incluye: evita discusiones en la entrega.">{(id) => <textarea id={id} rows={2} className="campo" value={f.exclusiones || ""} onChange={poner("exclusiones")} />}</Campo>
            </div>
          </Seccion>

          <Seccion numero="3" titulo="Áreas que intervienen y secuencia" ayuda="En el orden en que trabajan. Las que tienen el mismo número van a la vez. Coordinación emite una Orden de Área por cada fila.">
            {despuesDeLiberar ? (
              <div className="flex flex-wrap gap-1.5">{plan.map((p, i) => <AreaChip key={i} area={p.area} />)}<p className="w-full text-sm text-gris">Ya liberada: las áreas se agregan desde la OT («Agregar área»).</p></div>
            ) : (
              <>
                <ol className="space-y-3">
                  {plan.map((fila, i) => (
                    <FilaArea key={i} fila={fila} i={i} total={plan.length} catalogo={catalogo} tiempos={catalogo.tiempos || []}
                      onCambio={(nueva) => ponerPlan(plan.map((x, j) => (j === i ? nueva : x)))}
                      onQuitar={() => ponerPlan(plan.filter((_, j) => j !== i))}
                      onMover={(d) => { const l = [...plan]; [l[i], l[i + d]] = [l[i + d], l[i]]; ponerPlan(l); }} />
                  ))}
                </ol>
                <Boton variante="secundario" tam="sm" icono={Plus} className="mt-3" onClick={() => ponerPlan([...plan, { area: "", secuencia: (Number(plan.at(-1)?.secuencia) || plan.length) + 1, que_produce: "" }])}>Agregar área</Boton>
              </>
            )}
          </Seccion>

          <Seccion numero="4" titulo="Fechas y prioridad" ayuda="Fecha comprometida = tiempo estándar + cola del área + aprobación del cliente (24 h × rondas) + colchón (20 %, emergencia 30 %).">
            <div className="grid gap-4 sm:grid-cols-4">
              <Campo etiqueta="Fecha que pide el cliente">{(id) => <input id={id} type="date" className="campo" value={f.fecha_requerida || ""} onChange={poner("fecha_requerida")} />}</Campo>
              <Campo etiqueta="Prioridad">{(id) => (
                <select id={id} className="campo" value={f.prioridad || "N"} onChange={(e) => { setF({ ...f, prioridad: e.target.value }); setCalculo(null); }}>
                  {Object.entries(PRIORIDADES_OTM).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
                </select>
              )}</Campo>
              <Campo etiqueta="Rondas de cambios incluidas">{(id) => <input id={id} type="number" min={0} max={10} className="campo" value={f.rondas_incluidas ?? 2} onChange={poner("rondas_incluidas")} />}</Campo>
              <div className="flex items-end"><Boton variante="secundario" icono={Calculator} onClick={calcular} className="w-full">Calcular</Boton></div>
            </div>
            {calculo && (
              <div className={cx("mt-3 rounded-lg p-3 text-sm", f.fecha_requerida && calculo.fecha_compromiso > f.fecha_requerida ? "bg-amarillo-50" : "bg-verde-50")}>
                <p className="font-semibold">Fecha comprometida sugerida: {fechaCorta(calculo.fecha_compromiso)} <span className="font-normal text-gris">({Number(calculo.dias_habiles)} días hábiles)</span></p>
                <p className="text-gris">Estándar {Number(calculo.tiempo_estandar_dias)} d · cola {Number(calculo.cola_dias)} d · aprobación {Number(calculo.aprobacion_dias)} d · colchón {calculo.colchon_pct} %</p>
                {Number(calculo.horas_estimadas) > 0 && <p className="text-gris">{Number(calculo.horas_estimadas)} horas de trabajo según el cronograma de producción</p>}
                {f.fecha_requerida && calculo.fecha_compromiso > f.fecha_requerida && <p className="mt-1 font-medium text-[#7a5000]">El cliente la pide antes: negocia la fecha o súbele la prioridad.</p>}
                {calculo.anticipacion && <Anticipacion a={calculo.anticipacion} className="mt-2" />}
              </div>
            )}
          </Seccion>

          <Seccion numero="5" titulo="Cotización y dinero">
            <div className="grid gap-4 sm:grid-cols-3">
              <Campo etiqueta="No. de cotización">{(id) => <input id={id} className="campo" value={f.numero_cotizacion || ""} onChange={poner("numero_cotizacion")} maxLength={40} placeholder="COT-…" />}</Campo>
              <Campo etiqueta="Monto total RD$ (sin ITBIS)">{(id) => <input id={id} type="number" min={0} step="any" className="campo" value={f.monto ?? ""} onChange={poner("monto")} />}</Campo>
              <Campo etiqueta="Anticipo requerido RD$" ayuda={f.monto ? `50 % = ${dinero(Number(f.monto) / 2)}` : ""}>{(id) => <input id={id} type="number" min={0} step="any" className="campo" value={f.anticipo_requerido ?? ""} onChange={poner("anticipo_requerido")} />}</Campo>
            </div>
          </Seccion>

          {!despuesDeLiberar && (
            <Seccion numero="G0" titulo="Compuerta de apertura" ayuda="Coordinación no numera la OT si falta una casilla. El anticipo lo confirma Administración (o se marca solo al leer el pago en Cashflow).">
              <Checklist items={g0Items} valor={f.g0 || {}} onCambio={(v) => setF({ ...f, g0: esFinanzas ? v : { ...v, [ANTICIPO]: !!f.g0?.[ANTICIPO] } })} />
            </Seccion>
          )}
        </form>
      )}
    </Modal>
  );
}
