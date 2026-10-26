"""
Simulación: inventa una flota frente a Lambayeque con comportamientos
normales e irregulares, la pasa por el MISMO camino que usa el servidor en
vivo (features.construir_features_flota -> modelo.escalar -> modelo.predecir)
y compara lo esperado contra lo detectado.

Los registros tienen la forma que devuelve GFW (gfw_client.obtener_presencia_
diaria / obtener_esfuerzo_diario): una fila por barco, día y celda. Las celdas
son de 0.1° (la resolución de los datos de entrenamiento) y las posiciones se
ubican a X millas de la costa real de Lambayeque
(src/features/monitoring/data/lambayequeCoastline.ts).

Escenarios (N_POR_ESCENARIO barcos cada uno, con variación aleatoria):

  normal        Cerqueros peruanos: viajes de 2-4 días a 20-60 mn, vuelven a
                puerto, AIS continuo. Esperado: ninguna alerta.
  zona_5mn      Cerquero peruano pescando a 1-4 mn de la costa (reserva
                artesanal) varios días seguidos. Esperado: zona_protegida.
  transito_5mn  Cerquero peruano recorriendo la franja de 5 mn a lo largo de
                la costa sin pescar (perfil real de los positivos de
                zona_protegida frente a Lambayeque). Pasar sin pescar no es
                infracción. Esperado: ninguna alerta.
  islas_lobos   Cerquero peruano pescando a menos de 5 mn de las islas Lobos de
                Tierra / Lobos de Afuera (reserva RNSIIPG). Esperado: alerta de
                islas protegidas (regla, ver deteccion.py).
  zona_5mn_chimbote  Igual, pero frente a Chimbote, en la posición típica de
                los casos reales de 5 mn de esa zona (control: el modelo tiene
                ~50x más casos de 5 mn ahí que en Lambayeque).
  apagon        Transmite normal 15-30 días, apaga el AIS 15-40 días y
                reaparece (último día) a 20-80 km pescando. Esperado: apagon_ais.
  cruce_zee     Potero chino al borde de las 200 mn, apaga el AIS 10-25 días y
                reaparece dentro de la ZEE (150-180 mn). Esperado: apagon_ais.
  apagado_frontera  Potero chino operando a 185-215 mn que apaga el AIS los
                últimos 3-20 días y todavía no reaparece. Esperado: alerta de
                apagado junto a las 200 mn (regla, ver deteccion.py).
  demora        Potero chino 60+ días seguidos en el mar a 120-190 mn, sin
                volver nunca a puerto. Esperado: demora_puerto.

Además se agrega una flota de fondo (barcos normales) para que haya vecinos
en las mismas celdas, como en la realidad.

Uso:
  python scripts/simular_irregularidades.py              # genera y evalúa
  python scripts/simular_irregularidades.py --semilla 7  # otra flota inventada
"""
import json
import math
import random
import re
import sys
from datetime import date, timedelta
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "server"))

from app import deteccion, features, modelo  # noqa: E402

SALIDA = Path(__file__).resolve().parent / "simulacion_irregularidades.json"
COSTA_TS = RAIZ / "src" / "features" / "monitoring" / "data" / "lambayequeCoastline.ts"
FIN = date(2026, 9, 30)
DIAS = 90
N_POR_ESCENARIO = 12
N_FONDO = 20
CELDA = 0.1
# Puerto Eten y San José, los dos desembarcaderos de Lambayeque.
PUERTOS_LAMBAYEQUE = [(-6.93, -79.86), (-6.77, -79.97)]
ISLAS_LOBOS = [(-6.43, -80.86), (-6.93, -80.72)]  # Lobos de Tierra, Lobos de Afuera
# Mediana de posición de los casos reales de 5 mn frente a Chimbote (test.csv).
CHIMBOTE_5MN = (-9.2, -78.6)

ESPERADO = {
    "normal": None,
    "zona_5mn": "zona_protegida",
    # Pasar por la franja sin pescar no es infracción.
    "transito_5mn": None,
    "islas_lobos": "islas",
    "zona_5mn_chimbote": "zona_protegida",
    "apagon": "apagon_ais",
    "cruce_zee": "apagon_ais",
    "apagado_frontera": "apagado_frontera",
    "demora": "demora_puerto",
}


def _cargar_costa() -> list[tuple[float, float]]:
    puntos = re.findall(r"\[(-?\d+\.\d+),\s*(-?\d+\.\d+)\]", COSTA_TS.read_text(encoding="utf-8"))
    return sorted((float(lat), float(lon)) for lat, lon in puntos)


