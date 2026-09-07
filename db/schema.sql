-- Sistema de Detección de Pesca Ilegal
-- Esquema de base de datos (PostgreSQL 14+)
-- Cubre: login institucional, monitoreo en mapa, registro de incidentes,
-- cola de validación de noticias por IA, y las vistas que alimentan el
-- dashboard de reportes.
--
-- Fuente de datos de embarcaciones/eventos: API de Global Fishing Watch
-- (Vessels API + Events API: encounter, loitering, port_visit, fishing,
-- gap/AIS disabling; + 4Wings Report API para esfuerzo agregado).
-- "embarcaciones" guarda la identidad tal como la entrega GFW (mmsi/imo/
-- callsign/gfw_vessel_id + flag + vessel/gear type); "eventos_gfw" es la
-- bandeja de aterrizaje cruda de eventos puntuales de la Events API antes
-- de convertirse en una alerta o un incidente confirmado; y
-- "esfuerzo_pesquero_gfw" guarda las filas agregadas del 4Wings Report
-- (horas de pesca por celda/periodo) para estadística, no para alertas.

CREATE EXTENSION IF NOT EXISTS pgcrypto; -- gen_random_uuid()

-- =========================================================
-- Tipos enumerados
-- =========================================================

CREATE TYPE rol_usuario AS ENUM ('administrador', 'supervisor', 'analista');

CREATE TYPE tipo_embarcacion AS ENUM ('pesca_artesanal', 'pesca_industrial', 'carga', 'otro');

CREATE TYPE gravedad_incidente AS ENUM ('alto', 'medio', 'bajo');

CREATE TYPE estado_incidente AS ENUM ('sospechoso', 'confirmado', 'descartado');

CREATE TYPE estado_alerta AS ENUM ('activa', 'registrada', 'descartada');

CREATE TYPE estado_fuente AS ENUM ('pendiente', 'procesando', 'exitosa', 'fallida');

CREATE TYPE estado_sugerencia AS ENUM ('pendiente', 'aprobado', 'rechazado');

CREATE TYPE color_indicador AS ENUM ('red', 'amber', 'gray', 'dark');

-- Tipos de evento de la Events API de Global Fishing Watch
CREATE TYPE tipo_evento_gfw AS ENUM ('encuentro', 'merodeo', 'visita_puerto', 'pesca', 'vacio_ais');

-- =========================================================
-- Usuarios institucionales (LoginPage)
-- =========================================================

CREATE TABLE usuarios (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  usuario varchar(60) NOT NULL UNIQUE,       -- ej: inicial.apellido
  password_hash text NOT NULL,
  nombre_completo varchar(150) NOT NULL,
  rol rol_usuario NOT NULL DEFAULT 'analista',
  direccion varchar(150) NOT NULL DEFAULT 'Dirección de Supervisión',
  activo boolean NOT NULL DEFAULT true,
  ultimo_acceso timestamptz,
  creado_en timestamptz NOT NULL DEFAULT now()
);

-- =========================================================
-- Catálogos de referencia
-- =========================================================

CREATE TABLE zonas (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  nombre varchar(100) NOT NULL,
  region varchar(100) NOT NULL,
  es_critica boolean NOT NULL DEFAULT false,
  -- Polígono GeoJSON (coordenadas ingresadas manualmente en el sistema) usado
  -- para consultar el 4Wings Report de GFW y detectar embarcaciones dentro de
  -- la zona (patrón "zona_protegida" de detección de irregularidades).
  poligono jsonb,
  creado_en timestamptz NOT NULL DEFAULT now(),
  UNIQUE (nombre, region)
);

CREATE TABLE tipos_infraccion (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  nombre varchar(150) NOT NULL UNIQUE,
  color_indicador color_indicador NOT NULL DEFAULT 'gray',
  gravedad_sugerida gravedad_incidente NOT NULL DEFAULT 'medio'
);

-- =========================================================
-- Embarcaciones
-- =========================================================

