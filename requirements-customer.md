Integración RMS → Shopify
  Desarrollo de conector para lectura de la vista personalizada View_Items
  en RMS, extrayendo:
  – Información básica: SKU (C_ARTICULO), nombre, categoría, fa-
  milia, color, talla
  – Información de precios: Precio base (Price) y precio promocional
  (SalePrice)
  – Fechas de promoción: SaleStartDate, SaleEndDate
  – Información de inventario: Cantidad disponible (Quantity)
  – Información fiscal: Impuestos aplicables (Tax)
  – Atributos adicionales: Género, Descripción, ExtendedCategory
  • Implementación de lógica para creación y actualización de productos en
  Shopify:
  – Publicación controlada (productos inactivos hasta completar infor-
  mación visual)
  – Mapeo inteligente de variantes por color y talla
  – Motor de sincronización con detección de cambios
  – Sistema de conciliación para evitar duplicados


Integración Shopify → RMS: https://shopify.dev/docs/api/admin-graphql/latest/objects/order
• Desarrollo de conector para captura de pedidos formalizados en Shopify e
inserción en tablas ORDER y ORDERENTRY de RMS:
	– Datos de cabecera: cliente, fecha, total, impuestos
	– Datos de detalle: productos, cantidades, precios unitarios
	– Validación de existencias y gestión de excepciones
	– Manejo de estados del pedido


* Componentes principales: Dos microservicios de sincronización (RMS → Shopify y Shopify → RMS) y un módulo de administración y monitoreo.
* Automatización y programación: Sincronización automática programable con intervalos personalizables y API para ejecución manual y programada.
* Gestión de errores: Sistema avanzado de captura y notificación con alertas configurables y recuperación automática de fallos transitorios.

