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

