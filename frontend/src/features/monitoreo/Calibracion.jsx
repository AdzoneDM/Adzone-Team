// Calibración del piloto: aplicaciones y sitios que ninguna regla clasifica (cuentan como neutral) y se deciden de un toque.
import { useCallback, useEffect, useState } from "react";
import { Globe, AppWindow } from "lucide-react";
import { calibracion, clasificar, departamentos as cargarDeptos } from "@/lib/api";
import { reloj } from "@/lib/formato";
import { Alerta, Barra, Boton, Cargando, Insignia, Panel, Pestanas, Vacio, useAviso } from "@/components/ui";

const OPCIONES = [["P", "Productivo", "primario"], ["N", "Neutral", "secundario"], ["I", "Improductivo", "peligro"]];

function Fila({ item, deptos, onHecho }) {
  const unico = item.departamentos.length === 1 ? item.departamentos[0] : null;
  const [alcance, setAlcance] = useState(""); // "" = toda la empresa
  const [enviando, setEnviando] = useState("");
  const [error, setError] = useState("");
  const decidir = async (categoria) => {
    setEnviando(categoria); setError("");
    try { const r = await clasificar({ tipo: item.tipo, patron: item.patron, categoria, departamento: alcance || null }); onHecho(item, r.reclasificados); }
    catch (e) { setError(e.message); }
    setEnviando("");
  };
  const Icono = item.tipo === "DOMINIO" ? Globe : AppWindow;
  return (
    <li className="space-y-2 px-4 py-3">
      <div className="flex items-start gap-3">
        <Icono className="mt-0.5 size-4 shrink-0 text-gris" />
        <div className="min-w-0 flex-1">
          <p className="truncate font-medium">{item.patron}</p>
          <p className="truncate text-sm text-gris">{reloj(item.minutos)} · {item.personas} persona(s) · {item.departamentos.map((d) => d.nombre).join(", ")}</p>
          {item.ejemplo && <p className="truncate text-xs text-gris">«{item.ejemplo}»</p>}
        </div>
      </div>
      {error && <Alerta>{error}</Alerta>}
      <div className="flex flex-wrap items-center gap-2 pl-7">
        <select className="campo h-9 w-auto py-1 text-sm" value={alcance} onChange={(e) => setAlcance(e.target.value)} aria-label={`Para quién aplica ${item.patron}`}>
          <option value="">Toda la empresa</option>
          {(unico ? deptos.filter((d) => d.id === unico.id).concat(deptos.filter((d) => d.id !== unico.id)) : deptos).map((d) => <option key={d.id} value={d.id}>Solo {d.nombre}</option>)}
        </select>
        {OPCIONES.map(([c, texto, variante]) => (
          <Boton key={c} tam="sm" variante={variante} cargando={enviando === c} disabled={!!enviando} onClick={() => decidir(c)}>{texto}</Boton>
        ))}
      </div>
    </li>
  );
}

export default function Calibracion() {
  const [dias, setDias] = useState("7");
  const [d, setD] = useState(null);
  const [deptos, setDeptos] = useState([]);
  const [error, setError] = useState("");
  const avisar = useAviso();
  const cargar = useCallback(() => calibracion(dias).then(setD).catch((e) => setError(e.message)), [dias]);
  useEffect(() => { setD(null); cargar(); }, [cargar]);
  useEffect(() => { cargarDeptos().then((l) => setDeptos(l.results || l)).catch(() => {}); }, []);
  const hecho = (item, n) => {
    setD((x) => ({ ...x, sin_clasificar: x.sin_clasificar.filter((i) => i !== item), minutos_con_regla: x.minutos_con_regla + item.minutos }));
    avisar(`«${item.patron}» clasificado${n ? `: ${n} minutos actualizados` : ""}`);
  };
  const cobertura = d && d.minutos_total ? Math.round((d.minutos_con_regla / d.minutos_total) * 100) : null;
  return (
    <div className="space-y-4">
      <Panel>
        <div className="flex flex-wrap items-center gap-4">
          <div className="min-w-0 flex-1">
            <p className="font-display font-semibold">Calibración del piloto</p>
            <p className="text-sm text-gris">Lo que usa el equipo y ninguna regla clasifica (hoy cuenta como neutral). Decide cada uno para toda la empresa o solo para un departamento: se aplica a los últimos 30 días.</p>
          </div>
          <Pestanas className="!flex" opciones={[{ valor: "7", etiqueta: "7 días" }, { valor: "14", etiqueta: "14 días" }, { valor: "30", etiqueta: "30 días" }]} valor={dias} onCambio={setDias} />
        </div>
        {cobertura != null && (
          <div className="mt-4 flex items-center gap-3">
            <Barra valor={cobertura} className="flex-1" />
            <span className="w-56 text-right text-sm"><b className="num">{cobertura} %</b> del tiempo ya tiene regla</span>
          </div>
        )}
      </Panel>
      {error && <Alerta>{error}</Alerta>}
      {!d ? !error && <Cargando /> : d.sin_clasificar.length === 0 ? (
        <Vacio titulo={d.minutos_total ? "Todo lo usado tiene regla" : "Todavía no hay actividad registrada"}>
          {d.minutos_total ? "Revisa de nuevo después de unos días de piloto." : "Instala el agente en las computadoras del piloto y vuelve en un par de días."}
        </Vacio>
      ) : (
        <Panel cuerpo="p-0" titulo={`Sin clasificar · ${d.sin_clasificar.length}`} accion={<Insignia>Más usado primero</Insignia>}>
          <ul className="divide-y divide-linea-suave">{d.sin_clasificar.map((i) => <Fila key={`${i.tipo}:${i.patron}`} item={i} deptos={deptos} onHecho={hecho} />)}</ul>
        </Panel>
      )}
    </div>
  );
}
