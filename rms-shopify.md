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


## DATOS EJEMPLOS (View_Items):

[
  {
    "Familia": "Accesorios",
    "GENERO": "Niño",
    "Categoria": "Ropa",
    "CCOD": "1D8055",
    "C_ARTICULO": "1D8001055",
    "ItemID": 1,
    "Description": "FILA MEDIAS  7-09  NAVY",
    "color": "AZUL NAVY",
    "talla": "010",
    "Quantity": 0.0,
    "Price": 26549000000.0,
    "SaleStartDate": "2007-12-24T00:00:00",
    "SaleEndDate": "2008-01-01T00:00:00",
    "SalePrice": 15929000000.0,
    "ExtendedCategory": "MEDIAS-GENERAL            /NI",
    "Tax": 13,
    "Exis00": 0.0,
    "Exis57": 0.0
  },
  {
    "Familia": "Accesorios",
    "GENERO": "Niño",
    "Categoria": "Ropa",
    "CCOD": "1D8055",
    "C_ARTICULO": "1D8002055",
    "ItemID": 2,
    "Description": "FILA MEDIAS  9-11  NAVY",
    "color": "AZUL NAVY",
    "talla": "020",
    "Quantity": 0.0,
    "Price": 26549000000.0,
    "SaleStartDate": "2007-12-24T00:00:00",
    "SaleEndDate": "2008-01-01T00:00:00",
    "SalePrice": 15929000000.0,
    "ExtendedCategory": "MEDIAS-GENERAL            /NI",
    "Tax": 13,
    "Exis00": 0.0,
    "Exis57": 0.0
  },
  {
    "Familia": "Accesorios",
    "GENERO": "Mujer",
    "Categoria": "Bolsos",
    "CCOD": "4CI209",
    "C_ARTICULO": "4CI201009",
    "ItemID": 3,
    "Description": "UNLISTED       -   S-NEGRO    ",
    "color": "NEGRO",
    "talla": "010",
    "Quantity": 0.0,
    "Price": 168142000000.0,
    "SaleStartDate": "2008-05-08T00:00:00",
    "SaleEndDate": "2008-05-19T00:00:00",
    "SalePrice": 84071000000.0,
    "ExtendedCategory": "FAJA-GENERAL               /DA",
    "Tax": 13,
    "Exis00": 0.0,
    "Exis57": 0.0
  },
  {
    "Familia": "Accesorios",
    "GENERO": "Mujer",
    "Categoria": "Bolsos",
    "CCOD": "4CJ105",
    "C_ARTICULO": "4CJ102005",
    "ItemID": 4,
    "Description": "S.M.           -  M -CAFÉ     ",
    "color": "CAFÉ",
    "talla": "020",
    "Quantity": 0.0,
    "Price": 345133000000.0,
    "SaleStartDate": null,
    "SaleEndDate": null,
    "SalePrice": 0.0,
    "ExtendedCategory": "FAJA-GENERAL               /DA",
    "Tax": 13,
    "Exis00": 0.0,
    "Exis57": 0.0
  },
  {
    "Familia": "Accesorios",
    "GENERO": "Mujer",
    "Categoria": "Bolsos",
    "CCOD": "4CP549",
    "C_ARTICULO": "4CP501049",
    "ItemID": 5,
    "Description": "MARKS & S.     -   S-MARRÓN   ",
    "color": "MARRÓN",
    "talla": "010",
    "Quantity": 0.0,
    "Price": 221239000000.0,
    "SaleStartDate": null,
    "SaleEndDate": null,
    "SalePrice": 0.0,
    "ExtendedCategory": "FAJA-GENERAL               /DA",
    "Tax": 13,
    "Exis00": 0.0,
    "Exis57": 0.0
  },
  {
    "Familia": "Accesorios",
    "GENERO": "Mujer",
    "Categoria": "Bolsos",
    "CCOD": "4CP646",
    "C_ARTICULO": "4CP601046",
    "ItemID": 6,
    "Description": "GEORGE         -   S-NATURAL  ",
    "color": "NATURAL",
    "talla": "010",
    "Quantity": 0.0,
    "Price": 221239000000.0,
    "SaleStartDate": null,
    "SaleEndDate": null,
    "SalePrice": 0.0,
    "ExtendedCategory": "FAJA-GENERAL               /DA",
    "Tax": 13,
    "Exis00": 0.0,
    "Exis57": 0.0
  },
  {
    "Familia": "Accesorios",
    "GENERO": "Mujer",
    "Categoria": "Bolsos",
    "CCOD": "4CR425",
    "C_ARTICULO": "4CR401025",
    "ItemID": 7,
    "Description": "S.M.           -   S-CELESTE  ",
    "color": "CELESTE",
    "talla": "010",
    "Quantity": 0.0,
    "Price": 221239000000.0,
    "SaleStartDate": null,
    "SaleEndDate": null,
    "SalePrice": 0.0,
    "ExtendedCategory": "FAJA-GENERAL               /DA",
    "Tax": 13,
    "Exis00": 0.0,
    "Exis57": 0.0
  },
  {
    "Familia": "Accesorios",
    "GENERO": "Mujer",
    "Categoria": "Bolsos",
    "CCOD": "4CS609",
    "C_ARTICULO": "4CS602009",
    "ItemID": 8,
    "Description": "KENNETH COLE   -  M -NEGRO    ",
    "color": "NEGRO",
    "talla": "020",
    "Quantity": 0.0,
    "Price": 221239000000.0,
    "SaleStartDate": "2014-12-23T00:00:00",
    "SaleEndDate": "2014-12-24T22:00:00",
    "SalePrice": 176991000000.0,
    "ExtendedCategory": "FAJA-GENERAL               /DA",
    "Tax": 13,
    "Exis00": 0.0,
    "Exis57": 0.0
  },
  {
    "Familia": "Accesorios",
    "GENERO": "Mujer",
    "Categoria": "Bolsos",
    "CCOD": "4CS609",
    "C_ARTICULO": "4CS603009",
    "ItemID": 9,
    "Description": "KENNETH COLE   -   L-NEGRO    ",
    "color": "NEGRO",
    "talla": "030",
    "Quantity": 0.0,
    "Price": 221239000000.0,
    "SaleStartDate": "2014-12-23T00:00:00",
    "SaleEndDate": "2014-12-24T22:00:00",
    "SalePrice": 176991000000.0,
    "ExtendedCategory": "FAJA-GENERAL               /DA",
    "Tax": 13,
    "Exis00": 0.0,
    "Exis57": 0.0
  },
  {
    "Familia": "Accesorios",
    "GENERO": "Mujer",
    "Categoria": "Bolsos",
    "CCOD": "4CS609",
    "C_ARTICULO": "4CS601009",
    "ItemID": 10,
    "Description": "KENNETH COLE   -   S-NEGRO    ",
    "color": "NEGRO",
    "talla": "010",
    "Quantity": 0.0,
    "Price": 221239000000.0,
    "SaleStartDate": "2014-12-23T00:00:00",
    "SaleEndDate": "2014-12-24T22:00:00",
    "SalePrice": 176991000000.0,
    "ExtendedCategory": "FAJA-GENERAL               /DA",
    "Tax": 13,
    "Exis00": 0.0,
    "Exis57": 0.0
  }
]

