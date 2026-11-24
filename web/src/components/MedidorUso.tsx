import { useEffect, useRef, useState } from 'react';
import { duracionCorta, textoReinicio } from '../lib/texto';
import type { UsoChat } from '../lib/api';

const entero = (n: number) => n.toLocaleString('es-MX');

type Nivel = 'ok' | 'warn' | 'error' | 'neutro';

/** Verde con margen, ámbar al quedar el 20 % o menos, rojo en cero. */
function nivelDe(restantes: number | null, limite: number | null): Nivel {
  if (restantes === null || limite === null || limite <= 0) return 'neutro';
  if (restantes <= 0) return 'error';
  return restantes / limite <= 0.2 ? 'warn' : 'ok';
}

/** El peor de dos niveles, para que el punto del indicador avise de cualquiera de los dos límites. */
function peor(a: Nivel, b: Nivel): Nivel {
  const orden: Nivel[] = ['neutro', 'ok', 'warn', 'error'];
  return orden[Math.max(orden.indexOf(a), orden.indexOf(b))];
}

/** «Se reinician mañana a las 18:00 (en 19 h)» o, si la cuota se recarga sola, «Vuelve a estar completa a las 22:14 (en 2 min)». */
function textoVuelta(uso: UsoChat): string | null {
  if (!uso.reinicio_dia_utc) return null;
  if (new Date(uso.reinicio_dia_utc).getTime() - Date.now() < 1500) return uso.reinicio_modo === 'recarga' ? 'La cuota está completa.' : null;
  const cuando = textoReinicio(uso.reinicio_dia_utc);
  return uso.reinicio_modo === 'recarga' ? `Vuelve a estar completa ${cuando}.` : `Se reinicia ${cuando}.`;
}

/**
 * Indicador de uso del modelo, compacto y en una esquina del Chat: tokens consumidos y, si el proveedor lo
 * informa, cuánta cuota queda. El detalle (qué se limita, cuándo se recupera) está en el panel desplegable.
 * Con OpenRouter el límite es por peticiones, no por tokens; con Groq es por peticiones y por tokens.
 */
export function MedidorUso({ uso, error, modeloVision }: { uso: UsoChat | null; error: string | null; modeloVision?: string | null }) {
  const [abierto, setAbierto] = useState(false);
  const raiz = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!abierto) return;
    const fuera = (e: MouseEvent) => {
      if (!raiz.current?.contains(e.target as Node)) setAbierto(false);
    };
    const tecla = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setAbierto(false);
    };
    document.addEventListener('mousedown', fuera);
    document.addEventListener('keydown', tecla);
    return () => {
      document.removeEventListener('mousedown', fuera);
      document.removeEventListener('keydown', tecla);
    };
  }, [abierto]);

  const dia = uso?.dia ?? null;
  const tokensMin = uso?.tokens_minuto ?? null;
  const nivel: Nivel = uso
    ? peor(nivelDe(dia?.restantes ?? null, dia?.limite ?? null), nivelDe(tokensMin?.restantes ?? null, tokensMin?.limite ?? null))
    : 'neutro';
  const etiqueta = error ? 'Uso no disponible' : uso ? `${entero(uso.sesion.tokens_total)} tokens` : 'Uso…';
  const cuota = dia && dia.restantes !== null && dia.limite !== null ? `${entero(dia.restantes)}/${entero(dia.limite)}` : null;

  return (
    <div className="medidor" ref={raiz}>
      <button
        type="button"
        className={`medidor__boton medidor__boton--${nivel}`}
        aria-expanded={abierto}
        aria-controls="medidor-detalle"
        title="Tokens usados en esta sesión y cuota del modelo"
        onClick={() => setAbierto((a) => !a)}
      >
        <span className="medidor__punto" aria-hidden="true" />
        <span className="cifra">{etiqueta}</span>
        {cuota && <span className="medidor__cuota cifra">{cuota}</span>}
      </button>
      {abierto && (
        <div id="medidor-detalle" className="medidor__detalle" role="region" aria-label="Uso del modelo">
          {error ? <p>No se pudo leer el uso del modelo: {error}</p> : uso ? <Detalle uso={uso} modeloVision={modeloVision ?? null} nivel={nivel} /> : <p>Consultando el uso del modelo…</p>}
        </div>
      )}
    </div>
  );
}

