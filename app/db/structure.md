# Estructura de Base de Datos RMS - Sistema de Integración Shopify

## Información General

**Sistema**: Microsoft Retail Management System (RMS)  
**Base de Datos**: SQL Server 2019+  
**Versión de Integración**: 2.5.0  
**Fecha de Actualización**: 30 de Enero 2025  

Este documento describe la estructura de las tablas principales de RMS utilizadas por el sistema de integración con Shopify.

---

## 📊 Tablas Principales

### 1. Tabla ITEM - Productos Base

La tabla `Item` contiene la información básica de todos los productos en RMS y es fundamental para la detección de cambios.

```sql
SET ANSI_NULLS ON
GO
SET QUOTED_IDENTIFIER ON
GO
CREATE TABLE [dbo].[Item](
    -- Campos de identificación
    [ID] [int] IDENTITY(1,1) NOT NULL,              -- ID único del producto
    [ItemLookupCode] [nvarchar](25) NOT NULL,       -- SKU base del producto
    [Description] [nvarchar](30) NOT NULL,          -- Descripción corta
    [DateCreated] [datetime] NOT NULL,              -- Fecha de creación
    [LastUpdated] [datetime] NOT NULL,              -- 🔥 CRÍTICO: Usado para detectar cambios
    
    -- Clasificación y categorización
    [DepartmentID] [int] NOT NULL,                  -- Departamento del producto
    [CategoryID] [int] NOT NULL,                    -- Categoría principal
    [SubCategoryID] [int] NOT NULL,                 -- Subcategoría
    
    -- Información de precios
    [Price] [money] NOT NULL,                       -- Precio base de venta
    [SalePrice] [money] NOT NULL,                   -- Precio promocional
    [SaleStartDate] [datetime] NULL,                -- Inicio de promoción
    [SaleEndDate] [datetime] NULL,                  -- Fin de promoción
    [Cost] [money] NOT NULL,                        -- Costo del producto
    [LastCost] [money] NOT NULL,                    -- Último costo
    [MSRP] [money] NOT NULL,                        -- Precio sugerido
    
    -- Inventario y stock
    [Quantity] [float] NOT NULL,                    -- Cantidad disponible
    [ReorderPoint] [float] NOT NULL,                -- Punto de reorden
    [RestockLevel] [float] NOT NULL,                -- Nivel de restock
    [LastReceived] [datetime] NULL,                 -- Última recepción
    [LastSold] [datetime] NULL,                     -- Última venta
    [LastCounted] [datetime] NULL,                  -- Último conteo
    
    -- Configuración de impuestos
    [TaxID] [int] NOT NULL,                         -- ID de configuración fiscal
    [Taxable] [bit] NOT NULL,                       -- Aplica impuestos
    
    -- Configuración del producto
    [ItemType] [smallint] NOT NULL,                 -- Tipo de item (1=normal, 2=servicio)
    [Inactive] [bit] NOT NULL,                      -- Producto inactivo
    [WebItem] [bit] NOT NULL,                       -- Disponible para web
    [DoNotOrder] [bit] NOT NULL,                    -- No ordenar automáticamente
    
    -- Información física
    [Weight] [float] NOT NULL,                      -- Peso del producto
    [UnitOfMeasure] [nvarchar](4) NOT NULL,         -- Unidad de medida
    [BarcodeFormat] [smallint] NOT NULL,            -- Formato de código de barras
    
    -- Proveedores y relaciones
    [SupplierID] [int] NOT NULL,                    -- Proveedor principal
    [ParentItem] [int] NOT NULL,                    -- Producto padre (kits)
    [ParentQuantity] [float] NOT NULL,              -- Cantidad en kit
    
    -- Información adicional
    [PictureName] [nvarchar](50) NOT NULL,          -- Nombre del archivo de imagen
    [ExtendedDescription] [ntext] NOT NULL,         -- Descripción extendida
    [Notes] [ntext] NULL,                           -- Notas del producto
    [Content] [ntext] NOT NULL,                     -- Contenido adicional
    
    -- Campos de auditoría
    [DBTimeStamp] [timestamp] NULL,                 -- Timestamp de base de datos
    
    -- Restricciones y controles
    [BlockSalesType] [int] NOT NULL,                -- Tipo de bloqueo de ventas
    [BlockSalesReason] [nvarchar](30) NOT NULL,     -- Razón del bloqueo
    [BlockSalesAfterDate] [datetime] NULL,          -- Bloquear ventas después de
    [BlockSalesBeforeDate] [datetime] NULL,         -- Bloquear ventas antes de
    
 CONSTRAINT [PK_Item] PRIMARY KEY CLUSTERED 
(
    [ID] ASC
)WITH (PAD_INDEX = OFF, STATISTICS_NORECOMPUTE = OFF, IGNORE_DUP_KEY = OFF, 
       ALLOW_ROW_LOCKS = ON, ALLOW_PAGE_LOCKS = ON, FILLFACTOR = 50, 
       OPTIMIZE_FOR_SEQUENTIAL_KEY = OFF) ON [PRIMARY]
) ON [PRIMARY] TEXTIMAGE_ON [PRIMARY]
GO

-- 🔥 ÍNDICE CRÍTICO para detección de cambios
CREATE INDEX IX_Item_LastUpdated ON [dbo].[Item] ([LastUpdated]) INCLUDE ([ID], [ItemLookupCode])
GO
```

