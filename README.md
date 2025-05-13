# FastAPI Chat Microservice

Este microservicio proporciona una API de chat que puede responder preguntas utilizando datos de una base de datos PostgreSQL o mediante la API de OpenAI.

## Características

-   Endpoint de chat (`POST /api/v1/chat/`)
-   Validación de token JWT
-   Conexión a PostgreSQL usando SQLAlchemy (async)
-   Integración (básica) con OpenAI
-   Soporte para múltiples proyectos (a través del campo `proyecto` en la solicitud)

## Configuración del Proyecto

### 1. Prerrequisitos

-   Python 3.8+
-   PostgreSQL (base de datos ya existente y accesible)
-   Una cuenta de OpenAI y una API key (opcional, si se usa la funcionalidad de OpenAI)

### 2. Clonar el Repositorio (si aplica)

```bash
# git clone <url-del-repositorio>
# cd fastapi_chat_microservice
```

### 3. Crear un Entorno Virtual

```bash
python -m venv venv
```

Activar el entorno virtual:

-   Windows (pwsh):
    ```powershell
    .\venv\Scripts\Activate.ps1
    ```
-   Windows (cmd.exe):
    ```bash
    .\venv\Scripts\activate.bat
    ```
-   macOS/Linux:
    ```bash
    source venv/bin/activate
    ```

### 4. Instalar Dependencias

```bash
pip install -r requirements.txt
```

### 5. Configurar Variables de Entorno

Cree un archivo `.env` en la raíz del proyecto (junto a `requirements.txt`) copiando el archivo `.env.example`:

-   Windows (pwsh):
    ```powershell
    Copy-Item .env.example .env
    ```
-   macOS/Linux (bash):
    ```bash
    cp .env.example .env
    ```

Edite el archivo `.env` con sus configuraciones:

```env
DATABASE_URL="postgresql+asyncpg://TU_USUARIO:TU_PASSWORD@TU_HOST:TU_PUERTO/TU_BASE_DE_DATOS"
OPENAI_API_KEY="sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx" # Tu API Key de OpenAI
JWT_SECRET_KEY="tu_clave_secreta_jwt_compartida_con_django" # Debe ser la misma que usa Django
ALGORITHM="HS256" # El algoritmo que usa Django para los tokens JWT (e.g., HS256)
ACCESS_TOKEN_EXPIRE_MINUTES=30 # Opcional, no usado directamente por este servicio para generar tokens
```

**Importante sobre JWT_SECRET_KEY y ALGORITHM:**
Estos valores deben coincidir exactamente con los que utiliza su aplicación Django para generar los tokens JWT. Consulte la configuración de `SIMPLE_JWT` o el paquete JWT que esté utilizando en Django.

### 6. Estructura de la Base de Datos

Este microservicio espera interactuar con tablas existentes en su base de datos PostgreSQL. Deberá ajustar las consultas SQL en `app/services/database_service.py` para que coincidan con su esquema de base de datos.

Por ejemplo, la función `query_database` actualmente tiene ejemplos para una tabla `orders` con columnas `status` y `project_name`. Modifique esto según sea necesario.

## Ejecutar la Aplicación

Para iniciar el servidor de desarrollo Uvicorn:

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

-   `--reload`: El servidor se reiniciará automáticamente después de cambios en el código.
-   `--host 0.0.0.0`: Hace que el servidor sea accesible desde otras máquinas en la red.
-   `--port 8000`: Especifica el puerto en el que se ejecutará la aplicación.

## Probar el Endpoint

Puede probar el endpoint `POST /api/v1/chat/` utilizando herramientas como `curl`, Postman, o Insomnia.

**URL:** `http://localhost:8000/api/v1/chat/`
**Método:** `POST`
**Headers:**
-   `Content-Type: application/json`
-   `Authorization: Bearer <tu_token_jwt_generado_por_django>`

**Cuerpo (Body) - JSON:**

Ejemplo para consulta a base de datos:
```json
{
  "mensaje": "¿Cuántas órdenes pendientes hay?",
  "usuario_id": "123",
  "proyecto": "dashboard_miempresa"
}
```

Ejemplo para pregunta genérica a OpenAI:
```json
{
  "mensaje": "Explícame qué es una orden inbound",
  "usuario_id": "456",
  "proyecto": "conocimiento_general"
}
```

### Documentación de la API (Swagger UI)

Una vez que la aplicación esté en ejecución, puede acceder a la documentación interactiva de la API (generada por Swagger UI) en su navegador:

`http://localhost:8000/docs`

Y la especificación OpenAPI en:

`http://localhost:8000/api/v1/openapi.json`

## Estructura del Proyecto

```
fastapi_chat_microservice/
├── app/                  # Directorio principal de la aplicación
│   ├── __init__.py
│   ├── main.py           # Punto de entrada de FastAPI, configuración de la app
│   ├── api/              # Módulos relacionados con la API
│   │   └── v1/           # Versión 1 de la API
│   │       ├── api.py    # Router principal para v1
│   │       └── endpoints/
│   │           └── chat.py # Lógica del endpoint de chat
│   ├── core/             # Configuración central, seguridad
│   │   ├── config.py     # Carga de configuraciones (variables de entorno)
│   │   └── security.py   # Lógica de autenticación y autorización (JWT)
│   ├── db/               # Módulos de base de datos
│   │   ├── session.py    # Configuración de SQLAlchemy y sesión de BD
│   │   └── utils.py      # Utilidades de base de datos (si son necesarias)
│   ├── schemas/          # Esquemas Pydantic para validación de datos
│   │   └── chat.py       # Esquemas para las solicitudes y respuestas del chat
│   └── services/         # Lógica de negocio
│       ├── chat_processing_service.py # Orquesta la lógica de chat (BD vs OpenAI)
│       ├── database_service.py        # Lógica para interactuar con la BD
│       └── openai_service.py          # Lógica para interactuar con OpenAI
├── .env                  # (No versionado) Variables de entorno locales
├── .env.example          # Ejemplo de variables de entorno
├── requirements.txt      # Dependencias de Python
└── README.md             # Este archivo
```

## Próximos Pasos y Mejoras

-   **Implementación Detallada de Consultas a BD:** Adaptar `app/services/database_service.py` con las consultas SQL/SQLAlchemy específicas para su esquema de base de datos y las preguntas que espera manejar.
-   **Manejo de Errores Avanzado:** Mejorar el manejo de errores y los mensajes de respuesta.
-   **Logging:** Implementar un sistema de logging robusto.
-   **Testing:** Añadir pruebas unitarias e de integración.
-   **LangChain/pgvector:** Integrar estas herramientas para capacidades de búsqueda semántica y RAG (Retrieval Augmented Generation) más avanzadas.
-   **Modelos SQLAlchemy:** Si prefiere usar el ORM de SQLAlchemy en lugar de SQL en texto plano, defina sus modelos en un nuevo archivo `app/db/models.py` y úselos en `app/services/database_service.py`.
-   **Optimización de OpenAI:** Ajustar los prompts y parámetros de OpenAI para mejores respuestas.
-   **Gestión de Conversaciones:** Implementar persistencia de historial de chat si es necesario.
-   **Validación de `usuario_id`:** Considerar validar el `usuario_id` del cuerpo de la solicitud contra el identificador de usuario presente en el token JWT.