CREATE TABLE embarcaciones (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  nombre varchar(150) NOT NULL,

  -- Identidad: una embarcación con AIS trae mmsi (+ opcionalmente imo/
  -- callsign) desde GFW; una artesanal sin AIS puede existir solo con su
  -- matrícula del registro pesquero nacional.
  mmsi varchar(9) UNIQUE,
  imo varchar(10) UNIQUE,
  callsign varchar(20),
  matricula varchar(30) UNIQUE,
  gfw_vessel_id varchar(64) UNIQUE,          -- id propio de Global Fishing Watch

  bandera varchar(3),                         -- país de bandera, ISO-3166 alpha-3 (ej: PER, PAN)
  tipo tipo_embarcacion NOT NULL DEFAULT 'otro', -- clasificación simplificada usada en la UI
  gfw_vessel_type varchar(40),                -- valor crudo de GFW: fishing/carrier/support/...
  gfw_gear_type varchar(60),                  -- arte de pesca cruda de GFW: trawlers/purse_seines/...
  primera_transmision_ais timestamptz,
  ultima_transmision_ais timestamptz,

  capturada boolean NOT NULL DEFAULT false,
  capturada_en timestamptz,
  creado_en timestamptz NOT NULL DEFAULT now(),

  CONSTRAINT chk_embarcacion_tiene_identidad
    CHECK (mmsi IS NOT NULL OR imo IS NOT NULL OR matricula IS NOT NULL OR gfw_vessel_id IS NOT NULL)
);

CREATE INDEX idx_embarcaciones_gfw_vessel_id ON embarcaciones (gfw_vessel_id);

-- =========================================================
-- Eventos crudos de Global Fishing Watch (Events API)
-- =========================================================
-- Bandeja de aterrizaje de la ingesta: cada fila es un evento tal como lo
-- entrega GFW (encounter/loitering/port_visit/fishing/gap). Un job de
-- ingesta hace upsert por gfw_event_id; un analista (o una regla
-- automática) decide si genera una alerta de monitoreo y/o un incidente,
-- igual que el flujo de "Cola de Validación IA" de Noticias.