**Campos Críticos para Integración:**
- `LastUpdated` - 🔥 **Más importante**: Usado por ChangeDetector para detectar modificaciones
- `ID` - Clave primaria vinculada con View_Items.ItemID
- `ItemLookupCode` - SKU base del producto
- `Inactive` - Estado del producto (activo/inactivo)

### 2. Vista VIEW_ITEMS - Datos Completos de Productos

La vista `View_Items` consolida información de múltiples tablas y es la fuente principal de datos para la sincronización.

```sql
-- Vista personalizada que combina datos de múltiples tablas RMS
-- Esta vista es READ-ONLY y se actualiza automáticamente cuando cambian las tablas base

SELECT 
    -- Información básica del producto
    vi.ItemID,                          -- ID único (vincula con Item.ID)
    vi.C_ARTICULO,                      -- 🔥 SKU completo y único para Shopify
    vi.Description,                     -- Nombre comercial del producto
    
    -- Clasificación jerárquica
    vi.Familia,                         -- Clasificación principal (Zapatos, Ropa, Accesorios)
    vi.Categoria,                       -- Categoría específica (Tenis, Botas, Sandalias)
    vi.ExtendedCategory,                -- Categoría completa con subcategorías
    vi.Genero,                          -- Audiencia objetivo (Hombre, Mujer, Niño, Niña)
    
    -- Variantes del producto
    vi.CCOD,                           -- 🔥 Código modelo+color (clave agrupación variantes)
    vi.color,                          -- Color específico del producto
    vi.talla,                          -- Talla del producto (se normaliza 23½ → 23.5)
    
    -- Información de precios
    vi.Price,                          -- Precio base antes de impuestos
    vi.SalePrice,                      -- Precio promocional (si aplica)
    vi.SaleStartDate,                  -- Fecha inicio promoción
    vi.SaleEndDate,                    -- Fecha fin promoción
    
    -- Inventario y disponibilidad
    vi.Quantity,                       -- Cantidad total disponible
    vi.Exis00,                         -- Stock bodega principal
    vi.Exis57,                         -- Stock tienda/alternativo
    
    -- Información fiscal
    vi.Tax,                            -- Porcentaje de impuesto (ej: 13%)
    
    -- Información adicional
    vi.UPC,                            -- Código de barras
    vi.Weight,                         -- Peso del producto
    vi.Manufacturer,                   -- Fabricante/marca
    
    -- Timestamp de última modificación (desde tabla Item)
    i.LastUpdated                      -- 🔥 Para detección de cambios

FROM View_Items vi
INNER JOIN Item i ON vi.ItemID = i.ID
WHERE 
    vi.C_ARTICULO IS NOT NULL          -- SKU debe existir
    AND vi.Description IS NOT NULL     -- Descripción requerida
    AND vi.Price > 0                   -- Precio válido
    -- Filtros opcionales aplicados dinámicamente:
    -- AND (@include_zero_stock = 1 OR vi.Quantity > 0)
    -- AND vi.Familia IN (@filter_families)
    -- AND vi.Categoria IN (@filter_categories)
```

