# Core - Configuración y Utilidades

Esta carpeta contiene la configuración central y utilidades compartidas.

## Archivos

- `config.py` - Settings de la aplicacion (Pydantic Settings).
- `database.py` - Configuracion de SQLAlchemy async (engine, session, Base).
- `security.py` - Autenticacion (JWT), hashing y dependencias asociadas.

Las variables de entorno estan documentadas en `.env.example` (raiz del repo) y se cargan via `app.core.config.settings`.

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
