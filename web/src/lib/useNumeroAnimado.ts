import { useEffect, useRef, useState } from 'react';

/** Cifra que «rueda» hacia su nuevo valor. Respeta prefers-reduced-motion. El valor final siempre es exacto. */
export function useNumeroAnimado(objetivo: number, ms = 420): number {
  const [valor, setValor] = useState(objetivo);
  const actual = useRef(objetivo);

  useEffect(() => {
    const sinMovimiento = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (sinMovimiento || actual.current === objetivo) {
      actual.current = objetivo;
      setValor(objetivo);
      return;
    }
    const desde = actual.current;
    const t0 = performance.now();
    let raf = 0;
    const paso = (t: number) => {
      const p = Math.min(1, (t - t0) / ms);
      const suave = 1 - Math.pow(1 - p, 3);
      const v = p === 1 ? objetivo : Math.round(desde + (objetivo - desde) * suave);
      actual.current = v;
      setValor(v);
      if (p < 1) raf = requestAnimationFrame(paso);
    };
    raf = requestAnimationFrame(paso);
    return () => cancelAnimationFrame(raf);
  }, [objetivo, ms]);

  return valor;
}