CREATE TABLE eventos_gfw (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  gfw_event_id varchar(100) NOT NULL UNIQUE, -- id del evento en GFW, para deduplicar la ingesta
  tipo tipo_evento_gfw NOT NULL,
  embarcacion_id uuid REFERENCES embarcaciones (id), -- null si el vessel aún no fue resuelto/creado
  zona_id uuid REFERENCES zonas (id),         -- resuelta cruzando "regiones" (EEZ/MPA/RFMO) del evento

  inicio timestamptz NOT NULL,
  fin timestamptz,
  latitud numeric(9, 6),
  longitud numeric(9, 6),
  velocidad_nudos numeric(5, 1),
  distancia_costa_km numeric(7, 2),
  distancia_puerto_km numeric(7, 2),
  regiones jsonb,                             -- EEZ/MPA/RFMO reportadas por GFW para el evento
  payload_raw jsonb NOT NULL,                 -- respuesta cruda de la API, para trazabilidad/reproceso

  estado estado_sugerencia NOT NULL DEFAULT 'pendiente',
  incidente_id uuid,                          -- FK diferida a incidentes (se agrega más abajo)
  creado_en timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX idx_eventos_gfw_estado ON eventos_gfw (estado);
CREATE INDEX idx_eventos_gfw_tipo ON eventos_gfw (tipo);
CREATE INDEX idx_eventos_gfw_embarcacion ON eventos_gfw (embarcacion_id);
CREATE INDEX idx_eventos_gfw_inicio ON eventos_gfw (inicio DESC);

-- =========================================================
-- Esfuerzo pesquero (4Wings Report API de Global Fishing Watch)
-- =========================================================
-- Filas planas de esfuerzo pesquero agregado por embarcación / celda /
-- periodo (campos "hours", "date" como rango, lat/lon de celda). A
-- diferencia de eventos_gfw, aquí una fila NO es un evento puntual con id
-- propio, sino una agregación estadística — sirve para reportes/mapas de
-- calor de esfuerzo, no para generar una alerta o un incidente individual.

CREATE TABLE esfuerzo_pesquero_gfw (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  embarcacion_id uuid REFERENCES embarcaciones (id), -- resuelta por mmsi/gfw_vessel_id al ingestar
  gfw_vessel_id varchar(64),
  mmsi varchar(9),
  imo varchar(10),
  callsign varchar(20),
  ship_name varchar(150),
  flag varchar(3),
  vessel_type varchar(40),
  geartype varchar(60),
  dataset varchar(100),

  rango_desde date,                           -- primer valor del campo "date" (rango de consulta)
  rango_hasta date,                           -- segundo valor del campo "date"
  entry_timestamp timestamptz,
  exit_timestamp timestamptz,
  primera_transmision_ais timestamptz,
  ultima_transmision_ais timestamptz,

  horas numeric(10, 4) NOT NULL,              -- horas de pesca aparente en la celda/periodo
  latitud numeric(9, 6),                      -- centroide de la celda (no la posición exacta de un evento)
  longitud numeric(9, 6),

  payload_raw jsonb NOT NULL,
  creado_en timestamptz NOT NULL DEFAULT now(),

  -- clave natural para upsert idempotente al reingestar el mismo reporte
  UNIQUE (gfw_vessel_id, entry_timestamp, exit_timestamp, latitud, longitud)
);

CREATE INDEX idx_esfuerzo_embarcacion ON esfuerzo_pesquero_gfw (embarcacion_id);
CREATE INDEX idx_esfuerzo_mmsi ON esfuerzo_pesquero_gfw (mmsi);
CREATE INDEX idx_esfuerzo_entry ON esfuerzo_pesquero_gfw (entry_timestamp);

-- =========================================================
-- Alertas de monitoreo (mapa en tiempo real / AlertCard)
-- =========================================================

CREATE TABLE alertas_monitoreo (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  embarcacion_id uuid NOT NULL REFERENCES embarcaciones (id),
  origen_evento_gfw_id uuid REFERENCES eventos_gfw (id),
  descripcion text NOT NULL,
  velocidad_nudos numeric(5, 1),
  rumbo_grados smallint CHECK (rumbo_grados BETWEEN 0 AND 360),
  latitud numeric(9, 6) NOT NULL,
  longitud numeric(9, 6) NOT NULL,
  estado estado_alerta NOT NULL DEFAULT 'activa',
  creado_en timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX idx_alertas_estado ON alertas_monitoreo (estado);
CREATE INDEX idx_alertas_embarcacion ON alertas_monitoreo (embarcacion_id);

-- =========================================================
-- Incidentes (IncidentsPage / registro central)
-- =========================================================

CREATE SEQUENCE incidentes_codigo_seq;

CREATE TABLE incidentes (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  codigo varchar(20) NOT NULL UNIQUE,        -- ej: INC-2023-089
  embarcacion_id uuid REFERENCES embarcaciones (id),
  zona_id uuid REFERENCES zonas (id),
  tipo_infraccion_id uuid NOT NULL REFERENCES tipos_infraccion (id),
  descripcion text,
  gravedad gravedad_incidente NOT NULL,
  estado estado_incidente NOT NULL DEFAULT 'sospechoso',
  latitud numeric(9, 6),
  longitud numeric(9, 6),
  velocidad_nudos numeric(5, 1),
  rumbo_grados smallint CHECK (rumbo_grados BETWEEN 0 AND 360),
  fecha_deteccion timestamptz NOT NULL DEFAULT now(),
  registrado_por uuid REFERENCES usuarios (id),
  origen_alerta_id uuid REFERENCES alertas_monitoreo (id),
  origen_evento_gfw_id uuid REFERENCES eventos_gfw (id),
  creado_en timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX idx_incidentes_fecha ON incidentes (fecha_deteccion DESC);
CREATE INDEX idx_incidentes_gravedad ON incidentes (gravedad);
CREATE INDEX idx_incidentes_zona ON incidentes (zona_id);
CREATE INDEX idx_incidentes_tipo_infraccion ON incidentes (tipo_infraccion_id);

-- Cierra la referencia diferida desde eventos_gfw.incidente_id (la tabla
-- eventos_gfw se crea antes que incidentes, así que la FK se agrega aquí).
ALTER TABLE eventos_gfw
  ADD CONSTRAINT fk_eventos_gfw_incidente FOREIGN KEY (incidente_id) REFERENCES incidentes (id);

CREATE INDEX idx_eventos_gfw_incidente ON eventos_gfw (incidente_id);

-- Autogenera "INC-<año>-<correlativo>" cuando no se envía código explícito
CREATE OR REPLACE FUNCTION fn_generar_codigo_incidente()
RETURNS trigger AS $$
BEGIN
  IF NEW.codigo IS NULL THEN
    NEW.codigo := 'INC-' || to_char(now(), 'YYYY') || '-' ||
                  lpad(nextval('incidentes_codigo_seq')::text, 3, '0');
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_generar_codigo_incidente
  BEFORE INSERT ON incidentes
  FOR EACH ROW
  EXECUTE FUNCTION fn_generar_codigo_incidente();

-- =========================================================
-- Noticias: cola de fuentes analizadas + sugerencias de IA
-- =========================================================

CREATE TABLE fuentes_noticias (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  url text NOT NULL,
  dominio varchar(150) NOT NULL,
  estado estado_fuente NOT NULL DEFAULT 'pendiente',
  enviado_por uuid REFERENCES usuarios (id),
  creado_en timestamptz NOT NULL DEFAULT now(),
  procesado_en timestamptz
);

CREATE INDEX idx_fuentes_estado ON fuentes_noticias (estado);

CREATE TABLE incidentes_sugeridos_ia (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  fuente_id uuid NOT NULL REFERENCES fuentes_noticias (id) ON DELETE CASCADE,
  titular text NOT NULL,
  resumen text,
  tipo_infraccion_id uuid REFERENCES tipos_infraccion (id),
  embarcacion_detectada varchar(200),        -- texto libre extraído por NLP
  ubicacion_estimada varchar(150),
  confianza numeric(4, 3) CHECK (confianza BETWEEN 0 AND 1),
  estado estado_sugerencia NOT NULL DEFAULT 'pendiente',
  incidente_id uuid REFERENCES incidentes (id), -- se enlaza al aprobarse
  creado_en timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX idx_sugerencias_estado ON incidentes_sugeridos_ia (estado);
CREATE INDEX idx_sugerencias_fuente ON incidentes_sugeridos_ia (fuente_id);

-- =========================================================
-- Vistas para el dashboard de reportes (ReportsPage)
-- =========================================================

-- Tarjetas de resumen: Total Incidentes / Embarc. Capturadas /
-- Alertas Procesadas / Zonas Críticas
CREATE OR REPLACE VIEW vw_reportes_resumen AS
SELECT
  (SELECT count(*) FROM incidentes) AS total_incidentes,
  (SELECT count(*) FROM embarcaciones WHERE capturada) AS embarcaciones_capturadas,
  (SELECT count(*) FROM alertas_monitoreo WHERE estado <> 'activa') AS alertas_procesadas,
  (SELECT count(*) FROM zonas WHERE es_critica) AS zonas_criticas;

-- Evolución de Incidentes (Últimos 12 Meses)
CREATE OR REPLACE VIEW vw_incidentes_por_mes AS
SELECT
  date_trunc('month', fecha_deteccion)::date AS mes,
  count(*) AS total
FROM incidentes
WHERE fecha_deteccion >= date_trunc('month', now()) - interval '11 months'
GROUP BY 1
ORDER BY 1;

-- Tipos de Infracciones (donut + leyenda con porcentaje)
CREATE OR REPLACE VIEW vw_tipos_infraccion_resumen AS
SELECT
  ti.nombre,
  ti.color_indicador,
  count(i.id) AS total,
  round(100.0 * count(i.id) / NULLIF(sum(count(i.id)) OVER (), 0), 1) AS porcentaje
FROM tipos_infraccion ti
LEFT JOIN incidentes i ON i.tipo_infraccion_id = ti.id
GROUP BY ti.id, ti.nombre, ti.color_indicador
ORDER BY total DESC;

-- Zonas con Mayor Incidencia (ranking)
CREATE OR REPLACE VIEW vw_zonas_top AS
SELECT
  z.nombre,
  z.region,
  count(i.id) AS total_incidentes,
  rank() OVER (ORDER BY count(i.id) DESC) AS ranking
FROM zonas z
JOIN incidentes i ON i.zona_id = z.id
GROUP BY z.id, z.nombre, z.region
ORDER BY total_incidentes DESC;
