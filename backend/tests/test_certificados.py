"""Tests for Certificados API endpoints."""

from datetime import date, datetime
from pathlib import Path

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.certificado import Certificado
from app.services.certificados_service import CertificadoInfo


@pytest.mark.asyncio
class TestCertificadosAPI:
    """Test suite for Certificados endpoints."""

    async def test_list_certificados_empty(
        self, client: AsyncClient, auth_headers: dict
    ):
        """Test listing certificados when there are none."""
        response = await client.get("/api/certificados", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 0

    async def test_generar_csr(self, client: AsyncClient, auth_headers: dict):
        """Test CSR generation."""
        response = await client.post(
            "/api/certificados/generar-csr",
            headers=auth_headers,
            json={
                "cuit": "20123456789",
                "nombre_empresa": "Test Empresa S.A.",
                "ambiente": "homologacion",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert "csr" in data
        assert "key_filename" in data
        assert "mensaje" in data
        assert data["csr"].startswith("-----BEGIN CERTIFICATE REQUEST-----")
        assert data["key_filename"].endswith(".key")

    async def test_generar_csr_invalid_cuit(
        self, client: AsyncClient, auth_headers: dict
    ):
        """Test CSR generation with invalid CUIT."""
        response = await client.post(
            "/api/certificados/generar-csr",
            headers=auth_headers,
            json={
                "cuit": "123",  # CUIT inválido
                "nombre_empresa": "Test Empresa S.A.",
                "ambiente": "homologacion",
            },
        )

        assert response.status_code == 422  # Validation error

    async def test_generar_csr_rechaza_cuit_de_otro_emisor(
        self, client: AsyncClient, auth_headers: dict
    ):
        """El CSR debe rechazar CUIT válido que no sea del emisor activo."""
        response = await client.post(
            "/api/certificados/generar-csr",
            headers=auth_headers,
            json={
                "cuit": "20304050607",
                "nombre_empresa": "Otro Emisor S.A.",
                "ambiente": "homologacion",
            },
        )

        assert response.status_code == 403
        assert response.json()["detail"] == (
            "El CUIT del CSR debe coincidir con el emisor activo"
        )

    async def test_generar_csr_invalid_ambiente(
        self, client: AsyncClient, auth_headers: dict
    ):
        """Test CSR generation with invalid ambiente."""
        response = await client.post(
            "/api/certificados/generar-csr",
            headers=auth_headers,
            json={
                "cuit": "20123456789",
                "nombre_empresa": "Test Empresa S.A.",
                "ambiente": "invalido",  # Ambiente inválido
            },
        )

        assert response.status_code == 422  # Validation error

    async def test_get_alertas_vencimiento_empty(
        self, client: AsyncClient, auth_headers: dict
    ):
        """Test getting alerts when there are no certificates."""
        response = await client.get(
            "/api/certificados/alertas-vencimiento", headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 0

    async def test_verificar_conexion_certificado_inexistente(
        self, client: AsyncClient, auth_headers: dict
    ):
        """Test verification with non-existent certificate."""
        response = await client.post(
            "/api/certificados/verificar-conexion/999", headers=auth_headers
        )

        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
        assert "no encontrado" in data["detail"].lower()

    async def test_verificar_conexion_rechaza_archivos_faltantes_sin_cache(
        self,
        client: AsyncClient,
        auth_headers: dict,
        db_session: AsyncSession,
        test_empresa,
        tmp_path: Path,
        monkeypatch,
    ):
        """La verificación debe fallar si falta el material del certificado."""
        monkeypatch.setattr(settings, "certs_path", str(tmp_path))
        certificado = Certificado(
            nombre="Certificado sin archivos",
            cuit=test_empresa.cuit,
            fecha_emision=date(2026, 1, 1),
            fecha_vencimiento=date(2026, 12, 31),
            archivo_crt="faltante.crt",
            archivo_key="faltante.key",
            activo=True,
            ambiente="homologacion",
            empresa_id=test_empresa.id,
        )
        db_session.add(certificado)
        await db_session.commit()
        await db_session.refresh(certificado)

        response = await client.post(
            f"/api/certificados/verificar-conexion/{certificado.id}",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["exito"] is False
        assert "no están disponibles" in data["error"]

    async def test_verificar_conexion_fuerza_login_sin_cache(
        self,
        client: AsyncClient,
        auth_headers: dict,
        db_session: AsyncSession,
        test_empresa,
        tmp_path: Path,
        monkeypatch,
    ):
        """La verificación debe probar el certificado seleccionado, no el cache."""
        from app.api import certificados as certificados_api

        monkeypatch.setattr(settings, "certs_path", str(tmp_path))
        cert_path = tmp_path / "certificado.crt"
        key_path = tmp_path / "certificado.key"
        cert_path.write_bytes(b"cert")
        key_path.write_bytes(b"key")
        certificado = Certificado(
            nombre="Certificado a verificar",
            cuit=test_empresa.cuit,
            fecha_emision=date(2026, 1, 1),
            fecha_vencimiento=date(2026, 12, 31),
            archivo_crt=cert_path.name,
            archivo_key=key_path.name,
            activo=True,
            ambiente="homologacion",
            empresa_id=test_empresa.id,
        )
        db_session.add(certificado)
        await db_session.commit()
        await db_session.refresh(certificado)
        login_args = {}

        class FakeWSAAClient:
            def __init__(self, **kwargs):
                login_args["ambiente"] = kwargs["ambiente"]

            async def login(self, **kwargs):
                login_args.update(kwargs)

        monkeypatch.setattr(certificados_api, "WSAAClient", FakeWSAAClient)

        response = await client.post(
            f"/api/certificados/verificar-conexion/{certificado.id}",
            headers=auth_headers,
        )

        assert response.status_code == 200
        assert response.json()["exito"] is True
        assert login_args["force_new"] is True
        assert Path(login_args["cert_path"]).name == cert_path.name
        assert Path(login_args["key_path"]).name == key_path.name

    async def test_subir_certificado_rechaza_key_filename_con_traversal(
        self, client: AsyncClient, auth_headers: dict, monkeypatch
    ):
        """No debe aceptar paths de clave privada fuera de certs_path."""
        from app.services.certificados_service import CertificadosService

        async def fail_validar_certificado(*_args, **_kwargs):
            raise AssertionError("No debe intentar validar una clave no administrada")

        monkeypatch.setattr(
            CertificadosService, "validar_certificado", fail_validar_certificado
        )

        response = await client.post(
            "/api/certificados/subir-certificado",
            headers=auth_headers,
            files={
                "file": ("certificado.crt", b"certificado", "application/pkix-cert")
            },
            data={
                "cuit": "20123456789",
                "nombre": "Certificado traversal",
                "ambiente": "homologacion",
                "key_filename": "../secret.key",
            },
        )

        assert response.status_code == 400
        assert "archivo" in response.json()["detail"].lower()

    async def test_subir_certificado_limpia_archivo_si_validacion_falla(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_empresa,
        tmp_path: Path,
        monkeypatch,
    ):
        """Un certificado inválido no debe dejar archivos no referenciados."""
        from app.arca.exceptions import ArcaCertificateError
        from app.services.certificados_service import CertificadosService

        monkeypatch.setattr(settings, "certs_path", str(tmp_path))
        key_filename = (
            "20123456789_homologacion_20260516_120000_"
            "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.key"
        )
        (tmp_path / key_filename).write_bytes(b"clave")
        cert_filename = (
            "20123456789_homologacion_20260516_120000_"
            "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb.crt"
        )
        saved_path = tmp_path / cert_filename

        async def fake_guardar_certificado(self, contenido, cuit, ambiente):
            saved_path.write_bytes(contenido)
            return str(saved_path)

        async def fail_validar_certificado(self, cert_path, key_path, cuit_esperado):
            raise ArcaCertificateError("Certificado inválido")

        monkeypatch.setattr(
            CertificadosService, "guardar_certificado", fake_guardar_certificado
        )
        monkeypatch.setattr(
            CertificadosService, "validar_certificado", fail_validar_certificado
        )

        response = await client.post(
            "/api/certificados/subir-certificado",
            headers=auth_headers,
            files={
                "file": ("certificado.crt", b"certificado", "application/pkix-cert")
            },
            data={
                "cuit": test_empresa.cuit,
                "nombre": "Certificado inválido",
                "ambiente": "homologacion",
                "key_filename": key_filename,
            },
        )

        assert response.status_code == 400
        assert not saved_path.exists()

    async def test_subir_certificado_desactiva_activo_previo(
        self,
        client: AsyncClient,
        auth_headers: dict,
        db_session: AsyncSession,
        test_empresa,
        tmp_path: Path,
        monkeypatch,
    ):
        """Al subir renovación queda activo solo el certificado nuevo."""
        from app.services.certificados_service import CertificadosService

        monkeypatch.setattr(settings, "certs_path", str(tmp_path))
        key_filename = (
            "20123456789_homologacion_20260516_120000_"
            "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.key"
        )
        (tmp_path / key_filename).write_bytes(b"clave")
        cert_filename = (
            "20123456789_homologacion_20260516_120000_"
            "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb.crt"
        )

        certificado_previo = Certificado(
            nombre="Certificado previo",
            cuit=test_empresa.cuit,
            fecha_emision=date(2026, 1, 1),
            fecha_vencimiento=date(2026, 12, 31),
            archivo_crt="previo.crt",
            archivo_key="previo.key",
            activo=True,
            ambiente="homologacion",
            empresa_id=test_empresa.id,
        )
        db_session.add(certificado_previo)
        await db_session.commit()

        async def fake_guardar_certificado(self, contenido, cuit, ambiente):
            path = tmp_path / cert_filename
            path.write_bytes(contenido)
            return str(path)

        async def fake_validar_certificado(self, cert_path, key_path, cuit_esperado):
            assert Path(cert_path).name == cert_filename
            assert Path(key_path).name == key_filename
            assert cuit_esperado == test_empresa.cuit
            return CertificadoInfo(
                cuit=test_empresa.cuit,
                fecha_emision=date(2026, 5, 16),
                fecha_vencimiento=date(2028, 5, 16),
                subject={},
                issuer={},
                serial_number="1",
            )

        monkeypatch.setattr(
            CertificadosService, "guardar_certificado", fake_guardar_certificado
        )
        monkeypatch.setattr(
            CertificadosService, "validar_certificado", fake_validar_certificado
        )

        response = await client.post(
            "/api/certificados/subir-certificado",
            headers=auth_headers,
            files={
                "file": ("certificado.crt", b"certificado", "application/pkix-cert")
            },
            data={
                "cuit": test_empresa.cuit,
                "nombre": "Certificado nuevo",
                "ambiente": "homologacion",
                "key_filename": key_filename,
            },
        )

        assert response.status_code == 200
        await db_session.refresh(certificado_previo)
        assert certificado_previo.activo is False

        activos = (
            (
                await db_session.execute(
                    select(Certificado).where(
                        Certificado.empresa_id == test_empresa.id,
                        Certificado.ambiente == "homologacion",
                        Certificado.activo.is_(True),
                    )
                )
            )
            .scalars()
            .all()
        )
        assert len(activos) == 1
        assert activos[0].nombre == "Certificado nuevo"
        assert activos[0].archivo_crt == cert_filename
        assert activos[0].archivo_key == key_filename

    async def test_delete_certificado_elimina_archivos_no_referenciados(
        self,
        client: AsyncClient,
        auth_headers: dict,
        db_session: AsyncSession,
        test_empresa,
        tmp_path: Path,
        monkeypatch,
    ):
        """Eliminar un certificado borra sus archivos gestionados si no se comparten."""
        monkeypatch.setattr(settings, "certs_path", str(tmp_path))
        cert_path = tmp_path / "certificado.crt"
        key_path = tmp_path / "certificado.key"
        cert_path.write_bytes(b"cert")
        key_path.write_bytes(b"key")

        certificado = Certificado(
            nombre="Certificado a borrar",
            cuit=test_empresa.cuit,
            fecha_emision=date(2026, 1, 1),
            fecha_vencimiento=date(2026, 12, 31),
            archivo_crt=cert_path.name,
            archivo_key=key_path.name,
            activo=True,
            ambiente="homologacion",
            empresa_id=test_empresa.id,
        )
        db_session.add(certificado)
        await db_session.commit()
        await db_session.refresh(certificado)

        response = await client.delete(
            f"/api/certificados/{certificado.id}", headers=auth_headers
        )

        assert response.status_code == 204
        assert not cert_path.exists()
        assert not key_path.exists()

    async def test_delete_certificado_no_elimina_archivos_si_commit_falla(
        self,
        client: AsyncClient,
        auth_headers: dict,
        db_session: AsyncSession,
        test_empresa,
        tmp_path: Path,
        monkeypatch,
    ):
        """Si el commit falla, los archivos del certificado deben conservarse."""
        monkeypatch.setattr(settings, "certs_path", str(tmp_path))
        cert_path = tmp_path / "certificado.crt"
        key_path = tmp_path / "certificado.key"
        cert_path.write_bytes(b"cert")
        key_path.write_bytes(b"key")

        certificado = Certificado(
            nombre="Certificado con commit fallido",
            cuit=test_empresa.cuit,
            fecha_emision=date(2026, 1, 1),
            fecha_vencimiento=date(2026, 12, 31),
            archivo_crt=cert_path.name,
            archivo_key=key_path.name,
            activo=True,
            ambiente="homologacion",
            empresa_id=test_empresa.id,
        )
        db_session.add(certificado)
        await db_session.commit()
        await db_session.refresh(certificado)
        certificado_id = certificado.id

        async def fail_commit():
            raise RuntimeError("commit fallido simulado")

        monkeypatch.setattr(db_session, "commit", fail_commit)

        with pytest.raises(RuntimeError, match="commit fallido simulado"):
            await client.delete(
                f"/api/certificados/{certificado_id}", headers=auth_headers
            )

        assert cert_path.exists()
        assert key_path.exists()
        await db_session.rollback()
        certificado_persistido = await db_session.get(Certificado, certificado_id)
        assert certificado_persistido is not None

    async def test_delete_certificado_rollback_si_limpieza_post_commit_falla(
        self,
        client: AsyncClient,
        auth_headers: dict,
        db_session: AsyncSession,
        test_empresa,
        tmp_path: Path,
        monkeypatch,
    ):
        """Un fallo de limpieza post-commit no debe dejar la sesión abortada."""
        from app.api import certificados as certificados_api

        monkeypatch.setattr(settings, "certs_path", str(tmp_path))
        cert_path = tmp_path / "certificado.crt"
        key_path = tmp_path / "certificado.key"
        cert_path.write_bytes(b"cert")
        key_path.write_bytes(b"key")

        certificado = Certificado(
            nombre="Certificado con limpieza fallida",
            cuit=test_empresa.cuit,
            fecha_emision=date(2026, 1, 1),
            fecha_vencimiento=date(2026, 12, 31),
            archivo_crt=cert_path.name,
            archivo_key=key_path.name,
            activo=True,
            ambiente="homologacion",
            empresa_id=test_empresa.id,
        )
        db_session.add(certificado)
        await db_session.commit()
        await db_session.refresh(certificado)
        certificado_id = certificado.id
        rollback_called = False
        original_rollback = db_session.rollback

        async def fail_cleanup(*_args, **_kwargs):
            raise SQLAlchemyError("limpieza fallida simulada")

        async def spy_rollback():
            nonlocal rollback_called
            rollback_called = True
            await original_rollback()

        monkeypatch.setattr(
            certificados_api,
            "_eliminar_archivos_certificado_no_referenciados",
            fail_cleanup,
        )
        monkeypatch.setattr(db_session, "rollback", spy_rollback)

        response = await client.delete(
            f"/api/certificados/{certificado_id}", headers=auth_headers
        )

        assert response.status_code == 204
        assert rollback_called is True
        assert cert_path.exists()
        assert key_path.exists()


@pytest.mark.asyncio
class TestCertificadosService:
    """Test suite for CertificadosService."""

    async def test_generar_clave_y_csr_service(self):
        """Test CSR generation service."""
        from app.services.certificados_service import CertificadosService

        service = CertificadosService()

        key_path, csr_pem, key_filename = await service.generar_clave_y_csr(
            cuit="20123456789", nombre_empresa="Test Empresa", ambiente="homologacion"
        )

        # Verificar que se generaron los archivos correctamente
        assert key_path is not None
        assert csr_pem.startswith("-----BEGIN CERTIFICATE REQUEST-----")
        assert key_filename.endswith(".key")
        assert "20123456789" in key_filename
        assert "homologacion" in key_filename
        assert b"ENCRYPTED" in Path(key_path).read_bytes()

    async def test_generar_clave_y_csr_same_second_uses_unique_filenames(
        self, tmp_path: Path, monkeypatch
    ):
        """Dos claves del mismo segundo no deben pisarse entre sí."""
        from app.services import certificados_service as certificados_module
        from app.services.certificados_service import CertificadosService

        class FixedDateTime:
            @classmethod
            def now(cls):
                return datetime(2026, 5, 16, 12, 0, 0)

        monkeypatch.setattr(settings, "certs_path", str(tmp_path))
        monkeypatch.setattr(certificados_module, "datetime", FixedDateTime)

        service = CertificadosService()
        first_key_path, _, first_filename = await service.generar_clave_y_csr(
            cuit="20123456789",
            nombre_empresa="Test Empresa",
            ambiente="homologacion",
        )
        second_key_path, _, second_filename = await service.generar_clave_y_csr(
            cuit="20123456789",
            nombre_empresa="Test Empresa",
            ambiente="homologacion",
        )

        assert first_filename != second_filename
        assert Path(first_key_path).exists()
        assert Path(second_key_path).exists()

    async def test_calcular_estado_service(self):
        """Test estado calculation."""
        from app.services.certificados_service import CertificadosService

        service = CertificadosService()

        # Certificado válido (más de 30 días)
        assert service.calcular_estado(60) == "valido"
        assert service.calcular_estado(31) == "valido"

        # Certificado por vencer (30 días o menos)
        assert service.calcular_estado(30) == "por_vencer"
        assert service.calcular_estado(15) == "por_vencer"
        assert service.calcular_estado(1) == "por_vencer"

        # Certificado vencido (0 o negativo)
        assert service.calcular_estado(0) == "vencido"
        assert service.calcular_estado(-1) == "vencido"
        assert service.calcular_estado(-30) == "vencido"

    async def test_get_tipo_alerta_service(self):
        """Test tipo alerta calculation."""
        from app.services.certificados_service import CertificadosService

        service = CertificadosService()

        # Info (más de 30 días)
        assert service.get_tipo_alerta(60) == "info"
        assert service.get_tipo_alerta(31) == "info"

        # Warning (8-30 días)
        assert service.get_tipo_alerta(30) == "warning"
        assert service.get_tipo_alerta(15) == "warning"
        assert service.get_tipo_alerta(8) == "warning"

        # Danger (7 días o menos, o vencido)
        assert service.get_tipo_alerta(7) == "danger"
        assert service.get_tipo_alerta(1) == "danger"
        assert service.get_tipo_alerta(0) == "danger"
        assert service.get_tipo_alerta(-10) == "danger"

    async def test_resolve_cert_storage_path_with_legacy_prefix(self, monkeypatch):
        """Acepta paths legacy guardados como certs/<archivo> en la BD."""
        from app.core.config import settings
        from app.services.certificados_service import resolve_cert_storage_path

        monkeypatch.setattr(settings, "certs_path", "./certs")

        resolved = resolve_cert_storage_path(
            "certs/23318277559_homologacion_20260309_190054.crt"
        )

        resolved_path = Path(resolved)
        assert resolved_path.name == "23318277559_homologacion_20260309_190054.crt"
        assert resolved_path.parent.name == "certs"
        assert resolved_path.parent.parent.name == "backend"

    async def test_resolve_cert_storage_path_with_filename_only(self, monkeypatch):
        """Mantiene soporte para paths relativos simples sin prefijo."""
        from app.core.config import settings
        from app.services.certificados_service import resolve_cert_storage_path

        monkeypatch.setattr(settings, "certs_path", "./certs")

        resolved = resolve_cert_storage_path(
            "23318277559_homologacion_20260309_190054.key"
        )

        resolved_path = Path(resolved)
        assert resolved_path.name == "23318277559_homologacion_20260309_190054.key"
        assert resolved_path.parent.name == "certs"
        assert resolved_path.parent.parent.name == "backend"

    async def test_resolve_cert_storage_path_rejects_escape(
        self, tmp_path: Path, monkeypatch
    ):
        """El resolver no debe permitir salir de CERTS_PATH."""
        from app.arca.exceptions import ArcaCertificateError
        from app.services.certificados_service import resolve_cert_storage_path

        monkeypatch.setattr(settings, "certs_path", str(tmp_path))

        with pytest.raises(ArcaCertificateError):
            resolve_cert_storage_path("../secret.key")

    async def test_resolve_managed_cert_filename_rejects_absolute_path(
        self, tmp_path: Path, monkeypatch
    ):
        """El nombre de clave informado por formulario debe ser un basename."""
        from app.arca.exceptions import ArcaCertificateError
        from app.services.certificados_service import resolve_managed_cert_filename

        monkeypatch.setattr(settings, "certs_path", str(tmp_path))

        with pytest.raises(ArcaCertificateError):
            resolve_managed_cert_filename(
                str(tmp_path / "20123456789_homologacion_20260516_120000.key"),
                "20123456789",
                "homologacion",
                "key",
            )
