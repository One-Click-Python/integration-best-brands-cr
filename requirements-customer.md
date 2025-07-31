# Requerimientos del Cliente - Sistema de Integración RMS-Shopify

## Información General del Proyecto

**Cliente**: OneClick Costa Rica  
**Proyecto**: Sistema de Integración Bidireccional RMS-Shopify  
**Versión**: 2.5.0  
**Fecha**: Enero 2025  
**Contacto técnico**: enzo@oneclick.cr  

---

## 🎯 Objetivo Principal

Desarrollar un sistema completo de integración bidireccional entre Microsoft Retail Management System (RMS) y Shopify para automatizar la sincronización de productos, inventarios, precios y pedidos, eliminando la gestión manual y asegurando coherencia de datos en tiempo real.

---

## 📋 Requerimientos Funcionales Principales

### 1. Integración RMS → Shopify (Productos y Inventario)

#### 1.1 Extracción de Datos RMS
- ✅ **Lectura de vista personalizada View_Items** con conexión optimizada a SQL Server
- ✅ **Extracción de información básica**:
  - SKU único (C_ARTICULO)
  - Nombre del producto (Description)
  - Categoría y familia de productos
  - Color y talla del producto
  - Código CCOD para agrupación de variantes

- ✅ **Extracción de información de precios**:
  - Precio base (Price)
  - Precio promocional (SalePrice)
  - Fechas de promoción (SaleStartDate, SaleEndDate)
  - Cálculo automático de porcentajes de descuento

- ✅ **Extracción de información de inventario**:
  - Cantidad disponible total (Quantity)
  - Stock por ubicación (Exis00, Exis57)
  - Gestión de productos sin inventario

- ✅ **Extracción de información fiscal y adicional**:
  - Impuestos aplicables (Tax)
  - Género/audiencia objetivo
  - Categoría extendida para filtros
  - Metadatos personalizados RMS

#### 1.2 Sincronización con Shopify
- ✅ **Creación y actualización automática de productos**:
  - Publicación controlada (productos inactivos hasta completar información)
  - Estado dinámico basado en inventario disponible
  - Manejo de productos archivados y eliminados

- ✅ **Mapeo inteligente de variantes por color y talla**:
  - Agrupación automática por código CCOD
  - Creación de opciones (Color, Talla) dinámicas
  - Normalización de tallas (23½ → 23.5)
  - Validación de consistencia entre variantes

- ✅ **Motor de sincronización automática**:
  - Detección de cambios usando `Item.LastUpdated`
  - Verificación automática cada 5 minutos (configurable)
  - Procesamiento por lotes optimizado
  - Sistema de bloqueo para prevenir concurrencia

- ✅ **Sistema de conciliación avanzado**:
  - Prevención de duplicados por SKU
  - Detección de productos huérfanos
  - Reconciliación de metadatos
  - Validación de integridad de datos

#### 1.3 Características Avanzadas
- ✅ **Taxonomía estándar de Shopify**: Mapeo automático a categorías oficiales
- ✅ **Metafields estructurados**: Preservación completa de datos RMS
- ✅ **Gestión automática de descuentos**: Creación de ofertas basadas en SalePrice
- ✅ **Soporte multi-ubicación**: Gestión de inventario en múltiples bodegas

### 2. Integración Shopify → RMS (Pedidos)

#### 2.1 Captura de Pedidos de Shopify
- ✅ **Sistema de webhooks en tiempo real**:
  - Configuración automática de webhooks necesarios
  - Validación HMAC para seguridad
  - Procesamiento asíncrono en background
  - Manejo de reintentos automáticos

- ✅ **Captura de datos de cabecera (tabla ORDER)**:
  - Información del cliente (ID, email, nombre)
  - Fecha y hora del pedido
  - Total del pedido incluyendo impuestos
  - Información de envío y facturación
  - Método de pago utilizado

- ✅ **Captura de datos de detalle (tabla ORDERENTRY)**:
  - Productos ordenados con SKU válido
  - Cantidades solicitadas
  - Precios unitarios (con y sin descuento)
  - Descripción detallada del producto
  - Información de impuestos por línea

