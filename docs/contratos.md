# Contratos entre capas

Regla de `CLAUDE.md`: no cambiar un contrato sin avisar a quienes lo consumen y actualizar este archivo.
Etiquetas de confianza: [Certeza] verificado, [Probable] por conocimiento general, [Suposición] sin verificar.

## Proveedor de LLM (`agent/llm/`)

Quién lo ofrece: C (agente). Quién lo consume: agente, `eval/` (comparativa de modelos), `api/`.

```python
from agent.llm import crear_proveedor

proveedor = crear_proveedor()   # lee LLM_PROVIDER y el resto de .env
r = proveedor.completar([{"role": "user", "content": "..."}])
r.texto, r.modelo, r.proveedor, r.latencia_s   # `modelo` = el que realmente respondió
```

- Interfaz compatible con OpenAI (formato de chat). Proveedores: `ollama` (predeterminado, local) y `openrouter` (solo desarrollo y pruebas; nunca dependencia obligatoria).
- Errores: todos heredan de `ErrorLLM` y su mensaje es apto para mostrarse al usuario (nunca contiene la clave).
- Variables de entorno: ver `.env.example`. La clave vive solo en `.env` local.
- Con `openrouter`, todos los IDs de `OPENROUTER_MODELS` deben terminar en `:free`; si no, falla al crear el proveedor.
- El modelo no calcula precios ni totales (regla 1): este contrato solo cubre redacción, decisión de herramienta y explicación.
- Gestión de tokens: `completar` aplica por defecto `max_tokens` (512), `temperature` (0.2) y recorte de historial (3000 tokens estimados), configurables con `LLM_MAX_TOKENS_SALIDA`, `LLM_TEMPERATURA` y `LLM_CONTEXTO_ENTRADA`. Cada respuesta trae `tokens_entrada` y `tokens_salida` reales (`usage`), y `proveedor.uso` acumula el total. La estimación de tokens es una heurística [Suposición]; el conteo real es el de `usage`.
- Contexto de dominio: `completar(..., sistema=PROMPT_SISTEMA_COTIZACIONES)` antepone el prompt de cotizaciones (~270 tokens, prefijo estable). Es opcional: quien llama decide cuándo pagarlo.
- Recortar historial descarta turnos viejos, no los resume; resumir y recordar corresponde a `agent/memory/`.
- Fuera de este contrato por ahora: streaming, tool calling y modo demo (`MODO_DEMO` solo se lee).
