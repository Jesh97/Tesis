-- Datos de ejemplo — reflejan exactamente los mocks usados en el frontend
-- (LoginPage, MonitoringPage, IncidentsPage, NewsPage, ReportsPage) y el
-- flujo de ingesta desde Global Fishing Watch (eventos_gfw), para poder
-- probar el esquema de db/schema.sql de punta a punta.
--
-- Nota: los KPIs grandes que se ven en el diseño (1,245 incidentes, 3,890
-- alertas, etc.) son valores ilustrativos del mockup. Este seed inserta un
-- conjunto pequeño y coherente de filas — suficiente para validar el
-- esquema y las vistas — no para reproducir esas cifras literalmente.

BEGIN;

-- =========================================================
-- Usuarios
-- =========================================================

INSERT INTO usuarios (id, usuario, password_hash, nombre_completo, rol, direccion) VALUES
  ('11111111-1111-1111-1111-111111111111', 'j.perez', crypt('changeme', gen_salt('bf')), 'Jorge Pérez', 'supervisor', 'Dirección de Supervisión'),
  ('11111111-1111-1111-1111-111111111112', 'a.rojas', crypt('changeme', gen_salt('bf')), 'Ana Rojas', 'analista', 'Dirección de Supervisión');

-- =========================================================
-- Zonas
-- =========================================================

INSERT INTO zonas (id, nombre, region, es_critica) VALUES
  ('22222222-2222-2222-2222-222222222221', 'Paita', 'Norte', true),
  ('22222222-2222-2222-2222-222222222222', 'Chimbote', 'Centro-Norte', true),
  ('22222222-2222-2222-2222-222222222223', 'Callao', 'Centro', true),
  ('22222222-2222-2222-2222-222222222224', 'Reserva de Paracas', 'Ica', true),
  ('22222222-2222-2222-2222-222222222225', 'Mar de Grau', 'Zona Económica Exclusiva', true);

-- =========================================================
-- Tipos de infracción
-- =========================================================

INSERT INTO tipos_infraccion (id, nombre, color_indicador, gravedad_sugerida) VALUES
  ('33333333-3333-3333-3333-333333333331', 'Pesca en Zona Prohibida', 'red', 'alto'),
  ('33333333-3333-3333-3333-333333333332', 'Falta de Permiso', 'dark', 'medio'),
  ('33333333-3333-3333-3333-333333333333', 'Transbordo Ilegal', 'amber', 'alto'),
  ('33333333-3333-3333-3333-333333333334', 'Contaminación', 'gray', 'medio'),
  ('33333333-3333-3333-3333-333333333335', 'Pérdida de Señal AIS', 'amber', 'medio'),
  ('33333333-3333-3333-3333-333333333336', 'Velocidad Inusual', 'gray', 'bajo'),
  ('33333333-3333-3333-3333-333333333337', 'Encuentro Sospechoso en Alta Mar', 'red', 'alto'),
  ('33333333-3333-3333-3333-333333333338', 'Incursión en Zona Económica Exclusiva', 'red', 'alto'),
  ('33333333-3333-3333-3333-333333333339', 'Visita a Puerto no Autorizado', 'dark', 'medio');

-- =========================================================
-- Embarcaciones
-- =========================================================
-- mmsi/imo/callsign/gfw_vessel_id como los entregaría la Vessels API de
-- GFW; "matricula" es el registro pesquero nacional (aplica sobre todo a
-- artesanales sin AIS, como San Pedro Pescador, que por eso no tiene GFW).

