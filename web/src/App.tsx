import { BrowserRouter, Route, Routes } from 'react-router-dom';
import { Layout } from './components/Layout';
import { ProveedorPanel } from './components/Panel';
import { ProveedorAlmacen } from './state/Almacen';
import Ajustes from './pages/Ajustes';
import Bitacora from './pages/Bitacora';
import Chat from './pages/Chat';
import Cotizaciones from './pages/Cotizaciones';
import Fuentes from './pages/Fuentes';
import Memoria from './pages/Memoria';
import Revision from './pages/Revision';
import { EstadoVacio } from './components/Estados';

export default function App() {
  return (
    <BrowserRouter>
      <ProveedorAlmacen>
        <ProveedorPanel>
          <Routes>
            <Route element={<Layout />}>
              <Route index element={<Chat />} />
              <Route path="cotizaciones" element={<Cotizaciones />} />
              <Route path="cotizaciones/:id" element={<Revision />} />
              <Route path="fuentes" element={<Fuentes />} />
              <Route path="memoria" element={<Memoria />} />
              <Route path="bitacora" element={<Bitacora />} />
              <Route path="ajustes" element={<Ajustes />} />
              <Route
                path="*"
                element={
                  <div className="pagina">
                    <EstadoVacio titulo="Página no encontrada" texto="La dirección no existe." accion={{ etiqueta: 'Ir al inicio', a: '/' }} />
                  </div>
                }
              />
            </Route>
          </Routes>
        </ProveedorPanel>
      </ProveedorAlmacen>
    </BrowserRouter>
  );
}
