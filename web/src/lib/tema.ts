import { useSyncExternalStore } from 'react';

export type Tema = 'sistema' | 'claro' | 'oscuro';
const CLAVE = 'tessera-tema';
const oyentes = new Set<() => void>();
let temporizadorTransicion: number | undefined;

function leer(): Tema {
  try {
    const v = localStorage.getItem(CLAVE);
    if (v === 'claro' || v === 'oscuro' || v === 'sistema') return v;
  } catch {
    /* almacenamiento no disponible: se usa oscuro por defecto */
  }
  return 'oscuro';
}

let actual: Tema = leer();

function aplicar(t: Tema) {
  const raiz = document.documentElement;
  if (t === 'sistema') raiz.removeAttribute('data-theme');
  else raiz.setAttribute('data-theme', t === 'claro' ? 'light' : 'dark');
}

export function iniciarTema() {
  aplicar(actual);
}

export function fijarTema(t: Tema) {
  if (t === actual) return;
  actual = t;
  // Suaviza el cambio de color solo mientras ocurre; no queda activa en el uso normal.
  const raiz = document.documentElement;
  raiz.classList.add('cambiando-tema');
  window.clearTimeout(temporizadorTransicion);
  temporizadorTransicion = window.setTimeout(() => raiz.classList.remove('cambiando-tema'), 400);
  aplicar(t);
  try {
    localStorage.setItem(CLAVE, t);
  } catch {
    /* sin persistencia */
  }
  oyentes.forEach((f) => f());
}

export function useTema(): [Tema, (t: Tema) => void] {
  const tema = useSyncExternalStore(
    (cb) => {
      oyentes.add(cb);
      return () => oyentes.delete(cb);
    },
    () => actual,
  );
  return [tema, fijarTema];
}

/** True si en este momento se está mostrando el modo oscuro. */
export function esOscuroAhora(tema: Tema): boolean {
  if (tema === 'oscuro') return true;
  if (tema === 'claro') return false;
  return window.matchMedia('(prefers-color-scheme: dark)').matches;
}
