"""Caché local de datos públicos; fallos y respuestas inválidas nunca se guardan."""

import hashlib
from contextlib import contextmanager
import json
import logging
import os
from pathlib import Path
import tempfile
from threading import RLock
import time

import config

_lock = RLock()
_consultas_activas = {}
_logger = logging.getLogger(__name__)


@contextmanager
def _bloquear_consulta(clave):
    # Solo las peticiones idénticas esperan la misma descarga. Una fuente lenta
    # no impide leer la caché ni consultar otra fuente. Retira las claves al salir.
    with _lock:
        entrada = _consultas_activas.setdefault(clave, [RLock(), 0])
        entrada[1] += 1
    try:
        with entrada[0]:
            yield
    finally:
        with _lock:
            entrada[1] -= 1
            if entrada[1] == 0:
                del _consultas_activas[clave]


def consultar_con_cache(url, params, descargar):
    if config.CACHE_TTL_SECONDS == 0:
        return descargar()
    clave = hashlib.sha256(
        json.dumps([url, params], sort_keys=True, default=str).encode()
    ).hexdigest()
    destino = Path(config.CACHE_DIR) / f"{clave}.json"
    # Evita descargas duplicadas dentro de un proceso. Los archivos son atómicos
    # para que otros procesos puedan leerlos sin observar una escritura parcial.
    with _bloquear_consulta(clave):
        try:
            entrada = json.loads(destino.read_text())
            if entrada["vence"] > time.time() and isinstance(entrada["datos"], list):
                return entrada["datos"]
        except (OSError, ValueError, KeyError, TypeError):
            pass

        datos = descargar()
        if not isinstance(datos, list):
            raise RuntimeError("La fuente no devolvió una lista de registros.")
        temporal = None
        try:
            destino.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(mode="w", dir=destino.parent, delete=False) as archivo:
                temporal = Path(archivo.name)
                json.dump({"vence": time.time() + config.CACHE_TTL_SECONDS, "datos": datos}, archivo)
            with _lock:
                archivos = sorted(destino.parent.glob("*.json"), key=lambda p: p.stat().st_mtime)
                for archivo in archivos[:max(0, len(archivos) - config.CACHE_MAX_ENTRIES + 1)]:
                    archivo.unlink(missing_ok=True)
                os.replace(temporal, destino)
        except OSError:
            _logger.warning("No fue posible guardar la caché de datos públicos", exc_info=True)
        finally:
            if temporal is not None:
                temporal.unlink(missing_ok=True)
        return datos
