import { useCallback, useEffect, useMemo, useState } from "react";
import { Pencil, Plus, Search, Target, Trash2 } from "lucide-react";
import { eliminarPlantilla, guardarPlantilla, plantillas as cargar } from "@/lib/api";
import { Alerta, Boton, Cabecera, Campo, Cargando, Insignia, Modal, Panel, Vacio, useAviso, useConfirmar } from "@/components/ui";

export default function PlantillasKpi() {
  const avisar = useAviso();
  const confirmar = useConfirmar();
  const [lista, setLista] = useState(null);
  const [error, setError] = useState("");
  const [buscar, setBuscar] = useState("");
  const [form, setForm] = useState(null);
  const [errorForm, setErrorForm] = useState("");
  const [guardando, setGuardando] = useState(false);

  const recargar = useCallback(() => { cargar().then(setLista).catch((e) => setError(e.message)); }, []);
  useEffect(() => { recargar(); }, [recargar]);
  const filtrada = useMemo(() => (lista || []).filter((p) => !buscar || p.nombre.toLowerCase().includes(buscar.toLowerCase())), [lista, buscar]);

  const guardar = async (e) => {
    e.preventDefault();
    setErrorForm("");
    if (!form.nombre?.trim()) return setErrorForm("Escribe qué mide el KPI.");
    setGuardando(true);
    try {
      await guardarPlantilla({ id: form.id, nombre: form.nombre.trim(), descripcion: form.descripcion || "", unidad_medida: form.unidad_medida || "", menor_es_mejor: !!form.menor_es_mejor });
      avisar(form.id ? "Plantilla actualizada." : "Plantilla creada. Ahora asígnala a los puestos que la usan.");
      setForm(null);
      recargar();
    } catch (err) { setErrorForm(err.message); }
    setGuardando(false);
  };

  if (error) return <Alerta>{error}</Alerta>;
  if (!lista) return <Cargando />;
  return (
    <div>
      <Cabecera titulo="Plantillas de KPI" descripcion="Cada KPI se define una vez aquí y después se asigna a uno o varios puestos, con su meta y su peso.">
        <Boton icono={Plus} onClick={() => { setForm({ nombre: "", descripcion: "", unidad_medida: "", menor_es_mejor: false }); setErrorForm(""); }}>Nueva plantilla</Boton>
      </Cabecera>
      <div className="relative mb-4 max-w-sm">
        <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-gris" />
        <input className="campo h-11 pl-9" placeholder="Buscar KPI" value={buscar} onChange={(e) => setBuscar(e.target.value)} aria-label="Buscar KPI" />
      </div>
      {filtrada.length === 0 ? <Vacio icono={Target} titulo="No hay plantillas">Ejemplos: «Contenidos programados», «Rondas de revisión por proyecto», «Tasa de conversión web».</Vacio> : (
        <Panel cuerpo="p-0">
          <div className="overflow-x-auto">
            <table className="tabla">
              <thead><tr><th>KPI</th><th>Unidad</th><th>Sentido</th><th className="text-right">Puestos</th><th className="w-24"><span className="sr-only">Acciones</span></th></tr></thead>
              <tbody>
                {filtrada.map((p) => (
                  <tr key={p.id}>
                    <td className="max-w-xl"><p className="font-medium">{p.nombre}</p>{p.descripcion && <p className="text-sm text-gris">{p.descripcion}</p>}</td>
                    <td className="text-sm">{p.unidad_medida || "—"}</td>
                    <td>{p.menor_es_mejor ? <Insignia tono="azul">Más bajo es mejor</Insignia> : <Insignia>Más alto es mejor</Insignia>}</td>
                    <td className="text-right num">{p.puestos_asignados}</td>
                    <td className="whitespace-nowrap text-right">
                      <Boton variante="fantasma" tam="sm" icono={Pencil} aria-label={`Editar ${p.nombre}`} onClick={() => { setForm(p); setErrorForm(""); }} />
                      <Boton variante="fantasma" tam="sm" icono={Trash2} aria-label={`Borrar ${p.nombre}`} className="text-rojo" onClick={async () => {
                        if (!(await confirmar({ titulo: "¿Borrar esta plantilla?", mensaje: p.puestos_asignados ? "Está asignada a puestos: primero quítala de ellos." : "No está asignada a ningún puesto.", boton: "Borrar", peligro: true }))) return;
                        try { await eliminarPlantilla(p.id); avisar("Plantilla borrada."); recargar(); } catch (e) { avisar(e.message, "rojo"); }
                      }} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Panel>
      )}
      <Modal abierto={!!form} onCerrar={() => setForm(null)} titulo={form?.id ? "Editar plantilla" : "Nueva plantilla de KPI"} ancho="md:max-w-xl"
        pie={<><Boton variante="secundario" onClick={() => setForm(null)}>Cancelar</Boton><Boton type="submit" form="form-plantilla" cargando={guardando}>{form?.id ? "Guardar" : "Crear"}</Boton></>}>
        {form && (
          <form id="form-plantilla" onSubmit={guardar} className="space-y-4">
            {errorForm && <Alerta>{errorForm}</Alerta>}
            <Campo etiqueta="Qué mide">{(id) => <input id={id} className="campo" value={form.nombre} onChange={(e) => setForm({ ...form, nombre: e.target.value })} maxLength={255} autoFocus />}</Campo>
            <Campo etiqueta="Descripción (opcional)">{(id) => <textarea id={id} className="campo" rows={3} value={form.descripcion || ""} onChange={(e) => setForm({ ...form, descripcion: e.target.value })} />}</Campo>
            <Campo etiqueta="Unidad" ayuda="Publicaciones, %, horas, RD$, rondas…">{(id) => <input id={id} className="campo" value={form.unidad_medida || ""} onChange={(e) => setForm({ ...form, unidad_medida: e.target.value })} maxLength={50} />}</Campo>
            <label className="flex items-start gap-2.5 rounded-lg border border-linea p-3 text-[15px]">
              <input type="checkbox" checked={!!form.menor_es_mejor} onChange={(e) => setForm({ ...form, menor_es_mejor: e.target.checked })} className="mt-1 accent-azul" />
              <span>Más bajo es mejor<span className="block text-sm text-gris">Para rondas de revisión, errores, quejas o tiempos de respuesta.</span></span>
            </label>
          </form>
        )}
      </Modal>
    </div>
  );
}
