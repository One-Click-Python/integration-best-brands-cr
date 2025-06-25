# Changelog

Todas las modificaciones notables a este proyecto serán documentadas en este archivo.

El formato está basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.0.0/), y este proyecto adhiere a [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Sin versionar] - 2025-06-24

### Arreglado
- 🐛 Mejorado el manejo de sesiones HTTP de aiohttp para evitar warnings de sesiones no cerradas
- 🔧 Agregado logging detallado para debugging de inicialización de sesiones Shopify
- 🔄 Mejorado el método close() del cliente GraphQL para verificar estado de sesión antes de cerrar

## [Sin versionar] - 2025-06-23

### Agregado
- ✨ Sistema de pruebas completo para conexiones de base de datos y Shopify
- 📋 Scripts de testing automatizado (`test_connection_simple.py`, `test_db_sync.py`)
- 🔧 Archivo de configuración de proyecto CLAUDE.md con comandos de desarrollo
- 📊 Verificación de health check para todos los servicios
- 🔍 Validación de conectividad con 556,649 productos en RMS View_Items
- ✅ Confirmación de acceso a 113,330 órdenes en tabla RMS Order

### Cambiado
- 🔄 Puerto de aplicación cambiado de 8000 a 8080 en toda la configuración
- 🛠️ Driver ODBC actualizado de "Driver 18" a "Driver 17 for SQL Server"
- 📝 Documentación actualizada con nuevos puertos en README.md y CLAUDE.md
- ⚙️ Configuración por defecto de puerto en config.py actualizada

### Arreglado
- 🐛 Error de binding de parámetros en verificación de tabla Order de RMS
- 🔧 Problema de duplicación de query SQL en rms_handler.py líneas 82-88
- 📡 Configuración de driver ODBC compatible con sistema macOS
- 🔗 Enlaces de documentación API actualizados a puerto 8080

### Verificado
- ✅ Conexión exitosa a base de datos RMS (latencia: ~1.6s)
- ✅ Conexión exitosa a Shopify API (latencia: ~1.3s) 
- ✅ Autenticación con token de acceso Shopify funcional
- ✅ Endpoints de health check operativos
- ✅ Endpoints de sincronización RMS-to-Shopify respondiendo correctamente
- ✅ Sistema de logging y métricas funcionando

### Técnico
- 🏗️ Arquitectura de conexión singleton para base de datos implementada
- 📊 Pool de conexiones SQL Server configurado (max: 10 conexiones)
- 🔄 Sistema de retry handler para APIs externas operativo
- 🎯 Background tasks para sincronización asíncrona configurados
- 📈 Sistema de métricas y monitoreo inicializado

## [0.1.0] - 2025-06-15

### Agregado
- ✨ Implementación inicial del sistema de integración RMS-Shopify
- 🔄 Sincronización bidireccional básica entre RMS y Shopify
- 📡 Sistema de webhooks para captura de eventos Shopify
- 📊 Sistema completo de logging estructurado y monitoreo
- 🐛 Manejo robusto de errores con reintentos automáticos
- 🏗️ Arquitectura modular con servicios independientes
- ⚙️ Configuración centralizada con variables de entorno
- 🔐 Sistema de autenticación para APIs
- 📈 Métricas y KPIs de sincronización
- 🐳 Soporte para Docker y contenedores

### Configuración Inicial
- 🛠️ FastAPI como framework web principal
- 🗄️ SQLAlchemy para manejo de base de datos SQL Server
- 🔄 Sistema de tareas asíncronas con Celery + Redis
- 📋 Validación de datos con Pydantic
- 🧪 Suite de testing con pytest
- 📚 Documentación automática con Swagger/OpenAPI

---

**Leyenda de Símbolos:**
- ✨ Nuevas características
- 🔄 Cambios en funcionalidad existente  
- 🐛 Corrección de errores
- 🔧 Mejoras técnicas
- 📊 Métricas y monitoreo
- 🛠️ Herramientas y configuración
- 📝 Documentación
- 🔐 Seguridad
- 🧪 Testing
- 🐳 DevOps
- ✅ Verificaciones
- 🏗️ Arquitectura