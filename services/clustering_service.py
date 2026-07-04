import re
import math
import unicodedata
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from sklearn.preprocessing import StandardScaler
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.metrics.pairwise import euclidean_distances

try:
    from config import DATASET_BASE, DEFAULT_ANALYTIC_LIMIT, MAX_LIMIT
except Exception:
    DATASET_BASE = "estadisticas_municipio"
    DEFAULT_ANALYTIC_LIMIT = 100_000
    MAX_LIMIT = 1_000_000

from services.socrata_service import consultar_dataset


PALABRAS_CLAVE_EDU = [
    "cobertura", "deserc", "aprob", "reprob", "repit", "matricula",
    "permanencia", "extraedad", "transicion", "basica", "media",
    "preescolar", "oficial", "no_oficial", "alumno", "estudiante",
    "tasa", "indicador", "bachiller", "graduado"
]


CACHE_CLUSTERING = {
    "pipelines": {},
    "ultimo_resultado": None,
    "ultima_metadata": None,
    "ultimo_cache_key": None
}


# ============================================================
# Utilidades de normalización
# ============================================================

def normalizar_texto_cluster(valor: Any) -> str:
    if valor is None:
        return ""

    texto = str(valor).strip().lower()
    texto = "".join(
        c for c in unicodedata.normalize("NFKD", texto)
        if not unicodedata.combining(c)
    )
    texto = re.sub(r"[^a-z0-9]+", "_", texto).strip("_")
    return texto


