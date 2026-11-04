// Asistencia → Horarios → Lugares de marcaje: la oficina (con su pantalla de QR) y otros sitios, con su ubicación y radio.
import { useCallback, useEffect, useState } from "react";
import { Copy, Crosshair, MapPin, Plus, RefreshCw, Trash2 } from "lucide-react";
import { borrarSitio, guardarSitio, miIp, nuevaClaveSitio, sitiosMarcaje } from "@/lib/api";
import { obtenerUbicacion } from "@/lib/ubicacion";
import { Alerta, Boton, Campo, Modal, Panel, Vacio, useAviso, useConfirmar } from "@/components/ui";

export default function Lugares() {
  const avisar = useAviso();
  const confirmar = useConfirmar();
  const [lista, setLista] = useState([]);
  const [f, setF] = useState(null);
  const [error, setError] = useState("");
  const cargar = useCallback(() => sitiosMarcaje().then((l) => setLista(l.results || l)).catch(() => {}), []);
  useEffect(() => { cargar(); }, [cargar]);
  const enlace = (s) => `${window.location.origin}/pantalla-qr/${s.clave_pantalla}`;
  const copiar = async (s) => { try { await navigator.clipboard.writeText(enlace(s)); avisar("Enlace de la pantalla copiado"); } catch { avisar(enlace(s)); } };
  const aqui = async () => {
    const u = await obtenerUbicacion();
    if (!u) return setError("No se pudo leer la ubicación. Permite la ubicación en el navegador.");
    setF({ ...f, latitud: u.latitud.toFixed(6), longitud: u.longitud.toFixed(6) });
  };
  const guardar = async (e) => {
    e.preventDefault(); setError("");
    try { await guardarSitio({ ...f, latitud: f.latitud || null, longitud: f.longitud || null }); setF(null); cargar(); } catch (er) { setError(er.message); }
  };
  return (
    <Panel titulo="Lugares de marcaje" cuerpo="p-0" accion={<Boton tam="sm" icono={Plus} onClick={() => { setError(""); setF({ nombre: "", latitud: "", longitud: "", radio_m: 150, redes: "", activo: true }); }}>Lugar</Boton>}>
      <p className="px-5 pt-4 text-sm text-gris">Quien marca «en la oficina» lo hace escaneando el QR de la pantalla de la recepción, o estando dentro del radio del lugar según su celular. Abre el enlace de la pantalla en una tablet o un monitor de la entrada.</p>
      {lista.length === 0 ? <Vacio titulo="Sin lugares todavía" /> : (
        <ul className="mt-2 divide-y divide-linea-suave">
          {lista.map((s) => (
            <li key={s.id} className="flex flex-wrap items-center gap-2 px-5 py-3">
              <MapPin className="size-4 text-gris" />
              <div className="min-w-0 flex-1"><p className="font-medium">{s.nombre}{!s.activo && <span className="ml-1 text-sm text-gris">(inactivo)</span>}</p>
                <p className="text-sm text-gris">{s.latitud ? `Radio ${s.radio_m} m` : "Sin ubicación: solo con QR"}{s.redes ? " · solo desde su red" : " · sin red configurada"}</p></div>
              <Boton tam="sm" variante="secundario" icono={Copy} onClick={() => copiar(s)}>Enlace de la pantalla</Boton>
              <Boton tam="sm" variante="fantasma" icono={RefreshCw} aria-label={`Nuevo enlace para ${s.nombre}`} title="Nuevo enlace (el anterior deja de servir)" onClick={async () => {
                if (await confirmar({ titulo: "¿Generar un enlace nuevo?", mensaje: "La pantalla con el enlace anterior dejará de mostrar el QR.", boton: "Generar" })) { await nuevaClaveSitio(s.id); cargar(); avisar("Enlace nuevo listo: cópialo a la pantalla"); }
              }} />
              <Boton tam="sm" variante="secundario" onClick={() => { setError(""); setF({ ...s }); }}>Editar</Boton>
              <Boton tam="sm" variante="fantasma" icono={Trash2} className="text-rojo" aria-label={`Borrar ${s.nombre}`} onClick={async () => {
                if (await confirmar({ titulo: `¿Borrar «${s.nombre}»?`, boton: "Borrar", peligro: true })) { await borrarSitio(s.id); cargar(); }
              }} />
            </li>
          ))}
        </ul>
      )}
      <Modal abierto={!!f} onCerrar={() => setF(null)} titulo={f?.id ? "Editar lugar" : "Nuevo lugar"}
        pie={<><Boton variante="secundario" onClick={() => setF(null)}>Cancelar</Boton><Boton type="submit" form="form-lugar">Guardar</Boton></>}>
        {f && (
          <form id="form-lugar" onSubmit={guardar} className="space-y-4">
            {error && <Alerta>{error}</Alerta>}
            <Campo etiqueta="Nombre">{(id) => <input id={id} className="campo" value={f.nombre} onChange={(e) => setF({ ...f, nombre: e.target.value })} placeholder="Oficina Bonao" />}</Campo>
            <div className="grid gap-3 sm:grid-cols-2">
              <Campo etiqueta="Latitud">{(id) => <input id={id} className="campo" inputMode="decimal" value={f.latitud || ""} onChange={(e) => setF({ ...f, latitud: e.target.value })} />}</Campo>
              <Campo etiqueta="Longitud">{(id) => <input id={id} className="campo" inputMode="decimal" value={f.longitud || ""} onChange={(e) => setF({ ...f, longitud: e.target.value })} />}</Campo>
            </div>
            <Boton variante="secundario" icono={Crosshair} onClick={aqui}>Usar mi ubicación actual</Boton>
            <Campo etiqueta="Radio (metros)" ayuda="Entre 30 y 2000. 100–150 m va bien para una oficina.">{(id) => <input id={id} type="number" min={30} max={2000} className="campo" value={f.radio_m} onChange={(e) => setF({ ...f, radio_m: Number(e.target.value) })} />}</Campo>
            <Campo etiqueta="Red de la oficina (recomendado)" ayuda="La IP pública del internet de la oficina. Con ella, el QR y la ubicación solo valen conectados al wifi de la oficina: una foto del QR o una ubicación falsa desde la casa no sirven.">
              {(id) => (
                <div className="flex gap-2">
                  <input id={id} className="campo font-mono" value={f.redes || ""} onChange={(e) => setF({ ...f, redes: e.target.value })} placeholder="190.80.1.23" />
                  <Boton variante="secundario" onClick={async () => { try { const r = await miIp(); setF((x) => ({ ...x, redes: x.redes ? `${x.redes}, ${r.ip}` : r.ip })); } catch (er) { setError(er.message); } }}>Usar la de aquí</Boton>
                </div>
              )}
            </Campo>
            <label className="flex items-center gap-2 text-sm"><input type="checkbox" className="accent-azul" checked={!!f.activo} onChange={(e) => setF({ ...f, activo: e.target.checked })} />Activo</label>
          </form>
        )}
      </Modal>
    </Panel>
  );
}