INSERT INTO embarcaciones
  (id, nombre, mmsi, imo, matricula, gfw_vessel_id, bandera, tipo, gfw_vessel_type, gfw_gear_type, primera_transmision_ais, ultima_transmision_ais) VALUES
  ('44444444-4444-4444-4444-444444444441', 'T/N Albatros', '760445920', NULL, 'PL-4920-ZM', 'gfw-8f2a1c90', 'PER', 'pesca_industrial', 'fishing', 'trawlers', '2021-03-10', now() - interval '10 minutes'),
  ('44444444-4444-4444-4444-444444444442', 'Marde Plata II', '720048123', NULL, NULL, 'gfw-3b7e5d21', 'PER', 'pesca_industrial', 'fishing', 'purse_seines', '2020-06-02', '2023-10-24 15:10:00-05'),
  ('44444444-4444-4444-4444-444444444443', 'Poseidón V', '720098441', NULL, NULL, 'gfw-9a41f6c3', 'PER', 'pesca_industrial', 'fishing', 'drifting_longlines', '2019-11-20', '2023-10-24 07:00:00-05'),
  ('44444444-4444-4444-4444-444444444444', 'San Pedro Pescador', NULL, NULL, 'PT-1123A-CM', NULL, 'PER', 'pesca_artesanal', NULL, NULL, NULL, NULL),
  ('44444444-4444-4444-4444-444444444445', 'Lobo de Mar IX', '720112990', NULL, NULL, 'gfw-1d9c8e77', 'PER', 'carga', 'carrier', NULL, '2022-01-15', '2023-10-23 19:10:00-05'),
  ('44444444-4444-4444-4444-444444444446', 'M/V Ocean Breeze', NULL, '9876543', NULL, 'gfw-6e2b4a10', 'PAN', 'pesca_industrial', 'fishing', 'trawlers', '2018-04-08', now() - interval '3 minutes'),
  ('44444444-4444-4444-4444-444444444447', 'Juancho', '760012232', NULL, NULL, '180e86ca7-7372-7478-19f1-2e1fb3ed00e2', 'PER', 'pesca_industrial', 'fishing', 'other_purse_seines', '2013-11-19 21:49:51+00', '2026-08-31 23:59:59+00');

UPDATE embarcaciones SET capturada = true, capturada_en = '2023-10-24 15:10:00-05'
  WHERE id = '44444444-4444-4444-4444-444444444442';

-- =========================================================
-- Eventos crudos de Global Fishing Watch (Events API)
-- =========================================================
-- payload_raw guarda una versión resumida de lo que devuelve la Events API
-- (id, type, start/end, vessel, position/regiones) para trazabilidad.

INSERT INTO eventos_gfw
  (id, gfw_event_id, tipo, embarcacion_id, zona_id, inicio, latitud, longitud, velocidad_nudos, regiones, payload_raw, estado) VALUES
  ('88888888-8888-8888-8888-888888888881', 'gfw-evt-a1', 'pesca',
   '44444444-4444-4444-4444-444444444441', '22222222-2222-2222-2222-222222222225',
   now() - interval '12 minutes', -12.0708, -77.7528, 14.2,
   '{"eez": ["PER"]}',
   '{"id":"gfw-evt-a1","type":"fishing","start":"2023-10-24T19:00:00Z","vessel":{"id":"gfw-8f2a1c90","ssvid":"760445920","name":"T/N ALBATROS","flag":"PER"},"position":{"lat":-12.0708,"lon":-77.7528}}',
   'pendiente');

INSERT INTO eventos_gfw
  (id, gfw_event_id, tipo, embarcacion_id, zona_id, inicio, fin, payload_raw, estado) VALUES
  ('88888888-8888-8888-8888-888888888882', 'gfw-evt-g1', 'vacio_ais',
   '44444444-4444-4444-4444-444444444443', NULL,
   '2023-10-24 07:00:00-05', '2023-10-24 11:15:00-05',
   '{"id":"gfw-evt-g1","type":"gap","start":"2023-10-24T12:00:00Z","end":"2023-10-24T16:15:00Z","vessel":{"id":"gfw-9a41f6c3","ssvid":"720098441","name":"POSEIDON V","flag":"PER"},"gapDurationHours":4.25}',
   'pendiente'),

  ('88888888-8888-8888-8888-888888888883', 'gfw-evt-e1', 'encuentro',
   '44444444-4444-4444-4444-444444444445', '22222222-2222-2222-2222-222222222225',
   '2023-10-23 18:40:00-05', '2023-10-23 19:10:00-05',
   '{"id":"gfw-evt-e1","type":"encounter","start":"2023-10-23T23:40:00Z","end":"2023-10-24T00:10:00Z","vessel":{"id":"gfw-1d9c8e77","ssvid":"720112990","name":"LOBO DE MAR IX","flag":"PER"},"medianDistanceKm":0.05,"medianSpeedKnots":1.2}',
   'pendiente'),

  ('88888888-8888-8888-8888-888888888884', 'gfw-evt-l1', 'merodeo',
   NULL, '22222222-2222-2222-2222-222222222221',
   now() - interval '4 hours', NULL,
   '{"id":"gfw-evt-l1","type":"loitering","start":"2023-10-25T07:15:00Z","vessel":{"id":null,"ssvid":"999000111","name":null,"flag":"UNK"},"position":{"lat":-5.084,"lon":-81.115}}',
   'pendiente');

-- =========================================================
-- Esfuerzo pesquero (4Wings Report API)
-- Fila tal como la entrega el reporte agregado: una embarcación, una
-- celda de mar, un rango de fechas — no un evento puntual.
-- =========================================================