**Estructura de Datos de Ejemplo:**
```json
{
    "ItemID": 123456,
    "C_ARTICULO": "24YM05051-NEG-38",      // SKU único completo
    "Description": "Zapato Deportivo Negro",
    "Familia": "Zapatos",                   // Vendor en Shopify
    "Categoria": "Tenis",                   // Product Type en Shopify
    "ExtendedCategory": "CALZADO-DEPORTIVO/HOMBRE",
    "Genero": "Hombre",                     // Tag en Shopify
    "CCOD": "24YM05051",                   // Modelo+Color (agrupa variantes)
    "color": "Negro",                       // Option1 en Shopify
    "talla": "38",                          // Option2 en Shopify
    "Price": 89.99,                        // Precio base
    "SalePrice": 69.99,                    // Precio oferta (compare_at_price)
    "SaleStartDate": "2025-01-01T00:00:00Z",
    "SaleEndDate": "2025-01-31T23:59:59Z",
    "Quantity": 5.0,                       // Inventory quantity
    "Exis00": 3.0,                         // Stock bodega
    "Exis57": 2.0,                         // Stock tienda
    "Tax": 13.0,                           // 13% IVA Costa Rica
    "UPC": "1234567890123",
    "Weight": 0.5,
    "Manufacturer": "Nike",
    "LastUpdated": "2025-01-30T10:30:00Z"  // Para ChangeDetector
}
```

### 3. Tabla ORDER - Cabecera de Pedidos

La tabla `Order` almacena la información principal de cada pedido que viene de Shopify.

```sql
SET ANSI_NULLS ON
GO
SET QUOTED_IDENTIFIER ON
GO
CREATE TABLE [dbo].[Order](
    -- Identificación del pedido
    [ID] [int] IDENTITY(1,1) NOT NULL,              -- ID único del pedido RMS
    [StoreID] [int] NOT NULL,                       -- ID de tienda (40 para Shopify)
    [Type] [int] NOT NULL,                          -- Tipo: 1=Venta, 2=Devolución
    [Time] [datetime] NOT NULL,                     -- Fecha/hora del pedido
    [Comment] [nvarchar](255) NOT NULL,             -- 🔥 Contiene ID de Shopify
    
    -- Información del cliente
    [CustomerID] [int] NOT NULL,                    -- ID cliente RMS (puede ser NULL)
    [ShipToID] [int] NOT NULL,                      -- Dirección de envío
    
    -- Totales del pedido
    [Total] [money] NOT NULL,                       -- Total del pedido
    [Tax] [money] NOT NULL,                         -- Impuestos totales
    [Deposit] [money] NOT NULL,                     -- Depósito (normalmente 0)
    [DepositOverride] [bit] NOT NULL,               -- Override del depósito
    
    -- Estado del pedido
    [Closed] [bit] NOT NULL,                        -- Pedido cerrado
    [Taxable] [bit] NOT NULL,                       -- Aplica impuestos
    [ExpirationOrDueDate] [datetime] NOT NULL,      -- Fecha vencimiento
    
    -- Información de envío
    [ShippingChargeOnOrder] [money] NOT NULL,       -- Costo de envío
    [ShippingChargeOverride] [bit] NOT NULL,        -- Override envío
    [ShippingServiceID] [int] NOT NULL,             -- Servicio de envío
    [ShippingTrackingNumber] [nvarchar](255) NOT NULL, -- Tracking number
    [ShippingNotes] [ntext] NOT NULL,               -- 🔥 Dirección completa de envío
    
    -- Información de ventas
    [SalesRepID] [int] NOT NULL,                    -- Vendedor asignado
    [ReferenceNumber] [nvarchar](50) NOT NULL,      -- Número de referencia
    
    -- Campos de auditoría
    [LastUpdated] [datetime] NOT NULL,              -- Última modificación
    [DBTimeStamp] [timestamp] NULL,                 -- Timestamp de BD
    
    -- Campos adicionales
    [ReasonCodeID] [int] NOT NULL,                  -- Código de razón
    [ExchangeID] [int] NOT NULL,                    -- ID de intercambio
    [ChannelType] [int] NOT NULL,                   -- Canal de venta
    [DefaultDiscountReasonCodeID] [int] NOT NULL,   -- Razón descuento por defecto
    [DefaultReturnReasonCodeID] [int] NOT NULL,     -- Razón devolución por defecto
    [DefaultTaxChangeReasonCodeID] [int] NOT NULL,  -- Razón cambio impuesto
    
 CONSTRAINT [PK_Order] PRIMARY KEY NONCLUSTERED 
(
    [ID] ASC
)WITH (PAD_INDEX = OFF, STATISTICS_NORECOMPUTE = OFF, IGNORE_DUP_KEY = OFF, 
       ALLOW_ROW_LOCKS = ON, ALLOW_PAGE_LOCKS = ON, FILLFACTOR = 50, 
       OPTIMIZE_FOR_SEQUENTIAL_KEY = OFF) ON [PRIMARY]
) ON [PRIMARY] TEXTIMAGE_ON [PRIMARY]
GO

-- Índice para búsqueda por comentario (ID de Shopify)
CREATE INDEX IX_Order_Comment ON [dbo].[Order] ([Comment])
GO
```

