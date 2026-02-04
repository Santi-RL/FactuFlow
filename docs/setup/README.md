# Guías de Instalación

Instrucciones paso a paso para instalar y configurar FactuFlow.

## Instalación con Docker (Recomendada)

### Requisitos Previos
- Docker 20.10+
- Docker Compose 2.0+

### Pasos

1. **Clonar el repositorio**
   ```bash
   git clone https://github.com/Santi-RL/FactuFlow.git
   cd FactuFlow
   ```

2. **Configurar variables de entorno**
   ```bash
   cp .env.example .env
   # Editar .env con tu editor preferido
   nano .env
   ```

3. **Generar clave secreta**
   ```bash
   python3 -c "import secrets; print(secrets.token_urlsafe(32))"
   # Copiar el resultado y reemplazar APP_SECRET_KEY en .env
   ```

4. **Levantar los servicios**
   ```bash
   docker-compose up -d
   ```

5. **Verificar que todo esté corriendo**
   ```bash
   docker-compose ps
   # Deberías ver backend y frontend en estado "Up"
   ```

6. **Acceder a la aplicación**
   - Frontend: http://localhost:8080
   - Backend API: http://localhost:8000
   - Documentación API: http://localhost:8000/docs

7. **Ver logs (opcional)**
   ```bash
   docker-compose logs -f backend
   docker-compose logs -f frontend
   ```

### Actualizar

```bash
git pull origin main
docker-compose down
docker-compose up -d --build
```

---

## Instalación Manual (Sin Docker)

### Requisitos Previos
- Python 3.11+
- Node.js 20+
- npm o pnpm

### Backend

1. **Crear entorno virtual**
   ```bash
   cd backend
   python3 -m venv .venv
   source .venv/bin/activate  # En Linux/Mac
   # O en Windows: .venv\Scripts\activate
   ```

2. **Instalar dependencias**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configurar variables de entorno**
   ```bash
   cd ..
   cp .env.example .env
   # Editar .env
   ```

4. **Ejecutar migraciones**
   ```bash
   cd backend
   alembic upgrade head
   ```

5. **Ejecutar servidor**
   ```bash
   uvicorn app.main:app --reload --port 8000
   ```

### Frontend

1. **Instalar dependencias**
   ```bash
   cd frontend
   npm install
   ```

2. **Ejecutar servidor de desarrollo**
   ```bash
   npm run dev
   ```

3. **Acceder**
   - Frontend: http://localhost:8080
   - Backend: http://localhost:8000

---

## Instalación en VPS (Producción)

### Requisitos
- VPS con Ubuntu 22.04 o superior
- Dominio configurado (opcional)
- Certificado SSL (Let's Encrypt recomendado)

### Pasos

1. **Conectarse al VPS**
   ```bash
   ssh user@tu-servidor.com
   ```

2. **Instalar Docker**
   ```bash
   curl -fsSL https://get.docker.com -o get-docker.sh
   sh get-docker.sh
   sudo usermod -aG docker $USER
   ```

3. **Instalar Docker Compose**
   ```bash
   sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
   sudo chmod +x /usr/local/bin/docker-compose
   ```

4. **Clonar repositorio**
   ```bash
   git clone https://github.com/Santi-RL/FactuFlow.git
   cd FactuFlow
   ```

5. **Configurar .env para producción**
   ```bash
   cp .env.example .env
   nano .env
   ```

   Cambios importantes:
   ```bash
   APP_ENV=production
   APP_DEBUG=false
   APP_SECRET_KEY=<generar-clave-segura>
   ARCA_ENV=produccion  # Solo si ya tenés certificados de producción
   # También acepta AFIP_ENV por compatibilidad
   ```

6. **Configurar Nginx (opcional, para HTTPS)**
   ```bash
   sudo apt install nginx certbot python3-certbot-nginx
   ```

   Archivo `/etc/nginx/sites-available/factuflow`:
   ```nginx
   server {
       listen 80;
       server_name tu-dominio.com;

       location / {
           proxy_pass http://localhost:8080;
           proxy_set_header Host $host;
           proxy_set_header X-Real-IP $remote_addr;
       }

       location /api {
           proxy_pass http://localhost:8000;
           proxy_set_header Host $host;
           proxy_set_header X-Real-IP $remote_addr;
       }
   }
   ```

   ```bash
   sudo ln -s /etc/nginx/sites-available/factuflow /etc/nginx/sites-enabled/
   sudo nginx -t
   sudo systemctl restart nginx
   sudo certbot --nginx -d tu-dominio.com
   ```

7. **Levantar FactuFlow**
   ```bash
   docker-compose up -d
   ```

8. **Configurar auto-inicio**
   ```bash
   sudo systemctl enable docker
   ```

---

## Troubleshooting

### Error: Puerto 8000 ya en uso
```bash
# Ver qué proceso está usando el puerto
sudo lsof -i :8000
# Matar el proceso
sudo kill -9 <PID>
```

### Error: Permisos en carpeta certs/
```bash
sudo chmod 700 certs/
sudo chown -R $USER:$USER certs/
```

### Error: Base de datos bloqueada (SQLite)
```bash
# Detener todos los servicios
docker-compose down
# Eliminar lock file si existe
rm data/*.db-shm data/*.db-wal
# Reiniciar
docker-compose up -d
```

### Error: "password cannot be longer than 72 bytes" al ejecutar tests
En Windows puede aparecer por incompatibilidad entre `passlib 1.7.4` y
`bcrypt >= 4`, aunque la contraseña sea corta.

Solución:
- Usar `bcrypt<4` (ya fijado en `backend/requirements.txt`).
- Si el entorno ya existía, reinstalar:

```bash
cd backend
pip install -r requirements.txt --force-reinstall
```

### Logs de errores
```bash
# Backend
docker-compose logs backend | tail -n 100

# Frontend
docker-compose logs frontend | tail -n 100
```

---

## Próximos Pasos

Después de la instalación:
1. Seguir el [Wizard de Certificados](../certificates/README.md)
2. Configurar tu empresa en la aplicación
3. Crear tu primer cliente
4. Emitir tu primera factura de prueba (en homologación)