INSERT INTO esfuerzo_pesquero_gfw
  (embarcacion_id, gfw_vessel_id, mmsi, imo, callsign, ship_name, flag, vessel_type, geartype, dataset,
   rango_desde, rango_hasta, entry_timestamp, exit_timestamp, primera_transmision_ais, ultima_transmision_ais,
   horas, latitud, longitud, payload_raw) VALUES
  ('44444444-4444-4444-4444-444444444447', '180e86ca7-7372-7478-19f1-2e1fb3ed00e2', '760012232', NULL, NULL,
   'JUANCHO', 'PER', 'FISHING', 'OTHER_PURSE_SEINES', 'public-global-vessel-identity:v4.0',
   '2023-01-01', '2023-01-08', '2023-01-01 00:00:00+00', '2023-01-06 06:00:00+00',
   '2013-11-19 21:49:51+00', '2026-08-31 23:59:59+00',
   0.9550, -11.8, -77.5,
   '{"callsign":"","dataset":"public-global-vessel-identity:v4.0","date":"2023-01-01,2023-01-08","entryTimestamp":"2023-01-01T00:00:00Z","exitTimestamp":"2023-01-06T06:00:00Z","firstTransmissionDate":"2013-11-19T21:49:51Z","flag":"PER","geartype":"OTHER_PURSE_SEINES","hours":0.9549999999999998,"imo":"","lastTransmissionDate":"2026-08-31T23:59:59Z","lat":-11.8,"lon":-77.5,"mmsi":"760012232","shipName":"JUANCHO","vesselId":"180e86ca7-7372-7478-19f1-2e1fb3ed00e2","vesselType":"FISHING"}');

-- =========================================================
-- Alerta de monitoreo activa (AlertCard sobre T/N Albatros)
-- Originada por el evento GFW "pesca" de arriba.
-- =========================================================

INSERT INTO alertas_monitoreo (id, embarcacion_id, origen_evento_gfw_id, descripcion, velocidad_nudos, rumbo_grados, latitud, longitud, estado) VALUES
  ('55555555-5555-5555-5555-555555555551',
   '44444444-4444-4444-4444-444444444441',
   '88888888-8888-8888-8888-888888888881',
   'Posible incursión en Zona Económica Exclusiva sin autorización registrada.',
   14.2, 340, -12.0708, -77.7528, 'activa');

-- =========================================================
-- Incidentes (tabla de Registro de Incidentes)
-- INC-088 y INC-086 se originan en los eventos GFW "vacio_ais" y
-- "encuentro" insertados arriba (origen_evento_gfw_id).
-- =========================================================

INSERT INTO incidentes
  (id, codigo, embarcacion_id, zona_id, tipo_infraccion_id, descripcion, gravedad, estado, fecha_deteccion, registrado_por, origen_evento_gfw_id) VALUES
  ('66666666-6666-6666-6666-666666666661', 'INC-2023-089',
   '44444444-4444-4444-4444-444444444442', '22222222-2222-2222-2222-222222222224',
   '33333333-3333-3333-3333-333333333331',
   'Pesca en Zona Protegida (Reserva de Paracas)', 'alto', 'confirmado',
   '2023-10-24 14:32:00-05', '11111111-1111-1111-1111-111111111112', NULL),

  ('66666666-6666-6666-6666-666666666662', 'INC-2023-088',
   '44444444-4444-4444-4444-444444444443', NULL,
   '33333333-3333-3333-3333-333333333335',
   'Pérdida de señal AIS (> 4 horas)', 'medio', 'sospechoso',
   '2023-10-24 11:15:00-05', '11111111-1111-1111-1111-111111111112',
   '88888888-8888-8888-8888-888888888882'),

  ('66666666-6666-6666-6666-666666666663', 'INC-2023-087',
   '44444444-4444-4444-4444-444444444444', NULL,
   '33333333-3333-3333-3333-333333333336',
   'Velocidad inusual en zona de tránsito', 'bajo', 'descartado',
   '2023-10-23 22:45:00-05', '11111111-1111-1111-1111-111111111112', NULL),

  ('66666666-6666-6666-6666-666666666664', 'INC-2023-086',
   '44444444-4444-4444-4444-444444444445', '22222222-2222-2222-2222-222222222225',
   '33333333-3333-3333-3333-333333333337',
   'Encuentro sospechoso en alta mar (Transbordo)', 'alto', 'sospechoso',
   '2023-10-23 19:10:00-05', '11111111-1111-1111-1111-111111111112',
   '88888888-8888-8888-8888-888888888883');