**Mapeo Shopify → RMS ORDER:**
- `Comment` → "Shopify Order #{order.name}" (ej: "Shopify Order #1001")
- `StoreID` → 40 (configurable con STORE_ID)
- `Time` → order.created_at
- `CustomerID` → Resultado de lookup/creación de cliente
- `Total` → order.total_price_set.shop_money.amount
- `Tax` → order.total_tax_set.shop_money.amount
- `ShippingNotes` → Dirección completa de envío formateada

### 4. Tabla ORDERENTRY - Detalle de Pedidos

La tabla `OrderEntry` contiene las líneas individuales de cada pedido.

```sql
SET ANSI_NULLS ON
GO
SET QUOTED_IDENTIFIER ON
GO
CREATE TABLE [dbo].[OrderEntry](
    -- Identificación de la línea
    [ID] [int] IDENTITY(1,1) NOT NULL,              -- ID único de la línea
    [StoreID] [int] NOT NULL,                       -- ID de tienda
    [OrderID] [int] NOT NULL,                       -- 🔥 FK a tabla Order
    [ItemID] [int] NOT NULL,                        -- 🔥 FK a tabla Item
    [DetailID] [int] NOT NULL,                      -- ID de detalle
    
    -- Información del producto
    [Description] [nvarchar](30) NOT NULL,          -- Descripción del producto
    
    -- Precios y cantidades
    [Price] [money] NOT NULL,                       -- 🔥 Precio unitario con descuento
    [FullPrice] [money] NOT NULL,                   -- 🔥 Precio original sin descuento
    [Cost] [money] NOT NULL,                        -- Costo del producto
    [QuantityOnOrder] [float] NOT NULL,             -- 🔥 Cantidad ordenada
    [QuantityRTD] [float] NOT NULL,                 -- Cantidad lista para despacho
    [PriceSource] [smallint] NOT NULL,              -- Fuente del precio
    
    -- Impuestos y descuentos
    [Taxable] [int] NOT NULL,                       -- Aplica impuestos
    [DiscountReasonCodeID] [int] NOT NULL,          -- Código razón de descuento
    [ReturnReasonCodeID] [int] NOT NULL,            -- Código razón de devolución
    [TaxChangeReasonCodeID] [int] NOT NULL,         -- Código cambio de impuesto
    
    -- Información de ventas
    [SalesRepID] [int] NOT NULL,                    -- Vendedor asignado
    
    -- Campos especiales
    [IsAddMoney] [bit] NOT NULL,                    -- Es cargo adicional
    [VoucherID] [int] NOT NULL,                     -- ID de cupón/voucher
    
    -- Campos de auditoría
    [LastUpdated] [datetime] NOT NULL,              -- Última modificación
    [TransactionTime] [datetime] NULL,              -- Tiempo de transacción
    [Comment] [nvarchar](255) NOT NULL,             -- Comentarios adicionales
    [DBTimeStamp] [timestamp] NULL,                 -- Timestamp de BD
    
 CONSTRAINT [PK_OrderEntry] PRIMARY KEY NONCLUSTERED 
(
    [ID] ASC
)WITH (PAD_INDEX = OFF, STATISTICS_NORECOMPUTE = OFF, IGNORE_DUP_KEY = OFF, 
       ALLOW_ROW_LOCKS = ON, ALLOW_PAGE_LOCKS = ON, FILLFACTOR = 50, 
       OPTIMIZE_FOR_SEQUENTIAL_KEY = OFF) ON [PRIMARY]
) ON [PRIMARY]
GO

-- Índices para performance
CREATE INDEX IX_OrderEntry_OrderID ON [dbo].[OrderEntry] ([OrderID])
GO
CREATE INDEX IX_OrderEntry_ItemID ON [dbo].[OrderEntry] ([ItemID])
GO
```