def limpiar_para_json(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {str(k): limpiar_para_json(v) for k, v in obj.items()}

    if isinstance(obj, list):
        return [limpiar_para_json(v) for v in obj]

    if isinstance(obj, tuple):
        return [limpiar_para_json(v) for v in obj]

    if isinstance(obj, np.integer):
        return int(obj)

    if isinstance(obj, np.floating):
        if np.isnan(obj) or np.isinf(obj):
            return None
        return float(obj)

    if isinstance(obj, pd.Timestamp):
        return obj.isoformat()

    if obj is pd.NA or obj is None:
        return None

    if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
        return None

    return obj


def resolver_limit_clustering(limit: Optional[int]) -> int:
    try:
        limit_final = int(limit) if limit is not None else DEFAULT_ANALYTIC_LIMIT
    except (TypeError, ValueError):
        limit_final = DEFAULT_ANALYTIC_LIMIT

    limit_final = max(100, limit_final)
    limit_final = min(limit_final, MAX_LIMIT)

    return limit_final


def valor_a_float(valor: Any) -> float:
    if pd.isna(valor):
        return np.nan

    if isinstance(valor, (int, float, np.integer, np.floating)):
        return float(valor)

    texto = str(valor).strip()

    if texto == "" or texto.lower() in ["nan", "none", "null", "sin dato", "nd", "n.d."]:
        return np.nan

    texto = texto.replace("%", "")
    texto = re.sub(r"[^0-9,\.\-]", "", texto)

    if texto in ["", "-", ".", ","]:
        return np.nan

    if "," in texto and "." in texto:
        if texto.rfind(",") > texto.rfind("."):
            texto = texto.replace(".", "").replace(",", ".")
        else:
            texto = texto.replace(",", "")
    elif "," in texto and "." not in texto:
        partes = texto.split(",")
        if len(partes[-1]) <= 2:
            texto = texto.replace(",", ".")
        else:
            texto = texto.replace(",", "")

    try:
        return float(texto)
    except ValueError:
        return np.nan


def serie_a_numerica(serie: pd.Series) -> pd.Series:
    return serie.apply(valor_a_float)


def limpiar_etiqueta_variable(nombre: str) -> str:
    """
    Convierte nombres técnicos de columnas en etiquetas más legibles.
    """
    texto = str(nombre).replace("_", " ").strip().lower()

    reemplazos = {
        "aprobaci n": "aprobación",
        "deserci n": "deserción",
        "reprobaci n": "reprobación",
        "repitici n": "repitición",
        "matr cula": "matrícula",
        "educaci n": "educación",
        "transici n": "transición",
        "b sica": "básica",
        "preescolar": "preescolar",
        "basica": "básica",
        "matricula": "matrícula",
        "aprobacion": "aprobación",
        "desercion": "deserción",
        "reprobacion": "reprobación",
        "transicion": "transición",
    }

    for malo, bueno in reemplazos.items():
        texto = texto.replace(malo, bueno)

    texto = re.sub(r"\s+", " ", texto).strip()
    return texto


def nombre_legible_variable(variable: str) -> str:
    return limpiar_etiqueta_variable(variable)


# ============================================================
# Detección de columnas
# ============================================================

def buscar_columna(
    df: pd.DataFrame,
    patrones: List[str],
    excluir: Optional[List[str]] = None
) -> Optional[str]:
    excluir = excluir or []

    patrones_norm = [normalizar_texto_cluster(p) for p in patrones]
    excluir_norm = [normalizar_texto_cluster(e) for e in excluir]

    for col in df.columns:
        nombre = normalizar_texto_cluster(col)

        if nombre in patrones_norm and not any(e in nombre for e in excluir_norm):
            return col

    for col in df.columns:
        nombre = normalizar_texto_cluster(col)

        if any(p in nombre for p in patrones_norm) and not any(e in nombre for e in excluir_norm):
            return col

    return None


def detectar_columnas_base(df: pd.DataFrame) -> Dict[str, Optional[str]]:
    depto_col = buscar_columna(
        df,
        ["departamento", "depto", "nombre_departamento", "nom_departamento", "dpto"],
        excluir=["codigo", "cod", "id"]
    )

    municipio_col = buscar_columna(
        df,
        ["municipio", "muni", "nombre_municipio", "nom_municipio", "mpio"],
        excluir=["codigo", "cod", "id"]
    )

    anio_col = buscar_columna(
        df,
        ["anio", "ano", "año", "vigencia", "periodo", "year"],
        excluir=["codigo", "cod", "id"]
    )

    return {
        "departamento": depto_col,
        "municipio": municipio_col,
        "anio": anio_col
    }


# ============================================================
# Preparación de datos
# ============================================================

def filtrar_por_departamento_y_anio(
    df: pd.DataFrame,
    columnas_base: Dict[str, Optional[str]],
    departamento: Optional[str] = None,
    anio: Optional[int] = None
) -> Tuple[pd.DataFrame, List[str], Optional[int]]:
    df_filtrado = df.copy()
    advertencias = []
    anio_usado = None

    depto_col = columnas_base.get("departamento")
    anio_col = columnas_base.get("anio")

    if departamento:
        if not depto_col:
            advertencias.append(
                "Se solicitó filtrar por departamento, pero no se detectó columna de departamento."
            )
        else:
            depto_norm = normalizar_texto_cluster(departamento)
            df_filtrado = df_filtrado[
                df_filtrado[depto_col].astype(str).apply(normalizar_texto_cluster) == depto_norm
            ]

            if df_filtrado.empty:
                raise ValueError(
                    f"No se encontraron registros para el departamento '{departamento}'."
                )

    if anio_col:
        df_filtrado["__anio_num__"] = serie_a_numerica(df_filtrado[anio_col])

        if anio is not None:
            df_filtrado = df_filtrado[df_filtrado["__anio_num__"] == int(anio)]
            anio_usado = int(anio)

            if df_filtrado.empty:
                raise ValueError(
                    f"No se encontraron registros para el año o vigencia {anio}."
                )
        else:
            anios_validos = sorted(df_filtrado["__anio_num__"].dropna().unique())

            if len(anios_validos) > 0:
                anio_usado = int(max(anios_validos))
                df_filtrado = df_filtrado[df_filtrado["__anio_num__"] == anio_usado]
                advertencias.append(
                    f"No se indicó año. Se usó la vigencia más reciente detectada: {anio_usado}."
                )
            else:
                advertencias.append(
                    "Se detectó columna de año, pero no fue posible convertir sus valores a número."
                )

    elif anio is not None:
        advertencias.append(
            "Se solicitó filtrar por año, pero no se detectó una columna temporal."
        )

    return df_filtrado, advertencias, anio_usado


def seleccionar_variables_numericas(
    df: pd.DataFrame,
    columnas_base: Dict[str, Optional[str]],
    max_variables: int = 120
) -> Tuple[pd.DataFrame, List[str], List[str]]:
    df_num = df.copy()
    advertencias = []

    columnas_excluidas = set()

    for col in columnas_base.values():
        if col:
            columnas_excluidas.add(col)

    columnas_excluidas.add("__anio_num__")

    patrones_exclusion = [
        "codigo", "cod", "id", "dane", "latitud", "longitud",
        "fecha", "telefono", "nit", "consecutivo"
    ]

    candidatas = []

    for col in df_num.columns:
        nombre = normalizar_texto_cluster(col)

        if col in columnas_excluidas:
            continue

        if any(p in nombre for p in patrones_exclusion):
            continue

        serie_num = serie_a_numerica(df_num[col])
        ratio = serie_num.notna().mean()
        unicos = serie_num.dropna().nunique()

        if ratio >= 0.5 and unicos >= 2:
            df_num[col] = serie_num
            candidatas.append(col)

    if len(candidatas) < 2:
        raise ValueError(
            "El dataset no tiene suficientes variables numéricas útiles para agrupación estadística. "
            "Se requieren al menos dos variables numéricas con variación."
        )

    candidatas_preferidas = [
        col for col in candidatas
        if any(palabra in normalizar_texto_cluster(col) for palabra in PALABRAS_CLAVE_EDU)
    ]

    if len(candidatas_preferidas) >= 2:
        candidatas = candidatas_preferidas
    else:
        advertencias.append(
            "No se encontraron suficientes variables con nombres educativos claros; "
            "se usaron variables numéricas disponibles."
        )

    if len(candidatas) > max_variables:
        varianzas = df_num[candidatas].var(numeric_only=True).sort_values(ascending=False)
        candidatas = varianzas.head(max_variables).index.tolist()
        advertencias.append(
            f"Había muchas variables numéricas. Se seleccionaron {max_variables} por mayor varianza."
        )

    return df_num, candidatas, advertencias


def preparar_datos_para_clustering(
    departamento: Optional[str] = None,
    anio: Optional[int] = None,
    limit: int = DEFAULT_ANALYTIC_LIMIT
) -> Dict[str, Any]:
    limit_final = resolver_limit_clustering(limit)

    registros = consultar_dataset(
        dataset_key=DATASET_BASE,
        limit=limit_final
    )

    if not registros:
        raise ValueError("No se recibieron registros desde el dataset base.")

    df_raw = pd.DataFrame(registros)
    columnas_base = detectar_columnas_base(df_raw)

    if not columnas_base.get("municipio"):
        raise ValueError(
            "No se detectó una columna de municipio. Para la agrupación estadística municipal se requiere identificar municipios."
        )

    df_filtrado, advertencias_filtro, anio_usado = filtrar_por_departamento_y_anio(
        df_raw,
        columnas_base,
        departamento=departamento,
        anio=anio
    )

    df_num, variables, advertencias_vars = seleccionar_variables_numericas(
        df_filtrado,
        columnas_base
    )

    depto_col = columnas_base.get("departamento")
    municipio_col = columnas_base.get("municipio")

    group_cols = []

    if depto_col:
        group_cols.append(depto_col)

    group_cols.append(municipio_col)

    df_entidades = df_num[group_cols + variables].copy()
    df_entidades = df_entidades.groupby(group_cols, dropna=False)[variables].mean().reset_index()

    variables_validas = []

    for col in variables:
        if df_entidades[col].notna().sum() >= 3 and df_entidades[col].nunique(dropna=True) >= 2:
            variables_validas.append(col)

    if len(variables_validas) < 2:
        raise ValueError(
            "Después de filtrar y agrupar no quedaron suficientes variables numéricas con variación."
        )

    variables = variables_validas

    for col in variables:
        mediana = df_entidades[col].median()
        df_entidades[col] = df_entidades[col].fillna(mediana)

    df_entidades = df_entidades.dropna(subset=variables)

    if len(df_entidades) < 4:
        raise ValueError(
            "No hay suficientes municipios o registros para aplicar agrupación estadística. "
            "Se recomiendan al menos 4 entidades."
        )

    advertencias = advertencias_filtro + advertencias_vars + [
        "Los valores faltantes fueron imputados con la mediana para permitir el análisis exploratorio.",
        "La agrupación estadística identifica similitudes entre municipios; no demuestra causalidad ni reemplaza el análisis territorial cualitativo."
    ]

    return {
        "df_modelo": df_entidades,
        "columnas_base": columnas_base,
        "variables": variables,
        "advertencias": advertencias,
        "anio_usado": anio_usado,
        "limit_usado": limit_final,
        "fecha_consulta": datetime.now().isoformat(timespec="seconds")
    }


# ============================================================
# Modelo KMeans
# ============================================================

def elegir_k_por_silhouette(X_scaled: np.ndarray, k_max: int = 6) -> Dict[str, Any]:
    n = X_scaled.shape[0]

    if n < 4:
        raise ValueError("No hay suficientes registros para evaluar silhouette score.")

    k_max = min(k_max, n - 1)
    resultados = []

    for k in range(2, k_max + 1):
        modelo = KMeans(n_clusters=k, random_state=42, n_init=10)
        labels = modelo.fit_predict(X_scaled)

        try:
            score = silhouette_score(X_scaled, labels)
            resultados.append({
                "k": k,
                "silhouette": float(score),
                "inertia": float(modelo.inertia_)
            })
        except Exception:
            continue

    if not resultados:
        return {
            "k_seleccionado": 2,
            "evaluacion": [],
            "criterio": "respaldo_k_2"
        }

    mejor = max(resultados, key=lambda x: x["silhouette"])

    return {
        "k_seleccionado": int(mejor["k"]),
        "evaluacion": resultados,
        "criterio": "mayor_silhouette_score"
    }


def aplicar_clustering(
    preparado: Dict[str, Any],
    n_clusters: Optional[int] = None
) -> Dict[str, Any]:
    df = preparado["df_modelo"].copy()
    variables = preparado["variables"]

    X = df[variables].values

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    n_registros = X_scaled.shape[0]

    if n_registros < 4:
        raise ValueError("Se requieren al menos 4 registros para aplicar agrupación estadística.")

    if n_clusters is None:
        evaluacion_k = elegir_k_por_silhouette(X_scaled, k_max=6)
        n_clusters_final = evaluacion_k["k_seleccionado"]
    else:
        n_clusters_final = int(n_clusters)
        n_clusters_final = max(2, min(n_clusters_final, min(8, n_registros - 1)))
        evaluacion_k = {
            "k_seleccionado": n_clusters_final,
            "evaluacion": [],
            "criterio": "valor_indicado_por_usuario_ajustado_a_rango_valido"
        }

    modelo = KMeans(n_clusters=n_clusters_final, random_state=42, n_init=10)
    labels = modelo.fit_predict(X_scaled)

    df["cluster"] = labels.astype(int)

    return {
        "df_resultado": df,
        "X_scaled": X_scaled,
        "scaler": scaler,
        "modelo": modelo,
        "modelo_usado": "KMeans",
        "n_clusters": int(n_clusters_final),
        "evaluacion_k": evaluacion_k,
        "variables": variables,
        "variables_legibles": [nombre_legible_variable(v) for v in variables],
        "columnas_base": preparado["columnas_base"],
        "advertencias": preparado["advertencias"],
        "anio_usado": preparado["anio_usado"],
        "limit_usado": preparado["limit_usado"],
        "fecha_consulta": preparado["fecha_consulta"]
    }


# ============================================================
# Interpretación
# ============================================================

def interpretar_clusteres(resultado: Dict[str, Any]) -> Dict[int, Dict[str, Any]]:
    df = resultado["df_resultado"]
    variables = resultado["variables"]

    medias_globales = df[variables].mean()
    desv_globales = df[variables].std().replace(0, np.nan)

    interpretaciones = {}

    for cluster_id in sorted(df["cluster"].unique()):
        subset = df[df["cluster"] == cluster_id]
        medias_cluster = subset[variables].mean()
        diferencias = (medias_cluster - medias_globales) / desv_globales

        altas = []
        bajas = []

        for var in variables:
            z = diferencias.get(var, 0)

            if pd.isna(z):
                continue

            nombre_legible = nombre_legible_variable(var)

            if z >= 0.35:
                altas.append(nombre_legible)
            elif z <= -0.35:
                bajas.append(nombre_legible)

        partes = []

        if altas:
            partes.append("valores relativamente más altos en " + ", ".join(altas[:4]))

        if bajas:
            partes.append("valores relativamente más bajos en " + ", ".join(bajas[:4]))

        if partes:
            resumen = (
                "Este grupo reúne municipios con "
                + " y ".join(partes)
                + " frente al conjunto analizado."
            )
        else:
            resumen = (
                "Este grupo reúne municipios con valores cercanos al promedio del conjunto analizado."
            )

        interpretaciones[int(cluster_id)] = {
            "cluster": int(cluster_id),
            "grupo_estadistico": int(cluster_id),
            "numero_municipios": int(len(subset)),
            "resumen_perfil": resumen,
            "variables_altas_relativas": altas,
            "variables_bajas_relativas": bajas,
            "promedios_cluster": {
                nombre_legible_variable(k): float(v)
                for k, v in medias_cluster.to_dict().items()
            }
        }

    return interpretaciones


def recomendaciones_generales_por_perfil(perfil: Dict[str, Any]) -> List[str]:
    altas = " ".join(perfil.get("variables_altas_relativas", [])).lower()
    bajas = " ".join(perfil.get("variables_bajas_relativas", [])).lower()
    texto_total = altas + " " + bajas

    recomendaciones = []

    if any(p in altas for p in ["deserc", "reprob", "repit", "extraedad"]):
        recomendaciones.append(
            "Fortalecer estrategias de permanencia, acompañamiento académico y alerta temprana."
        )

    if any(p in bajas for p in ["cobertura", "matrícula", "matricula", "transición", "transicion", "media", "preescolar"]):
        recomendaciones.append(
            "Revisar condiciones de acceso, oferta educativa y tránsito entre niveles escolares."
        )

    if any(p in bajas for p in ["aprob"]):
        recomendaciones.append(
            "Analizar factores asociados a aprobación, promoción y apoyos pedagógicos."
        )

    if any(p in texto_total for p in ["media", "bachiller", "graduado"]):
        recomendaciones.append(
            "Cruzar el análisis con bachilleres, oferta de educación superior, ETDH e ICETEX."
        )

    recomendaciones.extend([
        "Contrastar el resultado con información local cualitativa antes de priorizar acciones públicas.",
        "Usar este resultado como insumo exploratorio, no como clasificación definitiva de calidad educativa."
    ])

    salida = []
    vistos = set()

    for rec in recomendaciones:
        if rec not in vistos:
            salida.append(rec)
            vistos.add(rec)

    return salida


# ============================================================
# Caché
# ============================================================

def construir_cache_key_clustering(
    departamento: Optional[str] = None,
    anio: Optional[int] = None,
    n_clusters: Optional[int] = None,
    limit: int = DEFAULT_ANALYTIC_LIMIT
) -> str:
    departamento_key = normalizar_texto_cluster(departamento or "nacional")
    anio_key = str(anio) if anio is not None else "ultimo"
    clusters_key = str(n_clusters) if n_clusters is not None else "auto"
    limit_key = str(resolver_limit_clustering(limit))

    return f"{departamento_key}::{anio_key}::{clusters_key}::{limit_key}"


def guardar_pipeline_en_cache(
    cache_key: str,
    resultado: Dict[str, Any],
    metadata: Dict[str, Any]
) -> None:
    CACHE_CLUSTERING["pipelines"][cache_key] = {
        "resultado": resultado,
        "metadata": metadata
    }

    CACHE_CLUSTERING["ultimo_resultado"] = resultado
    CACHE_CLUSTERING["ultima_metadata"] = metadata
    CACHE_CLUSTERING["ultimo_cache_key"] = cache_key


def obtener_pipeline_desde_cache(cache_key: str) -> Optional[Dict[str, Any]]:
    entrada = CACHE_CLUSTERING["pipelines"].get(cache_key)

    if not entrada:
        return None

    CACHE_CLUSTERING["ultimo_resultado"] = entrada["resultado"]
    CACHE_CLUSTERING["ultima_metadata"] = entrada["metadata"]
    CACHE_CLUSTERING["ultimo_cache_key"] = cache_key

    return entrada["resultado"]


def obtener_metadata_desde_cache(cache_key: str) -> Optional[Dict[str, Any]]:
    entrada = CACHE_CLUSTERING["pipelines"].get(cache_key)

    if not entrada:
        return None

    return entrada["metadata"]


def limpiar_cache_clustering() -> Dict[str, str]:
    CACHE_CLUSTERING["pipelines"] = {}
    CACHE_CLUSTERING["ultimo_resultado"] = None
    CACHE_CLUSTERING["ultima_metadata"] = None
    CACHE_CLUSTERING["ultimo_cache_key"] = None

    return {
        "status": "ok",
        "message": "Caché de agrupación estadística limpiado correctamente."
    }


# ============================================================
# Pipeline principal
# ============================================================

def ejecutar_pipeline_clustering(
    departamento: Optional[str] = None,
    anio: Optional[int] = None,
    n_clusters: Optional[int] = None,
    limit: int = DEFAULT_ANALYTIC_LIMIT
) -> Dict[str, Any]:
    """
    Ejecuta preparación, KMeans e interpretación.

    Usa caché por combinación:
    departamento + año + n_clusters + limit.
    """
    limit_final = resolver_limit_clustering(limit)

    cache_key = construir_cache_key_clustering(
        departamento=departamento,
        anio=anio,
        n_clusters=n_clusters,
        limit=limit_final
    )

    resultado_cacheado = obtener_pipeline_desde_cache(cache_key)

    if resultado_cacheado is not None:
        return resultado_cacheado

    preparado = preparar_datos_para_clustering(
        departamento=departamento,
        anio=anio,
        limit=limit_final
    )

    resultado = aplicar_clustering(
        preparado=preparado,
        n_clusters=n_clusters
    )

    interpretaciones = interpretar_clusteres(resultado)
    resultado["interpretaciones"] = interpretaciones

    metadata = {
        "dataset_base": DATASET_BASE,
        "cache_key": cache_key,
        "limit_usado": limit_final,
        "variables_seleccionadas": resultado["variables"],
        "variables_legibles": resultado["variables_legibles"],
        "numero_registros_modelo": int(len(resultado["df_resultado"])),
        "fecha_consulta": resultado["fecha_consulta"],
        "modelo_usado": resultado["modelo_usado"],
        "numero_clusters": resultado["n_clusters"],
        "anio_usado": resultado["anio_usado"],
        "criterio_numero_clusters": resultado["evaluacion_k"],
        "columnas_detectadas": resultado["columnas_base"],
        "interpretacion_ciudadana": (
            "El modelo agrupa municipios con comportamiento educativo similar usando KMeans "
            "sobre variables numéricas estandarizadas. Es un análisis exploratorio, no un ranking."
        ),
        "advertencias": resultado["advertencias"]
    }

    guardar_pipeline_en_cache(
        cache_key=cache_key,
        resultado=resultado,
        metadata=metadata
    )

    return resultado


# ============================================================
# Servicios públicos
# ============================================================

def obtener_metadata_clustering_service(
    limit: int = DEFAULT_ANALYTIC_LIMIT
) -> Dict[str, Any]:
    """
    Devuelve metadata del pipeline nacional por defecto.
    Si no existe, lo ejecuta.
    """
    limit_final = resolver_limit_clustering(limit)

    cache_key = construir_cache_key_clustering(
        departamento=None,
        anio=None,
        n_clusters=None,
        limit=limit_final
    )

    metadata = obtener_metadata_desde_cache(cache_key)

    if metadata is None:
        ejecutar_pipeline_clustering(limit=limit_final)
        metadata = obtener_metadata_desde_cache(cache_key)

    return limpiar_para_json(metadata or CACHE_CLUSTERING["ultima_metadata"])


def consultar_clusters_municipios_service(
    departamento: Optional[str] = None,
    anio: Optional[int] = None,
    n_clusters: Optional[int] = None,
    max_resultados: int = 100,
    limit: int = DEFAULT_ANALYTIC_LIMIT
) -> Dict[str, Any]:
    resultado = ejecutar_pipeline_clustering(
        departamento=departamento,
        anio=anio,
        n_clusters=n_clusters,
        limit=limit
    )

    df = resultado["df_resultado"].copy()
    cols = resultado["columnas_base"]

    depto_col = cols.get("departamento")
    municipio_col = cols.get("municipio")
    interpretaciones = resultado["interpretaciones"]

    max_resultados = max(1, min(int(max_resultados), 1000))

    salida = []

    for _, row in df.head(max_resultados).iterrows():
        cluster_id = int(row["cluster"])

        salida.append({
            "departamento": row[depto_col] if depto_col else None,
            "municipio": row[municipio_col],
            "cluster": cluster_id,
            "grupo_estadistico": cluster_id,
            "resumen_perfil_grupo": interpretaciones[cluster_id]["resumen_perfil"]
        })

    return limpiar_para_json({
        "total_municipios_analizados": int(len(df)),
        "total_devuelto": int(len(salida)),
        "modelo_usado": resultado["modelo_usado"],
        "n_clusters": resultado["n_clusters"],
        "n_grupos_estadisticos": resultado["n_clusters"],
        "anio_usado": resultado["anio_usado"],
        "limit_usado": resultado["limit_usado"],
        "variables_usadas": resultado["variables"],
        "variables_legibles": resultado["variables_legibles"],
        "resultados": salida,
        "advertencias": resultado["advertencias"]
    })


def consultar_cluster_municipio_service(
    departamento: str,
    municipio: str,
    anio: Optional[int] = None,
    n_clusters: Optional[int] = None,
    limit: int = DEFAULT_ANALYTIC_LIMIT
) -> Dict[str, Any]:
    """
    Consulta el grupo estadístico educativo de un municipio.

    Se usa el pipeline nacional para comparar el municipio frente al conjunto nacional,
    no solo contra su departamento.
    """
    resultado = ejecutar_pipeline_clustering(
        departamento=None,
        anio=anio,
        n_clusters=n_clusters,
        limit=limit
    )

    df = resultado["df_resultado"].copy()
    cols = resultado["columnas_base"]

    depto_col = cols.get("departamento")
    municipio_col = cols.get("municipio")

    municipio_norm = normalizar_texto_cluster(municipio)
    depto_norm = normalizar_texto_cluster(departamento)

    mascara = df[municipio_col].astype(str).apply(normalizar_texto_cluster) == municipio_norm

    if depto_col and departamento:
        mascara = mascara & (
            df[depto_col].astype(str).apply(normalizar_texto_cluster) == depto_norm
        )

    encontrado = df[mascara]

    if encontrado.empty:
        raise ValueError(
            f"No se encontró el municipio '{municipio}' en el departamento '{departamento}'."
        )

    row = encontrado.iloc[0]
    cluster_id = int(row["cluster"])
    perfil = resultado["interpretaciones"][cluster_id]

    valores_variables = {
        nombre_legible_variable(var): float(row[var])
        for var in resultado["variables"]
    }

    return limpiar_para_json({
        "municipio_consultado": row[municipio_col],
        "departamento": row[depto_col] if depto_col else departamento,
        "cluster_asignado": cluster_id,
        "grupo_estadistico_asignado": cluster_id,
        "explicacion_cluster": perfil["resumen_perfil"],
        "explicacion_grupo_estadistico": perfil["resumen_perfil"],
        "variables_mas_relevantes": {
            "variables_usadas": resultado["variables"],
            "variables_legibles": resultado["variables_legibles"],
            "valores_municipio": valores_variables,
            "variables_altas_relativas_del_grupo": perfil["variables_altas_relativas"],
            "variables_bajas_relativas_del_grupo": perfil["variables_bajas_relativas"],
            "variables_altas_relativas_del_cluster": perfil["variables_altas_relativas"],
            "variables_bajas_relativas_del_cluster": perfil["variables_bajas_relativas"]
        },
        "modelo_usado": resultado["modelo_usado"],
        "n_clusters": resultado["n_clusters"],
        "n_grupos_estadisticos": resultado["n_clusters"],
        "anio_usado": resultado["anio_usado"],
        "limit_usado": resultado["limit_usado"],
        "advertencias_o_limitaciones": resultado["advertencias"]
    })


def buscar_municipios_similares_service(
    departamento: str,
    municipio: str,
    top_n: int = 5,
    anio: Optional[int] = None,
    n_clusters: Optional[int] = None,
    solo_mismo_departamento: bool = False,
    limit: int = DEFAULT_ANALYTIC_LIMIT
) -> Dict[str, Any]:
    """
    Busca municipios similares usando distancia euclidiana sobre variables estandarizadas.
    """
    resultado = ejecutar_pipeline_clustering(
        departamento=None,
        anio=anio,
        n_clusters=n_clusters,
        limit=limit
    )

    df = resultado["df_resultado"].copy().reset_index(drop=True)
    X_scaled = resultado["X_scaled"]

    cols = resultado["columnas_base"]

    depto_col = cols.get("departamento")
    municipio_col = cols.get("municipio")

    municipio_norm = normalizar_texto_cluster(municipio)
    depto_norm = normalizar_texto_cluster(departamento)

    mascara = df[municipio_col].astype(str).apply(normalizar_texto_cluster) == municipio_norm

    if depto_col and departamento:
        mascara = mascara & (
            df[depto_col].astype(str).apply(normalizar_texto_cluster) == depto_norm
        )

    indices = df.index[mascara].tolist()

    if not indices:
        raise ValueError(
            f"No se encontró el municipio '{municipio}' en el departamento '{departamento}'."
        )

    idx = indices[0]

    distancias = euclidean_distances(
        X_scaled[idx].reshape(1, -1),
        X_scaled
    ).flatten()

    df_dist = df.copy()
    df_dist["distancia_estandarizada"] = distancias
    df_dist = df_dist.drop(index=idx)

    if solo_mismo_departamento and depto_col:
        df_dist = df_dist[
            df_dist[depto_col].astype(str).apply(normalizar_texto_cluster) == depto_norm
        ]

    top_n = max(1, min(int(top_n), 50))
    df_dist = df_dist.sort_values("distancia_estandarizada").head(top_n)

    similares = []

    for _, row in df_dist.iterrows():
        similares.append({
            "departamento": row[depto_col] if depto_col else None,
            "municipio": row[municipio_col],
            "cluster": int(row["cluster"]),
            "grupo_estadistico": int(row["cluster"]),
            "distancia_estandarizada": round(float(row["distancia_estandarizada"]), 4),
            "interpretacion": (
                "Menor distancia significa mayor similitud en las variables educativas usadas."
            )
        })

    return limpiar_para_json({
        "municipio_base": municipio,
        "departamento_base": departamento,
        "top_n": top_n,
        "variables_usadas": resultado["variables"],
        "variables_legibles": resultado["variables_legibles"],
        "anio_usado": resultado["anio_usado"],
        "limit_usado": resultado["limit_usado"],
        "similares": similares,
        "advertencias": resultado["advertencias"]
    })


def generar_recomendaciones_municipio_service(
    departamento: str,
    municipio: str,
    anio: Optional[int] = None,
    n_clusters: Optional[int] = None,
    limit: int = DEFAULT_ANALYTIC_LIMIT
) -> Dict[str, Any]:
    resultado_municipio = consultar_cluster_municipio_service(
        departamento=departamento,
        municipio=municipio,
        anio=anio,
        n_clusters=n_clusters,
        limit=limit
    )

    resultado = ejecutar_pipeline_clustering(
        departamento=None,
        anio=anio,
        n_clusters=n_clusters,
        limit=limit
    )

    cluster_id = resultado_municipio["cluster_asignado"]
    perfil = resultado["interpretaciones"][cluster_id]
    recomendaciones = recomendaciones_generales_por_perfil(perfil)

    return limpiar_para_json({
        "municipio": resultado_municipio["municipio_consultado"],
        "departamento": resultado_municipio["departamento"],
        "cluster": cluster_id,
        "grupo_estadistico": cluster_id,
        "perfil_cluster": perfil["resumen_perfil"],
        "perfil_grupo_estadistico": perfil["resumen_perfil"],
        "recomendaciones_generales": recomendaciones,
        "variables_usadas": resultado_municipio["variables_mas_relevantes"]["variables_usadas"],
        "variables_legibles": resultado_municipio["variables_mas_relevantes"]["variables_legibles"]
        if "variables_legibles" in resultado_municipio.get("variables_mas_relevantes", {})
        else resultado.get("variables_legibles", []),
        "anio_usado": resultado_municipio["anio_usado"],
        "limit_usado": resultado_municipio["limit_usado"],
        "advertencias": resultado_municipio["advertencias_o_limitaciones"]
    })