COSTA = _cargar_costa()


def lon_costa(lat: float) -> float:
    """Longitud de la costa de Lambayeque a esa latitud (interpolación lineal)."""
    lat = min(max(lat, COSTA[0][0]), COSTA[-1][0])
    for (lat1, lon1), (lat2, lon2) in zip(COSTA, COSTA[1:]):
        if lat1 <= lat <= lat2:
            return lon1 if lat2 == lat1 else lon1 + (lon2 - lon1) * (lat - lat1) / (lat2 - lat1)
    return COSTA[-1][1]


def mar_adentro(lat: float, millas: float) -> tuple[float, float]:
    """Punto a `millas` al oeste de la costa a esa latitud."""
    return lat, lon_costa(lat) - millas / (60 * math.cos(math.radians(lat)))


def a_millas_de_la_costa_peruana(lat: float, millas: float) -> tuple[float, float]:
    """Punto a esa latitud cuya distancia a la costa peruana MÁS CERCANA
    (features._distancia_costa_nm, la misma que usa el sistema para el
    límite de las 200 mn) es `millas`. Lejos de Lambayeque la costa más
    cercana es la península de Sechura, no la de enfrente."""
    oeste, este = -90.0, lon_costa(lat)
    for _ in range(40):
        medio = (oeste + este) / 2
        if features._distancia_costa_nm(lat, medio) > millas:
            oeste = medio
        else:
            este = medio
    return lat, (oeste + este) / 2


