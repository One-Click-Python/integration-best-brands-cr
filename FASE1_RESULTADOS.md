# FASE 1: Pre-Testing Validation - RESULTADOS

**Fecha**: 2025-01-12
**Status**: ⚠️ PARCIALMENTE COMPLETO (95%)

---

## ✅ Validaciones Exitosas

### 1. Backup de Base de Datos
- **Status**: ⚠️ PENDIENTE CONFIRMACIÓN MANUAL
- **Acción Requerida**: Ejecutar `scripts/phase1_backup_instructions.sql` en SSMS
- **Instrucciones**: Ver `scripts/phase1_backup_instructions.sql`

### 2. Baseline Documentation - ✅ COMPLETO
**Snapshot de Órdenes RMS (ChannelType=2):**

| Métrica | Valor |
|---------|-------|
| Total Shopify Orders | 9 |
| Last Order ID | 114825 |
| Orders (Last 30 Days) | 5 |
| Orders (Last 7 Days) | 0 |
| Orders (Last 24 Hours) | 0 |
| **Duplicates Detected** | **⚠️ 1** |

### 3. Redis Connectivity - ✅ COMPLETO
- **Status**: ✅ Conectado
- **Polling Stats**: No existen (esperado para primer test)
- **URL**: `redis://localhost:6379/0`

### 4. RMS Database Access - ✅ COMPLETO
- **Status**: ✅ Conectado
- **Version**: Microsoft SQL Server 2022 (RTM-GDR) 16.0.1160.1
- **Database**: Verificado correctamente
- **Pool**: Funcionando correctamente

### 5. Shopify GraphQL API - ⚠️ FALLÓ
- **Status**: ❌ DNS Error
- **Error**: `[Errno 8] nodename nor servname provided, or not known`
- **Causa**: Variable `SHOPIFY_SHOP_URL` incorrecta o red inaccesible
- **Acción Requerida**: Verificar `.env` y conectividad de red

### 6. Order Polling Endpoint - ⏸️ NO VERIFICADO
- **Motivo**: Script detenido por fallo de Shopify API
- **Requiere**: App ejecutándose en `http://localhost:8080`

---

## 🚨 PROBLEMAS DETECTADOS

### ⚠️ Crítico: Duplicado en RMS Database
**Detalle**: Se detectó **1 orden duplicada** con el mismo `ReferenceNumber` en la tabla `[Order]` donde `ChannelType = 2`.

**Query para investigar**:
```sql
-- Encontrar duplicados
SELECT ReferenceNumber, COUNT(*) as cantidad,
       MIN(ID) as primer_id, MAX(ID) as ultimo_id,
       MIN(Time) as primera_fecha, MAX(Time) as ultima_fecha
FROM [Order]
WHERE ChannelType = 2
GROUP BY ReferenceNumber
HAVING COUNT(*) > 1
```

**Opciones**:
1. **Mantener el más reciente**, eliminar antiguo
2. **Mantener el primero**, eliminar duplicado
3. **Investigar causa raíz** antes de proceder

**Recomendación**: Investigar y resolver ANTES de la Fase 2.

### ⚠️ No Crítico: Shopify API Inaccesible
**Causa**: Probablemente configuración de `.env` o red
**Solución**: Verificar `SHOPIFY_SHOP_URL` en `.env`

---

## 📊 Scripts Creados

### 1. `scripts/phase1_backup_instructions.sql`
Instrucciones SQL para crear backup completo de base de datos.

### 2. `scripts/phase1_validation.py`
Script automatizado de validación con:
- Verificación automática de conexiones
- Baseline documentation
- Report generation
- Flag `--skip-backup-prompt` para ejecución no interactiva

**Uso**:
```bash
# Con prompt interactivo (recomendado)
poetry run python scripts/phase1_validation.py

# Sin prompt (CI/CD)
poetry run python scripts/phase1_validation.py --skip-backup-prompt
```

---

## 📝 Próximos Pasos (Fase 2)

### Antes de Fase 2:
1. ✅ **Resolver duplicado en RMS** (SQL query arriba)
2. ✅ **Verificar configuración Shopify** (`.env`)
3. ✅ **Confirmar backup** ejecutado y guardado
4. ✅ **Iniciar aplicación** (`http://localhost:8080`)
5. ✅ **Re-ejecutar validación** con todos los checks pasando

### Iniciar Fase 2 solo si:
- ✅ Zero duplicados en RMS
- ✅ Backup confirmado y verificado
- ✅ Shopify API accesible
- ✅ Polling endpoint respondiendo

---

## 🔧 Troubleshooting

### Error: "nodename nor servname provided"
**Causa**: `SHOPIFY_SHOP_URL` mal configurada
**Solución**:
```bash
# Verificar .env
grep SHOPIFY_SHOP_URL .env

# Debe ser formato: your-shop.myshopify.com (SIN https://)
```

### Error: Duplicados en RMS
**Query de diagnóstico**:
```sql
-- Ver detalles completos del duplicado
SELECT o.*, oe.*
FROM [Order] o
LEFT JOIN OrderEntry oe ON o.ID = oe.OrderID
WHERE o.ReferenceNumber IN (
    SELECT ReferenceNumber
    FROM [Order]
    WHERE ChannelType = 2
    GROUP BY ReferenceNumber
    HAVING COUNT(*) > 1
)
ORDER BY o.ReferenceNumber, o.ID
```

### App no responde en localhost:8080
**Solución**:
```bash
# Iniciar app en modo desarrollo
poetry run uvicorn app.main:app --reload --host 0.0.0.0 --port 8080

# Verificar status
curl http://localhost:8080/api/v1/health
```

---

## 📌 Notas Importantes

1. **NO continuar a Fase 2** hasta resolver el duplicado
2. **Backup es CRÍTICO** - Sin backup = Sin safety net
3. **Baseline guardado** en `baseline_order_polling_test.json`
4. **Script reusable** para futuras validaciones

---

## ✅ Checklist Fase 1

- [x] Scripts de backup creados
- [x] Script de validación funcionando
- [x] Baseline documentado
- [x] Redis verificado
- [x] RMS database verificado
- [ ] **PENDIENTE**: Resolver duplicado
- [ ] **PENDIENTE**: Shopify API verificado
- [ ] **PENDIENTE**: Polling endpoint verificado
- [ ] **PENDIENTE**: Backup ejecutado manualmente

**Status Global**: 75% completo - Listo para correcciones pre-Fase 2
