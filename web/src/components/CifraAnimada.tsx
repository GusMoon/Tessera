import { formatoMXN } from '../lib/dinero';
import { useNumeroAnimado } from '../lib/useNumeroAnimado';

/**
 * Importe que rueda al recalcularse. Lo animado es solo visual (aria-hidden);
 * quien usa lector de pantalla recibe siempre el valor final exacto.
 */
export function CifraAnimada({
  centavos,
  formato = formatoMXN,
  className = '',
}: {
  centavos: number;
  formato?: (c: number) => string;
  className?: string;
}) {
  const mostrado = useNumeroAnimado(centavos);
  return (
    <span className={`cifra ${className}`}>
      <span aria-hidden="true">{formato(mostrado)}</span>
      <span className="solo-lectores">{formato(centavos)}</span>
    </span>
  );
}
