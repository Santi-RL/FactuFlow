"""Tests for Certificados API endpoints."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.empresa import Empresa
from app.models.usuario import Usuario


@pytest.mark.asyncio
class TestCertificadosAPI:
    """Test suite for Certificados endpoints."""
    
    async def test_list_certificados_empty(
        self,
        client: AsyncClient,
        auth_headers: dict
    ):
        """Test listing certificados when there are none."""
        response = await client.get(
            "/api/certificados",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 0
    
    async def test_generar_csr(
        self,
        client: AsyncClient,
        auth_headers: dict
    ):
        """Test CSR generation."""
        response = await client.post(
            "/api/certificados/generar-csr",
            headers=auth_headers,
            json={
                "cuit": "20123456789",
                "nombre_empresa": "Test Empresa S.A.",
                "ambiente": "homologacion"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "csr" in data
        assert "key_filename" in data
        assert "mensaje" in data
        assert data["csr"].startswith("-----BEGIN CERTIFICATE REQUEST-----")
        assert data["key_filename"].endswith(".key")
    
    async def test_generar_csr_invalid_cuit(
        self,
        client: AsyncClient,
        auth_headers: dict
    ):
        """Test CSR generation with invalid CUIT."""
        response = await client.post(
            "/api/certificados/generar-csr",
            headers=auth_headers,
            json={
                "cuit": "123",  # CUIT inválido
                "nombre_empresa": "Test Empresa S.A.",
                "ambiente": "homologacion"
            }
        )
        
        assert response.status_code == 422  # Validation error
    
    async def test_generar_csr_invalid_ambiente(
        self,
        client: AsyncClient,
        auth_headers: dict
    ):
        """Test CSR generation with invalid ambiente."""
        response = await client.post(
            "/api/certificados/generar-csr",
            headers=auth_headers,
            json={
                "cuit": "20123456789",
                "nombre_empresa": "Test Empresa S.A.",
                "ambiente": "invalido"  # Ambiente inválido
            }
        )
        
        assert response.status_code == 422  # Validation error
    
    async def test_get_alertas_vencimiento_empty(
        self,
        client: AsyncClient,
        auth_headers: dict
    ):
        """Test getting alerts when there are no certificates."""
        response = await client.get(
            "/api/certificados/alertas-vencimiento",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 0
    
    async def test_verificar_conexion_certificado_inexistente(
        self,
        client: AsyncClient,
        auth_headers: dict
    ):
        """Test verification with non-existent certificate."""
        response = await client.post(
            "/api/certificados/verificar-conexion/999",
            headers=auth_headers
        )
        
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
        assert "no encontrado" in data["detail"].lower()


@pytest.mark.asyncio
class TestCertificadosService:
    """Test suite for CertificadosService."""
    
    async def test_generar_clave_y_csr_service(self):
        """Test CSR generation service."""
        from app.services.certificados_service import CertificadosService
        
        service = CertificadosService()
        
        key_path, csr_pem, key_filename = await service.generar_clave_y_csr(
            cuit="20123456789",
            nombre_empresa="Test Empresa",
            ambiente="homologacion"
        )
        
        # Verificar que se generaron los archivos correctamente
        assert key_path is not None
        assert csr_pem.startswith("-----BEGIN CERTIFICATE REQUEST-----")
        assert key_filename.endswith(".key")
        assert "20123456789" in key_filename
        assert "homologacion" in key_filename
    
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
