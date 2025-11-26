# Guía de Usuario - Dashboard de Monitoreo

## Tabla de Contenido

1. [Introducción](#1-introducción)
2. [Acceso y Navegación](#2-acceso-y-navegación)
3. [Página Principal (Home)](#3-página-principal-home)
4. [Gestión de Sincronización](#4-gestión-de-sincronización)
5. [Gestión de Pedidos](#5-gestión-de-pedidos)
6. [Monitor del Sistema](#6-monitor-del-sistema)
7. [Logs del Sistema](#7-logs-del-sistema)
8. [Operaciones Comunes](#8-operaciones-comunes)
9. [Solución de Problemas](#9-solución-de-problemas)
10. [Referencia Rápida](#10-referencia-rápida)

---

## 1. Introducción

### ¿Qué es el Dashboard?

El Dashboard de Monitoreo es una interfaz web que permite visualizar y controlar el sistema de integración RMS-Shopify. Desde aquí puede:

- **Monitorear** el estado de salud del sistema en tiempo real
- **Controlar** las sincronizaciones de productos e inventario
- **Gestionar** el polling de pedidos desde Shopify
- **Visualizar** métricas de rendimiento y recursos
- **Revisar** logs y errores del sistema

### Requisitos

- El servidor API debe estar ejecutándose (`http://localhost:8080`)
- Conexión de red estable
- Navegador web moderno (Chrome, Firefox, Safari, Edge)

### ¿Quién debería usar este Dashboard?

- **Operadores**: Monitoreo diario y control de sincronizaciones
- **Supervisores**: Revisión de métricas y estadísticas
- **Soporte Técnico**: Diagnóstico de problemas y revisión de logs

---

## 2. Acceso y Navegación

### Cómo Acceder

1. Abra su navegador web
2. Vaya a: **http://localhost:8501**
3. El Dashboard cargará automáticamente la página principal

### Estructura de Navegación

El Dashboard tiene una **barra lateral izquierda** con las siguientes páginas:

| Ícono | Página | Propósito |
|-------|--------|-----------|
| 🛍️ | **Home** | Vista general del sistema |
| 🔄 | **Sync Management** | Control de sincronizaciones |
| 📦 | **Orders** | Gestión de pedidos |
| 🖥️ | **System Monitor** | Monitoreo de recursos |
| 📝 | **Logs** | Visualización de logs |

### Barra Lateral (Sidebar)

En la barra lateral encontrará:

#### ⚙️ Configuraciones

- **Auto-Refresh**: Configure la frecuencia de actualización automática
  - `5s` - Cada 5 segundos (uso intensivo)
  - `10s` - Cada 10 segundos
  - `30s` - Cada 30 segundos (recomendado)
  - `1min` - Cada minuto
  - `5min` - Cada 5 minutos
  - `Deshabilitado` - Sin actualización automática

- **🔄 Actualizar Ahora**: Botón para forzar actualización inmediata

#### 🔗 Conexión API

Muestra la información de conexión:
- **Base URL**: Dirección del servidor API
- **Timeout**: Tiempo máximo de espera

#### 🕐 Última Actualización

Indica cuándo se actualizaron los datos por última vez.

---

## 3. Página Principal (Home)

La página principal ofrece una **vista completa del estado del sistema** en un solo lugar.

### 🏥 Estado del Sistema

#### Indicadores de Conexión

Tres indicadores visuales muestran el estado de cada servicio:

| Servicio | Descripción | ¿Qué significa si está verde? |
|----------|-------------|-------------------------------|
| **RMS** | Base de datos de Microsoft RMS | La conexión a la base de datos está funcionando |
| **Shopify** | API de Shopify | La comunicación con Shopify está activa |
| **Redis** | Caché y estado | El sistema de caché está operativo |

**Interpretación de colores:**

| Color | Estado | Significado |
|-------|--------|-------------|
| 🟢 Verde | Healthy | Servicio funcionando correctamente |
| 🔴 Rojo | Unhealthy | Servicio con problemas o desconectado |
| 🟡 Amarillo | Warning | Servicio degradado o con latencia alta |
| ⚪ Blanco | Unknown | Estado desconocido |

#### Latencia

Cada servicio muestra su **latencia en milisegundos (ms)**:
- **< 100ms**: Excelente
- **100-500ms**: Normal
- **> 500ms**: Lento (puede indicar problemas)

#### ⏱️ Uptime del Sistema

Muestra cuánto tiempo ha estado ejecutándose el servidor sin interrupciones.
- Ejemplo: "2 días, 5 horas, 30 minutos"

### 📊 Métricas de Sincronización

#### Sincronización RMS → Shopify

| Métrica | Descripción | ¿Qué debo buscar? |
|---------|-------------|-------------------|
| **Total Sincronizado** | Productos procesados en total | Número creciente es normal |
| **Tasa de Éxito** | Porcentaje de éxito | Debe ser ≥95% |
| **Última Sincronización** | Cuándo fue la última | Menos de 10 minutos es normal |
| **Estado** | Activo/Inactivo | Debe estar Activo |

**Interpretación de la Tasa de Éxito:**
- **≥95%**: 🟢 Excelente - Sistema funcionando correctamente
- **90-95%**: 🟡 Advertencia - Revisar errores
- **<90%**: 🔴 Crítico - Requiere atención inmediata

### 📦 Métricas de Polling de Pedidos

| Métrica | Descripción |
|---------|-------------|
| **Total Consultado** | Pedidos revisados desde Shopify |
| **Ya Sincronizados** | Pedidos que ya existían en RMS |
| **Nuevos** | Pedidos nuevos creados en RMS |
| **Actualizados** | Pedidos existentes que fueron actualizados |
| **Errores** | Pedidos con errores de sincronización |

### 🔁 Estado de Sincronización Reversa

La sincronización reversa actualiza el inventario de Shopify basándose en RMS.

| Campo | Descripción |
|-------|-------------|
| **Habilitado** | Si la función está activa |
| **Retraso** | Minutos de espera después de la sync principal |
| **Estado** | Esperando, Listo, o Bloqueado |

### 🖥️ Recursos del Sistema

Muestra el uso actual de recursos:

| Recurso | Umbral Normal | Advertencia | Crítico |
|---------|---------------|-------------|---------|
| **CPU** | <70% | 70-90% | >90% |
| **Memoria** | <75% | 75-90% | >90% |
| **Disco** | <80% | 80-95% | >95% |

### Acciones Rápidas

Tres botones para operaciones comunes:

1. **🔄 Reiniciar Métricas**: Limpia los contadores de estadísticas
2. **🔧 Reiniciar Circuit Breakers**: Restablece protecciones de circuito
3. **🔄 Recargar Página**: Actualiza los datos mostrados

---

## 4. Gestión de Sincronización

Esta página permite **controlar manualmente** las sincronizaciones.

### 🎮 Controles Manuales

#### Tipos de Sincronización

| Botón | Tipo | ¿Cuándo usarlo? |
|-------|------|-----------------|
| **🔄 Sincronización Incremental** | Solo cambios | Uso diario normal, sincroniza solo items modificados |
| **🔄 Sincronización Completa** | Todo | Cuando hay inconsistencias o después de problemas |
| **🔁 Sincronización Reversa** | Shopify → RMS | Verificar inventario cuando hay discrepancias |

**Advertencia**: La sincronización completa puede tardar varios minutos y consume más recursos. Úsela solo cuando sea necesario.

### ⏱️ Configuración de Intervalo

Permite ajustar cada cuántos minutos se ejecuta la sincronización automática:

- **Rango**: 1 a 60 minutos
- **Valor recomendado**: 5-15 minutos
- **Slider**: Deslice para ajustar el valor
- **Botón "Actualizar Intervalo"**: Guarda el cambio

**Ejemplo de uso:**
1. Deslice el slider a 10 minutos
2. Haga clic en "💾 Actualizar Intervalo"
3. Verá confirmación "✅ Intervalo actualizado para 10 minutos!"

### 📍 Gestión de Checkpoints

Los checkpoints son **puntos de guardado** que permiten reanudar sincronizaciones interrumpidas.

#### ¿Qué muestra cada checkpoint?

| Campo | Descripción |
|-------|-------------|
| **ID** | Identificador único (ej: sync_20250123_153000) |
| **Estado** | pending, in_progress, completed |
| **Progreso** | Items procesados / Total (ej: 150/250) |
| **Barra de progreso** | Indicador visual del avance |

#### Acciones disponibles

- **▶️ Reanudar**: Continúa una sincronización interrumpida
- **🗑️ Excluir**: Elimina el checkpoint (para empezar de cero)

**Cuándo usar "Reanudar":**
- Después de un reinicio del sistema
- Si la sincronización se detuvo por un error temporal
- Para continuar donde quedó

**Cuándo usar "Excluir":**
- Si el checkpoint está corrupto
- Para forzar una sincronización desde cero
- Si hay problemas recurrentes con ese checkpoint

### 📚 Sincronización de Colecciones

**Nota**: Requiere `SYNC_ENABLE_COLLECTIONS=true` en la configuración.

| Opción | Descripción |
|--------|-------------|
| **Colecciones principales** | Sincroniza familias (Zapatos, Ropa, etc.) |
| **Subcategorías** | Sincroniza subcategorías (Tenis, Botas, etc.) |
| **Dry-run** | Simula sin hacer cambios reales |

### 📊 Estado Actual de Sincronización

Muestra información en tiempo real:

| Métrica | Significado |
|---------|-------------|
| **Monitoreo** | Si el sistema está activo monitoreando cambios |
| **Detección de Cambios** | Si detecta automáticamente items modificados |
| **Intervalo** | Minutos entre cada verificación |

#### Estadísticas del Detector de Cambios

| Estadística | Descripción |
|-------------|-------------|
| **Total de Verificaciones** | Cuántas veces ha buscado cambios |
| **Cambios Detectados** | Cuántos items modificados encontró |
| **Items Sincronizados** | Cuántos items actualizó en Shopify |
| **Última Verificación** | Hace cuánto tiempo revisó por última vez |

---

## 5. Gestión de Pedidos

Esta página muestra el **estado del polling de pedidos** desde Shopify hacia RMS.

### 🎮 Controles de Polling

| Botón | Función | Resultado |
|-------|---------|-----------|
| **📦 Polling Manual** | Ejecuta polling inmediatamente | Sincroniza pedidos ahora |
| **🧪 Dry-Run Polling** | Simula sin hacer cambios | Muestra qué se sincronizaría |
| **🔄 Reiniciar Estadísticas** | Limpia contadores | Estadísticas vuelven a cero |

**Cuándo usar cada uno:**

- **Polling Manual**: Cuando necesita los pedidos más recientes inmediatamente
- **Dry-Run**: Para verificar qué pedidos se sincronizarían sin afectar el sistema
- **Reiniciar Estadísticas**: Al inicio de un nuevo período de monitoreo

### 📊 Configuración del Polling

| Parámetro | Descripción | Valor típico |
|-----------|-------------|--------------|
| **Estado** | Habilitado/Deshabilitado | Habilitado |
| **Intervalo** | Minutos entre polling | 10 min |
| **Ventana de Consulta** | Minutos hacia atrás para buscar | 15 min |
| **Tamaño del Lote** | Pedidos por página | 50 |

### 📈 Estadísticas de Sincronización

#### Métricas Principales

| Métrica | Ícono | Descripción |
|---------|-------|-------------|
| **Total Consultado** | 📊 | Pedidos revisados desde Shopify |
| **Ya Sincronizados** | ✓ | Pedidos que ya existían en RMS |
| **Nuevos** | + | Pedidos recién creados en RMS |
| **Actualizados** | ↻ | Pedidos existentes actualizados |
| **Errores** | ⚠️ | Pedidos con errores |

#### Gráfico Gauge: Tasa de Éxito

El gráfico circular muestra la tasa de éxito:

| Rango | Color | Significado |
|-------|-------|-------------|
| 95-100% | 🟢 Verde | Excelente |
| 90-95% | 🟡 Amarillo | Aceptable |
| 0-90% | 🔴 Rojo | Requiere atención |

La línea roja en 95% indica el **umbral objetivo**.

#### Gráfico de Barras: Comparación

Muestra visualmente la distribución de pedidos:
- **Azul**: Total consultado
- **Verde**: Nuevos sincronizados
- **Morado**: Ya sincronizados
- **Rojo**: Errores

### ⏱️ Información de Tiempo

| Campo | Descripción |
|-------|-------------|
| **Última Consulta** | Hace cuánto fue el último polling |
| **Próximo Ciclo** | Si se ejecutará en el próximo intervalo |
| **Tiempo hasta el Próximo Poll** | Segundos restantes |

### ⚙️ Configuración Avanzada

Expanda esta sección para modificar:

1. **Intervalo (minutos)**: 1-60 minutos
2. **Ventana de Consulta (minutos)**: 5-120 minutos

**Recomendación**: La ventana de consulta debe ser mayor que el intervalo para evitar pedidos perdidos.

---

## 6. Monitor del Sistema

Página dedicada al **monitoreo detallado de recursos y rendimiento**.

### 🏥 Estado Detallado de Salud

#### Indicador General

- **✅ Sistema Operando Normalmente**: Todo funciona correctamente
- **❌ Sistema con Problemas**: Algún servicio tiene fallas

#### Uptime del Sistema

Muestra:
- Tiempo total de ejecución (ej: "5 días, 12 horas")
- Cuándo se inició el sistema

#### Grid de Servicios

Cada servicio muestra:
- **Nombre**: RMS, SHOPIFY, REDIS
- **Estado**: Healthy/Unhealthy
- **Latencia**: Tiempo de respuesta en ms
- **Error** (si aplica): Descripción del problema

### 📊 Métricas de Performance

#### Gráfico de Barras: Uso de Recursos

Muestra tres barras horizontales:

| Recurso | Color Verde | Color Amarillo | Color Rojo |
|---------|-------------|----------------|------------|
| **CPU** | <70% | 70-90% | >90% |
| **Memoria** | <70% | 70-90% | >90% |
| **Disco** | <70% | 70-90% | >90% |

#### 💾 Detalles de Recursos

**CPU:**
- Uso actual en porcentaje

**Memoria:**
- Uso actual en porcentaje
- Total disponible (ej: 16 GB)
- Usado actualmente
- Disponible

**Disco:**
- Uso actual en porcentaje
- Total
- Usado
- Libre

### 📈 Métricas Adicionales

Tres pestañas con información especializada:

#### 🔄 Retry Handler

Muestra estadísticas de reintentos automáticos:
- **Total de Tentativas**: Cuántos reintentos se han hecho
- **Éxitos**: Reintentos exitosos
- **Fallas**: Reintentos fallidos
- **Tasa de Éxito**: Porcentaje de éxito

#### 📡 Webhooks

Estadísticas de webhooks de Shopify:
- **Webhooks Procesados**: Total recibidos
- **Éxitos**: Procesados correctamente
- **Fallas**: Con errores

#### 📦 Inventory

Actualizaciones de inventario:
- **Actualizaciones Totales**: Total de cambios
- **Éxitos**: Actualizaciones exitosas
- **Fallas**: Actualizaciones fallidas

### 🗄️ Salud de la Base de Datos

Sección expandible (requiere modo DEBUG):
- **Pool Size**: Tamaño del pool de conexiones
- **Conexiones Activas**: En uso actualmente
- **Conexiones Ociosas**: Disponibles

---

## 7. Logs del Sistema

**Importante**: Esta página requiere `DEBUG=true` en la configuración.

### 📊 Estadísticas de Logs

| Métrica | Descripción |
|---------|-------------|
| **Total de Registros** | Cantidad total de logs |
| **Errores** | Logs de nivel ERROR |
| **Avisos** | Logs de nivel WARNING |
| **Info** | Logs de nivel INFO |

### Gráfico: Distribución por Nivel

Gráfico de barras mostrando la cantidad de logs por nivel:
- **Rojo**: ERROR
- **Amarillo**: WARNING
- **Azul**: INFO

### ❌ Errores Recientes

Lista de los últimos 10 errores, cada uno expandible:

| Campo | Descripción |
|-------|-------------|
| **Timestamp** | Fecha y hora del error |
| **Level** | Nivel (ERROR) |
| **Source** | Módulo que generó el error |
| **Message** | Descripción del error |
| **Stacktrace** | Traza de la pila (si está disponible) |

### 🔍 Buscar y Filtrar Logs

Formulario de búsqueda con:

| Campo | Opciones | Uso |
|-------|----------|-----|
| **Nivel** | ALL, INFO, WARNING, ERROR | Filtrar por severidad |
| **Buscar en mensaje** | Texto libre | Buscar términos específicos |
| **Límite de resultados** | 10-500 | Cantidad máxima a mostrar |

**Ejemplo de búsqueda:**
1. Seleccione "ERROR" en Nivel
2. Escriba "Shopify" en Buscar
3. Establezca límite en 100
4. Haga clic en "🔍 Buscar"

#### Resultados de Búsqueda

Los resultados se muestran en una tabla con:
- Timestamp
- Level
- Source
- Message

**Descargar resultados:**
- Botón "📥 Descargar como CSV" para exportar los resultados

### 📜 Logs Recientes

Muestra los últimos 50 logs en orden cronológico inverso (más recientes primero).

**Código de colores:**
- 🔴 Rojo: ERROR
- 🟡 Amarillo: WARNING
- 🔵 Azul: INFO

---

## 8. Operaciones Comunes

### Forzar una Sincronización Inmediata

**Escenario**: Necesita sincronizar productos inmediatamente.

1. Vaya a **Sync Management**
2. En "Controles Manuales", haga clic en:
   - **🔄 Sincronización Incremental** (solo cambios)
   - **🔄 Sincronización Completa** (todo)
3. Espere la confirmación
4. Verifique el resultado en el mensaje

### Verificar si Algo Falló

**Escenario**: Sospecha que hay problemas.

1. Vaya a **Home** → Revise los indicadores de salud
2. Si alguno está 🔴, vaya a **System Monitor** para detalles
3. Revise **Logs** → "Errores Recientes" para más información

### Sincronizar Pedidos Manualmente

**Escenario**: Necesita los pedidos más recientes de Shopify.

1. Vaya a **Orders**
2. Haga clic en "📦 Polling Manual"
3. Revise el resultado:
   - Total consultado
   - Nuevos sincronizados
   - Errores (si hay)

### Ajustar la Frecuencia de Sincronización

**Escenario**: La sincronización es muy frecuente o poco frecuente.

1. Vaya a **Sync Management**
2. En "Configuración de Intervalo":
   - Use el slider para ajustar (1-60 minutos)
   - Haga clic en "💾 Actualizar Intervalo"
3. Verifique la confirmación

### Exportar Logs para Análisis

**Escenario**: Necesita compartir logs con soporte técnico.

1. Vaya a **Logs** (requiere DEBUG=true)
2. Use el formulario de búsqueda
3. Haga clic en "🔍 Buscar"
4. Haga clic en "📥 Descargar como CSV"
5. El archivo se descargará automáticamente

### Reanudar una Sincronización Interrumpida

**Escenario**: La sincronización se detuvo a mitad del proceso.

1. Vaya a **Sync Management**
2. Busque el checkpoint en "Gestión de Checkpoints"
3. Haga clic en "▶️ Reanudar" junto al checkpoint
4. La sincronización continuará desde donde quedó

### Verificar el Uso de Recursos

**Escenario**: El sistema parece lento.

1. Vaya a **System Monitor**
2. Revise el gráfico de "Uso de Recursos"
3. Si alguna barra está en 🔴 rojo:
   - **CPU alto**: Puede haber procesos pesados ejecutándose
   - **Memoria alta**: Puede necesitar reiniciar el servidor
   - **Disco alto**: Necesita liberar espacio

---

## 9. Solución de Problemas

### El Dashboard no carga

**Síntomas**: Página en blanco o error de conexión.

**Soluciones:**
1. Verifique que el Dashboard está ejecutando:
   ```bash
   poetry run streamlit run dashboard/main.py
   ```
2. Verifique la URL: `http://localhost:8501`
3. Revise si el puerto 8501 está disponible
4. Intente acceder desde otro navegador

### "Error al cargar dashboard"

**Síntomas**: Mensaje de error en la página principal.

**Soluciones:**
1. Verifique que la API está ejecutando:
   ```bash
   curl http://localhost:8080/health
   ```
2. Revise la configuración `DASHBOARD_API_URL` en `.env`
3. Haga clic en "🔄 Intentar Nuevamente"

### Los datos no se actualizan

**Síntomas**: Los datos parecen estáticos.

**Soluciones:**
1. Verifique el intervalo de auto-refresh (sidebar)
2. Haga clic en "🔄 Actualizar Ahora" en la sidebar
3. Si persiste, revise la conexión con la API
4. Limpie la caché del navegador

### Los indicadores de salud están en rojo

**Síntomas**: 🔴 RMS, Shopify, o Redis están rojos.

**Para RMS:**
1. Verifique la conexión a SQL Server
2. Revise las credenciales en `.env`
3. Confirme que la base de datos está accesible

**Para Shopify:**
1. Verifique el token de acceso
2. Revise si la tienda está activa
3. Confirme que la versión de API es correcta

**Para Redis:**
1. Verifique que Redis está ejecutando
2. Revise `REDIS_URL` en `.env`
3. Intente `redis-cli ping` desde la terminal

### La página de Logs dice "DEBUG mode required"

**Síntomas**: No puede ver los logs.

**Solución:**
1. Edite el archivo `.env`
2. Agregue o modifique: `DEBUG=true`
3. Reinicie la aplicación API
4. Recargue el Dashboard

### La sincronización está bloqueada

**Síntomas**: El estado muestra "Bloqueado" o no avanza.

**Soluciones:**
1. Vaya a **Sync Management**
2. Revise los checkpoints activos
3. Si hay un checkpoint corrupto:
   - Haga clic en "🗑️ Excluir"
   - Intente una nueva sincronización
4. Reinicie los circuit breakers en la página Home

### Tasa de éxito muy baja

**Síntomas**: La tasa de éxito está por debajo del 90%.

**Pasos de diagnóstico:**
1. Revise los errores recientes en **Logs**
2. Verifique la conexión con Shopify
3. Revise si hay productos con datos inválidos
4. Considere ejecutar una sincronización completa

---

## 10. Referencia Rápida

### Colores e Indicadores

| Elemento | Color | Significado |
|----------|-------|-------------|
| Servicio | 🟢 Verde | Funcionando correctamente |
| Servicio | 🔴 Rojo | Con problemas |
| Servicio | 🟡 Amarillo | Advertencia o degradado |
| Servicio | ⚪ Blanco | Estado desconocido |
| Recurso | Verde | Uso normal (<70%) |
| Recurso | Amarillo | Uso alto (70-90%) |
| Recurso | Rojo | Uso crítico (>90%) |
| Éxito | ≥95% | Excelente |
| Éxito | 90-95% | Aceptable |
| Éxito | <90% | Requiere atención |

### Íconos Comunes

| Ícono | Significado |
|-------|-------------|
| ✅ | Éxito / Completado |
| ❌ | Error / Falla |
| ⚠️ | Advertencia |
| ℹ️ | Información |
| 🔄 | Actualizar / En progreso |
| ⏳ | Pendiente / Esperando |
| 🎮 | Controles manuales |
| 📊 | Métricas / Estadísticas |
| ⏱️ | Tiempo / Intervalo |
| 📍 | Checkpoint |
| 🔍 | Búsqueda |
| 💾 | Guardar |
| 🗑️ | Eliminar |

### Umbrales Importantes

| Métrica | Normal | Advertencia | Crítico |
|---------|--------|-------------|---------|
| CPU | <70% | 70-90% | >90% |
| Memoria | <75% | 75-90% | >90% |
| Disco | <80% | 80-95% | >95% |
| Tasa de Éxito | ≥95% | 90-95% | <90% |
| Latencia | <100ms | 100-500ms | >500ms |

### Atajos de Teclado

| Tecla | Acción |
|-------|--------|
| `F5` | Recargar página |
| `Ctrl+F` | Buscar en página |

### URLs de Acceso

| Recurso | URL |
|---------|-----|
| Dashboard | http://localhost:8501 |
| API | http://localhost:8080 |
| API Docs | http://localhost:8080/docs |
| Health Check | http://localhost:8080/health |

### Contacto de Soporte

Si tiene problemas que no puede resolver:

1. Exporte los logs relevantes (página Logs → CSV)
2. Tome capturas de pantalla de los errores
3. Documente los pasos para reproducir el problema
4. Contacte a soporte técnico con esta información

**Email**: enzo@oneclick.cr

---

## Historial de Versiones

| Versión | Fecha | Cambios |
|---------|-------|---------|
| 1.0.0 | 2025-01 | Versión inicial |

---

*Documento generado para RMS-Shopify Integration Dashboard v1.0.0*