#### 2.2 Validaciones y Controles
- ✅ **Validación de existencias**: Verificación de productos en RMS antes de procesar
- ✅ **Control de estados financieros**: Solo pedidos pagados, autorizados o parcialmente pagados
- ✅ **Mapeo SKU → ItemID**: Resolución automática de productos RMS
- ✅ **Control de duplicados**: Prevención de inserción duplicada por ID Shopify
- ✅ **Gestión de excepciones**: Rollback automático en caso de errores

#### 2.3 Soporte para Pedidos de Invitados
- ✅ **Configuración flexible para checkout sin registro**:
  - Opción de permitir/rechazar pedidos sin cliente
  - Cliente por defecto configurable para invitados
  - Creación automática de registros de cliente
  - Manejo de emails temporales para invitados

### 3. Automatización y Programación

#### 3.1 Motor de Sincronización Automática
- ✅ **Detección automática de cambios**:
  - Consulta periódica a `Item.LastUpdated` cada 5 minutos
  - Vinculación inteligente entre `Item` y `View_Items`
  - Procesamiento por lotes para eficiencia
  - Rate limiting automático para APIs

- ✅ **Health monitoring y auto-recovery**:
  - Verificación del estado del motor cada 5 minutos
  - Reinicio automático en caso de fallos
  - Alertas automáticas por email/Slack
  - Métricas en tiempo real del sistema

- ✅ **APIs de control y monitoreo**:
  - Estado general del sistema
  - Estadísticas detalladas de sincronización
  - Trigger manual de sincronización
  - Configuración dinámica de intervalos

#### 3.2 Sincronización Programada
- ✅ **Intervalos personalizables**: Configuración desde 1 minuto hasta 24 horas
- ✅ **API para ejecución manual**: Triggers bajo demanda con filtros específicos
- ✅ **Sincronización por categorías**: Filtros por familia, categoría o CCOD
- ✅ **Modo dry-run**: Validación sin realizar cambios reales

### 4. Gestión Avanzada de Errores

#### 4.1 Sistema de Captura y Notificación
- ✅ **Logging estructurado**: Registros detallados en formato JSON
- ✅ **Categorización de errores**: Separación por severidad y tipo
- ✅ **Alertas configurables**: Email, Slack, webhook personalizado
- ✅ **Dashboard de errores**: Interface web para revisión

#### 4.2 Recuperación Automática
- ✅ **Reintentos inteligentes**: Backoff exponencial para fallos transitorios
- ✅ **Circuit breaker**: Pausa automática ante múltiples fallos
- ✅ **Auto-recovery**: Reanudación automática del servicio
- ✅ **Rollback automático**: Reversión de transacciones fallidas

---

## 🏗️ Arquitectura del Sistema

### Componentes Principales

#### 1. Microservicios de Sincronización
- **RMSToShopifySync**: Servicio de sincronización RMS → Shopify
- **ShopifyToRMSSync**: Servicio de sincronización Shopify → RMS
- **ChangeDetector**: Motor de detección automática de cambios
- **WebhookHandler**: Procesamiento de eventos de Shopify

#### 2. Módulo de Administración y Monitoreo
- **SyncMonitor**: Sistema de health checks y métricas
- **API Dashboard**: Endpoints de control y estadísticas
- **AlertManager**: Sistema de notificaciones automáticas
- **ConfigManager**: Gestión centralizada de configuración

#### 3. Servicios de Soporte
- **DataMapper**: Transformación y mapeo de datos
- **TaxonomyMapper**: Resolución de categorías Shopify
- **LockManager**: Sistema de bloqueo distribuido
- **CacheManager**: Sistema de cache con Redis

---

## 🔧 Requerimientos Técnicos

### Stack Tecnológico
- ✅ **Backend**: Python 3.13+ con FastAPI
- ✅ **Base de datos**: SQL Server (RMS) + Redis (cache)
- ✅ **APIs**: REST + GraphQL (Shopify)
- ✅ **Contenedores**: Docker + Docker Compose
- ✅ **Monitoreo**: Logging estructurado + métricas

### Conectividad
- ✅ **RMS Database**: Conexión SQL Server con ODBC Driver 17
- ✅ **Shopify API**: GraphQL API 2025-04 con autenticación
- ✅ **Redis**: Sistema de cache y locks distribuidos
- ✅ **Webhooks**: Endpoints HTTPS con validación HMAC