**Mapeo Shopify → RMS ORDERENTRY:**
- `OrderID` → ID generado en tabla Order
- `ItemID` → Resolución de line_item.sku → View_Items.C_ARTICULO → Item.ID
- `Price` → line_item.discounted_unit_price_set.shop_money.amount
- `FullPrice` → line_item.original_unit_price_set.shop_money.amount
- `QuantityOnOrder` → line_item.quantity
- `Description` → line_item.title (truncado a 30 caracteres)

### 5. Tabla ORDERHISTORY - Historial de Cambios

```sql
SET ANSI_NULLS ON
GO
SET QUOTED_IDENTIFIER ON
GO
CREATE TABLE [dbo].[OrderHistory](
    [ID] [int] IDENTITY(1,1) NOT NULL,              -- ID único del registro
    [StoreID] [int] NOT NULL,                       -- ID de tienda
    [BatchNumber] [int] NOT NULL,                   -- Número de lote
    [Date] [datetime] NOT NULL,                     -- Fecha del cambio
    [OrderID] [int] NOT NULL,                       -- ID del pedido afectado
    [CashierID] [int] NOT NULL,                     -- ID del cajero/usuario
    [DeltaDeposit] [money] NOT NULL,                -- Cambio en depósito
    [TransactionNumber] [int] NOT NULL,             -- Número de transacción
    [Comment] [nvarchar](30) NOT NULL,              -- Comentario del cambio
    [DBTimeStamp] [timestamp] NULL,                 -- Timestamp de BD
    
 CONSTRAINT [PK_OrderHistory] PRIMARY KEY NONCLUSTERED 
(
    [ID] ASC
)WITH (PAD_INDEX = OFF, STATISTICS_NORECOMPUTE = OFF, IGNORE_DUP_KEY = OFF, 
       ALLOW_ROW_LOCKS = ON, ALLOW_PAGE_LOCKS = ON, FILLFACTOR = 50, 
       OPTIMIZE_FOR_SEQUENTIAL_KEY = OFF) ON [PRIMARY]
) ON [PRIMARY]
GO
```

---

## 🔍 Consultas Críticas para Integración

### 1. Detección de Cambios (ChangeDetector)

```sql
-- Query principal para detectar productos modificados
SELECT TOP (@batch_size)
    ID as ItemID,
    LastUpdated,
    DateCreated,
    ItemLookupCode
FROM Item 
WHERE LastUpdated > @last_sync_time
    AND LastUpdated IS NOT NULL
    AND LastUpdated <= GETUTCDATE()
ORDER BY LastUpdated ASC
```

### 2. Obtener Datos Completos de Productos Modificados

```sql
-- Query para obtener datos completos después de detectar cambios
SELECT 
    ItemID, C_ARTICULO, Description, Price, Quantity,
    Familia, Categoria, color, talla, CCOD,
    SalePrice, SaleStartDate, SaleEndDate,
    ExtendedCategory, Tax, Exis00, Exis57,
    Genero, UPC, Weight, Manufacturer
FROM View_Items 
WHERE ItemID IN (@modified_item_ids)
    AND C_ARTICULO IS NOT NULL 
    AND Description IS NOT NULL
    AND Price > 0
    AND (@include_zero_stock = 1 OR Quantity > 0)
ORDER BY CCOD, color, talla
```

