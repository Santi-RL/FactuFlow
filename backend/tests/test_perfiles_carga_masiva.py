"""Tests para perfiles de carga masiva por emisor."""

from datetime import date

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.empresa import Empresa


def _perfil_payload(nombre: str = "Servicios mensuales") -> dict:
    """Devuelve un payload válido de perfil de carga masiva."""
    return {
        "nombre": nombre,
        "descripcion": "Configuración mensual de prueba",
        "es_predeterminado": False,
        "activo": True,
        "configuracion_json": {
            "version": 1,
            "formato_importacion_version_id": None,
            "concepto_modo": "servicios",
            "descripcion_item_modo": "fija",
            "descripcion_item_fija": "Ajuste",
            "fecha_emision": {"modo": "ultimo_dia_mes_anterior"},
            "periodo_servicio": {"modo": "mes_anterior_completo"},
            "fecha_vto_pago": {"modo": "emision_mas_dias", "dias": 0},
        },
    }


@pytest.fixture
async def segunda_empresa(db_session: AsyncSession) -> Empresa:
    """Crea un segundo emisor para pruebas de scoping."""
    empresa = Empresa(
        razon_social="Segunda Empresa S.A.",
        cuit="20999999993",
        condicion_iva="RI",
        domicilio="Calle Test 456",
        localidad="Buenos Aires",
        provincia="Buenos Aires",
        codigo_postal="1001",
        email="segunda@empresa.com",
        telefono="1234567890",
        inicio_actividades=date(2021, 1, 1),
    )
    db_session.add(empresa)
    await db_session.commit()
    await db_session.refresh(empresa)
    return empresa


@pytest.mark.asyncio
async def test_crud_perfiles_scopiado_por_emisor(
    client: AsyncClient,
    auth_headers: dict,
):
    """Permite crear, listar, actualizar y eliminar perfiles del emisor activo."""
    crear = await client.post(
        "/api/perfiles-carga-masiva",
        headers=auth_headers,
        json=_perfil_payload(),
    )
    assert crear.status_code == 201, crear.text
    perfil_id = crear.json()["id"]

    listar = await client.get("/api/perfiles-carga-masiva", headers=auth_headers)
    assert listar.status_code == 200
    assert [perfil["id"] for perfil in listar.json()] == [perfil_id]

    actualizar = await client.put(
        f"/api/perfiles-carga-masiva/{perfil_id}",
        headers=auth_headers,
        json={"nombre": "Servicios editados"},
    )
    assert actualizar.status_code == 200, actualizar.text
    assert actualizar.json()["nombre"] == "Servicios editados"

    eliminar = await client.delete(
        f"/api/perfiles-carga-masiva/{perfil_id}",
        headers=auth_headers,
    )
    assert eliminar.status_code == 204

    listar_final = await client.get("/api/perfiles-carga-masiva", headers=auth_headers)
    assert listar_final.json() == []


@pytest.mark.asyncio
async def test_nombre_unico_por_emisor(
    client: AsyncClient,
    auth_headers: dict,
):
    """Rechaza perfiles duplicados dentro del mismo emisor."""
    response = await client.post(
        "/api/perfiles-carga-masiva",
        headers=auth_headers,
        json=_perfil_payload("Mensual"),
    )
    assert response.status_code == 201

    duplicado = await client.post(
        "/api/perfiles-carga-masiva",
        headers=auth_headers,
        json=_perfil_payload("Mensual"),
    )
    assert duplicado.status_code == 400
    assert "Ya existe" in duplicado.json()["detail"]


@pytest.mark.asyncio
async def test_rechaza_fecha_actual_en_fecha_emision(
    client: AsyncClient,
    auth_headers: dict,
):
    """No permite perfiles que conviertan la fecha actual en fecha fiscal."""
    payload = _perfil_payload("Fecha actual")
    payload["configuracion_json"]["fecha_emision"] = {"modo": "fecha_actual"}

    response = await client.post(
        "/api/perfiles-carga-masiva",
        headers=auth_headers,
        json=payload,
    )

    assert response.status_code == 400
    assert "fecha de emisión" in response.json()["detail"]


@pytest.mark.asyncio
async def test_rechaza_reglas_incompletas_de_fechas(
    client: AsyncClient,
    auth_headers: dict,
):
    """Rechaza reglas relativas o personalizadas que no puedan resolverse."""
    payload = _perfil_payload("Personalizada incompleta")
    payload["configuracion_json"]["fecha_emision"] = {"modo": "personalizada"}

    response = await client.post(
        "/api/perfiles-carga-masiva",
        headers=auth_headers,
        json=payload,
    )

    assert response.status_code == 400
    assert "requiere una fecha explícita" in response.json()["detail"]

    payload = _perfil_payload("Vencimiento sin emisión concreta")
    payload["configuracion_json"]["fecha_emision"] = {"modo": "archivo"}
    payload["configuracion_json"]["fecha_vto_pago"] = {
        "modo": "emision_mas_dias",
        "dias": 10,
    }

    response = await client.post(
        "/api/perfiles-carga-masiva",
        headers=auth_headers,
        json=payload,
    )

    assert response.status_code == 400
    assert "vencimiento relativo" in response.json()["detail"]