### Performance y Escalabilidad
- ✅ **Connection pooling**: Hasta 20 conexiones simultáneas
- ✅ **Rate limiting**: Respeto a límites de API (2 req/seg Shopify)
- ✅ **Procesamiento por lotes**: 10-20 productos por lote
- ✅ **Cache inteligente**: TTL configurable por tipo de dato

---

## 📊 Métricas y KPIs

### Métricas de Sincronización
- **Productos sincronizados por hora/día**
- **Tasa de éxito de sincronización (%)**
- **Tiempo promedio de procesamiento**
- **Pedidos procesados automáticamente**
- **Errores por tipo y frecuencia**

### Métricas de Sistema
- **Uptime del motor automático**
- **Uso de recursos (CPU, memoria)**
- **Latencia de APIs (RMS, Shopify)**
- **Estado de conexiones de base de datos**
- **Performance de cache (hit rate)**

---

## 🔐 Requerimientos de Seguridad

### Autenticación y Autorización
- ✅ **Tokens seguros**: Shopify access tokens con scopes limitados
- ✅ **Validación HMAC**: Webhooks con firmas criptográficas
- ✅ **Conexiones seguras**: TLS/SSL para todas las comunicaciones
- ✅ **Secrets management**: Variables de entorno seguras

### Protección de Datos
- ✅ **Sanitización**: Limpieza de datos antes de inserción
- ✅ **Logging seguro**: No exposición de información sensible
- ✅ **Rate limiting**: Protección contra ataques DDoS
- ✅ **Rollback seguro**: Reversión completa ante errores

---

## 🚀 Instalación y Deployment

### Instalación Local
- ✅ **Poetry**: Gestión de dependencias Python
- ✅ **Docker**: Containerización completa
- ✅ **Scripts automatizados**: Setup de base de datos y configuración

### Instalación Windows Service
- ✅ **Scripts PowerShell**: Instalación automatizada
- ✅ **NSSM**: Gestión como servicio Windows
- ✅ **Task Scheduler**: Monitoreo y mantenimiento
- ✅ **Event Viewer**: Integración con logs Windows

### Deployment en Producción
- ✅ **Docker Compose**: Orquestación de servicios
- ✅ **Environment configs**: Configuración por entorno
- ✅ **Health checks**: Verificación automática de servicios
- ✅ **Backup automatizado**: Respaldo de configuración

---

## ✅ Estado de Implementación

### Completado (v2.5.0)
- ✅ **Integración RMS → Shopify**: 100% implementada
- ✅ **Integración Shopify → RMS**: 100% implementada  
- ✅ **Motor automático**: Funcionando con detección de cambios
- ✅ **Sistema de webhooks**: Configuración y procesamiento completo
- ✅ **Soporte pedidos invitados**: Configuración flexible
- ✅ **Docker deployment**: Completo con docker-compose
- ✅ **Windows Service**: Scripts PowerShell automatizados
- ✅ **APIs de monitoreo**: 8+ endpoints de control
- ✅ **Documentación**: Guías completas para todas las funcionalidades

### Próximas Mejoras (v2.6+)
- 🔄 **Sincronización de imágenes**: Upload automático desde URLs RMS
- 🔄 **Multi-tenant**: Soporte para múltiples tiendas Shopify
- 🔄 **Dashboard web**: Interface gráfica de administración
- 🔄 **Machine Learning**: IA para categorización automática
- 🔄 **WebSockets**: Actualizaciones en tiempo real

---

## 📞 Soporte y Contacto

**Desarrollador Principal**: Enzo Candotti  
**Email**: enzo@oneclick.cr  
**Empresa**: OneClick Costa Rica  
**Documentación técnica**: http://localhost:8080/docs  
**Repositorio**: Sistema privado de OneClick CR  

**Horario de soporte**: Lunes a Viernes, 8:00 AM - 6:00 PM (GMT-6)  
**SLA de respuesta**: < 4 horas para issues críticos  
**Actualizaciones**: Releases mensuales con mejoras y correcciones  

---

*Documento actualizado: 30 de Enero 2025*  
*Versión del sistema: 2.5.0*  
*Estado: Sistema en producción estable*