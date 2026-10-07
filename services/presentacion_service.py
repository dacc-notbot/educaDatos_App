"""Colecciones legibles para explorar la información ya devuelta por cada servicio."""

ETIQUETAS = {
    "lista_oferta": "Oferta de educación superior",
    "muestra_programas": "Títulos e instituciones de educación superior",
    "muestra_bachilleres": "Registros de bachilleres",
    "muestra_icetex": "Registros de ICETEX",
    "distribucion_secretaria_o_etc": "Bachilleres por secretaría",
    "lineas_o_modalidades_frecuentes": "Modalidades de ICETEX",
    "instituciones_frecuentes": "Instituciones reportadas",
    "sectores_frecuentes": "Sectores reportados",
    "titulos_frecuentes": "Títulos reportados",
    "similares": "Municipios con indicadores similares",
    "recomendaciones_generales": "Orientaciones basadas en indicadores",
    "coincidencias_dane": "Colegios y códigos DANE",
}


def construir_resumenes_icetex(fragmentos):
    resumenes = []
    vistos = set()
    for fragmento in fragmentos:
        datos = fragmento.get("datos")
        for contenido in (fragmento, datos if isinstance(datos, dict) else {}):
            visual = contenido.get("visualizacion_icetex")
            if isinstance(visual, dict) and id(visual) not in vistos:
                vistos.add(id(visual))
                resumenes.append({"tipo_credito": contenido.get("tipo_credito"), "visualizacion_icetex": visual})
    return resumenes


def construir_colecciones(fragmentos):
    colecciones = []
    vistos = set()
    muestra = None
    for fragmento in fragmentos:
        if muestra is None and isinstance(fragmento.get("resultados_muestra"), list):
            muestra = fragmento["resultados_muestra"]
        datos = fragmento.get("datos")
        for contenido in (fragmento, datos if isinstance(datos, dict) else {}):
            for clave, titulo in ETIQUETAS.items():
                if clave == "muestra_programas" and contenido.get("lista_oferta"):
                    continue
                valor = contenido.get(clave)
                if not valor or id(valor) in vistos:
                    continue
                if isinstance(valor, dict):
                    filas = [{"categoria": k, "cantidad": v} for k, v in valor.items()]
                elif isinstance(valor, list):
                    filas = [
                        fila if isinstance(fila, dict) else {"descripcion": fila}
                        for fila in valor
                        if isinstance(fila, (dict, str))
                    ]
                else:
                    continue
                if filas:
                    vistos.add(id(valor))
                    colecciones.append(
                        {
                            "titulo": titulo,
                            "filas": filas,
                            "es_muestra": clave != "coincidencias_dane"
                            and not (
                                clave == "lista_oferta"
                                and contenido.get("consulta_completa") is True
                            ),
                        }
                    )
    if not colecciones and muestra:
        filas = [
            fila if isinstance(fila, dict) else {"descripcion": fila}
            for fila in muestra
            if isinstance(fila, (dict, str))
        ]
        if filas:
            colecciones.append(
                {
                    "titulo": "Registros disponibles en esta respuesta",
                    "filas": filas,
                    "es_muestra": True,
                }
            )
    return colecciones