class Simulador:
    def __init__(self, semilla: int):
        self.rng = random.Random(semilla)
        self.presencia: list[dict] = []
        self.esfuerzo: list[dict] = []
        self.escenario_por_mmsi: dict[str, str] = {}

    def _fecha(self, dia: int) -> str:
        return (FIN - timedelta(days=DIAS - 1 - dia)).isoformat()

    def registrar_dia(self, barco: dict, dia: int, centro: tuple[float, float], n_celdas: int, horas: float,
                      ratio_pesca: float, dispersion: float = 0.06):
        """Reparte `horas` del día entre `n_celdas` celdas de 0.1° alrededor de
        `centro` (desvío `dispersion` en grados); la fracción `ratio_pesca`
        de cada celda es pesca aparente."""
        lat0, lon0 = centro
        pesos = [self.rng.random() + 0.2 for _ in range(n_celdas)]
        for peso in pesos:
            lat = round(math.floor((lat0 + self.rng.gauss(0, dispersion)) / CELDA) * CELDA, 2)
            lon = round(math.floor((lon0 + self.rng.gauss(0, dispersion)) / CELDA) * CELDA, 2)
            h = round(horas * peso / sum(pesos), 3)
            base = {"mmsi": barco["mmsi"], "date": self._fecha(dia), "shipName": barco["nombre"],
                    "flag": barco["flag"], "vesselType": "FISHING", "lat": lat, "lon": lon}
            self.presencia.append({**base, "hours": h})
            pesca = round(h * min(max(ratio_pesca + self.rng.gauss(0, 0.05), 0), 1), 3) if ratio_pesca > 0 else 0
            if pesca > 0:
                self.esfuerzo.append({**base, "hours": pesca})

    def nuevo_barco(self, escenario: str, i: int, flag: str, prefijo: str) -> dict:
        mmsi = f"{prefijo}{len(self.escenario_por_mmsi):06d}"
        self.escenario_por_mmsi[mmsi] = escenario
        return {"mmsi": mmsi, "nombre": f"{escenario.upper()} {i + 1}", "flag": flag}

    # --- comportamientos ---------------------------------------------------

    def viajes_normales(self, barco: dict, dia_inicio: int, dia_fin: int):
        """Cerquero: sale 2-4 días a 15-60 mn y vuelve a puerto 1 día."""
        dia = dia_inicio
        while dia <= dia_fin:
            for _ in range(self.rng.randint(2, 4)):
                if dia > dia_fin:
                    break
                # Caladeros legales: lejos de las islas Lobos (las celdas se
                # dispersan unas 4 mn alrededor del centro).
                centro = mar_adentro(self.rng.uniform(-7.1, -6.2), self.rng.uniform(20, 60))
                while features._distancia_islas_nm(*centro) < features.RADIO_ISLAS_PROTEGIDAS_NM + 12:
                    centro = mar_adentro(self.rng.uniform(-7.1, -6.2), self.rng.uniform(20, 60))
                self.registrar_dia(barco, dia, centro, self.rng.randint(5, 12), self.rng.uniform(16, 24), self.rng.uniform(0.2, 0.45))
                dia += 1
            if dia <= dia_fin:
                # Amarrado en el muelle: sin dispersión.
                self.registrar_dia(barco, dia, self.rng.choice(PUERTOS_LAMBAYEQUE), 1, self.rng.uniform(18, 24), 0.0, dispersion=0)
                dia += 1

    def alrededor_de(self, barco: dict, punto: tuple[float, float]):
        """Pesca 7 días seguidos a menos de ~4 mn de `punto`."""
        self.viajes_normales(barco, 0, DIAS - 8)
        for dia in range(DIAS - 7, DIAS):
            centro = (punto[0] + self.rng.gauss(0, 0.03), punto[1] + self.rng.gauss(0, 0.03))
            self.registrar_dia(barco, dia, centro, self.rng.randint(2, 5), self.rng.uniform(14, 22), self.rng.uniform(0.5, 0.8))

    def zona_5mn(self, barco: dict):
        self.viajes_normales(barco, 0, DIAS - 8)
        lat = self.rng.uniform(-7.0, -6.4)
        for dia in range(DIAS - 7, DIAS):
            self.registrar_dia(barco, dia, mar_adentro(lat + self.rng.gauss(0, 0.03), self.rng.uniform(1, 4)),
                               self.rng.randint(2, 5), self.rng.uniform(14, 22), self.rng.uniform(0.5, 0.8))

    def transito_5mn(self, barco: dict):
        """Recorre la franja de 5 mn a lo largo de la costa (muchas celdas,
        ~100+ km por día, casi sin pesca): el perfil de los casos reales de
        reserva artesanal frente a Lambayeque en train.csv."""
        self.viajes_normales(barco, 0, DIAS - 8)
        for dia in range(DIAS - 7, DIAS):
            lat = self.rng.uniform(-7.0, -6.4)
            # Un día de recorrido norte-sur: celdas repartidas por ~1° de latitud.
            celdas = [mar_adentro(lat + k * 0.05, self.rng.uniform(1, 4)) for k in range(-10, 10)]
            for c in self.rng.sample(celdas, self.rng.randint(15, 20)):
                self.registrar_dia(barco, dia, c, 1, self.rng.uniform(1, 1.6), 0.01)

    def apagon(self, barco: dict):
        hueco = self.rng.randint(15, 40)
        fin_transmision = DIAS - 1 - hueco
        inicio = max(0, fin_transmision - self.rng.randint(15, 30))
        self.viajes_normales(barco, inicio, fin_transmision)
        lat = self.rng.uniform(-7.1, -6.2)
        self.registrar_dia(barco, DIAS - 1, mar_adentro(lat, self.rng.uniform(30, 80)),
                           self.rng.randint(2, 4), self.rng.uniform(4, 10), self.rng.uniform(0.6, 0.9))

    def cruce_zee(self, barco: dict):
        hueco = self.rng.randint(10, 25)
        fin_transmision = DIAS - 1 - hueco
        for dia in range(max(0, fin_transmision - self.rng.randint(15, 30)), fin_transmision + 1):
            self.registrar_dia(barco, dia, a_millas_de_la_costa_peruana(self.rng.uniform(-7.1, -6.2), self.rng.uniform(195, 215)),
                               self.rng.randint(3, 10), self.rng.uniform(20, 24), self.rng.uniform(0.2, 0.5))
        self.registrar_dia(barco, DIAS - 1, a_millas_de_la_costa_peruana(self.rng.uniform(-7.1, -6.2), self.rng.uniform(150, 180)),
                           self.rng.randint(2, 4), self.rng.uniform(4, 10), self.rng.uniform(0.6, 0.9))

    def apagado_frontera(self, barco: dict):
        fin_transmision = DIAS - 1 - self.rng.randint(3, 20)
        for dia in range(max(0, fin_transmision - self.rng.randint(15, 30)), fin_transmision + 1):
            self.registrar_dia(barco, dia, a_millas_de_la_costa_peruana(self.rng.uniform(-7.1, -6.2), self.rng.uniform(185, 215)),
                               self.rng.randint(3, 10), self.rng.uniform(20, 24), self.rng.uniform(0.2, 0.5))

    def demora(self, barco: dict):
        lat = self.rng.uniform(-7.1, -6.2)
        millas = self.rng.uniform(120, 190)
        for dia in range(DIAS - self.rng.randint(60, 89), DIAS):
            lat += self.rng.gauss(0, 0.05)
            millas = min(max(millas + self.rng.gauss(0, 5), 110), 195)
            self.registrar_dia(barco, dia, a_millas_de_la_costa_peruana(lat, millas), self.rng.randint(4, 12),
                               self.rng.uniform(22, 24), self.rng.uniform(0.3, 0.6))

    def generar(self):
        for i in range(N_FONDO):
            self.viajes_normales(self.nuevo_barco("fondo", i, "PER", "76"), 0, DIAS - 1)
        for i in range(N_POR_ESCENARIO):
            self.viajes_normales(self.nuevo_barco("normal", i, "PER", "76"), 0, DIAS - 1)
            self.zona_5mn(self.nuevo_barco("zona_5mn", i, "PER", "76"))
            self.transito_5mn(self.nuevo_barco("transito_5mn", i, "PER", "76"))
            self.alrededor_de(self.nuevo_barco("islas_lobos", i, "PER", "76"), ISLAS_LOBOS[i % 2])
            self.alrededor_de(self.nuevo_barco("zona_5mn_chimbote", i, "PER", "76"), CHIMBOTE_5MN)
            self.apagon(self.nuevo_barco("apagon", i, "PER", "76"))
            self.cruce_zee(self.nuevo_barco("cruce_zee", i, "CHN", "41"))
            self.demora(self.nuevo_barco("demora", i, "CHN", "41"))
            self.apagado_frontera(self.nuevo_barco("apagado_frontera", i, "CHN", "41"))


