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
- [Idempotencia](#idempotencia)
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
| Validación de tipos y formato antes de disparar (fecha ISO, `float` excluyendo `bool`, strings no vacíos tras `strip()`) | El enunciado pide explícitamente "validar y decidir". `ParserModel` es una caja negra para el agente: no se asume que los datos siempre llegan bien formados. |
| Sin librerías externas de producción | El alcance no lo requiere (todo simulado); menos dependencias, menos superficie de fallo. |

## Supuestos asumidos

El enunciado se recibió como dos capturas de pantalla; un fragmento sobre la
autenticación quedó parcialmente cortado/impreciso en el texto:

> "...autenticación mediante el Bearer Token (header, body) y considerar
> como headers adicionales los datos devueltos por
> ringr_test_token_9f3a2c1d"

Interpretación adoptada (`src/ringr_agents/auth.py`):

1. El token `ringr_test_token_9f3a2c1d` viaja en el header
   `Authorization: Bearer <token>` **y** duplicado en el cuerpo de la
   petición (`{"auth_token": "<token>"}`), ya que el enunciado dice
   explícitamente "(header, body)".
2. "Los datos devueltos por" se interpreta como los metadatos que un
   servicio de autenticación real devolvería al validar el token (p. ej.
   client id, scope). Como no existe tal servicio en el alcance de la
   prueba, se simula con una función pura (`resolve_token_metadata`) que
   devuelve headers adicionales fijos.

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

## Idempotencia

Cada `AgentAction` expone una `key` estable y única. `BaseAgent` guarda un
`set[str]` de claves ya ejecutadas con éxito; antes de evaluar
`is_triggered`, si la clave ya está en el set, la acción se ignora. Esto
garantiza que ninguna integración se dispare dos veces durante la misma
conversación, incluso si el usuario repite la misma información en varios
turnos (cubierto en `tests/test_debt_agent.py` y
`tests/test_assistance_agent.py`).

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
  despliegue horizontalmente escalado. En producción, esa idempotencia
  debería respaldarse en un almacén compartido (Redis, base de datos) con
  clave `conversation_id + action.key`, sin cambiar la interfaz de
  `AgentAction` ni de `BaseAgent` — solo la implementación del tracking de
  ejecutadas.
- **`IntegrationClient` desacoplado del transporte real**: pasar de
  simulado a HTTP real (con timeouts, reintentos con backoff, circuit
  breaker) es un cambio contenido a una sola clase, sin tocar agentes ni
  reglas de negocio.

## Cómo extender el proyecto

### Añadir un nuevo tipo de acción a un agente existente

```python
class SendReminderSmsAction(AgentAction):
    key = "debt.send_reminder_sms"
    endpoint = "https://api.debt.v1/reminder-sms"

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
    def __init__(self, conversation_model, parser_model, integration_client):
        super().__init__(
            conversation_model, parser_model, integration_client,
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
│       ├── auth.py                # Bearer token + metadata simulada
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

19 tests, sin dependencias externas de red ni de mocking de librerías (los
dobles de prueba en `tests/fakes.py` están escritos a mano).

```bash
pytest -v
```
