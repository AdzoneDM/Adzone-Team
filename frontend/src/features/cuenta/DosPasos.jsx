// Verificación en dos pasos con app de códigos (Google Authenticator, Microsoft Authenticator…).
// Se usa en Mi cuenta y como pantalla obligatoria para quien maneja datos de la empresa.
import { useEffect, useState } from "react";
import { Copy, ShieldCheck, Smartphone } from "lucide-react";
import { confirmarDosPasos, desactivarDosPasos, dosPasos, iniciarDosPasos, nuevosCodigosRespaldo } from "@/lib/api";
import { useSesion } from "@/lib/sesion";
import { Alerta, Boton, Campo, Cargando, Insignia, Panel, useAviso } from "@/components/ui";

function CampoCodigo({ valor, onCambio, autoFocus }) {
  return (
    <input className="campo w-40 text-center font-mono text-xl tracking-[0.3em]" inputMode="numeric" autoComplete="one-time-code" maxLength={9}
      placeholder="000000" aria-label="Código de 6 dígitos" value={valor} autoFocus={autoFocus}
      onChange={(e) => onCambio(e.target.value.replace(/[^\d a-f-]/gi, ""))} />
  );
}

function CodigosRespaldo({ codigos, onListo }) {
  const avisar = useAviso();
  const copiar = async () => { try { await navigator.clipboard.writeText(codigos.join("\n")); avisar("Códigos copiados"); } catch { /* sin portapapeles */ } };
  return (
    <div className="space-y-3">
      <Alerta tono="amarillo">Guarda estos 10 códigos de respaldo en un lugar seguro (impresos o en tu gestor de contraseñas). Cada uno sirve una sola vez si pierdes el celular. No se vuelven a mostrar.</Alerta>
      <ol className="grid grid-cols-2 gap-2 rounded-lg border border-linea bg-niebla/60 p-3 font-mono text-[15px] sm:grid-cols-5">
        {codigos.map((c) => <li key={c}>{c}</li>)}
      </ol>
      <div className="flex flex-wrap gap-2">
        <Boton variante="secundario" icono={Copy} onClick={copiar}>Copiar</Boton>
        <Boton onClick={onListo}>Ya los guardé</Boton>
      </div>
    </div>
  );
}

export function ActivarDosPasos({ onActivada, clave }) {
  const [datos, setDatos] = useState(null);
  const [codigo, setCodigo] = useState("");
  const [respaldo, setRespaldo] = useState(null);
  const [error, setError] = useState("");
  const [enviando, setEnviando] = useState(false);
  useEffect(() => { iniciarDosPasos(clave).then(setDatos).catch((e) => setError(e.message)); }, [clave]);
  if (respaldo) return <CodigosRespaldo codigos={respaldo} onListo={onActivada} />;
  if (!datos) return error ? <Alerta>{error}</Alerta> : <Cargando />;
  const confirmar = async (e) => {
    e.preventDefault();
    setError(""); setEnviando(true);
    try { setRespaldo((await confirmarDosPasos(codigo)).codigos_respaldo); } catch (err) { setError(err.message); }
    setEnviando(false);
  };
  return (
    <form onSubmit={confirmar} className="space-y-4">
      <ol className="list-decimal space-y-1 pl-5 text-[15px]">
        <li>Instala en tu celular <b>Google Authenticator</b> o <b>Microsoft Authenticator</b>.</li>
        <li>En la app toca <b>+</b> y escanea este código.</li>
        <li>Escribe el código de 6 dígitos que te muestra.</li>
      </ol>
      <div className="flex flex-col items-start gap-4 sm:flex-row sm:items-center">
        {/* El SVG lo genera el servidor (sin datos externos) */}
        <div className="size-48 shrink-0 rounded-lg border border-linea bg-white p-2 [&_svg]:size-full" dangerouslySetInnerHTML={{ __html: datos.qr }} />
        <div className="min-w-0 text-sm text-gris">
          <p>¿No puedes escanear? Escribe esta clave en la app:</p>
          <p className="mt-1 break-all font-mono text-noche">{datos.secreto.replace(/(.{4})/g, "$1 ").trim()}</p>
        </div>
      </div>
      {error && <Alerta>{error}</Alerta>}
      <div className="flex flex-wrap items-center gap-3">
        <CampoCodigo valor={codigo} onCambio={setCodigo} autoFocus />
        <Boton type="submit" cargando={enviando} disabled={codigo.replace(/\D/g, "").length !== 6}>Activar</Boton>
      </div>
    </form>
  );
}

