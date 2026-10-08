"""Distingue la vigencia explícita de registros y la actualización del portal."""

from datetime import datetime, timezone
import re

import requests

from utils.cache_datos import consultar_con_cache


URL_METADATOS = "https://www.datos.gov.co/api/views/upr9-nkiz.json"
NOMBRE_FUENTE = "Programas de educación superior · Ministerio de Educación Nacional"
MESES = ["", "enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
COLUMNAS_ANIO = ("anio_registro", "ano_registro", "año_registro", "anio", "ano", "año", "a_o", "vigencia")


def anio_explicito(valor):
    texto = str(valor).strip() if valor is not None else ""
    if not re.fullmatch(r"\d{4}(?:\.0+)?", texto):
        return None
    anio = int(float(texto))
    return anio if 1900 <= anio <= datetime.now(timezone.utc).year + 1 else None


def seleccionar_registro_reciente(registros):
    """Solo selecciona vigencia con una columna de año explícita, nunca por fechas de creación."""
    columnas = {clave for fila in registros for clave in fila}
    for columna in COLUMNAS_ANIO:
        if columna not in columnas:
            continue
        anios = [anio_explicito(fila.get(columna)) for fila in registros]
        publicados = [anio for anio in anios if anio is not None]
        if publicados:
            ultimo = max(publicados)
            return [fila for fila, anio in zip(registros, anios) if anio == ultimo], ultimo
    return registros, None


def obtener_metadatos_oferta():
    def descargar():
        try:
            respuesta = requests.get(URL_METADATOS, timeout=10)
            respuesta.raise_for_status()
            dato = respuesta.json()
        except (requests.RequestException, ValueError) as error:
            raise RuntimeError("No se pudo consultar la fecha de actualización de la fuente.") from error
        if not isinstance(dato, dict):
            raise RuntimeError("La fuente no informó metadatos válidos.")
        return [dato]

    try:
        datos = consultar_con_cache(URL_METADATOS, {}, descargar)
        return datos[0] if datos else {}
    except RuntimeError:
        # La falta de esta fecha no impide presentar las ofertas verificadas.
        return {}


def construir_procedencia_oferta(anio_registro=None):
    metadatos = obtener_metadatos_oferta()
    fecha = None
    try:
        if metadatos.get("rowsUpdatedAt") is not None:
            fecha = datetime.fromtimestamp(float(metadatos["rowsUpdatedAt"]), timezone.utc).date()
    except (TypeError, ValueError, OverflowError, OSError):
        pass
    texto = "Información de datos abiertos del Gobierno de Colombia, publicada por el Ministerio de Educación Nacional."
    if anio_registro is not None:
        texto += f" Se muestra el registro de {anio_registro}, el año más reciente que informa esta fuente."
    else:
        texto += " La fuente no informa el año de registro."
    if fecha is not None:
        texto += f" Última actualización de los datos: {fecha.day} de {MESES[fecha.month]} de {fecha.year}."
    else:
        texto += " No se pudo comprobar la fecha de actualización de los datos."
    return {
        "nombre_fuente": NOMBRE_FUENTE,
        "anio_registro": anio_registro,
        "fecha_actualizacion": fecha.isoformat() if fecha else None,
        "descripcion_ciudadana": texto,
    }
