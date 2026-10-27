-- Rol con el que corre la API en runtime (server/app/db.py -> DATABASE_URL).
-- A diferencia del rol usado para migraciones (dueño de las tablas, ej.
-- "postgres"), este rol NO tiene ningún permiso directo de SELECT/INSERT/
-- UPDATE/DELETE sobre las tablas: solo puede ejecutar las funciones de
-- db/procedures.sql. Si las credenciales de la app se filtran, quien las
-- tenga puede invocar esas operaciones (ya validadas) pero no correr SQL
-- arbitrario contra las tablas.
--
-- Aplicar DESPUÉS de db/procedures.sql:
--   psql "$DATABASE_URL" -f db/roles.sql
--
-- La contraseña de abajo es un placeholder -- cambiarla enseguida con:
--   ALTER ROLE app_runtime WITH PASSWORD 'una-clave-larga-y-aleatoria';
-- y actualizar DATABASE_URL en server/.env para conectar como app_runtime
-- en vez del rol dueño de las tablas.

DO $$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'app_runtime') THEN
    CREATE ROLE app_runtime LOGIN PASSWORD 'cambiar-esta-clave';
  END IF;
END $$;

DO $$
BEGIN
  EXECUTE format('GRANT CONNECT ON DATABASE %I TO app_runtime', current_database());
END $$;

GRANT USAGE ON SCHEMA public TO app_runtime;

-- Se revoca explícitamente todo acceso directo a tablas/secuencias/funciones
-- para que el modelo de privilegios no dependa de "nunca se otorgó nada":
-- queda declarado que la única vía es EXECUTE en las funciones de abajo.
REVOKE ALL ON ALL TABLES IN SCHEMA public FROM app_runtime;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM app_runtime;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA public FROM PUBLIC;

GRANT EXECUTE ON FUNCTION
  sp_usuarios_buscar_para_login(varchar),
  sp_usuarios_marcar_acceso(uuid),
  sp_usuarios_listar(),
  sp_usuarios_crear(varchar, text, varchar, rol_usuario, uuid),
  sp_usuarios_cambiar_password(uuid, text, uuid),
  sp_usuarios_cambiar_estado(uuid, boolean, uuid),
  sp_incidentes_listar(date, date, tipo_embarcacion, gravedad_incidente),
  sp_incidentes_mmsi_con_incidente(),
  sp_incidentes_mmsi_reportados(),
  -- p_usuario_id (para la auditoría, ver db/schema.sql:auditoria) es un
  -- parámetro nuevo al final con DEFAULT NULL: como con p_zona_id más abajo,
  -- esto reemplaza la función existente en el catálogo (no crea un overload)
  -- pero cambia su firma catalogada a 2 argumentos.
  sp_incidentes_descartar(varchar, uuid),
  sp_incidentes_confirmar(varchar, uuid),
  -- Firma completa con los 9 parámetros declarados (p_zona_id y p_usuario_id,
  -- ambos DEFAULT NULL): un GRANT con una firma más corta fallaría, porque
  -- CREATE OR REPLACE con un parámetro nuevo al final cambia la firma
  -- catalogada de la función aunque siga siendo invocable con menos argumentos.
  sp_incidentes_registrar(uuid, uuid, text, gravedad_incidente, numeric, numeric, timestamptz, uuid, uuid),
  sp_incidentes_registrar_desde_sugerencia(uuid, text, gravedad_incidente, uuid, timestamptz, varchar),
  sp_tipos_infraccion_listar(),
  sp_tipos_infraccion_obtener(uuid),
  sp_tipos_infraccion_obtener_por_nombre(varchar),
  sp_embarcaciones_vincular_o_crear(varchar, varchar, varchar, varchar, varchar),
  sp_zonas_listar(),
  sp_zonas_crear(varchar, varchar, boolean, jsonb, uuid),
  sp_zonas_eliminar(uuid, uuid),
  sp_zonas_criticas(),
  sp_fuentes_crear(text, varchar, uuid),
  sp_fuentes_listar(),
  sp_sugerencias_listar_pendientes(),
  sp_sugerencias_rechazar(uuid, uuid),
  sp_sugerencias_obtener_pendiente(uuid),
  sp_sugerencias_aprobar_vincular(uuid, uuid, uuid),
  sp_sugerencias_verificar_duplicado(varchar, varchar),
  sp_sugerencias_crear(uuid, text, text, uuid, varchar, varchar, numeric, timestamptz, varchar, boolean),
  sp_tipos_infraccion_nombres(),
  sp_fuentes_marcar_estado(uuid, estado_fuente),
  sp_reportes_resumen(),
  sp_reportes_incidentes_por_mes(),
  sp_reportes_incidentes_por_mes_rango(date, date),
  sp_reportes_tipos_infraccion(),
  sp_reportes_zonas_top(),
  -- sp_auditoria_registrar (procedures.sql) NO se otorga a propósito: solo
  -- la llaman las funciones de arriba desde adentro, con privilegios ya
  -- elevados -- ver el comentario en su definición.
  sp_auditoria_listar(int)
TO app_runtime;
