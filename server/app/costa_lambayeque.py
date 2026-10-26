"""Costa real de Lambayeque e islas frente a ella, para medir la distancia
a costa con precisión en la jurisdicción (la reserva artesanal de 5 mn se
mide desde ahí). features.COSTA_PERU son solo 13 vértices de todo el Perú:
frente a Lambayeque se equivoca por decenas de millas.

COSTA_LAMBAYEQUE es la misma línea que
src/features/monitoring/data/lambayequeCoastline.ts (OpenStreetMap,
natural=coastline, simplificada), de sur a norte, en tuplas (lat, lon).

Islas Lobos de Tierra y Lobos de Afuera (Reserva Nacional Sistema de Islas,
Islotes y Puntas Guaneras), contorno aproximado (unos pocos vértices por
isla). Cuentan como costa para la distancia que ve el modelo (en el dataset
de entrenamiento casi todos los casos de "reserva 5 mn" de Lambayeque están
junto a ellas), pero NO para la regla de la reserva artesanal, que se mide
desde el continente: tienen su propia alerta -- ver features.py.
"""

COSTA_LAMBAYEQUE: list[tuple[float, float]] = [
    (-7.15985, -79.68542),
    (-7.15207, -79.68216),
    (-7.14259, -79.68465),
    (-7.13864, -79.68294),
    (-7.13486, -79.68267),
    (-7.12593, -79.68416),
    (-7.11825, -79.68897),
    (-7.10424, -79.70016),
    (-7.08535, -79.71724),
    (-7.06859, -79.73435),
    (-7.0632, -79.73596),
    (-7.05754, -79.73984),
    (-7.04931, -79.74777),
    (-7.01241, -79.78709),
    (-6.97652, -79.8281),
    (-6.9486, -79.86612),
    (-6.94436, -79.86413),
    (-6.94061, -79.86654),
    (-6.9373, -79.86576),
    (-6.93305, -79.86617),
    (-6.92483, -79.87148),
    (-6.91791, -79.8787),
    (-6.90664, -79.89338),
    (-6.89299, -79.91545),
    (-6.88707, -79.91895),
    (-6.87488, -79.93064),
    (-6.87208, -79.93232),
    (-6.86727, -79.93284),
    (-6.86328, -79.93505),
    (-6.85813, -79.9354),
    (-6.84618, -79.93877),
    (-6.83865, -79.93801),
    (-6.82925, -79.94058),
    (-6.82619, -79.94019),
    (-6.82316, -79.94258),
    (-6.8196, -79.94315),
    (-6.80136, -79.95264),
    (-6.79165, -79.9562),
    (-6.7838, -79.96385),
    (-6.77464, -79.96869),
    (-6.75742, -79.9806),
    (-6.74705, -79.98603),
    (-6.73458, -80.00278),
    (-6.72863, -80.01057),
    (-6.71204, -80.02805),
    (-6.67552, -80.07489),
    (-6.65318, -80.10931),
    (-6.60604, -80.17732),
    (-6.56083, -80.25648),
    (-6.54161, -80.29145),
    (-6.48178, -80.40892),
    (-6.43342, -80.5),
    (-6.40642, -80.55403),
    (-6.37079, -80.6299),
    (-6.34047, -80.68803),
]

ISLAS_LAMBAYEQUE: dict[str, list[tuple[float, float]]] = {
    "Lobos de Tierra": [(-6.385, -80.855), (-6.410, -80.840), (-6.445, -80.845), (-6.475, -80.865), (-6.450, -80.880), (-6.410, -80.875), (-6.385, -80.855)],
    "Lobos de Afuera": [(-6.915, -80.705), (-6.930, -80.700), (-6.950, -80.715), (-6.945, -80.735), (-6.925, -80.730), (-6.915, -80.705)],
}
