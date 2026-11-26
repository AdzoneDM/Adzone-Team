// Copia texto al portapapeles. Si el navegador no da permiso (algunos celulares o webviews), usa el método antiguo.
export async function copiarTexto(texto) {
  try { await navigator.clipboard.writeText(texto); return true; } catch { /* sin permiso: se intenta a la antigua */ }
  const area = document.createElement("textarea");
  area.value = texto; area.setAttribute("readonly", ""); area.style.position = "fixed"; area.style.opacity = "0";
  document.body.appendChild(area); area.select();
  let ok = false;
  try { ok = document.execCommand("copy"); } catch { ok = false; }
  area.remove();
  return ok;
}