# Patrón -> (campo de la alerta final en deteccion.evaluar_actividad,
# detector entrenado que lo cubre o None si es solo regla).
ALERTA_POR_PATRON = {
    "zona_protegida": ("reservaArtesanal", "zona_protegida"),
    "islas": ("islasProtegidas", None),
    "apagon_ais": ("apagonAis", "apagon_ais"),
    "demora_puerto": ("demoraPuerto", "demora_puerto"),
    "apagado_frontera": ("apagadoEnFronteraZee", None),
}


def evaluar(datos: dict):
    """Por escenario y patrón: cuántos barcos marca solo el modelo entrenado
    y cuántos marca la decisión final del sistema (regla o modelo)."""
    por_mmsi = features.construir_features_flota(datos["presencia"], datos["esfuerzo"])
    escenarios = datos["escenario_por_mmsi"]
    alertas = {m: deteccion.evaluar_actividad(m, d) or {} for m, d in por_mmsi.items()}

    print(f"\n{'escenario':<18}{'esperado':<16}" + "".join(f"{p:>18}" for p in ALERTA_POR_PATRON))
    print(f"{'':<34}" + "".join(f"{'modelo -> final':>18}" for _ in ALERTA_POR_PATRON))
    print("-" * 124)
    for escenario, esperado in ESPERADO.items():
        barcos = [m for m, e in escenarios.items() if e == escenario and m in por_mmsi]
        celdas = []
        for patron, (campo, detector) in ALERTA_POR_PATRON.items():
            solo_modelo = (
                f"{sum(modelo.predecir(detector, por_mmsi[m]['features'])['detectado'] for m in barcos):>2}"
                if detector else " -"
            )
            final = sum(bool(alertas[m].get(campo)) for m in barcos)
            marca = "*" if patron == esperado else " "
            celdas.append(f"{marca}{solo_modelo} -> {final:>2}/{len(barcos)}")
        print(f"{escenario:<18}{esperado or 'ninguna':<16}" + "".join(f"{c:>18}" for c in celdas))
    cruces = sum(bool(alertas[m].get("cruceFronteraZee")) for m, e in escenarios.items() if e == "cruce_zee" and m in por_mmsi)
    print(f"\n* = patrón que debería dispararse. 'final' = regla o modelo, lo que ve el analista "
          f"(server/app/deteccion.py). Alerta de cruce de frontera ZEE en cruce_zee: {cruces}/{N_POR_ESCENARIO}")


def main():
    semilla = int(sys.argv[sys.argv.index("--semilla") + 1]) if "--semilla" in sys.argv else 42
    sim = Simulador(semilla)
    sim.generar()
    datos = {"semilla": semilla, "presencia": sim.presencia, "esfuerzo": sim.esfuerzo,
             "escenario_por_mmsi": sim.escenario_por_mmsi}
    SALIDA.write_text(json.dumps(datos), encoding="utf-8")
    print(f"Flota inventada (semilla {semilla}): {len(sim.escenario_por_mmsi)} barcos, "
          f"{len(sim.presencia)} filas de presencia, {len(sim.esfuerzo)} de esfuerzo -> {SALIDA.name}")
    evaluar(datos)


if __name__ == "__main__":
    main()