/** Panel de Mi cuenta. */
export default function DosPasosPanel() {
  const { recargar } = useSesion();
  const avisar = useAviso();
  const [estado, setEstado] = useState(null);
  const [modo, setModo] = useState(""); // activar | respaldo | desactivar | clave-celular | celular
  const [valor, setValor] = useState("");
  const [codigos, setCodigos] = useState(null);
  const [error, setError] = useState("");
  const cargar = () => dosPasos().then(setEstado).catch((e) => setError(e.message));
  useEffect(() => { cargar(); }, []);
  const terminar = () => { setModo(""); setValor(""); setCodigos(null); cargar(); recargar(); };
  const accion = async (fn, ok) => {
    setError("");
    try { const r = await fn(); if (r?.codigos_respaldo) setCodigos(r.codigos_respaldo); else { avisar(ok); terminar(); } } catch (e) { setError(e.message); }
  };
  if (!estado) return null;
  return (
    <Panel titulo="Verificación en dos pasos" accion={estado.activo ? <Insignia tono="verde"><ShieldCheck className="size-3" />Activa</Insignia> : <Insignia>Inactiva</Insignia>}>
      <div className="space-y-4">
        <p className="text-sm text-gris">
          Además de tu contraseña, al entrar se pide un código de tu celular. {estado.exige ? "Tu cuenta maneja datos de la empresa: es obligatoria." : "Es opcional para tu cuenta, pero la recomendamos."}
        </p>
        {error && <Alerta>{error}</Alerta>}
        {codigos ? <CodigosRespaldo codigos={codigos} onListo={terminar} />
          : modo === "activar" ? <ActivarDosPasos onActivada={() => { avisar("Verificación en dos pasos activada"); terminar(); }} />
            : modo === "celular" ? <ActivarDosPasos clave={valor} onActivada={() => { avisar("Listo: ahora usa el celular nuevo"); terminar(); }} />
            : modo === "clave-celular" ? (
              <form className="flex flex-wrap items-end gap-3" onSubmit={(e) => { e.preventDefault(); setModo("celular"); }}>
                <Campo etiqueta="Tu contraseña">{(id) => <input id={id} type="password" className="campo" value={valor} onChange={(e) => setValor(e.target.value)} autoComplete="current-password" autoFocus />}</Campo>
                <Boton type="submit" disabled={!valor}>Seguir</Boton>
                <Boton variante="fantasma" onClick={() => setModo("")}>Cancelar</Boton>
              </form>
            )
            : modo === "respaldo" ? (
              <form className="flex flex-wrap items-end gap-3" onSubmit={(e) => { e.preventDefault(); accion(() => nuevosCodigosRespaldo(valor)); }}>
                <Campo etiqueta="Código de tu app">{() => <CampoCodigo valor={valor} onCambio={setValor} autoFocus />}</Campo>
                <Boton type="submit">Generar códigos nuevos</Boton>
                <Boton variante="fantasma" onClick={() => setModo("")}>Cancelar</Boton>
              </form>
            ) : modo === "desactivar" ? (
              <form className="flex flex-wrap items-end gap-3" onSubmit={(e) => { e.preventDefault(); accion(() => desactivarDosPasos(valor), "Verificación desactivada"); }}>
                <Campo etiqueta="Tu contraseña">{(id) => <input id={id} type="password" className="campo" value={valor} onChange={(e) => setValor(e.target.value)} autoComplete="current-password" />}</Campo>
                <Boton type="submit" variante="peligro">Desactivar</Boton>
                <Boton variante="fantasma" onClick={() => setModo("")}>Cancelar</Boton>
              </form>
            ) : estado.activo ? (
              <div className="flex flex-wrap items-center gap-2">
                <p className="mr-auto text-sm">Te quedan <b>{estado.respaldo_restantes}</b> códigos de respaldo.</p>
                <Boton variante="secundario" onClick={() => { setValor(""); setModo("respaldo"); }}>Códigos de respaldo nuevos</Boton>
                <Boton variante="secundario" onClick={() => { setValor(""); setModo("clave-celular"); }}>Cambiar de celular</Boton>
                {!estado.exige && <Boton variante="fantasma" className="text-rojo" onClick={() => { setValor(""); setModo("desactivar"); }}>Desactivar</Boton>}
              </div>
            ) : <Boton icono={Smartphone} onClick={() => setModo("activar")}>Activar con mi celular</Boton>}
      </div>
    </Panel>
  );
}

/** Pantalla completa para quien debe activarla antes de seguir. */
export function DosPasosObligatoria() {
  const { usuario, recargar, logout } = useSesion();
  return (
    <div className="flex min-h-dvh items-start justify-center bg-niebla px-4 py-10 sm:items-center">
      <div className="w-full max-w-xl space-y-4 rounded-2xl border border-linea bg-white p-6 shadow-sm">
        <ShieldCheck className="size-8 text-azul" />
        <h1 className="text-2xl font-semibold">Protege tu cuenta, {usuario.first_name || usuario.nombre}</h1>
        <p className="text-gris">Tu cuenta maneja datos de la empresa (personas, salarios o la configuración). Antes de seguir, activa la verificación en dos pasos: al entrar se te pedirá un código de tu celular.</p>
        <ActivarDosPasos onActivada={recargar} />
        <button type="button" className="text-sm text-gris underline" onClick={logout}>Salir</button>
      </div>
    </div>
  );
}
