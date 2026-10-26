// Formatos ADZONE para imprimir o guardar en PDF, llenos con lo registrado: F-01 (OT Maestra), F-02 a F-10 (Orden de Área) y F-12 (Acta).
import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { Printer } from "lucide-react";
import { areaCompleta, obtenerActa, ordenCompleta } from "@/lib/api";
import { EMPRESA } from "@/lib/empresa";
import { dinero, fechaCorta, fechaHora } from "@/lib/formato";
import { useRecurso } from "@/lib/recursos";
import Marca from "@/components/Marca";
import { Alerta, Boton, Cargando } from "@/components/ui";
import { valorCampo } from "./piezas";

const Caja = ({ si }) => <span className="mr-1.5 inline-block w-3.5 text-center font-semibold">{si ? "☑" : "☐"}</span>;

function Hoja({ codigo, titulo, numero, children }) {
  return (
    <div className="min-h-dvh bg-fondo py-6 print:bg-white print:py-0">
      <div className="mx-auto mb-4 flex max-w-[210mm] justify-end px-4 print:hidden"><Boton icono={Printer} onClick={() => window.print()}>Imprimir o guardar PDF</Boton></div>
      <article className="mx-auto max-w-[210mm] bg-white p-9 text-[12px] leading-snug text-tinta shadow-sm print:max-w-none print:p-0 print:shadow-none">
        <header className="mb-4 flex items-start justify-between gap-6 border-b-4 border-amarillo pb-3">
          <div><Marca oscuro={false} className="text-lg" /><p className="mt-1 text-gris">{EMPRESA.nombre}</p></div>
          <div className="text-right"><p className="text-xs font-semibold text-gris">{codigo}</p><p className="font-display text-xl font-semibold text-noche">{titulo}</p><p className="text-base font-semibold num">{numero}</p></div>
        </header>
        {children}
        <p className="mt-6 border-t border-linea pt-2 text-[10px] text-gris">Generado en Adzone Team el {fechaHora(new Date().toISOString())}. Las casillas y firmas reflejan lo registrado en la plataforma.</p>
      </article>
    </div>
  );
}

function Seccion({ titulo, children }) {
  return <section className="mb-4 break-inside-avoid"><h2 className="mb-1.5 bg-noche px-2 py-1 text-[12px] font-semibold uppercase tracking-wide text-white">{titulo}</h2>{children}</section>;
}

function Tabla({ filas }) {
  return (
    <table className="w-full border-collapse">
      <tbody>{filas.filter(Boolean).map(([k, v], i) => (
        <tr key={i} className="border-b border-linea-suave"><th className="w-[34%] py-1 pr-2 text-left align-top font-medium text-gris">{k}</th><td className="whitespace-pre-line py-1">{v || "—"}</td></tr>
      ))}</tbody>
    </table>
  );
}

function Lista({ items, marcados = {} }) {
  return <ul className="grid gap-x-4 sm:grid-cols-2 print:grid-cols-2">{items.map((t) => <li key={t} className="py-0.5"><Caja si={marcados[t]} />{t}</li>)}</ul>;
}

function Firmas({ nombres }) {
  return (
    <div className="mt-6 grid grid-cols-2 gap-x-10 gap-y-8 md:grid-cols-4 print:grid-cols-4">
      {nombres.map(([rol, quien], i) => (
        <div key={i} className="text-center"><div className="flex h-10 items-end justify-center border-b border-tinta pb-1 text-[11px]">{quien}</div><p className="mt-1 text-[11px] text-gris">{rol}</p></div>
      ))}
    </div>
  );
}