-- Cierra el enlace inverso: marca los eventos GFW ya promovidos a incidente.
UPDATE eventos_gfw SET incidente_id = '66666666-6666-6666-6666-666666666662', estado = 'aprobado'
  WHERE id = '88888888-8888-8888-8888-888888888882';
UPDATE eventos_gfw SET incidente_id = '66666666-6666-6666-6666-666666666664', estado = 'aprobado'
  WHERE id = '88888888-8888-8888-8888-888888888883';

-- Filas adicionales solo para poblar el ranking de "Zonas con Mayor
-- Incidencia" (vw_zonas_top) con el mismo orden relativo del mockup:
-- Paita > Chimbote > Callao.
INSERT INTO incidentes (zona_id, tipo_infraccion_id, descripcion, gravedad, fecha_deteccion, registrado_por) VALUES
  ('22222222-2222-2222-2222-222222222221', '33333333-3333-3333-3333-333333333331', 'Pesca de arrastre no autorizada', 'alto', now() - interval '10 days', '11111111-1111-1111-1111-111111111112'),
  ('22222222-2222-2222-2222-222222222221', '33333333-3333-3333-3333-333333333331', 'Pesca de arrastre no autorizada', 'medio', now() - interval '20 days', '11111111-1111-1111-1111-111111111112'),
  ('22222222-2222-2222-2222-222222222221', '33333333-3333-3333-3333-333333333333', 'Transbordo sin declarar', 'alto', now() - interval '35 days', '11111111-1111-1111-1111-111111111112'),
  ('22222222-2222-2222-2222-222222222222', '33333333-3333-3333-3333-333333333331', 'Pesca en veda vigente', 'alto', now() - interval '5 days', '11111111-1111-1111-1111-111111111112'),
  ('22222222-2222-2222-2222-222222222222', '33333333-3333-3333-3333-333333333332', 'Operación sin permiso vigente', 'medio', now() - interval '18 days', '11111111-1111-1111-1111-111111111112'),
  ('22222222-2222-2222-2222-222222222223', '33333333-3333-3333-3333-333333333334', 'Descarga de residuos cerca al puerto', 'medio', now() - interval '8 days', '11111111-1111-1111-1111-111111111112');

-- =========================================================
-- Noticias: cola de fuentes + sugerencias de IA
-- =========================================================

INSERT INTO fuentes_noticias (id, url, dominio, estado, enviado_por, creado_en, procesado_en) VALUES
  ('77777777-7777-7777-7777-777777777771',
   'https://thefishingtimes.com/noticia-incautacion-mar-de-grau',
   'thefishingtimes.com', 'exitosa', '11111111-1111-1111-1111-111111111112',
   now() - interval '2 minutes', now() - interval '1 minute'),

  ('77777777-7777-7777-7777-777777777772',
   'https://localnoticias.pe/reporte-contaminacion-callao',
   'localnoticias.pe', 'exitosa', '11111111-1111-1111-1111-111111111112',
   now() - interval '15 minutes', now() - interval '14 minutes'),

  ('77777777-7777-7777-7777-777777777773',
   'https://maritimenews.net/report-suspicious-transshipment',
   'maritimenews.net', 'procesando', '11111111-1111-1111-1111-111111111112',
   now() - interval '1 minute', NULL);

INSERT INTO incidentes_sugeridos_ia
  (fuente_id, titular, resumen, tipo_infraccion_id, embarcacion_detectada, ubicacion_estimada, confianza, estado) VALUES
  ('77777777-7777-7777-7777-777777777771',
   'Autoridades incautan embarcación extranjera por pesca ilegal en el Mar de Grau',
   'La nave fue detectada realizando operaciones de arrastre dentro de las 5 millas, contraviniendo la normativa nacional vigente...',
   '33333333-3333-3333-3333-333333333331', 'M/V OCEAN BREEZE (IMO: 9876543)', 'Mar de Grau', 0.930, 'pendiente'),

  ('77777777-7777-7777-7777-777777777772',
   'Reporte de posible contaminación por hidrocarburos cerca al puerto',
   NULL,
   '33333333-3333-3333-3333-333333333334', NULL, 'Puerto del Callao (Aprox)', 0.780, 'pendiente');

-- Sincroniza la secuencia de códigos con los INC-2023-0XX insertados a mano
-- para que el próximo incidente generado automáticamente sea INC-2023-090.
SELECT setval('incidentes_codigo_seq', 89);

COMMIT;
