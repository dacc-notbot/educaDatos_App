# backend/config.py

# ============================================================
# Configuración general del proyecto
# ============================================================

APP_NAME = "EducaDatos API"
APP_VERSION = "1.1.0"

PROJECT_DESCRIPTION = (
    "Backend ciudadano para consultar datos abiertos educativos de Colombia, "
    "generar diagnósticos territoriales, analizar tránsito educativo y agrupar "
    "municipios con comportamiento educativo similar."
)

# URL pública de la API.
# Para pruebas locales puedes usar: http://127.0.0.1:8000
# Para conectar con GPT o la app pública usa la URL pública de ngrok.
PUBLIC_BASE_URL = "https://mustard-mom-default.ngrok-free.dev/"


# ============================================================
# Límites de consulta
# ============================================================

# Límite base para consultas analíticas.
DEFAULT_LIMIT = 100_000

# Máximo general permitido por la API.
MAX_LIMIT = 1_000_000

# Mínimos recomendados según escala territorial.
MIN_LIMIT_MUNICIPAL = 100_000
MIN_LIMIT_DEPARTAMENTAL = 500_000

# Límite por defecto para chat, diagnóstico, cruce y clustering.
DEFAULT_ANALYTIC_LIMIT = 100_000

# Límites para consultas ligeras.
PREVIEW_LIMIT = 10
SEARCH_LIMIT = 1_000


# ============================================================
# Dataset base para análisis municipal y agrupación estadística
# ============================================================

DATASET_BASE = "estadisticas_municipio"


# ============================================================
# Datasets de datos abiertos
# ============================================================

DATASETS = {
    "estadisticas_municipio": {
        "nombre": "MEN - Estadísticas en educación preescolar, básica y media por municipio",
        "url": "https://www.datos.gov.co/resource/nudc-7mev.json",
        "descripcion": "Indicadores sectoriales de educación preescolar, básica y media por municipio.",
        "uso_principal": "Agrupación estadística de municipios con comportamiento educativo similar.",
        "escala": "municipal",
        "activo": True,
        "alcance": "nacional",
    },
    "establecimientos_educativos": {
        "nombre": "MEN - Establecimientos educativos de preescolar, básica y media",
        "url": "https://www.datos.gov.co/resource/cfw5-qzt5.json",
        "descripcion": "Consulta de colegios, sedes, sector oficial/no oficial y ubicación institucional.",
        "uso_principal": "Búsqueda ciudadana de establecimientos educativos.",
        "escala": "sede/establecimiento",
        "activo": True,
        "alcance": "nacional",
    },
    "programas_superior": {
        "nombre": "Programas de educación superior",
        "url": "https://www.datos.gov.co/resource/upr9-nkiz.json",
        "descripcion": "Oferta de programas académicos de educación superior en Colombia.",
        "uso_principal": "Consulta de oportunidades de educación superior.",
        "escala": "programa/institución/territorio",
        "activo": True,
        "alcance": "nacional",
    },
    "instituciones_etdh": {
        "nombre": "Instituciones de educación para el trabajo y desarrollo humano",
        "url": "https://www.datos.gov.co/resource/gpje-sixt.json",
        "descripcion": "Instituciones de educación para el trabajo y el desarrollo humano registradas.",
        "uso_principal": "Consulta de instituciones de formación para el trabajo.",
        "escala": "institución",
        "activo": True,
        "alcance": "nacional",
    },
    "programas_etdh": {
        "nombre": "Programas de educación para el trabajo y desarrollo humano",
        "url": "https://www.datos.gov.co/resource/2v94-3ypi.json",
        "descripcion": "Programas técnicos laborales y de formación ETDH.",
        "uso_principal": "Consulta de programas de formación laboral.",
        "escala": "programa",
        "activo": True,
        "alcance": "nacional",
    },
    "bachilleres": {
        "nombre": "Número de bachilleres por entidad territorial certificada",
        "url": "https://www.datos.gov.co/resource/5c2k-ahfc.json",
        "descripcion": "Información sobre bachilleres por entidad territorial certificada.",
        "uso_principal": "Análisis de tránsito hacia educación superior.",
        "escala": "ETC/departamento/municipio",
        "activo": True,
        "alcance": "nacional",
    },
    "primera_infancia": {
        "nombre": "Indicadores de primera infancia",
        "url": "https://www.datos.gov.co/resource/3y4s-dmxy.json",
        "descripcion": "Indicadores asociados a primera infancia.",
        "uso_principal": "Análisis de atención educativa inicial.",
        "escala": "territorial",
        "activo": True,
        "alcance": "nacional",
    },
    "icetex_otorgados": {
        "nombre": "Créditos otorgados por ICETEX",
        "url": "https://www.datos.gov.co/resource/26bn-e42j.json",
        "descripcion": "Créditos educativos otorgados por ICETEX.",
        "uso_principal": "Consulta de financiación educativa.",
        "escala": "beneficiario/crédito/territorio",
        "activo": True,
        "alcance": "nacional",
    },
    "icetex_renovados": {
        "nombre": "Créditos renovados por ICETEX",
        "url": "https://www.datos.gov.co/resource/nvcf-b8a3.json",
        "descripcion": "Créditos educativos renovados por ICETEX.",
        "uso_principal": "Seguimiento de continuidad en financiación educativa.",
        "escala": "beneficiario/crédito/territorio",
        "activo": True,
        "alcance": "nacional",
    },

    # --------------------------------------------------------
    # Datasets locales o complementarios
    # --------------------------------------------------------

    "barrios_veredas_villavicencio": {
        "nombre": "Barrios y veredas de Villavicencio",
        "url": "https://www.datos.gov.co/resource/x5yx-u8uk.json",
        "descripcion": "Información territorial de barrios y veredas del municipio de Villavicencio.",
        "uso_principal": "Ubicación territorial para consultas ciudadanas locales.",
        "escala": "local",
        "activo": True,
        "alcance": "local",
    },
    "zonas_wifi_meta": {
        "nombre": "Zonas wifi del departamento del Meta",
        "url": "https://www.datos.gov.co/resource/2ijd-648y.json",
        "descripcion": "Puntos de conectividad pública en el departamento del Meta.",
        "uso_principal": "Cruce entre educación y conectividad territorial.",
        "escala": "punto/localización",
        "activo": True,
        "alcance": "departamental",
    },
    "estadisticas_villavicencio": {
        "nombre": "Estadísticas educativas de Villavicencio",
        "url": "https://www.datos.gov.co/resource/du66-2rxt.json",
        "descripcion": "Indicadores educativos específicos del municipio de Villavicencio.",
        "uso_principal": "Análisis educativo local de Villavicencio.",
        "escala": "municipal/local",
        "activo": True,
        "alcance": "local",
    },
}


# ============================================================
# Agrupaciones útiles para validaciones futuras
# ============================================================

DATASETS_NACIONALES_ACTIVOS = [
    clave
    for clave, info in DATASETS.items()
    if info.get("activo") and info.get("alcance") == "nacional"
]

DATASETS_LOCALES_COMPLEMENTARIOS = [
    clave
    for clave, info in DATASETS.items()
    if info.get("alcance") in ["local", "departamental"]
]

DATASETS_TRANSITO_EDUCATIVO = [
    "bachilleres",
    "programas_superior",
    "icetex_otorgados",
    "icetex_renovados",
]

DATASETS_DIAGNOSTICO_TERRITORIAL = [
    "estadisticas_municipio",
    "establecimientos_educativos",
    "programas_superior",
    "bachilleres",
    "icetex_otorgados",
    "icetex_renovados",
]