function F01({ d, catalogo }) {
  const o = d.orden;
  const areas = d.areas.length ? d.areas : o.plan_areas;
  return (
    <Hoja codigo="F-01" titulo="OT Maestra" numero={o.numero || `Solicitud ${o.solicitud}`}>
      <Tabla filas={[["Fecha de solicitud", fechaCorta(o.fecha_creacion)], ["Fecha requerida", o.fecha_requerida && fechaCorta(o.fecha_requerida)], ["No. cotización", o.numero_cotizacion],
        ["Monto total", o.monto != null && dinero(o.monto)], ["Prioridad", o.prioridad_nombre]]} />
      <Seccion titulo="1 · Datos del cliente">
        <Tabla filas={[["Empresa / RNC", `${o.cliente_nombre}${o.cliente_rnc ? ` · ${o.cliente_rnc}` : ""}`], ["Contacto", [o.contacto, o.telefono, o.correo].filter(Boolean).join(" · ")],
          ["Dirección de entrega / instalación", o.direccion_entrega], ["Nombre del proyecto", o.titulo], ["Asesor comercial", o.asesor_comercial_nombre], ["Tipo de cliente", o.tipo_cliente_nombre]]} />
      </Seccion>
      <Seccion titulo="2 · Alcance"><p className="whitespace-pre-line">{o.descripcion}</p>{o.exclusiones && <p className="mt-1"><span className="font-medium">Exclusiones:</span> {o.exclusiones}</p>}</Seccion>
      <Seccion titulo="3 · Áreas que intervienen y secuencia">
        <table className="w-full border-collapse text-left"><thead><tr className="border-b border-tinta"><th className="py-1">Orden</th><th>Área</th><th>Qué produce</th><th>Entrega interna</th><th>Responsable</th></tr></thead>
          <tbody>{areas.map((a, i) => <tr key={i} className="border-b border-linea-suave"><td className="py-1 num">{a.secuencia}</td><td>{a.area}</td><td>{a.que_produce}</td><td>{a.fecha_entrega_interna ? fechaCorta(a.fecha_entrega_interna) : ""}</td><td>{a.responsable_nombre || ""}</td></tr>)}</tbody></table>
      </Seccion>
      <Seccion titulo="4 · Cálculo de la fecha comprometida">
        <Tabla filas={[["Tiempo estándar", o.tiempo_estandar_dias != null && `${Number(o.tiempo_estandar_dias)} días`], ["Cola del área", o.cola_dias != null && `${Number(o.cola_dias)} días`],
          ["Aprobación del cliente", o.aprobacion_dias != null && `${Number(o.aprobacion_dias)} días (24 h × ${o.rondas_incluidas} rondas)`], ["Colchón", o.colchon_pct != null && `${o.colchon_pct} %`],
          ["Fecha comprometida", o.fecha_compromiso && fechaCorta(o.fecha_compromiso)], ["Rondas de cambios incluidas", o.rondas_incluidas]]} />
      </Seccion>
      <Seccion titulo="G0 · Compuerta de apertura"><Lista items={(catalogo?.g0 || []).map((x) => x.texto)} marcados={o.g0} />
        {o.excepcion_g0_por_nombre && <p className="mt-1">Excepción sin anticipo: {o.excepcion_g0_por_nombre} · {o.excepcion_g0_motivo}</p>}
        <Firmas nombres={[["Entrega (Comercial)", o.solicitada_por_nombre], ["Recibe (Coordinación)", o.aprobada_por_nombre || ""]]} /></Seccion>
      <Seccion titulo="Cierre G6 (Administración)">
        <Tabla filas={[["Fecha de entrega real", o.fecha_entrega && fechaCorta(o.fecha_entrega)], ["Acta firmada", d.actas.find((a) => a.firmada)?.numero], ["Factura(s)", (d.facturas || []).map((f) => `${f.numero}${f.ncf ? ` · ${f.ncf}` : ""}`).join(", ")],
          ["Costo real", o.costo_real != null && dinero(o.costo_real)], ["Margen vs cotizado", o.costo_real != null && o.monto != null && dinero(o.monto - o.costo_real)], ["Estado", o.estado_nombre]]} />
        <Firmas nombres={[["Comercial", o.asesor_comercial_nombre], ["Coordinación", o.responsable_nombre || ""], ["Administración", ""], ["Gerencia", ""]]} />
      </Seccion>
    </Hoja>
  );
}

