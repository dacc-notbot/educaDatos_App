from unittest.mock import Mock

from fastapi.testclient import TestClient
import pytest

import main
from services import consulta_service, estadisticas_icetex as servicio


def fuente(monkeypatch, total=25):
    def descargar(dataset, limit, params_extra):
        assert limit == 5000
        assert 'sum(' in params_extra['$select']
        if params_extra['$group'] == 'vigencia':
            return [{'vigencia': '2023', 'cantidad': '100', 'registros': '2', 'informados': '2'},
                    {'vigencia': '2025', 'cantidad': str(total), 'registros': '2', 'informados': '2'}]
        assert 'vigencia = 2025' in params_extra['$where']
        return [{'categoria': 'A', 'cantidad': str(total)}, {'categoria': None, 'cantidad': '0'}]
    mock = Mock(side_effect=descargar)
    monkeypatch.setattr(servicio, 'consultar_dataset', mock)
    return mock


@pytest.mark.parametrize('tipo,medida,unidad', [
    ('otorgados', 'numero_de_nuevos_beneficiarios', 'Nuevos beneficiarios de crédito'),
    ('renovados', 'numero_de_renovaciones', 'Renovaciones de crédito'),
])
def test_suma_cantidades_no_filas_y_cubre_todas_las_dimensiones(monkeypatch,tipo,medida,unidad):
    descarga=fuente(monkeypatch)
    r=servicio.consultar_estadisticas_icetex(departamento='Meta',tipo=tipo)
    d=r['datos']; v=d['visualizacion_icetex']
    assert d['total_creditos_o_beneficiarios_aproximado']==25
    assert d['total_registros_vigencia']==2
    assert v['unidad']==unidad and v['anio']==2025
    assert len(v['distribuciones'])==10
    assert all(sum(f['cantidad'] for f in g['filas'])==25 for g in v['distribuciones'])
    assert all(medida in c.kwargs['params_extra']['$select'] for c in descarga.call_args_list)
    assert all('META' in str(c.kwargs['params_extra']) for c in descarga.call_args_list)
    rango=next(g for g in v['distribuciones'] if g['clave']=='rango_del_valor_total')
    assert not rango['permite_grafico'] and 'no montos exactos' in rango['nota']
    assert all(g['filas'][1]['cantidad']==0 for g in v['distribuciones'])
    assert 'créditos o beneficiarios' not in r['respuesta_corta']
    assert r['hallazgos_principales']==[]


def test_consulta_nacional_y_total_cero_conservados(monkeypatch):
    mock=fuente(monkeypatch,total=0)
    r=servicio.consultar_estadisticas_icetex()
    assert r['datos']['visualizacion_icetex']['total']==0
    assert r['datos']['visualizacion_icetex']['territorio']=='Colombia'
    assert '$where' not in mock.call_args_list[0].kwargs['params_extra']
    monkeypatch.setattr(consulta_service,'detectar_territorio',Mock(return_value=(None,None)))
    r=consulta_service.resolver_consulta_ciudadana('ICETEX en Colombia')
    assert r['total_resultados']==0


def test_ciudad_no_se_sustituye_por_departamento_ni_por_cero(monkeypatch):
    mock=Mock(side_effect=AssertionError('La fuente no identifica municipios'))
    monkeypatch.setattr(servicio,'consultar_dataset',mock)
    r=servicio.consultar_estadisticas_icetex(departamento='Meta',municipio='Villavicencio')
    assert 'no permite consultar Villavicencio por ciudad' in r['respuesta_corta']
    assert r['datos']['total_creditos_o_beneficiarios_aproximado'] is None
    assert r['datos']['total_registros_vigencia'] is None
    assert not r['datos']['visualizacion_icetex']['cobertura_disponible']
    mock.assert_not_called()


def test_anio_sin_datos_no_fabrica_total(monkeypatch):
    fuente(monkeypatch)
    r=servicio.consultar_estadisticas_icetex(anio=2020)
    assert 'No hay datos' in r['respuesta_corta']
    assert r['datos']['visualizacion_icetex']['total'] is None
    assert r['datos']['visualizacion_icetex']['serie_anual']


@pytest.mark.parametrize('cantidad,informados,registros', [('25','1','2'),('-1','2','2'),('no informado','2','2'),('2.5','2','2')])
def test_cantidades_invalidas_o_incompletas_no_se_publican(monkeypatch,cantidad,informados,registros):
    monkeypatch.setattr(servicio,'consultar_dataset',Mock(return_value=[{'vigencia':'2025','cantidad':cantidad,'registros':registros,'informados':informados}]))
    with pytest.raises(RuntimeError):
        servicio.consultar_estadisticas_icetex()


def test_distribuciones_que_no_suman_total_se_rechazan(monkeypatch):
    def descargar(dataset,limit,params_extra):
        return ([{'vigencia':'2025','cantidad':'20','registros':'2','informados':'2'}]
                if params_extra['$group']=='vigencia' else [{'categoria':'A','cantidad':'19'}])
    monkeypatch.setattr(servicio,'consultar_dataset',descargar)
    with pytest.raises(RuntimeError,match='no coinciden'):
        servicio.consultar_estadisticas_icetex()


def test_api_nacional_anio_y_validacion(monkeypatch):
    fuente(monkeypatch)
    with TestClient(main.app) as client:
        r=client.post('/icetex',json={'tipo':'renovados','anio':2025})
        assert r.status_code==200
        v=r.json()['datos']['detalle_consulta']['visualizacion_icetex']
        assert v['unidad']=='Renovaciones de crédito'
        assert client.post('/icetex',json={'anio':1}).status_code==422
        assert client.post('/icetex',json={'tipo':'inventado'}).status_code==422


