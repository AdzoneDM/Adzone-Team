// Entrada principal: cada persona escribe su usuario (o correo) y su contraseña.
// El directorio (clave general del equipo → área → persona → su contraseña) es solo para el
// administrador: se abre desde «Entrar como administrador» y pide la clave general.
import { useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { ChevronLeft, ChevronRight, Eye, EyeOff, Users } from "lucide-react";
import Marca from "@/components/Marca";
import { Alerta, Avatar, Boton, Cargando, TiraMes, cx } from "@/components/ui";
import { abrirEquipo, directorioEntrada } from "@/lib/api";
import { useSesion } from "@/lib/sesion";

export default function Entrar() {
  const { login, verificarCodigo, avisoSesion } = useSesion();
  const navigate = useNavigate();
  const location = useLocation();
  const [paso, setPaso] = useState("usuario"); // usuario | cargando | equipo | areas | personas | clave
  const [areas, setAreas] = useState([]);
  const [configurada, setConfigurada] = useState(true);
  const [area, setArea] = useState(null);
  const [persona, setPersona] = useState(null);

  const abrirDirectorio = () => {
    setPaso("cargando");
    directorioEntrada()
      .then((d) => { setAreas(d.areas); setPaso("areas"); })
      .catch((err) => { setConfigurada(err.data?.configurada !== false); setPaso("equipo"); });
  };

  const ir = () => navigate(location.state?.desde || "/", { replace: true });
  const entrar = async (credenciales) => {
    const r = await login(credenciales);
    if (r?.dosPasos) setPaso("codigo");
    else ir();
  };

  const ancho = paso === "areas" || paso === "personas" ? "max-w-xl" : "max-w-sm";

  return (
    <div className="grid min-h-dvh md:grid-cols-[minmax(0,1fr)_minmax(0,1.1fr)]">
      <aside className="relative hidden flex-col justify-between overflow-hidden bg-noche p-12 text-white md:flex">
        <Marca className="text-xl" />
        <div className="max-w-md">
          <p className="font-display text-[40px] font-semibold leading-[1.1] tracking-tight">
            Cada tarea validada suma a tu mes.
          </p>
          <p className="mt-4 text-lg text-white/70">
            Tus tareas, las entregas de tu equipo, los KPIs de tu puesto y el Empleado del Mes, en un solo lugar.
          </p>
          <div className="mt-10 max-w-sm">
            <TiraMes validadas={11} revision={2} vencidas={1} pendientes={6} oscuro />
            <p className="mt-2 text-sm text-white/60">Así se ve el avance de un mes: amarillo es trabajo validado.</p>
          </div>
        </div>
        <p className="text-sm text-white/50">ADZONE · Creatividad para Marcas Empoderadas</p>
      </aside>

      <main className="flex flex-col justify-center px-4 py-10 sm:px-12">
        <div className={cx("mx-auto w-full", ancho)}>
          <Marca oscuro={false} className="mb-10 text-lg md:hidden" />
          {avisoSesion && paso === "usuario" && <Alerta tono="amarillo" className="mb-6">{avisoSesion}</Alerta>}
          {paso === "cargando" && <Cargando />}
          {paso === "codigo" && (
            <PasoCodigo onVolver={() => setPaso("usuario")} onEntrar={async (codigo) => { await verificarCodigo(codigo); ir(); }} />
          )}
          {paso === "usuario" && (
            <PasoUsuario onAdmin={abrirDirectorio}
              onEntrar={(username, password, recordar) => entrar({ username, password, remember_me: recordar })} />
          )}
          {paso === "equipo" && (
            <PasoEquipo configurada={configurada} onAbierto={(a) => { setAreas(a); setPaso("areas"); }} onVolver={() => setPaso("usuario")} />
          )}
          {paso === "areas" && (
            <PasoAreas areas={areas} onElegir={(a) => { setArea(a); setPaso("personas"); }} onVolver={() => setPaso("usuario")} />
          )}
          {paso === "personas" && (
            <PasoPersonas area={area} onElegir={(p) => { setPersona(p); setPaso("clave"); }} onVolver={() => setPaso("areas")} />
          )}
          {paso === "clave" && (
            <PasoClave area={area} persona={persona} onVolver={() => setPaso("personas")}
              onEntrar={(password, recordar) => entrar({ user_id: persona.id, password, remember_me: recordar })} />
          )}
        </div>
      </main>
    </div>
  );
}

function Volver({ onClick, children }) {
  return (
    <button type="button" onClick={onClick} className="-ml-1 mb-6 flex w-fit items-center gap-1 text-sm font-medium text-azul hover:underline">
      <ChevronLeft className="size-4" aria-hidden /> {children}
    </button>
  );
}

function EnlaceAdmin({ onClick }) {
  return (
    <p className="mt-10 text-center text-sm text-gris">
      <button type="button" onClick={onClick} className="hover:text-azul hover:underline">Entrar como administrador</button>
    </p>
  );
}

/** Campo de contraseña con botón para mostrarla. */
function CampoClave({ id, valor, onCambio, autoFocus, autoComplete = "current-password" }) {
  const [ver, setVer] = useState(false);
  return (
    <div className="relative">
      <input id={id} type={ver ? "text" : "password"} className="campo pr-11" autoComplete={autoComplete}
        value={valor} onChange={(e) => onCambio(e.target.value)} autoFocus={autoFocus} />
      <button type="button" onClick={() => setVer((v) => !v)} className="absolute inset-y-0 right-0 flex w-11 items-center justify-center text-gris hover:text-azul"
        aria-label={ver ? "Ocultar contraseña" : "Mostrar contraseña"}>
        {ver ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
      </button>
    </div>
  );
}

function Recordar({ valor, onCambio }) {
  return (
    <label className="flex items-center gap-2.5 text-sm text-tinta">
      <input type="checkbox" checked={valor} onChange={(e) => onCambio(e.target.checked)} className="size-4 rounded accent-azul" />
      Mantener la sesión abierta en este equipo (7 días)
    </label>
  );
}

/** Envía el formulario y muestra el error del servidor, si lo hay. */
function useEnvio(accion) {
  const [error, setError] = useState("");
  const [enviando, setEnviando] = useState(false);
  const enviar = async (validar) => {
    setError("");
    const problema = validar();
    if (problema) return setError(problema);
    setEnviando(true);
    try {
      await accion();
    } catch (err) {
      setError(err.message);
      setEnviando(false);
    }
  };
  return { error, enviando, enviar };
}

function PasoEquipo({ configurada, onAbierto, onVolver }) {
  const [clave, setClave] = useState("");
  const { error, enviando, enviar } = useEnvio(async () => onAbierto((await abrirEquipo(clave)).areas));
  return (
    <>
      <Volver onClick={onVolver}>Volver</Volver>
      <h1 className="text-3xl font-semibold">Administrador</h1>
      <p className="mt-1 text-gris">Escribe la clave general del equipo ADZONE para abrir el directorio.</p>
      <form onSubmit={(e) => { e.preventDefault(); enviar(() => !clave && "Escribe la clave del equipo."); }} className="mt-8 space-y-5" noValidate>
        {!configurada && <Alerta tono="amarillo">Todavía no hay clave del equipo. Un administrador debe definirla en «Mi cuenta».</Alerta>}
        {error && <Alerta>{error}</Alerta>}
        <div>
          <label htmlFor="clave-equipo" className="etiqueta">Clave del equipo</label>
          <CampoClave id="clave-equipo" valor={clave} onCambio={setClave} autoFocus autoComplete="off" />
        </div>
        <Boton type="submit" tam="lg" className="w-full" cargando={enviando}>Continuar</Boton>
      </form>
      <p className="mt-8 text-sm text-gris">El directorio de áreas y personas es solo para administradores de ADZONE.</p>
    </>
  );
}

function PasoAreas({ areas, onElegir, onVolver }) {
  return (
    <>
      <Volver onClick={onVolver}>Volver</Volver>
      <h1 className="text-3xl font-semibold">¿De qué área eres?</h1>
      <p className="mt-1 text-gris">Elige tu área y luego tu nombre.</p>
      <ul className="mt-8 grid gap-3 sm:grid-cols-2">
        {areas.map((a) => {
          const vacia = a.personas.length === 0;
          return (
            <li key={a.id}>
              <button type="button" disabled={vacia} onClick={() => onElegir(a)}
                className="group flex w-full items-center gap-3 rounded-xl border border-linea bg-white p-4 text-left transition-colors hover:border-azul/40 hover:bg-fondo disabled:cursor-not-allowed disabled:opacity-50">
                <span className="flex size-10 shrink-0 items-center justify-center rounded-lg font-display text-base font-semibold"
                  style={{ color: a.color, backgroundColor: a.color_fondo }} aria-hidden>
                  {a.nombre.charAt(0)}
                </span>
                <span className="min-w-0 flex-1">
                  <span className="block truncate font-semibold text-noche">{a.nombre}</span>
                  <span className="flex items-center gap-1 text-sm text-gris">
                    <Users className="size-3.5" aria-hidden />
                    {vacia ? "Sin personas" : a.personas.length === 1 ? "1 persona" : `${a.personas.length} personas`}
                  </span>
                </span>
                {!vacia && <ChevronRight className="size-4 shrink-0 text-gris group-hover:text-azul" aria-hidden />}
              </button>
            </li>
          );
        })}
      </ul>
    </>
  );
}

function PasoPersonas({ area, onElegir, onVolver }) {
  // Sangría según el nivel en el organigrama, relativa a quien encabeza el área.
  const base = Math.min(...area.personas.map((p) => p.nivel));
  return (
    <>
      <Volver onClick={onVolver}>Áreas</Volver>
      <h1 className="text-3xl font-semibold" style={{ color: area.color }}>{area.nombre}</h1>
      <p className="mt-1 text-gris">Toca tu nombre.</p>
      <ul className="mt-8 space-y-2">
        {area.personas.map((p) => {
          const nivel = Math.min(p.nivel - base, 3);
          return (
            <li key={p.id} style={{ paddingLeft: `${nivel * 1.25}rem` }}>
              <button type="button" onClick={() => onElegir(p)}
                className={cx("group flex w-full items-center gap-3 rounded-xl border bg-white p-3 text-left transition-colors hover:border-azul/40 hover:bg-fondo",
                  nivel === 0 ? "border-linea" : "border-linea-suave")}>
                <Avatar nombre={p.nombre} />
                <span className="min-w-0 flex-1">
                  <span className="block truncate font-semibold text-noche">{p.nombre}</span>
                  <span className="block truncate text-sm text-tinta">{p.puesto}</span>
                  {p.reporta_a && <span className="block truncate text-xs text-gris">Reporta a {p.reporta_a}</span>}
                </span>
                <ChevronRight className="size-4 shrink-0 text-gris group-hover:text-azul" aria-hidden />
              </button>
            </li>
          );
        })}
      </ul>
    </>
  );
}

function PasoClave({ area, persona, onVolver, onEntrar }) {
  const [clave, setClave] = useState("");
  const [recordar, setRecordar] = useState(true);
  const { error, enviando, enviar } = useEnvio(() => onEntrar(clave, recordar));
  return (
    <>
      <Volver onClick={onVolver}>{area.nombre}</Volver>
      <div className="flex items-center gap-4">
        <Avatar nombre={persona.nombre} tam="lg" />
        <div className="min-w-0">
          <h1 className="truncate text-2xl font-semibold">{persona.nombre}</h1>
          <p className="truncate text-gris">{persona.puesto}</p>
        </div>
      </div>
      <form onSubmit={(e) => { e.preventDefault(); enviar(() => !clave && "Escribe tu contraseña."); }} className="mt-8 space-y-5" noValidate>
        {error && <Alerta>{error}</Alerta>}
        {/* Para que el gestor de contraseñas del navegador la guarde a nombre de esta persona */}
        <input type="text" name="username" autoComplete="username" value={persona.nombre} readOnly hidden />
        <div>
          <label htmlFor="clave" className="etiqueta">Tu contraseña</label>
          <CampoClave id="clave" valor={clave} onCambio={setClave} autoFocus />
        </div>
        <Recordar valor={recordar} onCambio={setRecordar} />
        <Boton type="submit" tam="lg" className="w-full" cargando={enviando}>Entrar</Boton>
      </form>
      <p className="mt-8 text-sm text-gris">¿No eres tú? Vuelve y elige tu nombre. ¿Olvidaste tu contraseña? Pídele a un administrador de ADZONE que te asigne una nueva.</p>
    </>
  );
}

function PasoCodigo({ onVolver, onEntrar }) {
  const [codigo, setCodigo] = useState("");
  const [respaldo, setRespaldo] = useState(false);
  const { error, enviando, enviar } = useEnvio(() => onEntrar(codigo.trim()));
  return (
    <>
      <Volver onClick={onVolver}>Entrar</Volver>
      <h1 className="text-3xl font-semibold">Código de verificación</h1>
      <p className="mt-1 text-gris">{respaldo ? "Escribe uno de tus códigos de respaldo (por ejemplo, a1b2-c3d4)." : "Abre tu app de verificación (Google o Microsoft Authenticator) y escribe el código de 6 dígitos de Adzone Team."}</p>
      <form onSubmit={(e) => { e.preventDefault(); enviar(() => !codigo.trim() && "Escribe el código."); }} className="mt-8 space-y-5" noValidate>
        {error && <Alerta>{error}</Alerta>}
        <div>
          <label htmlFor="codigo" className="etiqueta">{respaldo ? "Código de respaldo" : "Código"}</label>
          <input id="codigo" className="campo text-center font-mono text-2xl tracking-[0.3em]" inputMode={respaldo ? "text" : "numeric"}
            autoComplete="one-time-code" maxLength={respaldo ? 9 : 6} value={codigo} autoFocus
            onChange={(e) => setCodigo(respaldo ? e.target.value : e.target.value.replace(/\D/g, ""))} />
        </div>
        <Boton type="submit" tam="lg" className="w-full" cargando={enviando}>Entrar</Boton>
      </form>
      <button type="button" className="mt-6 text-sm text-azul hover:underline" onClick={() => { setRespaldo(!respaldo); setCodigo(""); }}>
        {respaldo ? "Usar el código de la app" : "No tengo el celular: usar un código de respaldo"}
      </button>
      <p className="mt-4 text-sm text-gris">¿Perdiste el celular y los códigos? Pide a quien administra los accesos que reinicie tu verificación.</p>
    </>
  );
}

function PasoUsuario({ onAdmin, onEntrar }) {
  const [identificador, setIdentificador] = useState("");
  const [clave, setClave] = useState("");
  const [recordar, setRecordar] = useState(true);
  const { error, enviando, enviar } = useEnvio(() => onEntrar(identificador.trim(), clave, recordar));
  return (
    <>
      <h1 className="text-3xl font-semibold">Entrar</h1>
      <p className="mt-1 text-gris">Entra con tu usuario o tu correo de ADZONE.</p>
      <form onSubmit={(e) => { e.preventDefault(); enviar(() => (!identificador.trim() || !clave) && "Escribe tu usuario (o correo) y tu contraseña."); }}
        className="mt-8 space-y-5" noValidate>
        {error && <Alerta>{error}</Alerta>}
        <div>
          <label htmlFor="identificador" className="etiqueta">Usuario o correo</label>
          <input id="identificador" name="identifier" className="campo" autoComplete="username" autoCapitalize="none"
            value={identificador} onChange={(e) => setIdentificador(e.target.value)} autoFocus />
        </div>
        <div>
          <label htmlFor="clave-admin" className="etiqueta">Contraseña</label>
          <CampoClave id="clave-admin" valor={clave} onCambio={setClave} />
        </div>
        <Recordar valor={recordar} onCambio={setRecordar} />
        <Boton type="submit" tam="lg" className="w-full" cargando={enviando}>Entrar</Boton>
      </form>
      <p className="mt-8 text-sm text-gris">¿Olvidaste tu contraseña? Pídele a un administrador de ADZONE que te asigne una nueva.</p>
      <EnlaceAdmin onClick={onAdmin} />
    </>
  );
}
