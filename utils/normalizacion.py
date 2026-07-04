import re
import unicodedata
from typing import Any, List, Optional


def normalizar_texto(valor: Any) -> str:
    """
    Normaliza texto para comparaciones:
    - minúsculas,
    - sin tildes,
    - sin signos especiales,
    - espacios unificados.
    """
    if valor is None:
        return ""

    texto = str(valor).strip().lower()

    texto = "".join(
        c for c in unicodedata.normalize("NFKD", texto)
        if not unicodedata.combining(c)
    )

    texto = re.sub(r"[^a-z0-9]+", " ", texto)
    texto = re.sub(r"\s+", " ", texto).strip()

    return texto


def limpiar_valor(valor: Any) -> str:
    """
    Convierte valores a texto limpio.
    """
    if valor is None:
        return ""

    texto = str(valor).strip()

    if texto.lower() in ["none", "null", "nan", ""]:
        return ""

    return texto


def valor_a_numero(valor: Any) -> Optional[float]:
    """
    Convierte valores numéricos escritos como texto a float.
    Soporta porcentajes y separadores comunes.
    """
    if valor is None:
        return None

    texto = str(valor).strip()

    if texto == "":
        return None

    texto = texto.replace("%", "")
    texto = texto.replace(".", "")
    texto = texto.replace(",", ".")

    permitido = "0123456789.-"
    texto = "".join(c for c in texto if c in permitido)

    if texto in ["", "-", ".", "-."]:
        return None

    try:
        return float(texto)
    except ValueError:
        return None


def contiene_frase_completa(texto: str, frase: str) -> bool:
    """
    Verifica si una frase aparece como unidad completa.
    Evita falsos positivos como Achí dentro de bachilleres.
    """
    texto_norm = normalizar_texto(texto)
    frase_norm = normalizar_texto(frase)

    if not texto_norm or not frase_norm:
        return False

    return f" {frase_norm} " in f" {texto_norm} "


def contiene_alguna(texto: str, palabras: List[str]) -> bool:
    """
    Verifica si el texto contiene alguna palabra o expresión.
    """
    texto_norm = normalizar_texto(texto)

    return any(
        normalizar_texto(palabra) in texto_norm
        for palabra in palabras
    )


def deduplicar_lista(valores: List[Any]) -> List[Any]:
    """
    Elimina duplicados conservando el orden original.
    """
    salida = []
    vistos = set()

    for valor in valores:
        clave = normalizar_texto(valor)

        if clave and clave not in vistos:
            salida.append(valor)
            vistos.add(clave)

    return salida