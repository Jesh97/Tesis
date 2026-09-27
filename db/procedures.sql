-- Sistema de Detección de Pesca Ilegal
-- Procedimientos/funciones almacenadas: TODO el acceso a datos del backend
-- (server/app/routes/*.py) pasa por una de las funciones de este archivo en
-- vez de SQL embebido en Python. El objetivo es que el rol con el que corre
-- la API en runtime (ver db/roles.sql -> "app_runtime") no tenga NINGÚN
-- permiso directo de SELECT/INSERT/UPDATE/DELETE sobre las tablas: solo
-- puede invocar estas funciones, ya validadas, con parámetros tipados.
--
-- Convención de errores de negocio (duplicados, no encontrado, etc.): la
-- función hace `RAISE EXCEPTION '<codigo_http>|<mensaje para el usuario>'`.
-- server/app/db.py (ejecutar_sp) atrapa esa excepción y la traduce a un
-- HTTPException con ese status_code y ese mensaje -- así cada ruta de
-- FastAPI no repite el try/except, y el mensaje que ve el frontend no cambia
-- respecto a como era antes de esta migración.
--
-- Todas están en SECURITY DEFINER: corren con los privilegios de quien las
-- creó (el dueño de las tablas), no con los del rol que las invoca -- por
-- eso "app_runtime" puede leer/escribir datos sin tener grants directos.
-- `SET search_path = public` evita que alguien con permiso de crear objetos
-- en otro schema pueda "secuestrar" la función apuntando a una tabla falsa
-- con el mismo nombre.
--
-- Aplicar después de db/schema.sql y antes de db/roles.sql:
--   psql "$DATABASE_URL" -f db/schema.sql
--   psql "$DATABASE_URL" -f db/procedures.sql
--   psql "$DATABASE_URL" -f db/roles.sql

-- =========================================================
-- Usuarios (login)
-- =========================================================

CREATE OR REPLACE FUNCTION sp_usuarios_buscar_para_login(p_usuario varchar)
RETURNS TABLE (
  id uuid,
  usuario varchar,
  password_hash text,
  nombre_completo varchar,
  rol rol_usuario,
  activo boolean
)
SECURITY DEFINER SET search_path = public
LANGUAGE plpgsql AS $$
BEGIN
  RETURN QUERY
  SELECT u.id, u.usuario, u.password_hash, u.nombre_completo, u.rol, u.activo
  FROM usuarios u
  WHERE u.usuario = p_usuario;
END;
$$;

CREATE OR REPLACE FUNCTION sp_usuarios_marcar_acceso(p_id uuid)
RETURNS void
SECURITY DEFINER SET search_path = public
LANGUAGE plpgsql AS $$
BEGIN
  UPDATE usuarios SET ultimo_acceso = now() WHERE id = p_id;
END;
$$;

-- =========================================================
-- Incidentes
-- =========================================================

DROP FUNCTION IF EXISTS sp_incidentes_listar(date, date, tipo_embarcacion, gravedad_incidente);

CREATE OR REPLACE FUNCTION sp_incidentes_listar(
  p_desde date DEFAULT NULL,
  p_hasta date DEFAULT NULL,
  p_tipo tipo_embarcacion DEFAULT NULL,
  p_gravedad gravedad_incidente DEFAULT NULL
)
RETURNS TABLE (
  codigo varchar,
  vessel varchar,
  vessel_verificado boolean,
  mmsi varchar,
  matricula varchar,
  infraction text,
  fecha_deteccion timestamptz,
  severity gravedad_incidente,
  estado estado_incidente,
  latitud numeric,
  longitud numeric
)
SECURITY DEFINER SET search_path = public
LANGUAGE plpgsql AS $$
BEGIN
  RETURN QUERY
  SELECT
    i.codigo,
    -- Nombre real (vinculado a GFW) si existe; si no, el nombre que reportó
    -- la fuente sin verificar (ver embarcacion_nombre_reportado); si tampoco
    -- hay eso, NULL -> el route lo muestra como "Desconocido".
    coalesce(e.nombre, i.embarcacion_nombre_reportado),
    (e.nombre IS NOT NULL),
    e.mmsi,
    e.matricula,
    i.descripcion,
    i.fecha_deteccion,
    i.gravedad,
    i.estado,
    i.latitud,
    i.longitud
  FROM incidentes i
  LEFT JOIN embarcaciones e ON e.id = i.embarcacion_id
  WHERE (p_desde IS NULL OR i.fecha_deteccion >= p_desde)
    AND (p_hasta IS NULL OR i.fecha_deteccion < (p_hasta + interval '1 day'))
    AND (p_tipo IS NULL OR e.tipo = p_tipo)
    AND (p_gravedad IS NULL OR i.gravedad = p_gravedad)
  ORDER BY i.fecha_deteccion DESC;
END;
$$;

-- Mmsi con incidente confirmado (mapa: resaltar embarcación en rojo).
CREATE OR REPLACE FUNCTION sp_incidentes_mmsi_con_incidente()
RETURNS TABLE (mmsi varchar)
SECURITY DEFINER SET search_path = public
LANGUAGE plpgsql AS $$
BEGIN
  RETURN QUERY
  SELECT DISTINCT e.mmsi
  FROM incidentes i
  JOIN embarcaciones e ON e.id = i.embarcacion_id
  WHERE e.mmsi IS NOT NULL AND i.estado = 'confirmado';
END;
$$;

-- Mmsi con incidente activo (no descartado): para no repetir una alerta de
-- monitoreo ya reportada, incluso tras recargar el mapa.
CREATE OR REPLACE FUNCTION sp_incidentes_mmsi_reportados()
RETURNS TABLE (mmsi varchar)
SECURITY DEFINER SET search_path = public
LANGUAGE plpgsql AS $$
BEGIN
  RETURN QUERY
  SELECT DISTINCT e.mmsi
  FROM incidentes i
  JOIN embarcaciones e ON e.id = i.embarcacion_id
  WHERE e.mmsi IS NOT NULL AND i.estado <> 'descartado';
END;
$$;

CREATE OR REPLACE FUNCTION sp_incidentes_descartar(p_codigo varchar)
RETURNS void
SECURITY DEFINER SET search_path = public
LANGUAGE plpgsql AS $$
BEGIN
  UPDATE incidentes SET estado = 'descartado' WHERE codigo = p_codigo;
  IF NOT FOUND THEN
    RAISE EXCEPTION '404|No existe el incidente "%"', p_codigo;
  END IF;
END;
$$;

CREATE OR REPLACE FUNCTION sp_incidentes_confirmar(p_codigo varchar)
RETURNS void
SECURITY DEFINER SET search_path = public
LANGUAGE plpgsql AS $$
DECLARE
  v_estado estado_incidente;
BEGIN
  UPDATE incidentes SET estado = 'confirmado'
    WHERE codigo = p_codigo AND estado = 'sospechoso';
  IF FOUND THEN
    RETURN;
  END IF;

  SELECT i.estado INTO v_estado FROM incidentes i WHERE i.codigo = p_codigo;
  IF v_estado IS NULL THEN
    RAISE EXCEPTION '404|No existe el incidente "%"', p_codigo;
  END IF;
  RAISE EXCEPTION '409|El incidente "%" ya está en estado "%", no en "sospechoso"', p_codigo, v_estado;
END;
$$;

CREATE OR REPLACE FUNCTION sp_tipos_infraccion_listar()
RETURNS TABLE (id uuid, nombre varchar, gravedad_sugerida gravedad_incidente)
SECURITY DEFINER SET search_path = public
LANGUAGE plpgsql AS $$
BEGIN
  RETURN QUERY
  SELECT ti.id, ti.nombre, ti.gravedad_sugerida FROM tipos_infraccion ti ORDER BY ti.nombre;
END;
$$;

CREATE OR REPLACE FUNCTION sp_tipos_infraccion_obtener(p_id uuid)
RETURNS TABLE (id uuid, gravedad_sugerida gravedad_incidente)
SECURITY DEFINER SET search_path = public
LANGUAGE plpgsql AS $$
BEGIN
  RETURN QUERY
  SELECT ti.id, ti.gravedad_sugerida FROM tipos_infraccion ti WHERE ti.id = p_id;
END;
$$;

CREATE OR REPLACE FUNCTION sp_tipos_infraccion_obtener_por_nombre(p_nombre varchar)
RETURNS TABLE (id uuid, gravedad_sugerida gravedad_incidente)
SECURITY DEFINER SET search_path = public
LANGUAGE plpgsql AS $$
BEGIN
  RETURN QUERY
  SELECT ti.id, ti.gravedad_sugerida FROM tipos_infraccion ti WHERE ti.nombre = p_nombre;
END;
$$;

-- Busca la embarcación por mmsi; si no existe, la crea. Devuelve NULL si no
-- se pasó mmsi (reporte manual solo con nombre) o si hubo una carrera con
-- otra inserción concurrente del mismo mmsi (se sigue sin vincular, igual
-- que en el código Python original).
-- p_matricula es una identidad alternativa al mmsi: cubre embarcaciones
-- artesanales sin AIS que un artículo reporta con su matrícula de pesca
-- (ej. "matrícula 37499-BM", ver extraccion_reglas.py) pero que nunca van a
-- aparecer en una búsqueda de GFW porque no transmiten. Prioridad: mmsi
-- primero (viene verificado contra GFW), matrícula como respaldo (viene
-- directo del texto, sin verificación externa -- pero matrícula SÍ es una
-- identidad válida según chk_embarcacion_tiene_identidad, a diferencia de un
-- nombre suelto). Si no hay ninguna de las dos, sigue sin poder crear la fila.
DROP FUNCTION IF EXISTS sp_embarcaciones_vincular_o_crear(varchar, varchar, varchar, varchar);

CREATE OR REPLACE FUNCTION sp_embarcaciones_vincular_o_crear(
  p_mmsi varchar,
  p_vessel_name varchar,
  p_bandera varchar,
  p_gfw_vessel_type varchar,
  p_matricula varchar DEFAULT NULL
)
RETURNS uuid
SECURITY DEFINER SET search_path = public
LANGUAGE plpgsql AS $$
DECLARE
  v_id uuid;
  v_mmsi varchar;
  v_tipo tipo_embarcacion;
BEGIN
  IF p_mmsi IS NULL AND p_matricula IS NULL THEN
    RETURN NULL;
  END IF;

  IF p_mmsi IS NOT NULL THEN
    v_mmsi := left(p_mmsi, 9);
    SELECT e.id INTO v_id FROM embarcaciones e WHERE e.mmsi = v_mmsi;
    IF v_id IS NOT NULL THEN
      RETURN v_id;
    END IF;
  END IF;

  IF p_matricula IS NOT NULL THEN
    SELECT e.id INTO v_id FROM embarcaciones e WHERE e.matricula = p_matricula;
    IF v_id IS NOT NULL THEN
      RETURN v_id;
    END IF;
  END IF;

  v_tipo := CASE WHEN upper(coalesce(p_gfw_vessel_type, '')) = 'FISHING'
                 THEN 'pesca_industrial'::tipo_embarcacion
                 ELSE 'otro'::tipo_embarcacion END;

  BEGIN
    INSERT INTO embarcaciones (nombre, mmsi, matricula, bandera, tipo, gfw_vessel_type)
    VALUES (coalesce(p_vessel_name, 'Desconocido'), v_mmsi, p_matricula, p_bandera, v_tipo, p_gfw_vessel_type)
    RETURNING id INTO v_id;
    RETURN v_id;
  EXCEPTION WHEN unique_violation THEN
    RETURN NULL;
  END;
END;
$$;

-- Registra un incidente (alerta de monitoreo o reporte manual). Si ya existe
-- un incidente activo (no descartado) para la misma embarcación con el mismo
-- tipo de infracción, rechaza el duplicado en vez de insertar.
--
-- p_zona_id (agregado): antes de esto, NINGÚN incidente creado desde la app
-- en vivo quedaba vinculado a una zona (el parámetro no existía), así que
-- vw_zonas_top/"Zonas con Mayor Incidencia" en el dashboard quedaba siempre
-- vacío pese a haber incidentes reales -- las alertas del mapa (AlertCard)
-- SÍ conocen su zona (zona_protegida/apagon_ais/etc. se calculan por zona
-- crítica), solo que nunca se lo pasaban a este procedimiento. Va al final
-- con DEFAULT NULL para no romper la firma existente: un reporte manual
-- (sin alerta de por medio) sigue sin zona, que es lo correcto.
CREATE OR REPLACE FUNCTION sp_incidentes_registrar(
  p_embarcacion_id uuid,
  p_tipo_infraccion_id uuid,
  p_descripcion text,
  p_gravedad gravedad_incidente,
  p_lat numeric,
  p_lon numeric,
  p_fecha timestamptz,
  p_zona_id uuid DEFAULT NULL
)
RETURNS TABLE (id uuid, codigo varchar)
SECURITY DEFINER SET search_path = public
LANGUAGE plpgsql AS $$
DECLARE
  v_existente varchar;
BEGIN
  IF p_embarcacion_id IS NOT NULL THEN
    SELECT i.codigo INTO v_existente
    FROM incidentes i
    WHERE i.embarcacion_id = p_embarcacion_id
      AND i.tipo_infraccion_id = p_tipo_infraccion_id
      AND i.estado <> 'descartado';
    IF v_existente IS NOT NULL THEN
      RAISE EXCEPTION '409|Ya existe un incidente registrado (%) para esta embarcación con este tipo de infracción', v_existente;
    END IF;
  END IF;

  RETURN QUERY
  INSERT INTO incidentes (embarcacion_id, tipo_infraccion_id, descripcion, gravedad, estado, latitud, longitud, fecha_deteccion, zona_id)
  VALUES (p_embarcacion_id, p_tipo_infraccion_id, p_descripcion, p_gravedad, 'sospechoso', p_lat, p_lon, coalesce(p_fecha, now()), p_zona_id)
  RETURNING incidentes.id, incidentes.codigo;
END;
$$;

-- Igual que sp_incidentes_registrar pero para la aprobación de una
-- sugerencia de IA (sin lat/lon, sin dedup: la sugerencia ya pasó por su
-- propia validación de "pendiente" antes de esto). p_embarcacion_id es
-- opcional: sugerencias.py la resuelve buscando en GFW el nombre que la IA
-- extrajo del artículo (embarcacion_detectada); si no se pudo resolver a una
-- embarcación real, queda NULL igual que antes (ver chk_embarcacion_tiene_identidad
-- en schema.sql: no se puede inventar una fila de embarcación solo con un
-- nombre de texto libre). p_fecha_deteccion es la fecha de PUBLICACIÓN del
-- artículo (trafilatura/htmldate, ver fecha_publicacion en incidentes_sugeridos_ia):
-- se usa en vez de now() porque el hecho ocurrió cuando se publicó la
-- noticia, no cuando el analista aprobó la sugerencia en el sistema. Si no
-- se pudo extraer, cae a now() igual que antes. p_embarcacion_nombre_reportado
-- es el nombre que la IA extrajo del artículo cuando NO se pudo vincular a
-- una embarcación real (p_embarcacion_id queda NULL en ese caso) -- se
-- guarda igual como texto de referencia en vez de perderse, y
-- sp_incidentes_listar lo usa como fallback de display.
DROP FUNCTION IF EXISTS sp_incidentes_registrar_desde_sugerencia(uuid, text, gravedad_incidente);
DROP FUNCTION IF EXISTS sp_incidentes_registrar_desde_sugerencia(uuid, text, gravedad_incidente, uuid);
DROP FUNCTION IF EXISTS sp_incidentes_registrar_desde_sugerencia(uuid, text, gravedad_incidente, uuid, timestamptz);

CREATE OR REPLACE FUNCTION sp_incidentes_registrar_desde_sugerencia(
  p_tipo_infraccion_id uuid,
  p_descripcion text,
  p_gravedad gravedad_incidente,
  p_embarcacion_id uuid DEFAULT NULL,
  p_fecha_deteccion timestamptz DEFAULT NULL,
  p_embarcacion_nombre_reportado varchar DEFAULT NULL
)
RETURNS TABLE (id uuid, codigo varchar)
SECURITY DEFINER SET search_path = public
LANGUAGE plpgsql AS $$
BEGIN
  RETURN QUERY
  INSERT INTO incidentes (embarcacion_id, embarcacion_nombre_reportado, tipo_infraccion_id, descripcion, gravedad, estado, fecha_deteccion)
  VALUES (
    p_embarcacion_id,
    CASE WHEN p_embarcacion_id IS NULL THEN p_embarcacion_nombre_reportado END,
    p_tipo_infraccion_id, p_descripcion, p_gravedad, 'sospechoso', coalesce(p_fecha_deteccion, now())
  )
  RETURNING incidentes.id, incidentes.codigo;
END;
$$;

-- =========================================================
-- Zonas
-- =========================================================

CREATE OR REPLACE FUNCTION sp_zonas_listar()
RETURNS TABLE (id uuid, nombre varchar, region varchar, es_critica boolean, poligono jsonb, creado_en timestamptz)
SECURITY DEFINER SET search_path = public
LANGUAGE plpgsql AS $$
BEGIN
  RETURN QUERY
  SELECT z.id, z.nombre, z.region, z.es_critica, z.poligono, z.creado_en
  FROM zonas z ORDER BY z.creado_en DESC;
END;
$$;

CREATE OR REPLACE FUNCTION sp_zonas_crear(p_nombre varchar, p_region varchar, p_es_critica boolean, p_poligono jsonb)
RETURNS TABLE (id uuid, nombre varchar, region varchar, es_critica boolean, poligono jsonb, creado_en timestamptz)
SECURITY DEFINER SET search_path = public
LANGUAGE plpgsql AS $$
BEGIN
  BEGIN
    RETURN QUERY
    INSERT INTO zonas (nombre, region, es_critica, poligono)
    VALUES (p_nombre, p_region, p_es_critica, p_poligono)
    RETURNING zonas.id, zonas.nombre, zonas.region, zonas.es_critica, zonas.poligono, zonas.creado_en;
  EXCEPTION WHEN unique_violation THEN
    RAISE EXCEPTION '409|Ya existe una zona con ese nombre y región';
  END;
END;
$$;

CREATE OR REPLACE FUNCTION sp_zonas_eliminar(p_id uuid)
RETURNS void
SECURITY DEFINER SET search_path = public
LANGUAGE plpgsql AS $$
BEGIN
  DELETE FROM zonas WHERE id = p_id;
END;
$$;

-- Zonas críticas con polígono (usada por irregularidades.py para consultar
-- GFW dentro de cada una).
CREATE OR REPLACE FUNCTION sp_zonas_criticas()
RETURNS TABLE (id uuid, nombre varchar, region varchar, poligono jsonb)
SECURITY DEFINER SET search_path = public
LANGUAGE plpgsql AS $$
BEGIN
  RETURN QUERY
  SELECT z.id, z.nombre, z.region, z.poligono
  FROM zonas z
  WHERE z.es_critica AND z.poligono IS NOT NULL;
END;
$$;

-- =========================================================
-- Fuentes de noticias
-- =========================================================

-- Evita analizar la misma URL dos veces: si ya existe y sigue en proceso o
-- ya se analizó con éxito, no crea una fila nueva (debe_analizar = false, el
-- llamador la omite del lote a procesar). Si el intento anterior falló,
-- reintenta reutilizando la misma fila en vez de duplicarla.
CREATE OR REPLACE FUNCTION sp_fuentes_crear(p_url text, p_dominio varchar)
RETURNS TABLE (id uuid, debe_analizar boolean, estado_actual estado_fuente)
SECURITY DEFINER SET search_path = public
LANGUAGE plpgsql AS $$
DECLARE
  v_id uuid;
  v_estado estado_fuente;
BEGIN
  SELECT f.id, f.estado INTO v_id, v_estado FROM fuentes_noticias f WHERE f.url = p_url;

  IF v_id IS NULL THEN
    BEGIN
      INSERT INTO fuentes_noticias (url, dominio, estado)
      VALUES (p_url, p_dominio, 'procesando')
      RETURNING fuentes_noticias.id INTO v_id;
      RETURN QUERY SELECT v_id, true, 'procesando'::estado_fuente;
      RETURN;
    EXCEPTION WHEN unique_violation THEN
      -- carrera con otra petición concurrente que envió la misma URL: releer
      SELECT f.id, f.estado INTO v_id, v_estado FROM fuentes_noticias f WHERE f.url = p_url;
    END;
  END IF;

  IF v_estado IN ('fallida', 'descartada') THEN
    UPDATE fuentes_noticias SET estado = 'procesando', procesado_en = NULL WHERE fuentes_noticias.id = v_id;
    RETURN QUERY SELECT v_id, true, 'procesando'::estado_fuente;
  ELSE
    RETURN QUERY SELECT v_id, false, v_estado;
  END IF;
END;
$$;

CREATE OR REPLACE FUNCTION sp_fuentes_listar()
RETURNS TABLE (id uuid, url text, dominio varchar, estado estado_fuente, creado_en timestamptz, procesado_en timestamptz)
SECURITY DEFINER SET search_path = public
LANGUAGE plpgsql AS $$
BEGIN
  RETURN QUERY
  SELECT f.id, f.url, f.dominio, f.estado, f.creado_en, f.procesado_en
  FROM fuentes_noticias f ORDER BY f.creado_en DESC LIMIT 50;
END;
$$;

-- Nombres del catálogo, para el prompt de scripts/analyze_news.py (subproceso
-- lanzado en vivo por POST /api/fuentes/analizar, ver fuentes.py).
CREATE OR REPLACE FUNCTION sp_tipos_infraccion_nombres()
RETURNS TABLE (nombre varchar)
SECURITY DEFINER SET search_path = public
LANGUAGE plpgsql AS $$
BEGIN
  RETURN QUERY SELECT ti.nombre FROM tipos_infraccion ti ORDER BY ti.nombre;
END;
$$;

-- =========================================================
-- Sugerencias de IA (cola de validación)
-- =========================================================

-- Llamada por analyze_news.py antes de crear una sugerencia: ¿ya hay una
-- sugerencia activa (pendiente/aprobada) o un incidente para esta misma
-- embarcación (por nombre o matrícula)? Cubre el caso de que dos medios
-- distintos cubran el mismo hecho con URLs distintas -- sp_fuentes_crear
-- dedupe por URL exacta nomás, así que eso solo no alcanza. p_nombre/p_matricula
-- pueden venir NULL si no se extrajo ninguno; en ese caso no hay con qué
-- comparar y devuelve false.
CREATE OR REPLACE FUNCTION sp_sugerencias_verificar_duplicado(p_nombre varchar, p_matricula varchar)
RETURNS boolean
SECURITY DEFINER SET search_path = public
LANGUAGE plpgsql AS $$
BEGIN
  IF p_nombre IS NULL AND p_matricula IS NULL THEN
    RETURN false;
  END IF;

  IF EXISTS (
    SELECT 1 FROM incidentes_sugeridos_ia s
    WHERE s.estado IN ('pendiente', 'aprobado')
      AND (
        (p_nombre IS NOT NULL AND s.embarcacion_detectada ILIKE p_nombre)
        OR (p_matricula IS NOT NULL AND s.matricula_detectada = p_matricula)
      )
  ) THEN
    RETURN true;
  END IF;

  IF EXISTS (
    SELECT 1 FROM incidentes i
    JOIN embarcaciones e ON e.id = i.embarcacion_id
    WHERE i.estado != 'descartado'
      AND (
        (p_nombre IS NOT NULL AND e.nombre ILIKE p_nombre)
        OR (p_matricula IS NOT NULL AND e.matricula = p_matricula)
      )
  ) THEN
    RETURN true;
  END IF;

  RETURN false;
END;
$$;

DROP FUNCTION IF EXISTS sp_sugerencias_listar_pendientes();

CREATE OR REPLACE FUNCTION sp_sugerencias_listar_pendientes()
RETURNS TABLE (
  id uuid,
  fuente_id uuid,
  titular text,
  resumen text,
  tipo_infraccion_id uuid,
  embarcacion_detectada varchar,
  ubicacion_estimada varchar,
  confianza numeric,
  estado estado_sugerencia,
  incidente_id uuid,
  creado_en timestamptz,
  url text,
  dominio varchar,
  tipo_infraccion_nombre varchar,
  color_indicador color_indicador,
  posible_duplicado boolean
)
SECURITY DEFINER SET search_path = public
LANGUAGE plpgsql AS $$
BEGIN
  RETURN QUERY
  SELECT s.id, s.fuente_id, s.titular, s.resumen, s.tipo_infraccion_id, s.embarcacion_detectada,
         s.ubicacion_estimada, s.confianza, s.estado, s.incidente_id, s.creado_en,
         f.url, f.dominio, ti.nombre, ti.color_indicador, s.posible_duplicado
  FROM incidentes_sugeridos_ia s
  JOIN fuentes_noticias f ON f.id = s.fuente_id
  LEFT JOIN tipos_infraccion ti ON ti.id = s.tipo_infraccion_id
  WHERE s.estado = 'pendiente'
  ORDER BY s.creado_en DESC;
END;
$$;

CREATE OR REPLACE FUNCTION sp_sugerencias_rechazar(p_id uuid)
RETURNS void
SECURITY DEFINER SET search_path = public
LANGUAGE plpgsql AS $$
BEGIN
  UPDATE incidentes_sugeridos_ia SET estado = 'rechazado' WHERE id = p_id;
END;
$$;

DROP FUNCTION IF EXISTS sp_sugerencias_obtener_pendiente(uuid);

CREATE OR REPLACE FUNCTION sp_sugerencias_obtener_pendiente(p_id uuid)
RETURNS TABLE (
  id uuid,
  fuente_id uuid,
  titular text,
  resumen text,
  tipo_infraccion_id uuid,
  gravedad_sugerida gravedad_incidente,
  embarcacion_detectada varchar,
  matricula_detectada varchar,
  fecha_publicacion timestamptz
)
SECURITY DEFINER SET search_path = public
LANGUAGE plpgsql AS $$
BEGIN
  RETURN QUERY
  SELECT s.id, s.fuente_id, s.titular, s.resumen, s.tipo_infraccion_id, ti.gravedad_sugerida, s.embarcacion_detectada, s.matricula_detectada, s.fecha_publicacion
  FROM incidentes_sugeridos_ia s
  LEFT JOIN tipos_infraccion ti ON ti.id = s.tipo_infraccion_id
  WHERE s.id = p_id AND s.estado = 'pendiente';
END;
$$;

CREATE OR REPLACE FUNCTION sp_sugerencias_aprobar_vincular(p_sugerencia_id uuid, p_incidente_id uuid)
RETURNS void
SECURITY DEFINER SET search_path = public
LANGUAGE plpgsql AS $$
BEGIN
  UPDATE incidentes_sugeridos_ia
    SET estado = 'aprobado', incidente_id = p_incidente_id
    WHERE id = p_sugerencia_id;
END;
$$;

-- Crea una sugerencia a partir de lo que extrajo Claude (o la extracción
-- local de reglas, ver scripts/extraccion_reglas.py) en scripts/analyze_news.py
-- (subproceso lanzado en vivo por POST /api/fuentes/analizar).
-- p_fecha_publicacion es la fecha del artículo (trafilatura/htmldate, no la
-- de Claude/reglas): NULL si no se pudo extraer, y en ese caso
-- sp_incidentes_registrar_desde_sugerencia cae a now() al aprobar.
DROP FUNCTION IF EXISTS sp_sugerencias_crear(uuid, text, text, uuid, varchar, varchar, numeric);
DROP FUNCTION IF EXISTS sp_sugerencias_crear(uuid, text, text, uuid, varchar, varchar, numeric, timestamptz);
DROP FUNCTION IF EXISTS sp_sugerencias_crear(uuid, text, text, uuid, varchar, varchar, numeric, timestamptz, varchar);

CREATE OR REPLACE FUNCTION sp_sugerencias_crear(
  p_fuente_id uuid,
  p_titular text,
  p_resumen text,
  p_tipo_infraccion_id uuid,
  p_embarcacion_detectada varchar,
  p_ubicacion_estimada varchar,
  p_confianza numeric,
  p_fecha_publicacion timestamptz DEFAULT NULL,
  p_matricula_detectada varchar DEFAULT NULL,
  p_posible_duplicado boolean DEFAULT false
)
RETURNS void
SECURITY DEFINER SET search_path = public
LANGUAGE plpgsql AS $$
BEGIN
  INSERT INTO incidentes_sugeridos_ia
    (fuente_id, titular, resumen, tipo_infraccion_id, embarcacion_detectada, ubicacion_estimada, confianza, fecha_publicacion, matricula_detectada, posible_duplicado)
  VALUES (p_fuente_id, p_titular, p_resumen, p_tipo_infraccion_id, p_embarcacion_detectada, p_ubicacion_estimada, p_confianza, p_fecha_publicacion, p_matricula_detectada, p_posible_duplicado);
END;
$$;

-- Marca una fuente como procesada (exitosa/fallida), usada tanto por la ruta
-- de descarte inmediato (fuentes.py) como por scripts/analyze_news.py al
-- terminar de analizar cada URL.
CREATE OR REPLACE FUNCTION sp_fuentes_marcar_estado(p_id uuid, p_estado estado_fuente)
RETURNS void
SECURITY DEFINER SET search_path = public
LANGUAGE plpgsql AS $$
BEGIN
  UPDATE fuentes_noticias SET estado = p_estado, procesado_en = now() WHERE id = p_id;
END;
$$;

-- =========================================================
-- Reportes (envuelven las vistas de db/schema.sql)
-- =========================================================

-- Postgres no permite cambiar las columnas de retorno de una función vía
-- CREATE OR REPLACE (a diferencia de solo agregar un parámetro con DEFAULT
-- al final, como en sp_incidentes_registrar arriba) -- hace falta el DROP.
-- Ver el comentario en vw_reportes_resumen (schema.sql) sobre por qué
-- cambiaron las columnas: embarcaciones_capturadas/alertas_procesadas nunca
-- se podían obtener usando la app en vivo.
DROP FUNCTION IF EXISTS sp_reportes_resumen();

CREATE FUNCTION sp_reportes_resumen()
RETURNS TABLE (total_incidentes bigint, incidentes_confirmados bigint, incidentes_pendientes bigint, zonas_criticas bigint)
SECURITY DEFINER SET search_path = public
LANGUAGE plpgsql AS $$
BEGIN
  RETURN QUERY SELECT * FROM vw_reportes_resumen;
END;
$$;

CREATE OR REPLACE FUNCTION sp_reportes_incidentes_por_mes()
RETURNS TABLE (mes date, total bigint)
SECURITY DEFINER SET search_path = public
LANGUAGE plpgsql AS $$
BEGIN
  RETURN QUERY SELECT * FROM vw_incidentes_por_mes;
END;
$$;

CREATE OR REPLACE FUNCTION sp_reportes_tipos_infraccion()
RETURNS TABLE (nombre varchar, color_indicador color_indicador, total bigint, porcentaje numeric)
SECURITY DEFINER SET search_path = public
LANGUAGE plpgsql AS $$
BEGIN
  RETURN QUERY SELECT * FROM vw_tipos_infraccion_resumen;
END;
$$;

CREATE OR REPLACE FUNCTION sp_reportes_zonas_top()
RETURNS TABLE (nombre varchar, region varchar, total_incidentes bigint, ranking bigint)
SECURITY DEFINER SET search_path = public
LANGUAGE plpgsql AS $$
BEGIN
  RETURN QUERY SELECT * FROM vw_zonas_top;
END;
$$;
