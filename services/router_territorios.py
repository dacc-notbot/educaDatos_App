"""Ubicaciones oficiales para los campos de búsqueda de la interfaz ciudadana."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from services.catalogo_territorios_service import consultar_catalogo_territorios


class MunicipioCatalogo(BaseModel):
    municipio: str
    codigo: str | None = None


class DepartamentoCatalogo(BaseModel):
    departamento: str
    municipios: list[MunicipioCatalogo]


class CatalogoTerritorios(BaseModel):
    departamentos: list[DepartamentoCatalogo]
    fuente: str
    anio: int | None


router = APIRouter(tags=["Territorios"])


@router.get("/territorios", response_model=CatalogoTerritorios, operation_id="catalogoTerritoriosParaBuscar")
def territorios():
    try:
        return consultar_catalogo_territorios()
    except RuntimeError as error:
        raise HTTPException(
            status_code=502,
            detail="No pudimos cargar la lista de municipios desde la fuente oficial. Vuelve a intentarlo.",
        ) from error