function FOA({ d, catalogo }) {
  const { oa, formato, orden } = d;
  return (
    <Hoja codigo={oa.formato.formato} titulo={`Orden de Área · ${oa.area_nombre}`} numero={oa.numero}>
      <Tabla filas={[["OT Maestra", `${orden.codigo} · ${orden.titulo}`], ["Cliente", orden.cliente_nombre], ["Qué produce", oa.que_produce], ["Entrega interna", oa.fecha_entrega_interna && fechaCorta(oa.fecha_entrega_interna)],
        ["Ejecutor", oa.responsable_nombre], ["Prioridad", orden.prioridad_nombre]]} />
      <Seccion titulo="G1 · Compuerta de entrada"><Lista items={formato.g1} marcados={oa.g1} />{oa.g1_rechazo && <p className="mt-1">Rechazo: {oa.g1_rechazo}</p>}
        <Firmas nombres={[["Entrega (Coordinación)", oa.g1_entrega_por_nombre || ""], ["Recibe (área)", oa.g1_recibe_por_nombre || ""]]} /></Seccion>
      <Seccion titulo="Especificación"><Tabla filas={formato.especificacion.map((c) => [c.etiqueta, valorCampo(c, oa.especificacion?.[c.clave])])} /></Seccion>
      {oa.requiere_g4 && <Seccion titulo="G4 · Aprobación del cliente">
        <p>{(catalogo?.g4_canales || []).map((c) => <span key={c} className="mr-4"><Caja si={oa.g4_canales.includes(c)} />{c}</span>)}</p>
        <Tabla filas={[["Aprobó", oa.g4_aprobado_por], ["Fecha", oa.g4_fecha && fechaHora(oa.g4_fecha)], ["Versión", oa.g4_version], ["Ronda", oa.g4_ronda], ["Con cambios", oa.g4_con_cambios ? "Sí" : "No"]]} />
        {oa.formato.nota_g4 && <p className="mt-1 font-medium">{oa.formato.nota_g4}</p>}</Seccion>}
      <Seccion titulo="Seguimiento de etapas"><ol className="list-decimal pl-5">{formato.etapas.map((e) => <li key={e}>{e}</li>)}</ol></Seccion>
      <Seccion titulo="G3 · Control de calidad interno"><Lista items={formato.g3} marcados={oa.g3} />
        <Tabla filas={[["Resultado", oa.g3_resultado], ["Observaciones", oa.g3_observaciones], ["Supervisor", oa.g3_supervisor_nombre]]} /></Seccion>
      <Seccion titulo="G2 / G5 · Compuerta de salida"><Lista items={formato.g2} marcados={oa.g2} />
        {d.traspasos.filter((t) => ["G2", "G5"].includes(t.compuerta)).map((t) => <p key={t.id}>{t.numero} · {t.entrega_area} → {t.recibe_area} · {t.resultado_nombre} · {t.entrega_por_nombre}{t.recibe_por_nombre && ` / ${t.recibe_por_nombre}`}</p>)}</Seccion>
      <Seccion titulo="Incidencias y tiempos muertos">{d.incidencias.length ? <ul>{d.incidencias.map((i) => <li key={i.id}>{fechaCorta(i.fecha)} · {i.descripcion} · {i.minutos_perdidos} min{i.resolucion && ` · ${i.resolucion}`}</li>)}</ul> : <p className="text-gris">Ninguna.</p>}</Seccion>
      <Firmas nombres={[["Ejecutor", oa.responsable_nombre || ""], ["Supervisor", oa.g3_supervisor_nombre || ""], ["Coordinación", ""], ["Cliente", oa.g4_aprobado_por || ""]]} />
    </Hoja>
  );
}