function Detalle({ uso, modeloVision, nivel }: { uso: UsoChat; modeloVision: string | null; nivel: Nivel }) {
  const { dia, minuto, tokens_minuto: tokensMinuto, sesion } = uso;
  const proveedor = uso.proveedor === 'groq' ? 'Groq' : uso.proveedor === 'openrouter' ? 'OpenRouter' : 'Modelo local';
  const vuelta = textoVuelta(uso);
  const enMinuto = minuto ? Math.max(0, minuto.limite - minuto.usadas_aqui) : null;
  const porcentaje = dia && dia.restantes !== null && dia.limite ? Math.max(0, Math.min(100, (dia.restantes / dia.limite) * 100)) : null;

  return (
    <>
      <p className="medidor__modelo">
        <strong>{proveedor}</strong> · {uso.modelo}
        {modeloVision && uso.tipo_limite !== 'ninguno' && <span className="texto-suave"> (imágenes: {modeloVision})</span>}
      </p>

      {dia && dia.restantes !== null && dia.limite !== null && porcentaje !== null && (
        <div>
          <p>
            <span className={`insignia insignia--${nivel === 'neutro' ? 'ok' : nivel}`}>
              {dia.restantes <= 0 ? 'Sin solicitudes' : `${entero(dia.restantes)} de ${entero(dia.limite)} solicitudes hoy`}
            </span>
          </p>
          <div className={`medidor__barra medidor__barra--${nivel}`} role="progressbar" aria-valuemin={0} aria-valuemax={dia.limite} aria-valuenow={dia.restantes} aria-label="Solicitudes restantes">
            <span style={{ width: `${porcentaje}%` }} />
          </div>
          {vuelta && <p className="texto-suave medidor__nota">{vuelta}</p>}
        </div>
      )}

      {tokensMinuto && tokensMinuto.restantes !== null && tokensMinuto.limite !== null && (
        <p>
          Tokens este minuto: <strong className="cifra">{entero(tokensMinuto.restantes)}</strong> de {entero(tokensMinuto.limite)}
          {tokensMinuto.segundos_para_reiniciar ? <span className="texto-suave"> (se reinician en {duracionCorta(tokensMinuto.segundos_para_reiniciar)})</span> : null}
        </p>
      )}

      {minuto && enMinuto !== null && (
        <p className="texto-suave">
          Este minuto (estimado, solo cuenta esta app): {enMinuto} de {minuto.limite} disponibles
          {enMinuto === 0 && minuto.segundos_para_liberar ? `, se libera una en ${duracionCorta(minuto.segundos_para_liberar)}` : ''}.
        </p>
      )}

      <p>
        Sesión: <strong className="cifra">{entero(sesion.tokens_total)}</strong> tokens
        <span className="texto-suave"> ({entero(sesion.tokens_entrada)} de entrada y {entero(sesion.tokens_salida)} de salida) en {entero(sesion.llamadas)} {sesion.llamadas === 1 ? 'llamada' : 'llamadas'}, desde que arrancó el servidor.</span>
      </p>

      {uso.aviso && <p className="texto-suave">{uso.aviso}</p>}
      <p className="texto-suave medidor__nota">
        {uso.tipo_limite === 'ninguno'
          ? 'Un modelo local no tiene límite de peticiones ni de tokens.'
          : uso.tipo_limite === 'peticiones y tokens'
            ? 'Groq limita por solicitudes y por tokens.'
            : 'OpenRouter limita por solicitudes, no por tokens, y actualiza el contador diario con unos segundos de retraso.'}
      </p>
    </>
  );
}
