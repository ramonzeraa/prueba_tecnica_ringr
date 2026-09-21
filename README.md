# Ringr — Agentes conversacionales (prueba técnica Delivery Engineer)

Implementación de una arquitectura de agentes conversacionales orientada a
objetos: cada agente gestiona un turno de conversación de forma
estructurada, extrae información relevante, decide según reglas de negocio
si debe ejecutar una acción externa, y la ejecuta mediante una integración
HTTP **simulada** (nunca se realiza una llamada de red real).

Se implementan los dos agentes pedidos por el enunciado:

- **`DebtAgent`** (cobros): registra compromisos de pago de deudas.
- **`AssistanceAgent`** (atención al cliente): registra solicitudes para
  gestión por agentes humanos.

## Índice

- [Cómo ejecutar el proyecto](#cómo-ejecutar-el-proyecto)
- [Arquitectura](#arquitectura)
- [Flujo de un turno (`handle_turn`)](#flujo-de-un-turno-handle_turn)
- [Decisiones de diseño y justificación](#decisiones-de-diseño-y-justificación)
- [Supuestos asumidos](#supuestos-asumidos)
- [Idempotencia y `conversation_id`](#idempotencia-y-conversation_id)
- [Logging](#logging)
- [Seguridad de los datos](#seguridad-de-los-datos)
- [Escalabilidad](#escalabilidad)
- [Cómo extender el proyecto](#cómo-extender-el-proyecto)
- [Estructura del proyecto](#estructura-del-proyecto)
- [Tests](#tests)

## Cómo ejecutar el proyecto

Requiere Python 3.10+.

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux / macOS
source .venv/bin/activate

pip install -r requirements-dev.txt
pytest -v
```

No hay dependencias de producción (`requirements.txt`): el proyecto solo usa
la librería estándar de Python. `pytest` es la única dependencia, y es de
desarrollo/test.

## Arquitectura

```
                    ┌─────────────────────┐
                    │     BaseAgent        │  (template method)
                    │  handle_turn(msg)     │
                    └──────────┬───────────┘
                               │ usa (inyectadas por constructor)
          ┌────────────────────┼────────────────────┬─────────────────┐
          ▼                    ▼                    ▼                 ▼
 ConversationModel      ParserModel        IntegrationClient     [AgentAction, ...]
  .answer_user()        .parse_data()        .post()                 │
  (contrato Ringr)      (contrato Ringr)   (simulado, nunca red)      │
                                                                       ▼
                                                      ┌──────────────────────────┐
                                                      │ RegisterDebtCommitment    │
                                                      │ RegisterAssistanceRequest │
                                                      │ ... (extensible)          │
                                                      └──────────────────────────┘
```

**Patrones aplicados:**

- **Template Method** (`BaseAgent.handle_turn`): fija el algoritmo común a
  todo agente (responder → parsear → decidir → ejecutar) en un único lugar,
  sin duplicarlo por agente.
- **Strategy** (`AgentAction`): cada regla de negocio ("¿cuándo disparo?",
  "¿qué envío?") es un objeto independiente e intercambiable. Añadir un
  nuevo tipo de acción nunca requiere modificar `BaseAgent`.
- **Dependency Inversion**: `BaseAgent` depende únicamente de las
  abstracciones `ConversationModel`, `ParserModel`, `IntegrationClient` y
  `AgentAction` — nunca de una implementación concreta. Esto es lo que
  permite simular todo el sistema sin tocar la lógica de negocio.

## Flujo de un turno (`handle_turn`)

1. `ConversationModel.answer_user(mensaje)` → respuesta al usuario (`str`).
2. `ParserModel.parse_data()` → `dict` con la información estructurada
   extraída de la conversación (claves específicas de cada caso de uso).
3. Para cada `AgentAction` del agente que **no se haya ejecutado ya** en
   esta conversación:
   - `is_triggered(parsed_data)` decide si las condiciones de negocio se
     cumplen.
   - Si sí, `build_payload(parsed_data)` construye el cuerpo de la llamada.
4. `IntegrationClient.post(endpoint, payload)` ejecuta la integración
   (simulada). Si la respuesta es exitosa, la acción se marca como
   ejecutada para el resto de la conversación.

## Decisiones de diseño y justificación

| Decisión | Justificación |
|---|---|
| `ConversationModel`/`ParserModel` como `ABC` | El enunciado los describe con estado interno propio; una clase abstracta modela contrato + estado sin forzar una implementación concreta (que está fuera de alcance). |
| Reglas de negocio en objetos `AgentAction`, no en `if/elif` dentro del agente | Cumple explícitamente el requisito de extensibilidad ("incorporar fácilmente nuevos agentes, nuevos tipos de acciones") sin violar Open/Closed. |
| `IntegrationClient` como interfaz + `SimulatedIntegrationClient` | Permite construir el request (headers/body) igual que un cliente real, sin tocar la red, y sin que el agente sepa la diferencia. Sustituir por un cliente real (`requests`) es un cambio de una sola clase. |
| Idempotencia con `set[str]` de claves de acción, por instancia de agente | Una instancia de agente representa una conversación. Solo se marca una acción como ejecutada tras una respuesta exitosa (`response.ok`), así una falla transitoria puede reintentarse en el siguiente turno sin perder la acción de negocio. |
| Validación y normalización de tipos y formato antes de disparar (fecha ISO, `float` excluyendo `bool`, strings no vacíos tras `strip()`) | El enunciado pide explícitamente "validar y normalizar la información parseada". `ParserModel` es una caja negra para el agente: no se asume que los datos siempre llegan bien formados. |
| Headers adicionales = mismo `payload` que se envía en el body | El enunciado pide reflejar "los datos devueltos por el ParserModel" como headers, con los mismos nombres. Como `build_payload` siempre preserva los nombres de campo de `parse_data()` sin transformarlos, `payload` ya **es** esos datos — reutilizarlo evita una segunda copia del mismo estado. |
| Sin librerías externas de producción | El alcance no lo requiere (todo simulado); menos dependencias, menos superficie de fallo. |
| `conversation_id` obligatorio (valida que no esté vacío) en `BaseAgent` | Hace explícita una regla que ya era implícita ("una instancia = una conversación"), habilita correlacionar logs por conversación, y deja lista la mitad de la clave que necesitaría un backend de idempotencia compartido en producción. |

## Supuestos asumidos

El requisito de autenticación del enunciado pide incluir el Bearer Token
`ringr_test_token_9f3a2c1d` en cada llamada, y considerar como headers
adicionales los datos devueltos por `ParserModel`, con los mismos nombres.
Interpretación aplicada (`src/ringr_agents/auth.py` y
`src/ringr_agents/integration.py`):

1. El token viaja únicamente en el header `Authorization: Bearer
   ringr_test_token_9f3a2c1d`; no hay ningún requisito de duplicarlo en el
   body.
2. Los headers adicionales son, literalmente, los campos que `payload`
   trae — que a su vez son los mismos que devuelve `ParserModel.parse_data()`
   bajo idéntico nombre (`commitment_date`, `committed_amount`, `request`,
   según el agente), convertidos a `str` porque los headers HTTP no aceptan
   otro tipo.

Otros supuestos:

- Idempotencia por **tipo de acción** (su `key`), no por valor del payload:
  una vez que una acción se ejecuta con éxito, no vuelve a dispararse en esa
  conversación aunque los datos parseados cambien después. Alternativa
  descartada: reabrir la acción si los valores cambian, pero el enunciado
  pide explícitamente evitar duplicados, y "actualizar un compromiso ya
  registrado" es un caso de uso distinto (no descrito) que introduciría
  ambigüedad de negocio no especificada.
- Una respuesta simulada exitosa siempre es `200 OK` (explícitamente
  permitido por el enunciado).

## Idempotencia y `conversation_id`

Cada `AgentAction` expone una `key` estable y única. `BaseAgent` guarda un
`set[str]` de claves ya ejecutadas con éxito; antes de evaluar
`is_triggered`, si la clave ya está en el set, la acción se ignora. Esto
garantiza que ninguna integración se dispare dos veces durante la misma
conversación, incluso si el usuario repite la misma información en varios
turnos (cubierto en `tests/test_debt_agent.py` y
`tests/test_assistance_agent.py`).

Cada instancia de `BaseAgent` representa exactamente una conversación — es
una regla implícita del diseño desde el principio, pero antes no existía
nada en el código que la hiciera explícita. `conversation_id` (obligatorio
en el constructor, valida que no esté vacío) le pone nombre a esa identidad:
hoy se usa para poder correlacionar las líneas de log de una conversación
puntual, y es, junto con `action.key`, la clave que un backend de
idempotencia compartido usaría en producción (ver
[Escalabilidad](#escalabilidad)).

## Logging

`BaseAgent.handle_turn` emite logs (vía `logging.getLogger(__name__)`, sin
handlers ni configuración propia — el proyecto que lo use decide dónde
mandarlos) en cuatro puntos: acción no disparada por condiciones no
cumplidas (`DEBUG`), acción ya ejecutada en esta conversación y por tanto
omitida (`DEBUG`), acción ejecutada con éxito (`INFO`), y fallo de la
llamada de integración (`WARNING`). Cada línea arranca con
`[conversation_id]` (ver [Idempotencia y `conversation_id`](#idempotencia-y-conversation_id))
para poder filtrar los logs de una conversación puntual cuando hay muchas
corriendo en paralelo. Nunca se loguea el payload en sí — solo el
`conversation_id`, la clave de la acción, el endpoint y (en fallos) el
status code — por el mismo motivo detallado en la sección de seguridad: los
datos parseados pueden ser sensibles.

Tests (`tests/test_base_agent.py`) verifican, con el fixture `caplog` de
pytest, que los logs de éxito, fallo y omisión por idempotencia realmente
se emiten con el nivel esperado, y que incluyen el `conversation_id`.

Salida real (no editada) al correr tres escenarios representativos con el
logging habilitado:

```
$ pytest -s --log-cli-level=DEBUG -v \
    tests/test_debt_agent.py::test_fires_commitment_when_both_fields_present \
    tests/test_base_agent.py::test_a_failed_integration_call_is_retried_on_a_later_turn \
    tests/test_base_agent.py::test_logs_debug_when_an_already_executed_action_is_skipped

tests/test_debt_agent.py::test_fires_commitment_when_both_fields_present
-------------------------------- live log call --------------------------------
INFO     ringr_agents.agent:agent.py:88 [conv-debt-test] Action 'debt.register_commitment' executed successfully (endpoint=https://api.ringr.debt/v1/commitment).
PASSED

tests/test_base_agent.py::test_a_failed_integration_call_is_retried_on_a_later_turn
-------------------------------- live log call --------------------------------
WARNING  ringr_agents.agent:agent.py:95 [conv-base-agent-test] Action 'test.always_on' integration call failed (status=500, endpoint=https://api.example.test/always-on); will retry next turn.
WARNING  ringr_agents.agent:agent.py:95 [conv-base-agent-test] Action 'test.always_on' integration call failed (status=500, endpoint=https://api.example.test/always-on); will retry next turn.
PASSED

tests/test_base_agent.py::test_logs_debug_when_an_already_executed_action_is_skipped
-------------------------------- live log call --------------------------------
INFO     ringr_agents.agent:agent.py:88 [conv-base-agent-test] Action 'test.always_on' executed successfully (endpoint=https://api.example.test/always-on).
DEBUG    ringr_agents.agent:agent.py:65 [conv-base-agent-test] Action 'test.always_on' already executed for this conversation, skipping.
PASSED

3 passed in 0.09s
```

## Seguridad de los datos

- **Ninguna llamada de red real se ejecuta jamás** — es una decisión de
  diseño, no solo un requisito del enunciado: mientras el sistema esté en
  modo simulado, es estructuralmente imposible filtrar datos de clientes
  (importes de deuda, solicitudes de soporte) a un endpoint real por error.
- **Validación antes de envío**: los datos extraídos por `ParserModel` se
  validan (formato de fecha, tipo numérico, strings no vacíos) antes de
  construir cualquier payload, en vez de confiar ciegamente en una fuente
  externa.
- **El token de prueba está en el código porque el enunciado lo entrega
  como valor de prueba literal.** En un sistema real, un Bearer Token
  nunca debería vivir en el código fuente ni en el repositorio: debería
  inyectarse en tiempo de ejecución vía variables de entorno o un gestor de
  secretos (Vault, AWS Secrets Manager, etc.), y rotarse periódicamente.
- **Registro de llamadas (`sent_requests`) sin sanitizar el token**: en el
  cliente simulado, `sent_requests` guarda el header `Authorization`
  completo para poder inspeccionarlo en tests. En un sistema de logging de
  producción, un Bearer Token real nunca debería quedar en texto plano en
  logs — se enmascararía (p. ej. `Bearer ****2c1d`) antes de persistir o
  imprimir cualquier registro de la llamada.
- **Datos de negocio potencialmente sensibles** (importes de deuda,
  contenido de solicitudes de soporte) solo se procesan en memoria dentro
  del ciclo de vida del turno; no se persisten en ningún punto de este
  proyecto.
- **Los logs de `BaseAgent` (ver [Logging](#logging)) nunca incluyen el
  payload**, precisamente para no aplicar en la práctica lo contrario de
  este mismo punto: se loguea la clave de la acción y el endpoint, nunca el
  importe ni el contenido de la solicitud.

## Escalabilidad

- **Añadir un agente nuevo, un tipo de acción nuevo o una integración
  nueva nunca requiere modificar código existente** (Open/Closed): se
  suman una subclase de `AgentAction` y, si aplica, una subclase de
  `BaseAgent` que la configure. `tests/test_base_agent.py` lo demuestra en
  vivo con una acción de prueba creada ad-hoc.
- **Un agente puede tener múltiples acciones** (`BaseAgent` itera una
  lista) — soporta, por ejemplo, un agente que dispare dos integraciones
  distintas a partir del mismo turno sin cambios estructurales.
- **Límite conocido de la idempotencia actual**: el `set[str]` de claves
  ejecutadas vive en memoria, por instancia de agente. Es correcto para el
  alcance de esta prueba (una conversación = una instancia de proceso), pero
  **no sobrevive a un reinicio del proceso ni funciona si distintos turnos
  de la misma conversación son atendidos por instancias distintas** en un
  despliegue horizontalmente escalado. `conversation_id` ya existe como
  identidad explícita de la conversación en `BaseAgent` — en producción,
  esa idempotencia debería respaldarse en un almacén compartido (Redis,
  base de datos) con clave `conversation_id + action.key`, sin cambiar la
  interfaz de `AgentAction` ni de `BaseAgent` — solo la implementación
  interna del tracking de ejecutadas (hoy `self._executed_action_keys`).
- **`IntegrationClient` desacoplado del transporte real**: pasar de
  simulado a HTTP real (con timeouts, reintentos con backoff, circuit
  breaker) es un cambio contenido a una sola clase, sin tocar agentes ni
  reglas de negocio.

## Cómo extender el proyecto

### Añadir un nuevo tipo de acción a un agente existente

```python
class SendReminderSmsAction(AgentAction):
    key = "debt.send_reminder_sms"
    endpoint = "https://api.ringr.debt/v1/reminder-sms"

    def is_triggered(self, parsed_data: dict) -> bool:
        return parsed_data.get("phone_number") is not None

    def build_payload(self, parsed_data: dict) -> dict:
        return {"phone_number": parsed_data["phone_number"]}
```

Y añadirla a la lista de acciones del agente correspondiente — `BaseAgent`
no cambia.

### Añadir un agente completamente nuevo

```python
class LeadQualificationAgent(BaseAgent):
    def __init__(self, conversation_id, conversation_model, parser_model, integration_client):
        super().__init__(
            conversation_id, conversation_model, parser_model, integration_client,
            actions=[RegisterQualifiedLeadAction()],
        )
```

### Añadir una integración real (en lugar de la simulada)

Implementar `IntegrationClient.post(...)` con un cliente HTTP real (p. ej.
`requests`) e inyectarla donde hoy se inyecta `SimulatedIntegrationClient`.
Ningún agente ni ninguna `AgentAction` necesita cambiar.

## Estructura del proyecto

```
prueba_tecnica_ringr/
├── README.md
├── pyproject.toml
├── requirements-dev.txt
├── src/
│   └── ringr_agents/
│       ├── models.py              # ConversationModel, ParserModel (contratos)
│       ├── actions.py             # AgentAction (Strategy) + OutboundAction
│       ├── integration.py         # IntegrationClient + SimulatedIntegrationClient
│       ├── auth.py                # Constante del Bearer token de prueba
│       ├── agent.py               # BaseAgent (template method + idempotencia)
│       └── agents/
│           ├── debt_agent.py          # DebtAgent
│           └── assistance_agent.py    # AssistanceAgent
└── tests/
    ├── fakes.py                   # FakeConversationModel, FakeParserModel, SpyIntegrationClient
    ├── test_base_agent.py         # BaseAgent aislado + prueba viva de extensibilidad
    ├── test_debt_agent.py
    ├── test_assistance_agent.py
    └── test_integration_client.py
```

## Tests

24 tests, sin dependencias externas de red ni de mocking de librerías (los
dobles de prueba en `tests/fakes.py` están escritos a mano).

```bash
pytest -v
```
