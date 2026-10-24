// Palabra «ad zone» en los colores de la marca (amarillo + azul o blanco sobre fondo oscuro).
export default function Marca({ oscuro = true, className = "" }) {
  return (
    <span className={`inline-flex items-baseline gap-1.5 font-display font-semibold leading-none ${className}`}>
      <span className="text-[1.45em] tracking-tight">
        <span className="text-amarillo">ad</span>
        <span className={oscuro ? "text-white" : "text-azul"}>zone</span>
      </span>
      <span className={`text-[0.95em] font-medium ${oscuro ? "text-white/60" : "text-gris"}`}>Team</span>
    </span>
  );
}