@pytest.mark.asyncio
async def test_mismo_nombre_en_emisores_distintos(
    client: AsyncClient,
    admin_auth_headers: dict,
    test_empresa: Empresa,
    segunda_empresa: Empresa,
):
    """Permite reutilizar nombres en emisores diferentes."""
    headers_uno = {**admin_auth_headers, "X-Empresa-Id": str(test_empresa.id)}
    headers_dos = {**admin_auth_headers, "X-Empresa-Id": str(segunda_empresa.id)}

    crear_uno = await client.post(
        "/api/perfiles-carga-masiva",
        headers=headers_uno,
        json=_perfil_payload("Mensual"),
    )
    crear_dos = await client.post(
        "/api/perfiles-carga-masiva",
        headers=headers_dos,
        json=_perfil_payload("Mensual"),
    )

    assert crear_uno.status_code == 201, crear_uno.text
    assert crear_dos.status_code == 201, crear_dos.text


@pytest.mark.asyncio
async def test_un_solo_predeterminado_por_emisor(
    client: AsyncClient,
    auth_headers: dict,
):
    """Al marcar un perfil predeterminado se desmarca el anterior."""
    primero = await client.post(
        "/api/perfiles-carga-masiva",
        headers=auth_headers,
        json={**_perfil_payload("Primero"), "es_predeterminado": True},
    )
    segundo = await client.post(
        "/api/perfiles-carga-masiva",
        headers=auth_headers,
        json=_perfil_payload("Segundo"),
    )
    assert primero.status_code == 201, primero.text
    assert segundo.status_code == 201, segundo.text

    marcar = await client.post(
        f"/api/perfiles-carga-masiva/{segundo.json()['id']}/predeterminado",
        headers=auth_headers,
    )
    assert marcar.status_code == 200

    listar = await client.get("/api/perfiles-carga-masiva", headers=auth_headers)
    predeterminados = [
        perfil["nombre"] for perfil in listar.json() if perfil["es_predeterminado"]
    ]
    assert predeterminados == ["Segundo"]


@pytest.mark.asyncio
async def test_bloquea_acceso_cruzado_por_emisor(
    client: AsyncClient,
    admin_auth_headers: dict,
    test_empresa: Empresa,
    segunda_empresa: Empresa,
):
    """Impide operar perfiles de otro emisor activo."""
    headers_uno = {**admin_auth_headers, "X-Empresa-Id": str(test_empresa.id)}
    headers_dos = {**admin_auth_headers, "X-Empresa-Id": str(segunda_empresa.id)}
    crear = await client.post(
        "/api/perfiles-carga-masiva",
        headers=headers_uno,
        json=_perfil_payload(),
    )
    assert crear.status_code == 201

    editar_cruzado = await client.put(
        f"/api/perfiles-carga-masiva/{crear.json()['id']}",
        headers=headers_dos,
        json={"nombre": "No corresponde"},
    )
    assert editar_cruzado.status_code == 400
    assert "no encontrado" in editar_cruzado.json()["detail"].lower()


@pytest.mark.asyncio
async def test_valida_formato_global_y_rechaza_formato_de_otro_emisor(
    client: AsyncClient,
    admin_auth_headers: dict,
    test_empresa: Empresa,
    segunda_empresa: Empresa,
):
    """Valida referencias a formatos accesibles por el emisor activo."""
    headers_uno = {**admin_auth_headers, "X-Empresa-Id": str(test_empresa.id)}
    headers_dos = {**admin_auth_headers, "X-Empresa-Id": str(segunda_empresa.id)}

    formatos_globales = await client.get(
        "/api/formatos-importacion",
        headers=headers_uno,
    )
    global_version_id = formatos_globales.json()[0]["version_vigente"]["id"]
    payload_global = _perfil_payload("Con global")
    payload_global["configuracion_json"][
        "formato_importacion_version_id"
    ] = global_version_id
    crear_global = await client.post(
        "/api/perfiles-carga-masiva",
        headers=headers_uno,
        json=payload_global,
    )
    assert crear_global.status_code == 201, crear_global.text

    formato_propio = await client.post(
        "/api/formatos-importacion",
        headers=headers_uno,
        json={
            "nombre": "Formato propio emisor uno",
            "descripcion": "Formato minimo de prueba",
            "configuracion_json": {
                "tipo": "prueba",
                "header_row": 1,
                "modo_agrupacion": "fila",
                "campos": {
                    "importe_total": {
                        "origen": "header",
                        "encabezados": ["Importe"],
                        "transformacion": "decimal",
                        "requerido": True,
                    }
                },
            },
        },
    )
    version_propia = formato_propio.json()["version_vigente"]["id"]
    payload_cruzado = _perfil_payload("Formato cruzado")
    payload_cruzado["configuracion_json"][
        "formato_importacion_version_id"
    ] = version_propia

    crear_cruzado = await client.post(
        "/api/perfiles-carga-masiva",
        headers=headers_dos,
        json=payload_cruzado,
    )
    assert crear_cruzado.status_code == 400
    assert "no pertenece" in crear_cruzado.json()["detail"]