@pytest.mark.parametrize('pregunta', ['ICETEX de pregrado en Meta','ICETEX en universidades privadas de Meta','Renovaciones de ICETEX en Meta'])
def test_financiacion_no_se_confunde_con_busqueda_de_programas(pregunta):
    assert consulta_service.clasificar_intencion(pregunta)['dataset_key'].startswith('icetex_')


def test_filtros_pesan_las_cantidades_y_no_modifican_consultas(monkeypatch):
    mock=fuente(monkeypatch)
    filtros={'modalidad_de_linea':'PREGRADO','sexo_al_nacer':'Femenino','estrato_socio_economico':'2'}
    r=servicio.consultar_estadisticas_icetex(filtros=filtros)
    assert r['datos']['filtros_aplicados']==filtros
    assert 'Línea de financiación: PREGRADO' in r['respuesta_corta']
    assert all("upper(modalidad_de_linea) = 'PREGRADO'" in c.kwargs['params_extra']['$where'] for c in mock.call_args_list)
    assert all('estrato_socio_economico = 2' in c.kwargs['params_extra']['$where'] for c in mock.call_args_list)
    with pytest.raises(ValueError):
        servicio.consultar_estadisticas_icetex(filtros={'sum(vigencia)':'1'})


def test_filtros_explicitos_y_comparaciones_no_se_reducen_a_un_valor():
    assert servicio.extraer_filtros_icetex('ICETEX de pregrado para mujeres de estrato 2')=={'modalidad_de_linea':'PREGRADO','sexo_al_nacer':'Femenino','estrato_socio_economico':'2'}
    assert servicio.extraer_filtros_icetex('ICETEX para mujeres y hombres')=={}
    assert servicio.extraer_filtros_icetex('ICETEX pregrado y posgrado')=={}


def test_comparacion_no_suma_medidas_diferentes(monkeypatch):
    fuente(monkeypatch)
    monkeypatch.setattr(consulta_service,'detectar_territorio',Mock(return_value=('Meta',None)))
    r=consulta_service.resolver_consulta_ciudadana('ICETEX otorgados y renovados en Meta')
    assert r['total_resultados'] is None
    partes=r['resultados']['datos']['comparacion_icetex']
    assert [p['visualizacion_icetex']['unidad'] for p in partes]==['Nuevos beneficiarios de crédito','Renovaciones de crédito']
    assert 'no se suman' in r['respuesta_ciudadana']['respuesta_corta']


def test_api_filtros_no_permite_identificadores_arbitrarios(monkeypatch):
    fuente(monkeypatch)
    with TestClient(main.app) as client:
        assert client.post('/icetex',json={'filtros':{'nivel_de_formacion':'Doctorado'}}).status_code==200
        for filtros in [{'sum(vigencia)':'1'},{'sector_ies':' '},{'estrato_socio_economico':'8'}]:
            assert client.post('/icetex',json={'filtros':filtros}).status_code==422


def test_colombia_nacional_no_se_confunde_con_municipio_del_huila(monkeypatch):
    fuente(monkeypatch)
    monkeypatch.setattr(consulta_service,'detectar_territorio',Mock(return_value=('Huila','Colombia')))
    r=consulta_service.resolver_consulta_ciudadana('ICETEX en Colombia')
    assert r['resultados']['datos']['visualizacion_icetex']['territorio']=='Colombia'
    assert r['resultados']['datos']['visualizacion_icetex']['cobertura_disponible']
    assert not consulta_service.ambito_nacional('ICETEX en el municipio de Colombia en Huila')


def test_presentacion_integrada_conserva_graficos_y_no_duplica_componentes():
    from services.adaptador_api import adaptar_servicio_para_app
    servicio_icetex={'datos':{'tipo_credito':'renovados','visualizacion_icetex':{'unidad':'Renovaciones de crédito','total':20,'cobertura_disponible':True}}}
    resultado={'componentes_crudos':{'icetex':{'ok':True,'datos':servicio_icetex}},'respuesta_corta':'Consulta integrada.'}
    respuesta=adaptar_servicio_para_app(resultado)
    paneles=respuesta['datos']['resumenes_icetex']
    assert len(paneles)==1
    assert paneles[0]['visualizacion_icetex']['total']==20
    assert paneles[0]['tipo_credito']=='renovados'


def test_cruce_no_declara_disponible_un_componente_sin_cobertura_municipal():
    from services.cruce_service import resumir_icetex
    r=resumir_icetex({'ok':True,'datos':{'respuesta_corta':'No permite ciudad.','datos':{'visualizacion_icetex':{'cobertura_disponible':False},'total_creditos_o_beneficiarios_aproximado':None}}})
    assert not r['ok']
    assert r['error']=='No permite ciudad.'
    assert r['total_creditos_o_beneficiarios_aproximado'] is None


@pytest.mark.parametrize('pregunta,dimension', [('ICETEX por sexo','sexo_al_nacer'),('ICETEX por estrato','estrato_socio_economico'),('Evolución de ICETEX','serie_anual'),('ICETEX en pesos','rango_del_valor_total')])
def test_la_vista_inicial_corresponde_a_la_pregunta(monkeypatch,pregunta,dimension):
    fuente(monkeypatch)
    monkeypatch.setattr(consulta_service,'detectar_territorio',Mock(return_value=(None,None)))
    r=consulta_service.resolver_consulta_ciudadana(pregunta)
    assert r['resultados']['datos']['visualizacion_icetex']['dimension_preferida']==dimension
