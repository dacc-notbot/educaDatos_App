from typing import Optional
from pydantic import BaseModel, Field


class PreguntaRequest(BaseModel):
    pregunta: str = Field(
        ...,
        min_length=1,
        description="Pregunta ciudadana en lenguaje natural."
    )


class TerritorioRequest(BaseModel):
    departamento: str = Field(
        ...,
        min_length=1,
        description="Nombre del departamento."
    )
    municipio: Optional[str] = Field(
        None,
        description="Nombre del municipio, si aplica."
    )


class MunicipioRequest(BaseModel):
    departamento: str = Field(
        ...,
        min_length=1,
        description="Nombre del departamento."
    )
    municipio: str = Field(
        ...,
        min_length=1,
        description="Nombre del municipio."
    )


class ConsultaColegiosRequest(BaseModel):
    departamento: Optional[str] = Field(
        None,
        description="Departamento a consultar."
    )
    municipio: Optional[str] = Field(
        None,
        description="Municipio a consultar."
    )
    sector: Optional[str] = Field(
        None,
        description="Sector educativo: oficial, no oficial o privado."
    )
    limit: Optional[int] = Field(
        100000,
        ge=1,
        description="Límite máximo de registros a consultar."
    )


class ConsultaProgramasRequest(BaseModel):
    departamento: Optional[str] = Field(
        None,
        description="Departamento a consultar."
    )
    municipio: Optional[str] = Field(
        None,
        description="Municipio a consultar."
    )
    texto: Optional[str] = Field(
        None,
        description="Texto libre para buscar programa, institución o área."
    )
    limit: Optional[int] = Field(
        100000,
        ge=1,
        description="Límite máximo de registros a consultar."
    )


class ConsultaIcetexRequest(BaseModel):
    departamento: Optional[str] = Field(
        None,
        description="Departamento a consultar."
    )
    municipio: Optional[str] = Field(
        None,
        description="Municipio a consultar."
    )
    tipo: str = Field(
        "otorgados",
        description="Tipo de créditos ICETEX: otorgados o renovados."
    )
    limit: Optional[int] = Field(
        100000,
        ge=1,
        description="Límite máximo de registros a consultar."
    )


class GrupoEstadisticoRequest(BaseModel):
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
        description="Límite máximo de registros a consultar."
    )