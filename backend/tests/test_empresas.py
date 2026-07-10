"""Tests de endpoints de emisores."""

from datetime import date
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models.certificado import Certificado
from app.models.cliente import Cliente
from app.models.comprobante import Comprobante
from app.models.empresa import Empresa
from app.models.formato_importacion import FormatoImportacion
from app.models.idempotencia_fiscal import IntentoEmisionFiscal, OperacionIdempotente
from app.models.lote_comprobante import LoteComprobante
from app.models.perfil_carga_masiva import PerfilCargaMasiva
from app.models.punto_venta import PuntoVenta
from app.models.usuario import Usuario


async def _crear_comprobante_autorizado(db_session, empresa_id: int) -> Comprobante:
    """Crea un comprobante fiscal autorizado para el emisor indicado."""
    punto_venta = PuntoVenta(
        numero=1,
        nombre="Punto fiscal",
        es_webservice=True,
        empresa_id=empresa_id,
    )
    db_session.add(punto_venta)
    await db_session.flush()

    comprobante = Comprobante(
        tipo_comprobante=6,
        concepto=1,
        numero=1,
        fecha_emision=date(2026, 1, 15),
        subtotal=Decimal("100.00"),
        descuento=Decimal("0.00"),
        iva_21=Decimal("21.00"),
        iva_10_5=Decimal("0.00"),
        iva_27=Decimal("0.00"),
        otros_impuestos=Decimal("0.00"),
        total=Decimal("121.00"),
        cae="12345678901234",
        cae_vencimiento=date(2026, 1, 25),
        estado="autorizado",
        empresa_id=empresa_id,
        punto_venta_id=punto_venta.id,
    )
    db_session.add(comprobante)
    await db_session.commit()
    return comprobante


@pytest.mark.asyncio
async def test_usuario_comun_lista_solo_su_emisor_y_no_crea_emisores(
    client: AsyncClient,
    auth_headers: dict,
):
    """Un usuario común solo ve su emisor y no puede crear otros emisores."""
    list_response = await client.get("/api/empresas", headers=auth_headers)

    assert list_response.status_code == 200
    assert len(list_response.json()) == 1

    create_response = await client.post(
        "/api/empresas",
        headers=auth_headers,
        json={
            "razon_social": "Nuevo Emisor S.A.",
            "cuit": "30999999995",
            "condicion_iva": "RI",
            "domicilio": "Av. Nueva 123",
            "localidad": "CABA",
            "provincia": "Buenos Aires",
            "codigo_postal": "1000",
            "inicio_actividades": date(2024, 1, 1).isoformat(),
        },
    )

    assert create_response.status_code == 403
    assert (
        create_response.json()["detail"] == "Solo un administrador puede crear emisores"
    )


@pytest.mark.asyncio
async def test_admin_crea_emisor(
    client: AsyncClient,
    admin_auth_headers: dict,
):
    """Un administrador puede agregar otro emisor para operar."""
    response = await client.post(
        "/api/empresas",
        headers=admin_auth_headers,
        json={
            "razon_social": "Nuevo Emisor S.A.",
            "cuit": "30999999995",
            "condicion_iva": "RI",
            "domicilio": "Av. Nueva 123",
            "localidad": "CABA",
            "provincia": "Buenos Aires",
            "codigo_postal": "1000",
            "inicio_actividades": date(2024, 1, 1).isoformat(),
        },
    )

    assert response.status_code == 201
    assert response.json()["razon_social"] == "Nuevo Emisor S.A."


