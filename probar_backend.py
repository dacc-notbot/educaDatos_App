import os
import json
import time
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode

import requests


BASE_URL = os.getenv("EDUCADATOS_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
OUTPUT_FILE = os.getenv("EDUCADATOS_TEST_OUTPUT", "resultado_pruebas_backend.json")

TIMEOUT_GET = 180
TIMEOUT_CHAT = 240


PREGUNTAS_CHAT = [
    # Salud general
    "Hola",

    # Detección territorial
    "¿Qué datos educativos hay en Meta?",
    "Haz un diagnóstico educativo de Soacha",

    # Establecimientos educativos
    "¿Qué colegios hay en Soacha?",
    "¿Qué colegios oficiales hay en Soacha?",
    "¿Qué colegios privados hay en Villavicencio?",
    "¿Cuántos colegios hay en Villavicencio?",

    # Programas de educación superior
    "¿Qué programas de educación superior hay en Cundinamarca?",
    "¿Qué programas de educación superior hay en Medellín?",
    "¿Qué universidades ofrecen programas en Cali?",
    "¿Qué programas de ingeniería hay en Bogotá?",

    # Bachilleres
    "¿Cuántos bachilleres hay en Cundinamarca?",
    "¿Cuántos bachilleres se graduaron en Villavicencio?",
    "¿Cuántos bachilleres hay en Meta?",

    # ICETEX
    "¿Qué créditos ICETEX hay en Cundinamarca?",
    "¿Qué créditos ICETEX renovados hay en Cundinamarca?",
    "¿Qué créditos ICETEX hay en Meta?",

    # Cruce de tránsito educativo
    "¿Qué relación hay entre bachilleres, educación superior e ICETEX en Cundinamarca?",
    "¿Qué relación hay entre bachilleres, educación superior e ICETEX en Meta?",
    "¿Qué oportunidades tienen los bachilleres de Soacha para acceder a educación superior?",
    "¿Qué relación hay entre oferta de educación superior, graduados y crédito educativo en Cundinamarca?",

    # Agrupación estadística / clustering
    "¿Qué grupo estadístico describe mejor a Soacha?",
    "¿Qué grupo describe mejor a Villavicencio?",
    "¿Qué clúster describe mejor a Soacha?",
    "¿Qué municipios se parecen a Villavicencio?",
    "¿Qué municipios del Meta tienen condiciones educativas similares?",
    "¿Qué recomendaciones educativas tiene Soacha?",

    # Diagnóstico integral
    "Haz un diagnóstico educativo de Soacha",
    "Haz un diagnóstico educativo de Villavicencio",
    "Dame un panorama educativo de Cundinamarca",
]


def ruta_con_query(path: str, params: Optional[Dict[str, Any]] = None) -> str:
    if not params:
        return path

    return f"{path}?{urlencode(params)}"


RUTAS_GET = [
    {
        "nombre": "health",
        "ruta": "/health",
    },
    {
        "nombre": "verificar_estado_api",
        "ruta": "/verificarEstadoApi",
    },
    {
        "nombre": "datasets",
        "ruta": "/datasets",
    },
    {
        "nombre": "detectar_territorio_cundinamarca",
        "ruta": ruta_con_query(
            "/territorios/detectar",
            {
                "pregunta": "Qué relación hay entre bachilleres educación superior e ICETEX en Cundinamarca"
            }
        ),
    },
    {
        "nombre": "detectar_territorio_soacha",
        "ruta": ruta_con_query(
            "/territorios/detectar",
            {
                "pregunta": "Haz un diagnóstico educativo de Soacha"
            }
        ),
    },
    {
        "nombre": "colegios_soacha",
        "ruta": ruta_con_query(
            "/colegios",
            {
                "departamento": "Cundinamarca",
                "municipio": "Soacha"
            }
        ),
    },
    {
        "nombre": "colegios_villavicencio_privados",
        "ruta": ruta_con_query(
            "/colegios",
            {
                "departamento": "Meta",
                "municipio": "Villavicencio",
                "sector": "privado"
            }
        ),
    },
    {
        "nombre": "diagnostico_soacha",
        "ruta": ruta_con_query(
            "/diagnostico-municipal",
            {
                "departamento": "Cundinamarca",
                "municipio": "Soacha"
            }
        ),
    },
    {
        "nombre": "diagnostico_cundinamarca",
        "ruta": ruta_con_query(
            "/diagnostico-municipal",
            {
                "departamento": "Cundinamarca"
            }
        ),
    },
    {
        "nombre": "grupo_estadistico_soacha",
        "ruta": ruta_con_query(
            "/cluster/municipio",
            {
                "departamento": "Cundinamarca",
                "municipio": "Soacha"
            }
        ),
    },
    {
        "nombre": "similares_villavicencio",
        "ruta": ruta_con_query(
            "/similar/municipios",
            {
                "departamento": "Meta",
                "municipio": "Villavicencio"
            }
        ),
    },
    {
        "nombre": "transito_cundinamarca",
        "ruta": ruta_con_query(
            "/cruce/transito-educativo",
            {
                "departamento": "Cundinamarca"
            }
        ),
    },
    {
        "nombre": "metadata_clustering",
        "ruta": "/metadata",
    },
    {
        "nombre": "openapi_gpt",
        "ruta": "/openapi-gpt.json",
    },
]


def recortar(valor: Any, max_len: int = 700) -> str:
    if isinstance(valor, (dict, list)):
        texto = json.dumps(valor, ensure_ascii=False)
    else:
        texto = str(valor)

    if len(texto) <= max_len:
        return texto

    return texto[:max_len] + "..."


def leer_json_seguro(response: requests.Response) -> Any:
    try:
        return response.json()
    except Exception:
        return {
            "respuesta_no_json": recortar(response.text, 1000)
        }


def extraer_respuesta_chat(data: Dict[str, Any]) -> str:
    """
    Soporta varias estructuras posibles del backend:
    - respuesta
    - respuesta_corta
    - respuesta_ciudadana.respuesta_corta
    """
    if not isinstance(data, dict):
        return ""

    if data.get("respuesta"):
        return str(data.get("respuesta"))

    if data.get("respuesta_corta"):
        return str(data.get("respuesta_corta"))

    respuesta_ciudadana = data.get("respuesta_ciudadana")

    if isinstance(respuesta_ciudadana, dict):
        return str(respuesta_ciudadana.get("respuesta_corta", ""))

    return ""


def extraer_intencion_chat(data: Dict[str, Any]) -> Any:
    if not isinstance(data, dict):
        return None

    datos = data.get("datos", {})

    if isinstance(datos, dict):
        return datos.get("intencion_detectada") or datos.get("intencion")

    return None


def extraer_territorio_chat(data: Dict[str, Any]) -> Any:
    if not isinstance(data, dict):
        return None

    datos = data.get("datos", {})

    if isinstance(datos, dict):
        return datos.get("territorio_detectado") or datos.get("territorio")

    return None


def validar_openapi(data: Any) -> List[str]:
    """
    Revisa que el OpenAPI tenga rutas y operationId importantes para el GPT.
    """
    advertencias = []

    if not isinstance(data, dict):
        return ["La respuesta de OpenAPI no es un objeto JSON."]

    paths = data.get("paths", {})

    if not paths:
        advertencias.append("El OpenAPI no contiene paths.")

    texto_openapi = json.dumps(data, ensure_ascii=False)

    operation_ids_esperados = [
        "verificarEstadoApi",
        "chatCiudadanoEducaDatos",
        "consultaCiudadanaEducativa",
        "generarDiagnosticoTerritorialEducativo",
        "analizarTransitoEducativo",
        "consultarClusterMunicipio",
        "buscarMunicipiosSimilares",
        "consultarColegiosAlias",
        "detectarTerritorioPregunta",
    ]

    faltantes = [
        op_id
        for op_id in operation_ids_esperados
        if op_id not in texto_openapi
    ]

    if faltantes:
        advertencias.append(
            "OperationId faltantes o no visibles en OpenAPI: "
            + ", ".join(faltantes)
        )

    return advertencias


def validar_respuesta_get(nombre: str, ruta: str, data: Any) -> List[str]:
    advertencias = []

    if nombre == "openapi_gpt":
        advertencias.extend(validar_openapi(data))

    if nombre == "health" and isinstance(data, dict):
        status = str(data.get("status", "")).lower()
        if status not in ["ok", "healthy", "success"]:
            advertencias.append("La ruta /health no devolvió status esperado.")

    if nombre.startswith("detectar_territorio") and isinstance(data, dict):
        if not data.get("departamento_detectado") and not data.get("municipio_detectado"):
            advertencias.append("No se detectó territorio en la prueba.")

    return advertencias


def probar_get(session: requests.Session, item: Dict[str, str]) -> Dict[str, Any]:
    ruta = item["ruta"]
    nombre = item.get("nombre", ruta)
    url = BASE_URL + ruta
    inicio = time.time()

    try:
        response = session.get(url, timeout=TIMEOUT_GET)
        duracion = round(time.time() - inicio, 2)
        data = leer_json_seguro(response)
        ok = response.status_code < 400

        advertencias = validar_respuesta_get(nombre, ruta, data) if ok else []

        return {
            "tipo": "GET",
            "nombre": nombre,
            "ruta": ruta,
            "url": url,
            "status_code": response.status_code,
            "ok": ok,
            "tiempo_segundos": duracion,
            "advertencias": advertencias,
            "respuesta": data if ok else recortar(response.text, 1500)
        }

    except Exception as error:
        duracion = round(time.time() - inicio, 2)

        return {
            "tipo": "GET",
            "nombre": nombre,
            "ruta": ruta,
            "url": url,
            "status_code": None,
            "ok": False,
            "tiempo_segundos": duracion,
            "advertencias": [],
            "error": str(error)
        }


def validar_respuesta_chat(pregunta: str, data: Any) -> List[str]:
    advertencias = []

    if not isinstance(data, dict):
        return ["La respuesta del chat no es un objeto JSON."]

    respuesta = extraer_respuesta_chat(data)

    if not respuesta:
        advertencias.append("La respuesta del chat no trae texto principal.")

    pregunta_norm = pregunta.lower()

    if "villavicencio" in pregunta_norm:
        territorio = json.dumps(data, ensure_ascii=False).lower()
        if "villavicencio" not in territorio:
            advertencias.append("La respuesta no parece conservar Villavicencio como territorio.")

    if "soacha" in pregunta_norm:
        territorio = json.dumps(data, ensure_ascii=False).lower()
        if "soacha" not in territorio:
            advertencias.append("La respuesta no parece conservar Soacha como territorio.")

    if "clúster" in pregunta_norm or "cluster" in pregunta_norm or "grupo" in pregunta_norm:
        texto = json.dumps(data, ensure_ascii=False).lower()
        if "grupo" not in texto and "cluster" not in texto and "clúster" not in texto:
            advertencias.append("La respuesta no parece incluir grupo estadístico o cluster.")

    if "relación" in pregunta_norm or "oportunidades" in pregunta_norm:
        texto = json.dumps(data, ensure_ascii=False).lower()
        if "exploratorio" not in texto and "descriptiv" not in texto:
            advertencias.append("La respuesta de cruce debería aclarar que el análisis es descriptivo o exploratorio.")

    return advertencias


def probar_chat(session: requests.Session, pregunta: str) -> Dict[str, Any]:
    url = BASE_URL + "/chat"
    inicio = time.time()

    try:
        response = session.post(
            url,
            json={"pregunta": pregunta},
            timeout=TIMEOUT_CHAT
        )

        duracion = round(time.time() - inicio, 2)
        data = leer_json_seguro(response)
        ok = response.status_code < 400

        if ok:
            advertencias = validar_respuesta_chat(pregunta, data)

            return {
                "tipo": "POST /chat",
                "pregunta": pregunta,
                "status_code": response.status_code,
                "ok": True,
                "tiempo_segundos": duracion,
                "intencion": extraer_intencion_chat(data),
                "territorio": extraer_territorio_chat(data),
                "respuesta": recortar(extraer_respuesta_chat(data), 1000),
                "advertencias": advertencias,
                "respuesta_completa": data
            }

        return {
            "tipo": "POST /chat",
            "pregunta": pregunta,
            "status_code": response.status_code,
            "ok": False,
            "tiempo_segundos": duracion,
            "advertencias": [],
            "respuesta": recortar(response.text, 1500)
        }

    except Exception as error:
        duracion = round(time.time() - inicio, 2)

        return {
            "tipo": "POST /chat",
            "pregunta": pregunta,
            "status_code": None,
            "ok": False,
            "tiempo_segundos": duracion,
            "advertencias": [],
            "error": str(error)
        }


def imprimir_resultado_get(resultado: Dict[str, Any]) -> None:
    estado = "OK" if resultado["ok"] else "ERROR"
    print(f"[{estado}] GET {resultado.get('nombre')} → {resultado.get('status_code')} ({resultado.get('tiempo_segundos')}s)")

    if resultado.get("advertencias"):
        for advertencia in resultado["advertencias"]:
            print(f"  ADVERTENCIA: {advertencia}")

    if not resultado["ok"]:
        print("  Error:", resultado.get("error") or resultado.get("respuesta"))


def imprimir_resultado_chat(resultado: Dict[str, Any]) -> None:
    estado = "OK" if resultado["ok"] else "ERROR"
    print(f"[{estado}] {resultado.get('pregunta')} ({resultado.get('tiempo_segundos')}s)")

    if resultado["ok"]:
        print("  Intención:", resultado.get("intencion"))
        print("  Territorio:", resultado.get("territorio"))
        print("  Respuesta:", resultado.get("respuesta"))

        if resultado.get("advertencias"):
            for advertencia in resultado["advertencias"]:
                print(f"  ADVERTENCIA: {advertencia}")
    else:
        print("  Error:", resultado.get("error") or resultado.get("respuesta"))

    print("-" * 100)


def construir_resumen(
    resultados_get: List[Dict[str, Any]],
    resultados_chat: List[Dict[str, Any]]
) -> Dict[str, Any]:
    errores_get = [r for r in resultados_get if not r["ok"]]
    errores_chat = [r for r in resultados_chat if not r["ok"]]

    advertencias_get = [
        {
            "nombre": r.get("nombre"),
            "ruta": r.get("ruta"),
            "advertencias": r.get("advertencias", [])
        }
        for r in resultados_get
        if r.get("advertencias")
    ]

    advertencias_chat = [
        {
            "pregunta": r.get("pregunta"),
            "advertencias": r.get("advertencias", [])
        }
        for r in resultados_chat
        if r.get("advertencias")
    ]

    return {
        "base_url": BASE_URL,
        "get_total": len(resultados_get),
        "get_ok": sum(1 for r in resultados_get if r["ok"]),
        "get_error": len(errores_get),
        "chat_total": len(resultados_chat),
        "chat_ok": sum(1 for r in resultados_chat if r["ok"]),
        "chat_error": len(errores_chat),
        "advertencias_get_total": len(advertencias_get),
        "advertencias_chat_total": len(advertencias_chat),
        "errores_get": errores_get,
        "errores_chat": errores_chat,
        "advertencias_get": advertencias_get,
        "advertencias_chat": advertencias_chat,
    }


def main() -> None:
    print("\n=== EDUCADATOS - PRUEBAS DE BACKEND ===")
    print(f"Base URL: {BASE_URL}")
    print(f"Archivo de salida: {OUTPUT_FILE}")

    session = requests.Session()

    print("\n=== PROBANDO RUTAS GET ===\n")

    resultados_get = []

    for item in RUTAS_GET:
        resultado = probar_get(session, item)
        resultados_get.append(resultado)
        imprimir_resultado_get(resultado)

    print("\n=== PROBANDO CHAT CIUDADANO ===\n")

    resultados_chat = []

    for pregunta in PREGUNTAS_CHAT:
        resultado = probar_chat(session, pregunta)
        resultados_chat.append(resultado)
        imprimir_resultado_chat(resultado)

    resumen = construir_resumen(
        resultados_get=resultados_get,
        resultados_chat=resultados_chat
    )

    salida = {
        "resumen": resumen,
        "resultados_get": resultados_get,
        "resultados_chat": resultados_chat,
    }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(
            salida,
            f,
            ensure_ascii=False,
            indent=2
        )

    print("\n=== RESUMEN ===")
    print(json.dumps(resumen, ensure_ascii=False, indent=2))
    print(f"\nArchivo generado: {OUTPUT_FILE}")

    if resumen["get_error"] == 0 and resumen["chat_error"] == 0:
        print("\nRESULTADO GENERAL: OK. No hubo errores críticos.")
    else:
        print("\nRESULTADO GENERAL: REVISAR. Hay errores críticos en GET o CHAT.")


if __name__ == "__main__":
    main()