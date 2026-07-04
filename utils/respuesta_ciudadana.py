from typing import Any, Dict, List, Optional


def construir_fuente(
    dataset_key: str,
    nombre: str,
    url: str,
    descripcion: Optional[str] = None
) -> Dict[str, Any]:
    """
    Construye una fuente trazable para respuestas ciudadanas.
    """
    return {
        "dataset_key": dataset_key,
        "nombre": nombre,
        "url": url,
        "descripcion": descripcion
    }


def construir_respuesta_error(
    mensaje: str,
    detalle: Optional[str] = None,
    fuentes_usadas: Optional[List[Dict[str, Any]]] = None
) -> Dict[str, Any]:
    """
    Respuesta estándar cuando ocurre un error controlado.
    """
    hallazgos = [mensaje]

    if detalle:
        hallazgos.append(detalle)

    return {
        "respuesta_corta": mensaje,
        "hallazgos_principales": hallazgos,
        "datos": {},
        "fuentes_usadas": fuentes_usadas or [],
        "limitaciones": [
            "La consulta no pudo completarse con los filtros usados.",
            "Puede ser necesario revisar el nombre del territorio, ampliar el límite o verificar la fuente."
        ],
        "sugerencias_de_siguiente_pregunta": [
            "¿Quieres intentar con otro municipio o departamento?",
            "¿Quieres consultar las columnas disponibles del dataset?",
            "¿Quieres hacer una consulta más general?"
        ]
    }


def construir_respuesta_base(
    respuesta_corta: str,
    hallazgos_principales: Optional[List[str]] = None,
    datos: Optional[Dict[str, Any]] = None,
    fuentes_usadas: Optional[List[Dict[str, Any]]] = None,
    limitaciones: Optional[List[str]] = None,
    sugerencias: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Estructura base para respuestas ciudadanas.
    """
    return {
        "respuesta_corta": respuesta_corta,
        "hallazgos_principales": hallazgos_principales or [],
        "datos": datos or {},
        "fuentes_usadas": fuentes_usadas or [],
        "limitaciones": limitaciones or [
            "La respuesta depende de la disponibilidad y actualización de los datos abiertos.",
            "La lectura es descriptiva y debe contrastarse con fuentes institucionales."
        ],
        "sugerencias_de_siguiente_pregunta": sugerencias or []
    }


def adaptar_servicio_a_respuesta_ciudadana(resultado: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normaliza respuestas de servicios especializados para que la app o el GPT
    puedan consumirlas de manera consistente.
    """
    if not isinstance(resultado, dict):
        return construir_respuesta_error(
            mensaje="El servicio no devolvió una respuesta válida."
        )

    return {
        "respuesta_corta": resultado.get("respuesta_corta")
        or resultado.get("respuesta_ciudadana", {}).get("respuesta_corta")
        or "Consulta procesada.",
        "hallazgos_principales": resultado.get("hallazgos_principales")
        or resultado.get("respuesta_ciudadana", {}).get("hallazgos_integrados")
        or [],
        "datos": resultado.get("datos")
        or resultado.get("resumen_ejecutivo")
        or resultado.get("respuesta_ciudadana", {}).get("resumen_ejecutivo")
        or {},
        "fuentes_usadas": resultado.get("fuentes_usadas") or [],
        "limitaciones": resultado.get("limitaciones")
        or resultado.get("respuesta_ciudadana", {}).get("limitaciones")
        or [],
        "sugerencias_de_siguiente_pregunta": resultado.get("sugerencias_de_siguiente_pregunta")
        or resultado.get("respuesta_ciudadana", {}).get("sugerencias_de_siguiente_pregunta")
        or []
    }