// Iconos de trazo propios (sin dependencias). Siempre acompañan a texto o llevan aria-label en el botón.

const TRAZOS = {
  chat: 'M4 5h16v11H9l-5 4z',
  cotizaciones: 'M6 3h9l4 4v14H6z M14 3v5h5 M9 13h6 M9 17h6',
  fuentes: 'M3 6h6l2 2h10v11H3z',
  memoria: 'M5 6c0-1.7 3.1-3 7-3s7 1.3 7 3-3.1 3-7 3-7-1.3-7-3z M5 6v6c0 1.7 3.1 3 7 3s7-1.3 7-3V6 M5 12v6c0 1.7 3.1 3 7 3s7-1.3 7-3v-6',
  bitacora: 'M8 6h12 M8 12h12 M8 18h12 M4 6h.01 M4 12h.01 M4 18h.01',
  ajustes: 'M4 7h10 M18 7h2 M4 17h2 M10 17h10 M14 5v4 M6 15v4',
  buscar: 'M11 4a7 7 0 1 0 0 14 7 7 0 0 0 0-14z M20 20l-4-4',
  sol: 'M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8z M12 2v2 M12 20v2 M2 12h2 M20 12h2 M5 5l1.5 1.5 M17.5 17.5L19 19 M5 19l1.5-1.5 M17.5 6.5L19 5',
  luna: 'M20 14A8 8 0 0 1 10 4a8 8 0 1 0 10 10z',
  cerrar: 'M6 6l12 12 M18 6L6 18',
  panel: 'M4 5h16v14H4z M15 5v14',
  enviar: 'M4 12l16-8-6 16-3-7z',
  alerta: 'M12 3l10 18H2z M12 10v5 M12 18h.01',
  check: 'M5 12l5 5 9-10',
  reloj: 'M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18z M12 7v5l3 2',
  error: 'M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18z M9 9l6 6 M15 9l-6 6',
  omitir: 'M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18z M8 12h8',
  pausa: 'M8 5v14 M16 5v14',
  editar: 'M4 20h4L19 9l-4-4L4 16z',
  borrar: 'M5 7h14 M9 7V4h6v3 M7 7l1 13h8l1-13',
  estrella: 'M12 3l2.7 5.6 6.1.9-4.4 4.3 1 6.1L12 17l-5.4 2.9 1-6.1L3.2 9.5l6.1-.9z',
  descargar: 'M12 4v11 M7 11l5 5 5-5 M5 20h14',
  izquierda: 'M15 6l-6 6 6 6',
  derecha: 'M9 6l6 6-6 6',
  mas: 'M12 5v14 M5 12h14',
  candado: 'M6 11h12v9H6z M8 11V8a4 4 0 0 1 8 0v3',
  reintentar: 'M20 12a8 8 0 1 1-2.3-5.7 M20 4v5h-5',
  archivo: 'M6 3h9l4 4v14H6z M14 3v5h5',
  monitor: 'M3 5h18v11H3z M9 20h6 M12 16v4',
  calendario: 'M4 6h16v14H4z M4 10h16 M8 3v4 M16 3v4',
  clip: 'M21 11l-9 9a6 6 0 0 1-8.5-8.5l9-9a4 4 0 0 1 5.7 5.7l-9.2 9.2a2 2 0 0 1-2.8-2.8l8.5-8.5',
} as const;

export type NombreIcono = keyof typeof TRAZOS;

export function Icono({ nombre, tamano = 18 }: { nombre: NombreIcono; tamano?: number }) {
  return (
    <svg
      width={tamano}
      height={tamano}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
    >
      <path d={TRAZOS[nombre]} />
    </svg>
  );
}
