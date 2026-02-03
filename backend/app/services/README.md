# Services - Lógica de Negocio

Esta carpeta contiene la lógica de negocio de la aplicación.

## Estructura

Los servicios encapsulan la lógica compleja y son llamados desde los endpoints.

```
services/
├── cliente_service.py       # CRUD y validaciones de clientes
├── empresa_service.py       # Gestión de empresas
├── comprobante_service.py   # Emisión y gestión de comprobantes
├── certificado_service.py   # Gestión de certificados X.509
└── facturacion_service.py   # Orquestación de emisión de facturas
```

## Principios

- **Separación de responsabilidades**: La lógica de negocio NO debe estar en los endpoints
- **Reutilización**: Los servicios pueden ser llamados desde múltiples endpoints o entre sí
- **Testeable**: Los servicios deben poder testearse independientemente
- **Transaccional**: Manejar transacciones de BD dentro de servicios

## Ejemplo

```python
# services/cliente_service.py
from sqlalchemy.orm import Session
from app.models.cliente import Cliente
from app.schemas.cliente import ClienteCreate

class ClienteService:
    @staticmethod
    def crear_cliente(db: Session, cliente_data: ClienteCreate) -> Cliente:
        """Crea un nuevo cliente con validaciones."""
        # Validar CUIT
        if not ClienteService.validar_cuit(cliente_data.cuit):
            raise ValueError("CUIT inválido")
        
        # Verificar que no exista
        existente = db.query(Cliente).filter(Cliente.cuit == cliente_data.cuit).first()
        if existente:
            raise ValueError("El CUIT ya existe")
        
        # Crear
        cliente = Cliente(**cliente_data.dict())
        db.add(cliente)
        db.commit()
        db.refresh(cliente)
        return cliente
    
    @staticmethod
    def validar_cuit(cuit: str) -> bool:
        """Valida formato y dígito verificador de CUIT argentino."""
        # Implementación de validación de CUIT
        pass
```
