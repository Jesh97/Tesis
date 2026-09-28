# Seguridad y protección — evaluación de riesgos

Este documento resume los riesgos considerados para el sistema de monitoreo
de pesca ilegal (Lambayeque) y qué mitigación existe para cada uno. Sirve de
respaldo para el criterio "Protección" de la rúbrica del producto acreditable
(documentación de riesgos y evaluación de amenazas).

## 1. Acceso no autorizado a la API

**Riesgo:** cualquiera en internet podría llamar a los endpoints de la API
sin credenciales.

**Mitigación:**
- Todas las rutas salvo `/api/auth/login` y `/health` exigen
  `Authorization: Bearer <token>` (`server/app/auth_dep.py:usuario_actual`,
  aplicado en `server/app/main.py`).
- El token es un JWT firmado (HS256) con expiración de 12 horas
  (`DURACION_SESION`). La clave de firma (`SESSION_SECRET`) se exige por
  variable de entorno; el servidor no arranca sin ella (evita el riesgo de
  una clave por defecto conocida).
- CORS restringido a los orígenes declarados en `CORS_ORIGINS` (por defecto
  solo `localhost:5173` en desarrollo) — sin esto, cualquier página en
  cualquier dominio podría invocar la API desde el navegador de un usuario
  ya logueado.

## 2. Fuerza bruta / enumeración de usuarios en el login

**Riesgo:** sin límite de intentos, un atacante puede probar contraseñas
indefinidamente contra `/api/auth/login`; y si el servidor responde más
rápido cuando el usuario no existe que cuando existe, el tiempo de respuesta
por sí solo revela qué nombres de usuario son válidos.

**Mitigación** (`server/app/routes/auth.py`):
- Bloqueo de 15 minutos por combinación (IP, usuario) tras 5 intentos
  fallidos seguidos (`_INTENTOS_MAXIMOS`, `_VENTANA_BLOQUEO_SEGUNDOS`).
- `bcrypt.checkpw` se ejecuta siempre, incluso cuando el usuario no existe
  (contra un hash señuelo, `_HASH_SEÑUELO`), para que el tiempo de respuesta
  no distinga "usuario inexistente" de "contraseña incorrecta".

**Limitación aceptada:** el contador de intentos vive en memoria del
proceso Python (no en Redis ni en una tabla). Con un solo proceso Uvicorn
(el despliegue actual) esto alcanza; si el sistema se escalara a varias
instancias detrás de un balanceador, cada instancia tendría su propio
contador y el límite efectivo se multiplicaría por el número de instancias.
Migrarlo a un almacén compartido sería el siguiente paso en ese escenario.

## 3. Operaciones no autorizadas por un usuario autenticado

**Riesgo:** que cualquier sesión válida (sin importar el rol) pueda hacer
cambios de configuración que deberían quedar reservados a un administrador
— por ejemplo, crear o eliminar las zonas críticas que todo el sistema usa
para vigilar, lo que además deja huérfanos los incidentes que referencian
una zona eliminada.

**Mitigación:**
- `rol_usuario` (`administrador` | `supervisor` | `analista`,
  `db/schema.sql`) viaja en el JWT y se valida en el backend con la
  dependencia `requiere_rol` (`server/app/auth_dep.py`).
- Crear y eliminar zonas (`POST/DELETE /api/zonas`) exigen rol
  `administrador`.
- Confirmar/descartar un incidente y aprobar/rechazar una sugerencia de la
  IA se dejan abiertos a cualquier rol autenticado a propósito: es el
  trabajo normal de un analista, no una acción de configuración.
