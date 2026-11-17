import { useState } from 'react';
import { ContenidoConEstados, EncabezadoPagina } from '../components/Estados';
import { DetalleDocumento } from '../components/Fuentes';
import { EtiquetaPermiso, InsigniaEstado } from '../components/Insignia';
import { usePanel } from '../components/Panel';
import { useAlmacen } from '../state/Almacen';
import type { Documento } from '../data/tipos';
import { ChipFecha, TrazaAntiguedad } from '../components/Traza';
import { useEstadoSimulado } from '../lib/useEstadoSimulado';

export default function Fuentes() {
  const { documentos, reprocesar, avisar } = useAlmacen();
  const { abrir } = usePanel();
  const { estado, reintentar } = useEstadoSimulado();
  const [seleccion, setSeleccion] = useState<string | undefined>();

  const n = (e: Documento['estado']) => documentos.filter((d) => d.estado === e).length;

  const ver = (d: Documento) => {
    setSeleccion(d.id);
    abrir('Detalle de fuente', <DetalleDocumento documento={d} />);
  };

  return (
    <div className="pagina">
      <EncabezadoPagina
        titulo="Fuentes"
        descripcion="Lo que el sistema conoce: archivos cargados y su estado de ingesta."
        acciones={<button className="boton boton--primario" onClick={() => avisar('Conectar carpeta no está disponible en el prototipo.', 'info')}>Conectar carpeta</button>}
      />
      <ContenidoConEstados
        estado={estado}
        reintentar={reintentar}
        vacio={{ titulo: 'Aún no hay fuentes', texto: 'Conecta una carpeta con cotizaciones, fichas técnicas o chats para empezar.' }}
      >
        <p className="resumen" role="status">
          <strong>{documentos.length} documentos</strong> · {n('Listo')} listos · {n('Procesando')} procesando · {n('Error')} con error · {n('Omitido')} omitidos
        </p>
        <div className="tabla-contenedor">
          <table className="tabla tabla--filas">
            <caption className="solo-lectores">Documentos y su estado de ingesta.</caption>
            <thead>
              <tr>
                <th scope="col">Archivo</th><th scope="col">Tipo</th><th scope="col">Actualizado</th>
                <th scope="col">Antigüedad</th>
                <th scope="col">Permisos</th><th scope="col">Estado</th><th scope="col">Acciones</th>
              </tr>
            </thead>
            <tbody>
              {documentos.map((d) => (
                <tr key={d.id} className={seleccion === d.id ? 'fila-activa' : ''} onClick={() => ver(d)}>
                  <td><button className="enlace-boton" onClick={(e) => { e.stopPropagation(); ver(d); }}>{d.nombre}</button></td>
                  <td>{d.tipo}</td>
                  <td><ChipFecha fecha={d.actualizado} /></td>
                  <td><TrazaAntiguedad fecha={d.actualizado} compacta /></td>
                  <td><EtiquetaPermiso permiso={d.permisos} /></td>
                  <td><InsigniaEstado estado={d.estado} /></td>
                  <td>
                    {d.estado === 'Error' && (
                      <button className="boton boton--chico" onClick={(e) => { e.stopPropagation(); ver(d); }}>Ver motivo</button>
                    )}{' '}
                    {(d.estado === 'Listo' || d.estado === 'Error') && (
                      <button
                        className="boton boton--chico"
                        onClick={(e) => { e.stopPropagation(); reprocesar(d.id); avisar(`Reprocesando ${d.nombre} (simulado).`, 'info'); }}
                      >
                        Reprocesar
                      </button>
                    )}
                    {d.estado === 'Omitido' && <button className="boton boton--chico" onClick={(e) => { e.stopPropagation(); ver(d); }}>Ver motivo</button>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </ContenidoConEstados>
    </div>
  );
}