### 3. Verificar Existencia de Pedido (Evitar Duplicados)

```sql
-- Verificar si un pedido de Shopify ya existe en RMS
SELECT COUNT(*) 
FROM [Order] 
WHERE Comment LIKE 'Shopify Order #' + @shopify_order_name + '%'
```

### 4. Resolución SKU → ItemID

```sql
-- Convertir SKU de Shopify a ItemID de RMS
SELECT ItemID 
FROM View_Items 
WHERE C_ARTICULO = @shopify_sku
    AND C_ARTICULO IS NOT NULL
```

---

## 📈 Índices Recomendados para Performance

```sql
-- Índices críticos para performance de integración

-- Para detección de cambios (MUY IMPORTANTE)
CREATE INDEX IX_Item_LastUpdated ON Item (LastUpdated) 
INCLUDE (ID, ItemLookupCode, Inactive)

-- Para agrupación de variantes
CREATE INDEX IX_ViewItems_CCOD ON View_Items (CCOD) 
INCLUDE (ItemID, C_ARTICULO, color, talla)

-- Para resolución de SKUs
CREATE INDEX IX_ViewItems_SKU ON View_Items (C_ARTICULO) 
INCLUDE (ItemID, Description, Price, Quantity)

-- Para búsqueda de pedidos
CREATE INDEX IX_Order_Comment ON [Order] (Comment)
CREATE INDEX IX_Order_Time ON [Order] (Time)

-- Para líneas de pedido
CREATE INDEX IX_OrderEntry_OrderID ON OrderEntry (OrderID)
CREATE INDEX IX_OrderEntry_ItemID ON OrderEntry (ItemID)

-- Para filtros por categoría
CREATE INDEX IX_ViewItems_Categoria ON View_Items (Categoria) 
INCLUDE (ItemID, C_ARTICULO, Familia)
CREATE INDEX IX_ViewItems_Familia ON View_Items (Familia) 
INCLUDE (ItemID, C_ARTICULO, Categoria)
```

---

## 🔄 Flujo de Datos en la Integración

### RMS → Shopify (Productos)
1. **ChangeDetector** consulta `Item.LastUpdated` cada 5 minutos
2. **IDs modificados** se obtienen ordenados por timestamp
3. **Datos completos** se obtienen de `View_Items` para los IDs modificados
4. **Agrupación por CCOD** para crear productos con variantes
5. **Sincronización** a Shopify usando GraphQL

### Shopify → RMS (Pedidos)
1. **Webhook** recibido desde Shopify con datos del pedido
2. **Validación** de estado financiero y productos existentes
3. **Inserción en ORDER** con datos de cabecera
4. **Inserción en ORDERENTRY** con líneas del pedido
5. **Commit/Rollback** según éxito de la operación

---

## 🔧 Configuración de Conexión

```python
# Configuración típica para SQL Server RMS
DATABASE_CONFIG = {
    "host": "servidor-rms.empresa.com",
    "port": 1433,
    "database": "RMS_Database",
    "driver": "ODBC Driver 17 for SQL Server",
    "username": "rms_integration_user",
    "password": "secure_password",
    "connection_timeout": 30,
    "command_timeout": 60,
    "pool_size": 10,
    "max_overflow": 20,
    "pool_recycle": 3600
}
```

---

## 📊 Estadísticas de Base de Datos

**Tabla Item**: ~600,000 registros  
**Vista View_Items**: ~556,649 productos únicos disponibles  
**Tabla Order**: ~113,330 pedidos históricos  
**Tabla OrderEntry**: ~500,000+ líneas de pedido  

**Performance típica**:
- Consulta detección cambios: ~200ms
- Consulta datos completos (10 productos): ~400ms
- Inserción pedido completo: ~150ms

---

*Documento actualizado: 30 de Enero 2025*  
*Versión del sistema: 2.5.0*  
*Compatible con: SQL Server 2019+, ODBC Driver 17*