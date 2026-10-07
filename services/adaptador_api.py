"""Convierte los servicios educativos al contrato público, sin perder evidencia."""

from collections import deque
from typing import Any, Dict, Iterable, List, Optional
import re
from services.presentacion_service import construir_colecciones, construir_resumenes_icetex


def _textos(valor: Any) -> List[str]:
    if isinstance(valor, str):
        return [valor] if valor.strip() else []
    if isinstance(valor, (list, tuple)):
        return [texto for texto in valor if isinstance(texto, str) and texto.strip()]
    return []


def _unicos(textos: Iterable[str]) -> List[str]:
    return list(dict.fromkeys(textos))


def _fragmentos(resultado: Dict[str, Any]):
    # Solo recorrer estructuras de servicio conocidas, nunca las filas de datos.
    pendientes = deque([(resultado, 0)])
    vistos = set()
    while pendientes:
        fragmento, nivel = pendientes.popleft()
        if not isinstance(fragmento, dict) or id(fragmento) in vistos:
            continue
        vistos.add(id(fragmento))
        yield fragmento
        if nivel >= 5:
            continue
        for clave in ("respuesta_ciudadana", "resultados"):
            hijo = fragmento.get(clave)
            if isinstance(hijo, dict):
                pendientes.append((hijo, nivel + 1))
        for clave in ("componentes", "componentes_crudos"):
            hijos = fragmento.get(clave)
            if isinstance(hijos, dict):
                pendientes.extend((hijo, nivel + 1) for hijo in hijos.values() if isinstance(hijo, dict))
        if "ok" in fragmento and isinstance(fragmento.get("datos"), dict):
            pendientes.append((fragmento["datos"], nivel + 1))


def extraer_fuentes(resultado: Dict[str, Any]) -> List[str]:
    fuentes = []
    for fragmento in _fragmentos(resultado):
        for clave in ("fuente_usada", "fuentes_usadas", "fuentes"):
            valor = fragmento.get(clave)
            elementos = valor if isinstance(valor, list) else [valor]
            for fuente in elementos:
                if isinstance(fuente, dict):
                    fuentes.extend(_textos(fuente.get("nombre")))
                    fuentes.extend(_textos(fuente.get("url")))
                else:
                    fuentes.extend(_textos(fuente))
    return _unicos(fuentes)


def extraer_advertencias(resultado: Dict[str, Any]) -> List[str]:
    advertencias = []
    for fragmento in _fragmentos(resultado):
        for clave in ("limitaciones", "advertencias", "advertencias_o_limitaciones", "alertas_de_lectura"):
            advertencias.extend(_textos(fragmento.get(clave)))
        if fragmento.get("ok") is False and fragmento.get("error"):
            advertencias.extend(f"Componente no disponible: {texto}" for texto in _textos(fragmento["error"]))
    return _unicos(advertencias)


def _respuesta_ciudadana(resultado: Dict[str, Any]) -> Dict[str, Any]:
    valor = resultado.get("respuesta_ciudadana")
    return valor if isinstance(valor, dict) else resultado


def _adaptar(resultado: Dict[str, Any], pregunta: Optional[str], datos: Dict[str, Any], respuesta: Optional[str] = None) -> Dict[str, Any]:
    datos["colecciones"] = construir_colecciones(_fragmentos(resultado))
    datos["resumenes_icetex"] = construir_resumenes_icetex(_fragmentos(resultado))
    ciudadana = _respuesta_ciudadana(resultado)
    texto = respuesta or ciudadana.get("respuesta_corta") or resultado.get("respuesta") or "Consulta procesada por EducaDatos."
    hallazgos = _textos(ciudadana.get("hallazgos_principales") or ciudadana.get("hallazgos_integrados"))
    hallazgos = [h for h in hallazgos if not re.search(r"registros descargados|filtros locales|se filtr[oó] el dataset|l[ií]mite.*consulta|columna.*detectada", h, re.I)]
    if hallazgos:
        texto += "\n\nHallazgos principales:\n" + "\n".join(f"- {hallazgo}" for hallazgo in hallazgos[:8])
    fuentes = extraer_fuentes(resultado)
    advertencias = extraer_advertencias(resultado)
    # Expone también el formato estructurado que consume la interfaz del ZIP.
    resumen = {**ciudadana} if ciudadana is not resultado else {
        "respuesta_corta": respuesta or ciudadana.get("respuesta_corta") or texto,
        "hallazgos_principales": hallazgos,
        "sugerencias_de_siguiente_pregunta": ciudadana.get("sugerencias_de_siguiente_pregunta", []),
    }
    resumen["limitaciones"] = advertencias
    return {"pregunta": pregunta, "respuesta": texto, "datos": datos, "fuentes": fuentes,
            "advertencias": advertencias, "respuesta_ciudadana": resumen}


def adaptar_consulta_para_app(resultado: Dict[str, Any]) -> Dict[str, Any]:
    ciudadana = _respuesta_ciudadana(resultado)
    servicio = resultado.get("resultados")
    servicio = servicio if isinstance(servicio, dict) else {}
    campos = ("pregunta_recibida", "intencion_detectada", "explicacion_enrutamiento", "dataset_usado",
              "territorio_detectado", "texto_busqueda_usado", "total_resultados")
    datos = {clave: resultado.get(clave) for clave in campos}
    datos.update({"detalle_consulta": servicio.get("datos", {}),
                  "resultados_muestra": ciudadana.get("resultados_muestra", []),
                  "sugerencias_de_siguiente_pregunta": ciudadana.get("sugerencias_de_siguiente_pregunta", [])})
    return _adaptar(resultado, resultado.get("pregunta_recibida"), datos)


def adaptar_servicio_para_app(resultado: Dict[str, Any], pregunta: Optional[str] = None,
                              respuesta: Optional[str] = None) -> Dict[str, Any]:
    ciudadana = _respuesta_ciudadana(resultado)
    datos = {**resultado}
    datos["detalle_consulta"] = resultado.get("datos", resultado.get("resumen_ejecutivo", {}))
    muestras = ciudadana.get("resultados_muestra")
    if muestras is None and isinstance(datos["detalle_consulta"], dict):
        for clave in ("lista_establecimientos", "muestra_establecimientos", "muestra_programas",
                      "muestra_bachilleres", "muestra_icetex"):
            valor = datos["detalle_consulta"].get(clave)
            if isinstance(valor, list) and valor:
                muestras = valor
                break
    datos["resultados_muestra"] = muestras if isinstance(muestras, list) else []
    datos["sugerencias_de_siguiente_pregunta"] = ciudadana.get("sugerencias_de_siguiente_pregunta", [])
    return _adaptar(resultado, pregunta, datos, respuesta)
