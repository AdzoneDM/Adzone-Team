// Eliminar un cliente con confirmación, igual desde la lista y desde la ficha. Solo se borra un cliente sin historial; si ya tiene órdenes,
// proyectos o documentos de Finanzas el servidor lo impide (para no perder lo que se hizo y se cobró) y aquí se ofrece dejarlo inactivo.
import { eliminarCliente, guardarCliente } from "@/lib/api";
import { olvidarRecurso } from "@/lib/recursos";

/** Devuelve "eliminado", "inactivo" o null (canceló o falló; el aviso ya se mostró). */
export async function eliminarClienteConfirmando({ cliente, confirmar, avisar }) {
  const ok = await confirmar({
    titulo: `¿Eliminar a ${cliente.nombre}?`, boton: "Eliminar", peligro: true,
    mensaje: "Se borra el cliente y sus enlaces del portal. No se puede deshacer. Si ya tiene órdenes, proyectos o facturas no se podrá borrar y te ofreceremos dejarlo inactivo.",
  });
  if (!ok) return null;
  try {
    await eliminarCliente(cliente.id);
    olvidarRecurso("clientes");
    avisar("Cliente eliminado.");
    return "eliminado";
  } catch (e) {
    const protegido = /márcalo como inactivo/.test(e.message);
    if (protegido && cliente.activo && await confirmar({ titulo: "No se puede eliminar", mensaje: `${e.message} ¿Lo dejo inactivo ahora?`, boton: "Dejar inactivo" })) {
      try { await guardarCliente({ id: cliente.id, activo: false }); olvidarRecurso("clientes"); avisar("Cliente marcado como inactivo."); return "inactivo"; } catch (e2) { avisar(e2.message, "rojo"); return null; }
    }
    avisar(e.message, "rojo");
    return null;
  }
}
