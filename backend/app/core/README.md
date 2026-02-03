# Core - Configuración y Utilidades

Esta carpeta contiene la configuración central y utilidades compartidas.

## Archivos

- `config.py` - Settings de la aplicación (usando Pydantic Settings)
- `database.py` - Configuración de SQLAlchemy, session factory
- `security.py` - Funciones de autenticación, hashing de passwords, JWT
- `logging.py` - Configuración de logging
- `exceptions.py` - Excepciones personalizadas

## Ejemplo de uso

```python
from app.core.config import settings
from app.core.database import get_db
from app.core.security import get_current_user

@app.get("/ejemplo")
async def ejemplo(db: Session = Depends(get_db), user = Depends(get_current_user)):
    print(settings.app_env)
    return {"message": "OK"}
```
