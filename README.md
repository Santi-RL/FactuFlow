# 🧾 FactuFlow

**Sistema de Facturación Electrónica Argentina (ARCA) - Open Source**

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)
[![Versión: 1.0.0](https://img.shields.io/badge/Versión-1.0.0-blue.svg)]()
[![Estado: Estable](https://img.shields.io/badge/Estado-Estable-brightgreen.svg)]()

---

## 📋 Descripción

FactuFlow es un sistema de facturación electrónica argentino, diseñado para ser **simple, liviano y fácil de usar**. Pensado para emprendedores, pequeñas empresas y desarrolladores que necesitan una solución self-hosted para emitir comprobantes electrónicos válidos ante ARCA (Agencia de Recaudación y Control Aduanero, anteriormente conocida como AFIP).

### ✨ Características Principales

- 🚀 **Liviano y Rápido**: Mínimo consumo de recursos, ideal para cualquier servidor
- 🏠 **Self-Hosted**: Ejecutalo en tu PC, servidor local o VPS
- 🎨 **Interfaz Moderna**: UI limpia y contemporánea
- 👥 **User-Friendly**: Diseñado para usuarios no técnicos
- 🔐 **Gestión de Certificados**: Wizard guiado para configurar certificados ARCA
- 📄 **Comprobantes**: Facturas A, B, C, Notas de Crédito y Débito
- 📊 **PDF y Reportes**: Generación de PDFs con QR ARCA y reportes de ventas/IVA
- 🐳 **Docker Ready**: Un comando para levantar todo
- 🆓 **100% Open Source**: Licencia MIT, usalo como quieras

---

## 🛠️ Stack Tecnológico

| Componente | Tecnología |
|------------|------------|
| Backend | Python 3.11+ / FastAPI |
| Frontend | Vue.js 3 / Tailwind CSS |
| Base de datos | SQLite (default) / PostgreSQL |
| Despliegue | Docker / Docker Compose |

---

## 🚀 Instalación Rápida (Docker)

```bash
# Clonar el repositorio
git clone https://github.com/Santi-RL/FactuFlow.git
cd FactuFlow

# Copiar variables de entorno
cp .env.example .env

# Levantar con Docker Compose
docker-compose up -d
```

Accede a `http://localhost:8080` y sigue el wizard de configuración inicial.

---

## 📖 Documentación

- [Índice de documentación](docs/README.md)
- [Guía de Instalación](docs/setup/README.md)
- [Configuración de Certificados ARCA](docs/certificates/README.md)
- [PDF y Reportes](docs/FASE_6_PDF_REPORTES.md)
- [Manual de Usuario](docs/user-guide/README.md)
- [API Reference](docs/api/README.md)
- [Changelog](CHANGELOG.md) 📋

---

## 🗺️ Roadmap

Consulta nuestro [ROADMAP.md](ROADMAP.md) para ver el plan de desarrollo completo.

### Estado Actual: v1.0.0 - Release Estable ✅
- [x] Estructura inicial del proyecto
- [x] Configuración de Docker
- [x] Backend completo con FastAPI
- [x] Frontend con Vue.js 3
- [x] Wizard de certificados ARCA
- [x] Emisión de comprobantes con CAE
- [x] Generación de PDFs con QR ARCA
- [x] Sistema de reportes (Ventas, IVA, Clientes)
- [x] Tests E2E con Playwright
- [x] Optimización de rendimiento (lazy loading, índices BD)
- [x] Documentación completa

---

## 🤝 Contribuir

¡Las contribuciones son bienvenidas! Por favor lee [CONTRIBUTING.md](CONTRIBUTING.md) antes de enviar un Pull Request.

---

## 📄 Licencia

Este proyecto está bajo la Licencia MIT. Ver [LICENSE](LICENSE) para más detalles.

---

## ⚠️ Disclaimer

Este software es proporcionado "tal cual", sin garantías de ningún tipo. El usuario es responsable de verificar que los comprobantes emitidos cumplan con la normativa vigente de ARCA. Los desarrolladores no se hacen responsables por errores en la facturación o problemas fiscales derivados del uso de este sistema.

---

## 💬 Soporte

- 🐛 [Reportar un Bug](https://github.com/Santi-RL/FactuFlow/issues/new?labels=bug)
- 💡 [Sugerir una Feature](https://github.com/Santi-RL/FactuFlow/issues/new?labels=enhancement)
- 📧 Contacto: [Abrir un Issue](https://github.com/Santi-RL/FactuFlow/issues)

---

<p align="center">
  Hecho con ❤️ en Argentina 🇦🇷
</p>
