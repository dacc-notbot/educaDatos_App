from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from config import DEFAULT_ANALYTIC_LIMIT, MAX_LIMIT
from utils.normalizacion import normalizar_texto


class ModeloEntrada(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)


class PreguntaRequest(ModeloEntrada):
    pregunta: str = Field(
        ...,
        max_length=2000,
        description="Pregunta ciudadana en lenguaje natural."
    )
    limit: int = Field(1000, ge=1, le=MAX_LIMIT)


class TerritorioRequest(ModeloEntrada):
    departamento: Optional[str] = Field(
        None,
        min_length=1,
        max_length=120,
        description="Nombre del departamento."
    )
    municipio: Optional[str] = Field(
        None,
        min_length=1,
        max_length=120,
        description="Nombre del municipio, si aplica."
    )
    limit: int = Field(DEFAULT_ANALYTIC_LIMIT, ge=1, le=MAX_LIMIT)

    @model_validator(mode="after")
    def validar_territorio(self):
        if not self.departamento and not self.municipio:
            raise ValueError("Indica un departamento o un municipio para consultar.")
        return self


class MunicipioRequest(ModeloEntrada):
    departamento: str = Field(
        ...,
        min_length=1,
        max_length=120,
        description="Nombre del departamento."
    )
    municipio: str = Field(
        ...,
        min_length=1,
        max_length=120,
        description="Nombre del municipio."
    )
    limit: int = Field(DEFAULT_ANALYTIC_LIMIT, ge=1, le=MAX_LIMIT)


class ConsultaColegiosRequest(TerritorioRequest):
    sector: Optional[str] = Field(
        None,
        max_length=80,
        description="Sector educativo: oficial, no oficial o privado."
    )
    modo_respuesta: Literal["conteo", "lista"] = "conteo"

    @field_validator("sector")
    @classmethod
    def validar_sector(cls, valor):
        if valor is not None and normalizar_texto(valor) not in {
            "oficial", "oficiales", "publico", "publicos", "publica", "publicas",
            "no oficial", "no oficiales", "nooficial", "nooficiales",
            "privado", "privados", "privada", "privadas", "particular", "particulares",
        }:
            raise ValueError("El sector debe ser oficial, público, no oficial o privado.")
        return valor


class ConsultaProgramasRequest(ModeloEntrada):
    estado: Optional[Literal["Activo", "Inactivo"]] = None
    departamento: Optional[str] = Field(
        None,
        min_length=1,
        max_length=120,
        description="Departamento a consultar."
    )
    municipio: Optional[str] = Field(
        None,
        min_length=1,
        max_length=120,
        description="Municipio a consultar."
    )
    texto: Optional[str] = Field(
        None,
        max_length=500,
        description="Texto libre para buscar programa, institución o área."
    )
    limit: int = Field(
        DEFAULT_ANALYTIC_LIMIT,
        ge=1,
        le=MAX_LIMIT,
        description="Límite máximo de registros a consultar."
    )


class ConsultaDaneRequest(ModeloEntrada):
    nombre: Optional[str] = Field(None, min_length=2, max_length=200)
    codigo: Optional[str] = Field(None, pattern=r"^[0-9]{1,15}$")
    departamento: Optional[str] = Field(None, min_length=1, max_length=120)
    municipio: Optional[str] = Field(None, min_length=1, max_length=120)

    @field_validator("nombre")
    @classmethod
    def validar_nombre(cls, valor):
        if valor is not None and len(normalizar_texto(valor)) < 2:
            raise ValueError("Escribe al menos dos letras o números del nombre del colegio.")
        return valor

    @model_validator(mode="after")
    def validar_busqueda(self):
        if not self.nombre and not self.codigo:
            raise ValueError("Indica el nombre del colegio o el código DANE.")
        return self


class ConsultaIcetexRequest(ModeloEntrada):
    departamento: Optional[str] = Field(None, min_length=1, max_length=120)
    municipio: Optional[str] = Field(None, min_length=1, max_length=120)
    limit: int = Field(DEFAULT_ANALYTIC_LIMIT, ge=1, le=MAX_LIMIT)
    anio: Optional[int] = Field(None, ge=1900, le=2100)
    filtros: Dict[Literal["nivel_de_formacion", "modalidad_de_linea", "modalidad_del_credito", "sector_ies", "sexo_al_nacer", "estrato_socio_economico", "categoria_del_municipio_de", "rango_del_valor_total"], str] = Field(default_factory=dict)

    @field_validator("filtros")
    @classmethod
    def validar_filtros(cls, filtros):
        if any(not v.strip() or len(v) > 120 for v in filtros.values()):
            raise ValueError("Indica valores de filtro de entre 1 y 120 caracteres.")
        if "estrato_socio_economico" in filtros and filtros["estrato_socio_economico"] not in list("0123456"):
            raise ValueError("Indica un estrato del 0 al 6.")
        return filtros
    tipo: Literal["otorgados", "renovados"] = Field(
        "otorgados",
        description="Tipo de créditos ICETEX: otorgados o renovados."
    )


class GrupoEstadisticoRequest(ModeloEntrada):
    departamento: str = Field(
        ...,
        min_length=1,
        description="Departamento del municipio."
    )
    municipio: str = Field(
        ...,
        min_length=1,
        description="Municipio a analizar."
    )
    anio: Optional[int] = Field(
        None,
        description="Año o vigencia específica, si aplica."
    )
    n_clusters: Optional[int] = Field(
        None,
        description="Número de grupos estadísticos. Si no se indica, se selecciona automáticamente."
    )
    limit: Optional[int] = Field(
        100000,
        ge=1,
        le=MAX_LIMIT,
        description="Límite máximo de registros a consultar."
    )


class EducaDatosResponse(BaseModel):
    """Contrato común para la web actual y la interfaz del ZIP reconstruido."""

    pregunta: Optional[str] = None
    respuesta: str
    datos: Dict[str, Any] = Field(default_factory=dict)
    fuentes: List[str] = Field(default_factory=list)
    advertencias: List[str] = Field(default_factory=list)
    respuesta_ciudadana: Dict[str, Any] = Field(default_factory=dict)