@pytest.mark.asyncio
async def test_no_puede_crear_emisor_sin_auth_si_ya_hay_usuarios(
    client: AsyncClient,
    auth_headers: dict,
):
    """La creación anónima solo queda disponible durante el setup inicial."""
    assert auth_headers

    response = await client.post(
        "/api/empresas",
        json={
            "razon_social": "Emisor Anónimo S.A.",
            "cuit": "30888888889",
            "condicion_iva": "RI",
            "domicilio": "Av. Anónima 123",
            "localidad": "CABA",
            "provincia": "Buenos Aires",
            "codigo_postal": "1000",
            "inicio_actividades": date(2024, 1, 1).isoformat(),
        },
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_usuario_comun_no_lee_ni_modifica_emisor_ajeno(
    client: AsyncClient,
    auth_headers: dict,
    db_session,
):
    """Un usuario común no debe acceder por ID directo a otro emisor."""
    ajena = Empresa(
        razon_social="Empresa Ajena S.A.",
        cuit="30777777778",
        condicion_iva="RI",
        domicilio="Av. Ajena 123",
        localidad="CABA",
        provincia="Buenos Aires",
        codigo_postal="1000",
        inicio_actividades=date(2024, 1, 1),
    )
    db_session.add(ajena)
    await db_session.commit()
    await db_session.refresh(ajena)

    get_response = await client.get(
        f"/api/empresas/{ajena.id}",
        headers=auth_headers,
    )
    update_response = await client.put(
        f"/api/empresas/{ajena.id}",
        headers=auth_headers,
        json={"email": "intruso@example.com"},
    )

    assert get_response.status_code == 403
    assert update_response.status_code == 403
    await db_session.refresh(ajena)
    assert ajena.email is None


@pytest.mark.asyncio
async def test_usuario_comun_no_puede_actualizar_su_emisor(
    client: AsyncClient,
    auth_headers: dict,
):
    """La administración del emisor queda reservada a administradores."""
    list_response = await client.get("/api/empresas", headers=auth_headers)
    empresa_id = list_response.json()[0]["id"]

    response = await client.put(
        f"/api/empresas/{empresa_id}",
        headers=auth_headers,
        json={"email": "cambio-no-autorizado@example.com"},
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_usuario_comun_no_puede_eliminar_emisor(
    client: AsyncClient,
    auth_headers: dict,
):
    """El borrado físico de emisores queda reservado a administradores."""
    list_response = await client.get("/api/empresas", headers=auth_headers)
    empresa_id = list_response.json()[0]["id"]

    response = await client.delete(f"/api/empresas/{empresa_id}", headers=auth_headers)

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_admin_elimina_emisor_sin_borrar_usuarios_preferidos(
    client: AsyncClient,
    admin_auth_headers: dict,
    auth_headers: dict,
    db_session,
):
    """Borrar un emisor vacío debe limpiar preferencias sin borrar usuarios."""
    assert auth_headers
    list_response = await client.get("/api/empresas", headers=admin_auth_headers)
    empresa_id = list_response.json()[0]["id"]

    response = await client.delete(
        f"/api/empresas/{empresa_id}",
        headers=admin_auth_headers,
    )

    assert response.status_code == 204

    result = await db_session.execute(
        select(Usuario).where(Usuario.email == "test@user.com")
    )
    usuario = result.scalar_one()
    assert usuario.empresa_id is None


def _empresa_fk_ondelete(model) -> str:
    """Devuelve la política ondelete del FK empresa_id del modelo."""
    for foreign_key in model.__table__.foreign_keys:
        if (
            foreign_key.parent.name == "empresa_id"
            and foreign_key.column.table.name == "empresas"
        ):
            return foreign_key.ondelete
    raise AssertionError(f"{model.__name__} no tiene FK empresa_id a empresas")


def test_modelos_empresa_no_declaran_cascadas_destructivas():
    """Los modelos no deben borrar historial al eliminar un emisor por ORM/FK."""
    assert _empresa_fk_ondelete(Usuario) == "SET NULL"

    modelos_restringidos = (
        Certificado,
        Cliente,
        PuntoVenta,
        Comprobante,
        LoteComprobante,
        FormatoImportacion,
        PerfilCargaMasiva,
        OperacionIdempotente,
        IntentoEmisionFiscal,
    )
    for modelo in modelos_restringidos:
        assert _empresa_fk_ondelete(modelo) == "RESTRICT"

    relaciones_empresa = {
        "usuarios",
        "clientes",
        "puntos_venta",
        "certificados",
        "comprobantes",
        "lotes_comprobantes",
        "perfiles_carga_masiva",
    }
    for relacion in Empresa.__mapper__.relationships:
        if relacion.key in relaciones_empresa:
            assert "delete" not in relacion.cascade
            assert relacion.passive_deletes is True


@pytest.mark.asyncio
async def test_borrado_directo_emisor_con_historial_fiscal_falla_por_fk(
    db_session,
    test_empresa: Empresa,
):
    """La base debe restringir borrados directos con comprobantes fiscales."""
    empresa_id = test_empresa.id
    comprobante = await _crear_comprobante_autorizado(db_session, empresa_id)
    comprobante_id = comprobante.id

    await db_session.delete(test_empresa)
    with pytest.raises(IntegrityError):
        await db_session.commit()

    await db_session.rollback()
    assert await db_session.get(Empresa, empresa_id) is not None
    assert await db_session.get(Comprobante, comprobante_id) is not None


@pytest.mark.asyncio
async def test_admin_no_puede_eliminar_emisor_con_historial_fiscal(
    client: AsyncClient,
    admin_auth_headers: dict,
    db_session,
    test_empresa: Empresa,
):
    """Borrar un emisor no debe destruir comprobantes fiscales asociados."""
    empresa_id = test_empresa.id
    comprobante = await _crear_comprobante_autorizado(db_session, empresa_id)
    comprobante_id = comprobante.id

    response = await client.delete(
        f"/api/empresas/{empresa_id}",
        headers=admin_auth_headers,
    )

    assert response.status_code == 409
    detail = response.json()["detail"]
    assert "datos operativos o fiscales" in detail
    assert "comprobantes fiscales" in detail
    assert await db_session.get(Empresa, empresa_id) is not None
    assert await db_session.get(Comprobante, comprobante_id) is not None


@pytest.mark.asyncio
async def test_no_puede_modificar_identidad_fiscal_con_historial(
    client: AsyncClient,
    admin_auth_headers: dict,
    db_session,
    test_empresa: Empresa,
):
    """Un emisor con historial fiscal no debe permitir cambiar su CUIT."""
    await _crear_comprobante_autorizado(db_session, test_empresa.id)

    response = await client.put(
        f"/api/empresas/{test_empresa.id}",
        headers=admin_auth_headers,
        json={"cuit": "30999999995"},
    )

    assert response.status_code == 409
    detail = response.json()["detail"]
    assert "identidad fiscal" in detail
    assert "cuit" in detail
    assert "comprobantes fiscales" in detail
    await db_session.refresh(test_empresa)
    assert test_empresa.cuit == "20123456789"


@pytest.mark.asyncio
async def test_puede_modificar_contacto_con_historial_fiscal(
    client: AsyncClient,
    admin_auth_headers: dict,
    db_session,
    test_empresa: Empresa,
):
    """Un emisor con historial fiscal puede actualizar datos no fiscales."""
    await _crear_comprobante_autorizado(db_session, test_empresa.id)

    response = await client.put(
        f"/api/empresas/{test_empresa.id}",
        headers=admin_auth_headers,
        json={
            "email": "nuevo@example.com",
            "telefono": "11112222",
            "logo": "logos/nuevo.png",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "nuevo@example.com"
    assert data["telefono"] == "11112222"
    assert data["logo"] == "logos/nuevo.png"
