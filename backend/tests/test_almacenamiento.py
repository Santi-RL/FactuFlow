"""Tests del gestor administrativo de almacenamiento."""

from datetime import date
import os
from pathlib import Path
import zipfile

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.certificado import Certificado
from app.models.evento_sistema import EventoSistema, ExportacionAlmacenamiento
from app.models.lote_comprobante import (
    LoteComprobante,
    LoteComprobanteFila,
    LoteComprobanteGrupo,
)


async def _crear_lote_cerrado_con_filas(
    db_session: AsyncSession, empresa_id: int
) -> LoteComprobante:
    """Crea un lote cerrado mínimo con detalle compactable."""
    lote = LoteComprobante(
        nombre_archivo="lote-resguardo.xlsx",
        archivo_hash="hash-resguardo",
        estado="completado",
        total_filas=1,
        total_grupos=1,
        grupos_validos=1,
        grupos_emitidos=1,
        empresa_id=empresa_id,
    )
    db_session.add(lote)
    await db_session.flush()

    grupo = LoteComprobanteGrupo(
        lote_id=lote.id,
        comprobante_ref="A-1",
        orden=1,
        estado="autorizado",
        tipo_comprobante=6,
        punto_venta_numero=1,
        total_estimado=1210,
        payload_json={"fecha_emision": "2026-06-01", "concepto": 1},
    )
    db_session.add(grupo)
    await db_session.flush()

    fila = LoteComprobanteFila(
        lote_id=lote.id,
        grupo_id=grupo.id,
        fila_excel=2,
        comprobante_ref="A-1",
        estado="autorizado",
        datos_json={
            "tipo_comprobante": 6,
            "punto_venta": 1,
            "fecha_emision": "2026-06-01",
            "cliente_razon_social": "Consumidor Final",
            "item_descripcion": "Servicio",
            "item_cantidad": 1,
            "item_precio_unitario": 1000,
            "item_iva": 21,
        },
        mensajes_json=[],
    )
    db_session.add(fila)
    await db_session.commit()
    await db_session.refresh(lote)
    return lote


