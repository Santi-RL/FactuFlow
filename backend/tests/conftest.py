"""Pytest configuration and fixtures."""

import asyncio
import pytest
from typing import AsyncGenerator
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from app.main import app
from app.core.database import get_db, Base
from app.core.security import get_password_hash
from app.models.usuario import Usuario
from app.models.empresa import Empresa


# Test database URL
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


# Create test engine
test_engine = create_async_engine(
    TEST_DATABASE_URL,
    echo=False,
)

# Create test session factory
TestSessionLocal = async_sessionmaker(
    test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Create a test database session."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async with TestSessionLocal() as session:
        yield session
        await session.rollback()
    
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Create a test client with database override."""
    
    async def override_get_db():
        yield db_session
    
    app.dependency_overrides[get_db] = override_get_db
    
    from httpx import ASGITransport
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    
    app.dependency_overrides.clear()


@pytest.fixture
async def test_empresa(db_session: AsyncSession) -> Empresa:
    """Create a test empresa."""
    from datetime import date
    
    empresa = Empresa(
        razon_social="Empresa Test S.A.",
        cuit="20123456789",
        condicion_iva="RI",
        domicilio="Av. Test 123",
        localidad="Buenos Aires",
        provincia="Buenos Aires",
        codigo_postal="1000",
        email="test@empresa.com",
        telefono="1234567890",
        inicio_actividades=date(2020, 1, 1)
    )
    
    db_session.add(empresa)
    await db_session.commit()
    await db_session.refresh(empresa)
    
    return empresa


@pytest.fixture
async def test_user(db_session: AsyncSession, test_empresa: Empresa) -> Usuario:
    """Create a test user."""
    user = Usuario(
        email="test@user.com",
        hashed_password=get_password_hash("testpassword123"),
        nombre="Test User",
        activo=True,
        es_admin=False,
        empresa_id=test_empresa.id
    )
    
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    
    return user


@pytest.fixture
async def test_admin(db_session: AsyncSession) -> Usuario:
    """Create a test admin user."""
    admin = Usuario(
        email="admin@test.com",
        hashed_password=get_password_hash("adminpass123"),
        nombre="Admin User",
        activo=True,
        es_admin=True,
        empresa_id=None
    )
    
    db_session.add(admin)
    await db_session.commit()
    await db_session.refresh(admin)
    
    return admin


@pytest.fixture
async def auth_headers(client: AsyncClient, test_user) -> dict:
    """Get authentication headers for test user."""
    response = await client.post(
        "/api/auth/login",
        json={
            "email": "test@user.com",
            "password": "testpassword123"
        }
    )
    
    assert response.status_code == 200, f"Login failed: {response.json()}"
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
