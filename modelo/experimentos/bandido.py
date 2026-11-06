"""Reparto de propuestas por probabilidades: bandido bayesiano (Thompson) con préstamo de información.

Es el equivalente a las pruebas A/B de miniaturas, pero por sector y sin esperar a un ganador único:
cada oleada reparte las propuestas según la probabilidad de que cada una sea la mejor y aprende de lo
que respondan.

Modelo. Cada contacto tiene una probabilidad base `p0` (el score de producto x score de canal del reto).
Una propuesta `k` la multiplica por un factor `lift_k`: P(compra) = p0 x lift_k. Con muchos contactos
y p0 pequeña, las compras de una propuesta son aproximadamente Poisson(lift_k x suma de p0), de modo que
`lift_k ~ Gamma(a + compras, b + suma de p0)` es una posterior conjugada. Medir el `lift` contra el
score del reto, y no la tasa cruda, evita confundir una propuesta buena con un sector que ya compraba más.

Préstamo de información. Un sector pequeño tarda en aprender solo. Su prior es la posterior global de la
campaña (`fuerza_prior` mide cuántas compras esperadas vale): sin datos propios se comporta como el
promedio de todos los sectores y, a medida que acumula evidencia, se separa de él."""
import numpy as np


class Politica:
    """Interfaz común: elegir variante para un lote de contactos y aprender de la respuesta."""
    nombre = "politica"

    def elegir(self, lote, rng):
        raise NotImplementedError

    def aprender(self, lote, variante, exito):
        pass


class Uniforme(Politica):
    """Prueba A/B clásica sin aprendizaje: reparte las propuestas por igual todo el tiempo."""
    nombre = "uniforme"

    def __init__(self, contactos, k):
        self.k = k

    def elegir(self, lote, rng):
        return rng.integers(0, self.k, size=len(lote))


class _ConEvidencia(Politica):
    """Acumula compras y compras esperadas (suma de p0) por celda y variante."""

    def __init__(self, contactos, k, celdas_de, n_celdas):
        self.c, self.k = contactos, k
        self.celda = celdas_de
        self.compras = np.zeros((n_celdas, k))
        self.esperadas = np.zeros((n_celdas, k))

    def aprender(self, lote, variante, exito):
        np.add.at(self.compras, (self.celda[lote], variante), exito.astype(float))
        np.add.at(self.esperadas, (self.celda[lote], variante), self.c["p0"][lote])

    def lift_estimado(self, fuerza):
        return (fuerza + self.compras) / (fuerza + self.esperadas)


def _asignar(prob, celdas, rng):
    """Una variante por contacto, muestreada de las probabilidades de su celda."""
    acumulada = np.cumsum(prob, axis=1)[celdas]
    return np.minimum((rng.random(len(celdas))[:, None] > acumulada).sum(axis=1), prob.shape[1] - 1)


def prob_mejor(forma, tasa, muestras, rng):
    """P(cada variante sea la de mayor lift) por celda, por Monte Carlo sobre la posterior Gamma."""
    m = rng.gamma(forma[:, None, :], 1.0 / tasa[:, None, :], size=(forma.shape[0], muestras, forma.shape[1]))
    ganadora = m.argmax(axis=2)
    return np.stack([(ganadora == k).mean(axis=1) for k in range(forma.shape[1])], axis=1)


class BandidoSector(_ConEvidencia):
    """Thompson por sector x campaña con prior jerárquico (el nuestro)."""
    nombre = "bandido_sector"

    def __init__(self, contactos, k, config):
        super().__init__(contactos, k, contactos["sector"] * contactos["n_campanas"] + contactos["campana"],
                         contactos["n_sectores"] * contactos["n_campanas"])
        self.fuerza = config["fuerza_prior"]
        self.piso = config["piso_exploracion"]
        self.muestras = config["muestras_probabilidad"]
        self.nc = contactos["n_campanas"]

    def posterior(self):
        """(forma, tasa) de la Gamma de cada celda x variante, con el prior global de su campaña."""
        n_celdas = self.compras.shape[0]
        camp = np.arange(n_celdas) % self.nc
        compras_g = np.zeros((self.nc, self.k))
        esperadas_g = np.zeros((self.nc, self.k))
        np.add.at(compras_g, camp, self.compras)
        np.add.at(esperadas_g, camp, self.esperadas)
        lift_g = (self.fuerza + compras_g) / (self.fuerza + esperadas_g)
        return self.fuerza * lift_g[camp] + self.compras, self.fuerza + self.esperadas

    def probabilidades(self, rng):
        forma, tasa = self.posterior()
        p = prob_mejor(forma, tasa, self.muestras, rng)
        return (1 - self.k * self.piso) * p + self.piso  # piso: nunca se deja de mirar una propuesta

    def elegir(self, lote, rng):
        return _asignar(self.probabilidades(rng), self.celda[lote], rng)

    def lift_posterior(self):
        forma, tasa = self.posterior()
        return forma / tasa


class BandidoGlobal(_ConEvidencia):
    """Thompson por campaña, sin distinguir sectores: aísla cuánto aporta sectorizar."""
    nombre = "bandido_global"

    def __init__(self, contactos, k, config):
        super().__init__(contactos, k, contactos["campana"], contactos["n_campanas"])
        self.fuerza, self.piso, self.muestras = config["fuerza_prior"], config["piso_exploracion"], config["muestras_probabilidad"]

    def elegir(self, lote, rng):
        p = prob_mejor(self.fuerza + self.compras, self.fuerza + self.esperadas, self.muestras, rng)
        return _asignar((1 - self.k * self.piso) * p + self.piso, self.celda[lote], rng)


class GanadorGlobal(_ConEvidencia):
    """A/B tradicional: explora parejo una fracción del tiempo y luego fija un único ganador por campaña."""
    nombre = "ganador_global"

    def __init__(self, contactos, k, config, oleadas):
        super().__init__(contactos, k, contactos["campana"], contactos["n_campanas"])
        self.exploracion = max(1, int(round(oleadas * config["fraccion_exploracion_global"])))
        self.oleada = 0
        self.fuerza = config["fuerza_prior"]

    def elegir(self, lote, rng):
        self.oleada += 1
        if self.oleada <= self.exploracion:
            return rng.integers(0, self.k, size=len(lote))
        ganadora = self.lift_estimado(self.fuerza).argmax(axis=1)
        return ganadora[self.celda[lote]]


class Oraculo(Politica):
    """Cota superior: conoce la verdad y siempre elige la mejor propuesta de cada sector y campaña."""
    nombre = "oraculo"

    def __init__(self, contactos, lift_verdad):
        mejor = lift_verdad.argmax(axis=2)
        self.elegida = mejor[contactos["sector"], contactos["campana"]]

    def elegir(self, lote, rng):
        return self.elegida[lote]
