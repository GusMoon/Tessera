# Permisos por rol (propuesta del prototipo)

[Suposición] Esta matriz es una propuesta de implementación para el Hito 3; debe validarla la Persona E (decisiones abiertas 1 y 6 de `CLAUDE.md`). El servidor la aplica en cada ruta; la interfaz solo oculta o deshabilita lo que el servidor rechazaría.

**Esto no es autenticación.** La identidad llega en la cabecera `X-Usuario-Id` (ids de la tabla `usuarios`: `u1`, `u2`, `u3`), que elige el selector de usuario de la interfaz. No hay contraseñas ni sesiones: cualquiera que conozca un id puede usarlo. Antes de ponerlo en producción hay que sustituirlo por autenticación real.

| Acción | Vendedor | Responsable comercial | Administrador |
|---|---|---|---|
| Crear una cotización desde una solicitud | Sí | Sí | Sí |
| Editar partidas y notas (Borrador o En revisión) | Sí | Sí | Sí |
| Enviar a revisión | Sí | Sí | Sí |
| **Aprobar o rechazar** | No | Sí | Sí |
| Descargar el PDF (solo si hay aprobación registrada) | Sí | Sí | Sí |
| Ver cotizaciones y fuentes citadas | Sí | Sí | Sí |
| Proponer un hecho de memoria (entra «por confirmar») | Sí | Sí | Sí |
| Confirmar, editar, pausar o borrar hechos de memoria | No | Sí | Sí |
| Ver la bitácora | Solo sus entradas | Todas | Todas |
| Cargar, subir o vaciar fuentes | No | No | Sí |
| Borrar los datos de trabajo (cotizaciones, memoria, bitácora) | No | No | Sí |

## Reglas que no dependen del rol

- **Regla 3:** sin una aprobación registrada en `aprobaciones` el PDF no existe. `GET /api/cotizaciones/{id}/pdf` responde 409, y `documents/pdf.py::generar_pdf` es la única función que dibuja el PDF. Una cotización aprobada ya no se edita.
- **Regla 6:** las fuentes tienen permiso `Todos`, `Comercial` o `Administración`. Vendedor y Responsable comercial ven `Todos` y `Comercial`; el Administrador ve además `Administración`. Se filtra **antes** de buscar y, en el detalle de una cotización, el extracto de una fuente que el usuario no puede abrir no se entrega.
- **Regla 5:** la memoria es visible, y lo nuevo o editado queda «por confirmar»: el modelo solo recibe hechos activos y confirmados.
- Un usuario inexistente o sin cabecera recibe 401; un rol sin permiso recibe 403 con el motivo.