- **Auditoría** (tabla `auditoria`, `db/schema.sql`): confirmar/descartar un
  incidente, crear/eliminar una zona y aprobar/rechazar una sugerencia
  quedan registrados con `usuario_id`, acción, entidad y fecha
  (`sp_auditoria_registrar`, invocada desde dentro de cada función de
  `db/procedures.sql` — nunca expuesta directo a la API). Solo un
  administrador puede consultarla (`GET /api/auditoria`,
  `server/app/routes/auditoria.py`). `app_runtime` no tiene privilegio
  directo sobre esta tabla, igual que el resto (ver punto 4) — ni siquiera
  puede invocar `sp_auditoria_registrar` por su cuenta, solo las funciones
  que ya la llaman internamente.

La auditoría también cubre crear un incidente manualmente
(`POST /api/incidentes`, acción `incidente_registrado`) y disparar el
análisis de una fuente de noticias por IA (`POST /api/fuentes/analizar`,
acción `fuente_analisis_iniciado` en `sp_fuentes_crear`) — esta última solo
cuando realmente arranca un análisis nuevo, no cuando la URL se omite por
ya estar en proceso o ya analizada.

## 4. Acceso directo a la base de datos si se filtran las credenciales

**Riesgo:** que las credenciales de la API filtradas permitan ejecutar SQL
arbitrario contra las tablas (leer, modificar o borrar cualquier dato).

**Mitigación** (`db/roles.sql`): el rol con el que corre la API
(`app_runtime`) no tiene ningún privilegio directo de
`SELECT/INSERT/UPDATE/DELETE` sobre las tablas — se le revoca explícitamente
todo acceso y solo se le otorga `EXECUTE` sobre las funciones de
`db/procedures.sql`. Aunque las credenciales de la app se filtren, quien las
tenga solo puede invocar esas operaciones ya validadas, no correr SQL
arbitrario. Todas las rutas pasan por estas funciones vía `ejecutar_sp`
(`server/app/db.py`), nunca con SQL interpolado directamente.

## 5. Datos sensibles en el repositorio

**Riesgo:** que credenciales (`SESSION_SECRET`, `DATABASE_URL`,
`GFW_API_TOKEN`) terminen commiteadas.

**Mitigación:** `.env` está en `.gitignore` (solo se versiona
`.env.example` con placeholders); verificado que ningún `.env` real está
trackeado en el repositorio.

## 6. Errores no controlados que exponen detalles internos

**Riesgo:** una excepción no prevista (caída de la BD, GFW inalcanzable, un
bug) devolviendo un traceback o una respuesta sin el formato esperado al
cliente.

**Mitigación:** manejador genérico de excepciones en `server/app/main.py`
que responde siempre `{"error": "Error interno del servidor"}` con 500,
registrando el traceback real solo en el log del servidor (no en la
respuesta al cliente).

## 7. Saturación de la API por un usuario ya autenticado

**Riesgo:** el bloqueo de intentos fallidos del punto 2 solo protege
`/api/auth/login`. Un usuario ya autenticado (o alguien con un token
robado) podría, en teoría, saturar cualquier otro endpoint con solicitudes
repetidas.

**Mitigación** (`server/app/rate_limit.py`): límite general de 120
solicitudes/minuto por identidad (por usuario del token si es válido, si no
por IP — mismo criterio que el bloqueo de login), aplicado a toda la API
salvo `/health` vía `RateLimitMiddleware`. Devuelve 429 con el mismo
contrato `{"error": ...}` del resto de la API.

**Limitación aceptada:** ventana fija en memoria del proceso, misma
limitación que el bloqueo de login del punto 2 (no se comparte entre
instancias); permite hasta ~2x el límite justo en el borde de dos ventanas
consecutivas, aceptable para frenar abuso sostenido, no para contar
solicitudes con precisión.

## Fuera de alcance / riesgos no cubiertos todavía

- **CSRF:** no aplica mientras la sesión viaje por header `Authorization`
  (no por cookie) — si en algún momento se cambia a cookies, esto habría
  que revisarlo de nuevo.
- **HTTPS:** se asume que la terminación TLS la maneja el hosting/proxy en
  producción; la app en sí no la fuerza.
