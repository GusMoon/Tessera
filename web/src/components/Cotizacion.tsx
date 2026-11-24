import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { calcularCotizacion } from '../lib/calculo';
import { formatoFecha, formatoPesos, parsePesos } from '../lib/dinero';
import { normalizarUnidadesTipograficas } from '../lib/texto';
import type { Cotizacion, IdEscenario, Partida } from '../data/tipos';
import { escenarioVigente, useAlmacen } from '../state/Almacen';
import { ChipFuente } from './Fuentes';
import { Icono } from './Iconos';
import { InsigniaEstado } from './Insignia';
import { fechaMasAntigua, TrazaAntiguedad } from './Traza';

export function totalDe(c: Cotizacion, id: IdEscenario = escenarioVigente(c)): number {
  return calcularCotizacion(c.escenarios[id].partidas).total;
}

/** Tarjeta de cotización: folio, cliente, total, estado (doc UI §6). */
export function TarjetaCotizacion({ cotizacion }: { cotizacion: Cotizacion }) {
  const { citaPorId } = useAlmacen();
  const c = cotizacion;
  return (
    <div className="tarjeta-cot">
      <div className="tarjeta-cot__fila">
        <strong>Cotización {c.folio}</strong>
        <InsigniaEstado estado={c.estado} />
      </div>
      <div className="texto-suave">{c.cliente}</div>
      <div className="tarjeta-cot__escenarios">
        {(['economico', 'recomendado', 'premium'] as IdEscenario[]).map((id) => {
          const masVieja = fechaMasAntigua(
            c.escenarios[id].partidas.map((p) => citaPorId(p.citaId)?.fecha).filter((f): f is string => !!f),
          );
          return (
            <div key={id} className={id === 'recomendado' ? 'es-recomendado' : ''}>
              <span className="texto-suave">{id === 'economico' ? 'Económico' : id === 'recomendado' ? 'Recomendado' : 'Premium'}</span>
              <span className="cifra tarjeta-cot__total">
                {formatoPesos(totalDe(c, id))} <span className="sufijo-moneda">MXN</span>
              </span>
              {masVieja && <TrazaAntiguedad fecha={masVieja} compacta />}
            </div>
          );
        })}
      </div>
      <p className="texto-suave tarjeta-cot__nota">La traza muestra la fuente más antigua de cada opción.</p>
      <Link className="boton boton--pildora boton--primario" to={`/cotizaciones/${c.id}`}>
        Abrir revisión
      </Link>
    </div>
  );
}

/** Celda numérica editable: valida al salir y revierte si el valor no es válido. */
function CeldaEditable({
  valor,
  formato,
  interpretar,
  etiqueta,
  alineada,
  onConfirmar,
  deshabilitada,
}: {
  valor: number;
  formato: (n: number) => string;
  interpretar: (t: string) => number | null;
  etiqueta: string;
  alineada?: boolean;
  onConfirmar: (n: number) => void;
  deshabilitada: boolean;
}) {
  const [texto, setTexto] = useState(formato(valor));
  const [invalido, setInvalido] = useState(false);
  useEffect(() => {
    setTexto(formato(valor));
    setInvalido(false);
  }, [valor, formato]);

  if (deshabilitada) return <span className="cifra">{formato(valor)}</span>;

  const confirmar = () => {
    const n = interpretar(texto);
    if (n === null) {
      setInvalido(true);
      return;
    }
    setInvalido(false);
    if (n !== valor) onConfirmar(n);
    else setTexto(formato(valor));
  };

  return (
    <input
      className={`entrada entrada--celda cifra ${alineada ? 'derecha' : ''}`}
      value={texto}
      aria-label={etiqueta}
      aria-invalid={invalido}
      title={invalido ? 'Valor no válido' : undefined}
      inputMode="decimal"
      onChange={(e) => setTexto(e.target.value)}
      onBlur={confirmar}
      onKeyDown={(e) => {
        if (e.key === 'Enter') e.currentTarget.blur();
        if (e.key === 'Escape') {
          setTexto(formato(valor));
          setInvalido(false);
        }
      }}
    />
  );
}

const formatoCantidad = (n: number) => String(n);
const interpretarCantidad = (t: string) => (/^\d+$/.test(t.trim()) && Number(t) > 0 ? Number(t) : null);

/** Tabla de partidas: cantidad y precio editables; los importes salen de calcularCotizacion. */
export function TablaPartidas({
  partidas,
  importes,
  editable,
  citaActiva,
  onCambio,
  onVerFuente,
}: {
  partidas: Partida[];
  importes: number[];
  editable: boolean;
  citaActiva?: string;
  onCambio: (partidaId: string, cambios: Partial<Pick<Partida, 'cantidad' | 'precioUnitario'>>) => void;
  onVerFuente: (citaId: string) => void;
}) {
  const { citaPorId } = useAlmacen();
  return (
    <div className="tabla-contenedor">
      <table className="tabla tabla--partidas">
        <caption className="solo-lectores">Partidas de la cotización. Importes en pesos mexicanos.</caption>
        <thead>
          <tr>
            <th scope="col">Concepto</th>
            <th scope="col" className="derecha">Cant.</th>
            <th scope="col" className="derecha">P. unit. (MXN)</th>
            <th scope="col" className="derecha">Importe (MXN)</th>
            <th scope="col">Fuente y antigüedad</th>
          </tr>
        </thead>
        <tbody>
          {partidas.map((p, i) => {
            const cita = citaPorId(p.citaId);
            return (
              <tr key={p.id} className={p.editadaPor ? 'fila-editada' : ''}>
                <td data-etiqueta="Concepto" className="celda-concepto">
                  {normalizarUnidadesTipograficas(p.concepto)}
                  {p.editadaPor && (
                    <div className="marca-editada">
                      <Icono nombre="editar" tamano={12} /> editada por {p.editadaPor}
                    </div>
                  )}
                </td>
                <td className="derecha" data-etiqueta="Cantidad">
                  <CeldaEditable
                    valor={p.cantidad}
                    formato={formatoCantidad}
                    interpretar={interpretarCantidad}
                    etiqueta={`Cantidad de ${p.concepto}`}
                    alineada
                    deshabilitada={!editable}
                    onConfirmar={(n) => onCambio(p.id, { cantidad: n })}
                  />
                </td>
                <td className="derecha" data-etiqueta="Precio unitario">
                  <CeldaEditable
                    valor={p.precioUnitario}
                    formato={formatoPesos}
                    interpretar={parsePesos}
                    etiqueta={`Precio unitario de ${p.concepto}`}
                    alineada
                    deshabilitada={!editable}
                    onConfirmar={(n) => onCambio(p.id, { precioUnitario: n })}
                  />
                </td>
                <td className="derecha cifra celda-importe" data-etiqueta="Importe">{formatoPesos(importes[i])}</td>
                <td data-etiqueta="Fuente">
                  <div className="celda-fuente">
                    <ChipFuente citaId={p.citaId} activo={citaActiva === p.citaId} onAbrir={onVerFuente} />
                    {cita?.fecha && <TrazaAntiguedad fecha={cita.fecha} anima retraso={i * 70} />}
                  </div>
                  {cita?.fecha && <span className="solo-lectores">Fecha del dato {formatoFecha(cita.fecha)}</span>}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