function F12({ acta, d, catalogo }) {
  const o = d.orden;
  const firmaCliente = d.firmas.find((f) => f.contexto === "ACTA" && f.rol === "Cliente");
  return (
    <Hoja codigo="F-12" titulo={`Acta de ${acta.modalidad_nombre.toLowerCase()}`} numero={acta.numero}>
      <Tabla filas={[["OT", `${o.codigo} · ${o.titulo}`], ["Cliente", o.cliente_nombre], ["Fecha", fechaCorta(acta.fecha)], ["Dirección", acta.direccion], ["Contacto en sitio", acta.contacto_sitio]]} />
      <Seccion titulo="G5 · Liberación de salida"><Lista items={(catalogo?.g5_acta || []).map((x) => x.texto)} marcados={acta.g5} />
        <p className="mt-1">Liberada por {acta.liberada_por_nombre || "—"}{acta.saldo_al_liberar != null && ` · saldo al liberar ${dinero(acta.saldo_al_liberar)}`}</p></Seccion>
      <Seccion titulo="Detalle entregado">
        <table className="w-full border-collapse text-left"><thead><tr className="border-b border-tinta"><th className="py-1">Descripción</th><th>Cantidad</th><th>Observación</th></tr></thead>
          <tbody>{acta.items.map((i, k) => <tr key={k} className="border-b border-linea-suave"><td className="py-1">{i.descripcion}</td><td>{i.cantidad}</td><td>{i.observacion}</td></tr>)}</tbody></table></Seccion>
      <Seccion titulo="Verificación en sitio"><Lista items={catalogo?.verificacion_sitio || []} marcados={acta.verificacion} />
        <Tabla filas={[["Hallazgos / pendientes", acta.hallazgos], ["Material devuelto", acta.material_devuelto]]} /></Seccion>
      <Seccion titulo="Conformidad y garantía">
        <Tabla filas={[["Conformidad", acta.conformidad_nombre], ["Observaciones del cliente", acta.observaciones_cliente], ["Garantía", acta.garantia],
          ["Instrucciones de mantenimiento", acta.instrucciones_mantenimiento ? "Entregadas" : "—"], ["Próxima revisión", acta.proxima_revision && fechaCorta(acta.proxima_revision)]]} />
      </Seccion>
      <div className="mt-6 grid grid-cols-2 gap-10">
        <div className="text-center">{firmaCliente?.imagen ? <img src={firmaCliente.imagen} alt="Firma del cliente" className="mx-auto h-14" /> : <div className="h-14" />}
          <div className="border-t border-tinta pt-1 text-[11px]">{firmaCliente ? `${firmaCliente.nombre}${firmaCliente.documento ? ` · ${firmaCliente.documento}` : ""}` : ""}</div><p className="text-[11px] text-gris">Recibe conforme (cliente)</p></div>
        <div className="text-center"><div className="h-14" /><div className="border-t border-tinta pt-1 text-[11px]">{acta.supervisor_nombre || ""}</div><p className="text-[11px] text-gris">Supervisor de entrega / instalación</p></div>
      </div>
      <p className="mt-4 text-[11px] font-medium">Sin acta firmada no se cierra la OT ni se factura.</p>
    </Hoja>
  );
}

export default function ImprimirFormato({ tipo }) {
  const { id } = useParams();
  const [catalogo] = useRecurso("catalogo");
  const [d, setD] = useState(null);
  const [acta, setActa] = useState(null);
  const [error, setError] = useState("");
  useEffect(() => {
    if (tipo === "ot") ordenCompleta(id).then(setD).catch((e) => setError(e.message));
    if (tipo === "oa") areaCompleta(id).then(setD).catch((e) => setError(e.message));
    if (tipo === "acta") obtenerActa(id).then((a) => { setActa(a); return ordenCompleta(a.orden); }).then(setD).catch((e) => setError(e.message));
  }, [tipo, id]);
  useEffect(() => {
    if (!d) return;
    document.title = tipo === "oa" ? `${d.oa.numero} · ${d.oa.formato.formato}` : tipo === "acta" ? `${acta?.numero} · F-12` : `${d.orden.codigo} · F-01`;
  }, [d, tipo, acta]);
  if (error) return <div className="p-6"><Alerta>{error}</Alerta></div>;
  if (!d || !catalogo) return <Cargando />;
  if (tipo === "oa") return <FOA d={d} catalogo={catalogo} />;
  if (tipo === "acta") return <F12 acta={acta} d={d} catalogo={catalogo} />;
  return <F01 d={d} catalogo={catalogo} />;
}
