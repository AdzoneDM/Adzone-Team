// «Enlace para el cliente»: crea un enlace seguro al portal (ver sus OT, aprobar artes, firmar el acta) y lo comparte por WhatsApp o correo.
import { useEffect, useState } from "react";
import { Copy, Link2, Mail, MessageCircle } from "lucide-react";
import { crearEnlaceCliente, enlacesCliente, revocarEnlaceCliente } from "@/lib/api";
import { fechaCorta, hace } from "@/lib/formato";
import { Alerta, Boton, Campo, Insignia, Modal, useAviso } from "@/components/ui";

export default function EnlaceCliente({ orden, abierto, onCerrar }) {
  const avisar = useAviso();
  const [lista, setLista] = useState([]);
  const [f, setF] = useState({ para: orden.contacto || "", dias: 30, todas: false });
  const [nuevo, setNuevo] = useState(null);
  const [error, setError] = useState("");
  const cargar = () => enlacesCliente(orden.id).then(setLista).catch((e) => setError(e.message));
  useEffect(() => { if (abierto) { setNuevo(null); setError(""); cargar(); } }, [abierto]); // eslint-disable-line react-hooks/exhaustive-deps
  const crear = async (e) => {
    e.preventDefault(); setError("");
    try { setNuevo(await crearEnlaceCliente(orden.id, f)); cargar(); } catch (er) { setError(er.message); }
  };
  const texto = nuevo && `Hola${f.para ? ` ${f.para.split(" ")[0]}` : ""}, aquí puedes ver el avance de tu orden ${orden.numero || ""} con ADZONE, aprobar los artes y firmar la entrega: ${nuevo.url}`;
  const telefono = (orden.telefono || "").replace(/\D/g, "");
  return (
    <Modal abierto={abierto} onCerrar={onCerrar} titulo="Enlace para el cliente" ancho="md:max-w-xl"
      descripcion="El cliente entra sin contraseña: ve el avance, aprueba lo que le envíen y firma el acta. Vence solo y se puede revocar.">
      <div className="space-y-4">
        {error && <Alerta>{error}</Alerta>}
        {nuevo ? (
          <div className="space-y-3">
            <Alerta tono="verde">Enlace creado. Cópialo ahora: por seguridad no se vuelve a mostrar.</Alerta>
            <p className="break-all rounded-lg border border-linea bg-niebla/60 p-3 font-mono text-sm">{nuevo.url}</p>
            <div className="flex flex-wrap gap-2">
              <Boton icono={Copy} variante="secundario" onClick={async () => { try { await navigator.clipboard.writeText(nuevo.url); avisar("Enlace copiado"); } catch { /* sin portapapeles */ } }}>Copiar</Boton>
              <a className="inline-flex items-center gap-1.5 rounded-lg bg-verde px-3 py-2 text-sm font-medium text-white" target="_blank" rel="noreferrer"
                href={`https://wa.me/${telefono}?text=${encodeURIComponent(texto)}`}><MessageCircle className="size-4" />WhatsApp</a>
              <a className="inline-flex items-center gap-1.5 rounded-lg border border-linea px-3 py-2 text-sm font-medium" href={`mailto:${orden.correo || ""}?subject=${encodeURIComponent(`Tu orden ${orden.numero || ""} con ADZONE`)}&body=${encodeURIComponent(texto)}`}>
                <Mail className="size-4" />Correo</a>
            </div>
            <Boton variante="fantasma" onClick={() => setNuevo(null)}>Crear otro</Boton>
          </div>
        ) : (
          <form onSubmit={crear} className="space-y-3">
            <Campo etiqueta="Para quién">{(id) => <input id={id} className="campo" value={f.para} onChange={(e) => setF({ ...f, para: e.target.value })} placeholder="Nombre del contacto" />}</Campo>
            <div className="grid gap-3 sm:grid-cols-2">
              <Campo etiqueta="Vence en (días)">{(id) => <input id={id} type="number" min={1} max={90} className="campo" value={f.dias} onChange={(e) => setF({ ...f, dias: Number(e.target.value) })} />}</Campo>
              <label className="flex items-center gap-2 self-end pb-2 text-sm"><input type="checkbox" className="accent-azul" checked={f.todas} onChange={(e) => setF({ ...f, todas: e.target.checked })} />Todas las órdenes del cliente</label>
            </div>
            <Boton type="submit" icono={Link2}>Crear enlace</Boton>
          </form>
        )}
        {lista.length > 0 && (
          <div>
            <p className="etiqueta">Enlaces creados</p>
            <ul className="divide-y divide-linea-suave rounded-lg border border-linea">
              {lista.map((e) => (
                <li key={e.id} className="flex flex-wrap items-center gap-2 px-3 py-2 text-sm">
                  <span className="min-w-0 flex-1"><span className="font-medium">{e.para || "Sin nombre"}</span>{e.todas && <span className="text-gris"> · todas sus órdenes</span>}
                    <span className="block text-xs text-gris">Creado {fechaCorta(e.creado)} por {e.creado_por} · vence {fechaCorta(e.vence)} · {e.usos ? `abierto ${e.usos} vez(ces), ${hace(e.ultimo_uso)}` : "sin abrir"}</span></span>
                  {e.vigente ? <Boton tam="sm" variante="fantasma" className="text-rojo" onClick={async () => { await revocarEnlaceCliente(e.id); cargar(); avisar("Enlace revocado"); }}>Revocar</Boton>
                    : <Insignia>{e.revocado ? "Revocado" : "Vencido"}</Insignia>}
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </Modal>
  );
}