@pytest.mark.asyncio
async def test_usuario_comun_no_accede_almacenamiento(
    client: AsyncClient,
    auth_headers: dict,
):
    """El gestor de almacenamiento queda reservado a administradores."""
    response = await client.get("/api/almacenamiento/resumen", headers=auth_headers)

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_admin_obtiene_resumen_almacenamiento(
    client: AsyncClient,
    admin_auth_headers: dict,
    db_session: AsyncSession,
    test_empresa,
):
    """El resumen muestra categorías y desglose seguro por emisor."""
    await _crear_lote_cerrado_con_filas(db_session, test_empresa.id)

    response = await client.get(
        "/api/almacenamiento/resumen", headers=admin_auth_headers
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["estado"] in {"correcto", "necesita_atencion", "critico"}
    claves = {item["clave"] for item in data["categorias"]}
    assert {"base", "lotes", "certificados", "logs", "temporales", "cache"} <= claves
    assert data["emisores"][0]["empresa_id"] == test_empresa.id
    assert "20123456789" not in data["emisores"][0]["etiqueta"]


@pytest.mark.asyncio
async def test_exportar_descargar_y_liberar_lote_compacta_despues_de_confirmar(
    client: AsyncClient,
    admin_auth_headers: dict,
    db_session: AsyncSession,
    test_empresa,
    tmp_path: Path,
    monkeypatch,
):
    """La liberación exige descarga previa y confirmación manual."""
    monkeypatch.setattr(settings, "storage_tmp_path", str(tmp_path / "tmp"))
    lote = await _crear_lote_cerrado_con_filas(db_session, test_empresa.id)

    create_response = await client.post(
        "/api/almacenamiento/exportaciones",
        headers=admin_auth_headers,
        json={"lote_ids": [lote.id]},
    )

    assert create_response.status_code == 200, create_response.text
    export_data = create_response.json()
    token = export_data["token"]
    assert export_data["size_bytes"] > 0

    forged_download_ack = await client.post(
        f"/api/almacenamiento/exportaciones/{token}/confirmar-descarga",
        headers=admin_auth_headers,
        json={
            "checksum_sha256": export_data["checksum_sha256"],
            "download_token": "token-inventado-sin-descarga",
        },
    )
    assert forged_download_ack.status_code == 400
    assert "confirmación de descarga" in forged_download_ack.json()["detail"]

    early_release = await client.post(
        f"/api/almacenamiento/exportaciones/{token}/confirmar-liberacion",
        headers=admin_auth_headers,
        json={"confirmacion": "YA_LO_DESCARGUE"},
    )
    assert early_release.status_code == 400
    assert "Primero descargá" in early_release.json()["detail"]

    download = await client.get(
        f"/api/almacenamiento/exportaciones/{token}/descargar",
        headers=admin_auth_headers,
    )
    assert download.status_code == 200, download.text
    download_token = download.headers["x-factuflow-download-token"]
    zip_path = tmp_path / "resguardo.zip"
    zip_path.write_bytes(download.content)
    with zipfile.ZipFile(zip_path) as archive:
        assert "manifest.json" in archive.namelist()
        assert f"lotes/lote-{lote.id}/observado.xlsx" in archive.namelist()

    release_without_ack = await client.post(
        f"/api/almacenamiento/exportaciones/{token}/confirmar-liberacion",
        headers=admin_auth_headers,
        json={"confirmacion": "YA_LO_DESCARGUE"},
    )
    assert release_without_ack.status_code == 400
    assert "Primero descargá" in release_without_ack.json()["detail"]

    download_ack = await client.post(
        f"/api/almacenamiento/exportaciones/{token}/confirmar-descarga",
        headers=admin_auth_headers,
        json={
            "checksum_sha256": export_data["checksum_sha256"],
            "download_token": download_token,
        },
    )
    assert download_ack.status_code == 200, download_ack.text

    release = await client.post(
        f"/api/almacenamiento/exportaciones/{token}/confirmar-liberacion",
        headers=admin_auth_headers,
        json={"confirmacion": "YA_LO_DESCARGUE"},
    )

    assert release.status_code == 200, release.text
    filas = await db_session.scalar(
        select(func.count())
        .select_from(LoteComprobanteFila)
        .where(LoteComprobanteFila.lote_id == lote.id)
    )
    assert filas == 0
    eventos = (
        (
            await db_session.execute(
                select(EventoSistema).where(
                    EventoSistema.accion == "confirmar_liberacion"
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(eventos) == 1
    resumen = await client.get(
        "/api/almacenamiento/resumen", headers=admin_auth_headers
    )
    assert resumen.status_code == 200, resumen.text
    resumen_data = resumen.json()
    lotes_categoria = next(
        item for item in resumen_data["categorias"] if item["clave"] == "lotes"
    )
    assert lotes_categoria["bytes_usados"] == 0
    assert resumen_data["emisores"][0]["filas_persistidas"] == 0


@pytest.mark.asyncio
async def test_logs_antiguos_incluyen_rotaciones_del_log_activo(
    client: AsyncClient,
    admin_auth_headers: dict,
    tmp_path: Path,
    monkeypatch,
):
    """Los logs rotados como factuflow.log.1 deben poder resguardarse."""
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    active_log = log_dir / "factuflow.log"
    rotated_log = log_dir / "factuflow.log.1"
    other_log = log_dir / "worker.log"
    active_log.write_bytes(b"activo")
    rotated_log.write_bytes(b"rotado")
    other_log.write_bytes(b"otro")
    old_timestamp = 1_700_000_000
    rotated_log.touch()
    other_log.touch()
    os.utime(rotated_log, (old_timestamp, old_timestamp))
    os.utime(other_log, (old_timestamp, old_timestamp))
    monkeypatch.setattr(settings, "log_file", str(active_log))
    monkeypatch.setattr(settings, "storage_log_retention_days", 1)

    response = await client.get("/api/almacenamiento/logs", headers=admin_auth_headers)

    assert response.status_code == 200, response.text
    ids = {item["id"] for item in response.json()}
    assert "factuflow.log.1" in ids
    assert "worker.log" not in ids
    assert "factuflow.log" not in ids

    resumen = await client.get(
        "/api/almacenamiento/resumen", headers=admin_auth_headers
    )
    assert resumen.status_code == 200, resumen.text
    logs_categoria = next(
        item for item in resumen.json()["categorias"] if item["clave"] == "logs"
    )
    assert logs_categoria["bytes_usados"] == len(b"activo") + len(b"rotado")
    assert logs_categoria["bytes_recuperables"] == len(b"rotado")


@pytest.mark.asyncio
async def test_liberacion_no_borra_temporal_modificado_despues_del_resguardo(
    client: AsyncClient,
    admin_auth_headers: dict,
    db_session: AsyncSession,
    tmp_path: Path,
    monkeypatch,
):
    """La limpieza no debe borrar archivos que no coinciden con el ZIP."""
    storage_tmp = tmp_path / "tmp"
    storage_tmp.mkdir()
    temporal = storage_tmp / "observado.xlsx"
    temporal.write_bytes(b"version-original")
    monkeypatch.setattr(settings, "storage_tmp_path", str(storage_tmp))

    create_response = await client.post(
        "/api/almacenamiento/exportaciones",
        headers=admin_auth_headers,
        json={"temporal_ids": ["observado.xlsx"]},
    )
    assert create_response.status_code == 200, create_response.text
    token = create_response.json()["token"]

    download = await client.get(
        f"/api/almacenamiento/exportaciones/{token}/descargar",
        headers=admin_auth_headers,
    )
    assert download.status_code == 200, download.text
    download_token = download.headers["x-factuflow-download-token"]

    download_ack = await client.post(
        f"/api/almacenamiento/exportaciones/{token}/confirmar-descarga",
        headers=admin_auth_headers,
        json={
            "checksum_sha256": create_response.json()["checksum_sha256"],
            "download_token": download_token,
        },
    )
    assert download_ack.status_code == 200, download_ack.text

    temporal.write_bytes(b"version-nueva")
    release = await client.post(
        f"/api/almacenamiento/exportaciones/{token}/confirmar-liberacion",
        headers=admin_auth_headers,
        json={"confirmacion": "YA_LO_DESCARGUE"},
    )

    assert release.status_code == 400
    assert "cambió después de crear el ZIP" in release.json()["detail"]
    assert temporal.exists()
    assert temporal.read_bytes() == b"version-nueva"
    exportacion = await db_session.scalar(
        select(ExportacionAlmacenamiento).where(
            ExportacionAlmacenamiento.token == token
        )
    )
    assert exportacion is not None
    assert exportacion.estado == "descargada"
    assert exportacion.released_at is None


@pytest.mark.asyncio
async def test_liberacion_fallida_no_marca_exportacion_como_liberada(
    client: AsyncClient,
    admin_auth_headers: dict,
    db_session: AsyncSession,
    test_empresa,
    tmp_path: Path,
    monkeypatch,
):
    """Si falla compactar un lote, la exportación queda descargada y reintentable."""
    monkeypatch.setattr(settings, "storage_tmp_path", str(tmp_path / "tmp"))
    lote = await _crear_lote_cerrado_con_filas(db_session, test_empresa.id)

    create_response = await client.post(
        "/api/almacenamiento/exportaciones",
        headers=admin_auth_headers,
        json={"lote_ids": [lote.id]},
    )
    assert create_response.status_code == 200, create_response.text
    export_data = create_response.json()
    token = export_data["token"]

    download = await client.get(
        f"/api/almacenamiento/exportaciones/{token}/descargar",
        headers=admin_auth_headers,
    )
    assert download.status_code == 200, download.text
    download_token = download.headers["x-factuflow-download-token"]
    download_ack = await client.post(
        f"/api/almacenamiento/exportaciones/{token}/confirmar-descarga",
        headers=admin_auth_headers,
        json={
            "checksum_sha256": export_data["checksum_sha256"],
            "download_token": download_token,
        },
    )
    assert download_ack.status_code == 200, download_ack.text

    lote_id = lote.id
    lote.estado = "validado"
    db_session.add(lote)
    await db_session.commit()

    release = await client.post(
        f"/api/almacenamiento/exportaciones/{token}/confirmar-liberacion",
        headers=admin_auth_headers,
        json={"confirmacion": "YA_LO_DESCARGUE"},
    )

    assert release.status_code == 400
    assert "No se pudo compactar el lote" in release.json()["detail"]
    filas = await db_session.scalar(
        select(func.count())
        .select_from(LoteComprobanteFila)
        .where(LoteComprobanteFila.lote_id == lote_id)
    )
    assert filas == 1
    exportacion = await db_session.scalar(
        select(ExportacionAlmacenamiento).where(
            ExportacionAlmacenamiento.token == token
        )
    )
    assert exportacion is not None
    assert exportacion.estado == "descargada"
    assert exportacion.released_at is None
    assert (
        Path(settings.storage_tmp_path) / "exportaciones" / exportacion.archivo_nombre
    ).exists()


@pytest.mark.asyncio
async def test_limpieza_certificados_huerfanos_solo_elimina_gestionados(
    client: AsyncClient,
    admin_auth_headers: dict,
    db_session: AsyncSession,
    test_empresa,
    tmp_path: Path,
    monkeypatch,
):
    """La limpieza no debe borrar certificados activos ni archivos manuales."""
    monkeypatch.setattr(settings, "certs_path", str(tmp_path))
    orphan = (
        tmp_path
        / "20123456789_homologacion_20260603_120000_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.crt"
    )
    referenced = (
        tmp_path
        / "20123456789_homologacion_20260603_120000_bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb.key"
    )
    manual = tmp_path / "manual.pem"
    orphan.write_bytes(b"orphan")
    referenced.write_bytes(b"referenced")
    manual.write_bytes(b"manual")
    certificado = Certificado(
        nombre="Certificado activo",
        cuit=test_empresa.cuit,
        fecha_emision=date(2026, 1, 1),
        fecha_vencimiento=date(2027, 1, 1),
        archivo_crt=referenced.name,
        archivo_key=referenced.name,
        activo=True,
        ambiente="homologacion",
        empresa_id=test_empresa.id,
    )
    db_session.add(certificado)
    await db_session.commit()

    response = await client.get(
        "/api/almacenamiento/certificados-huerfanos",
        headers=admin_auth_headers,
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert len(data) == 1
    orphan_id = data[0]["id"]
    assert orphan_id != orphan.name
    assert test_empresa.cuit not in orphan_id
    assert test_empresa.cuit not in data[0]["nombre"]

    cleanup = await client.post(
        "/api/almacenamiento/certificados-huerfanos/limpiar",
        headers=admin_auth_headers,
        json={"ids": [orphan_id]},
    )

    assert cleanup.status_code == 200, cleanup.text
    assert not orphan.exists()
    assert referenced.exists()
    assert manual.exists()
