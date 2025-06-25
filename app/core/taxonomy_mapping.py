"""
Sistema de mapeo mejorado para taxonomías y metafields de Shopify.

Este módulo maneja la conversión de campos RMS (familia, categoria, talla, color)
a taxonomías estándar de Shopify y metafields estructurados.
"""

from typing import Dict, List, Optional, Any, Tuple
import re
import logging
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class MetafieldType(Enum):
    """Tipos de metafields de Shopify."""
    SINGLE_LINE_TEXT = "single_line_text_field"
    MULTI_LINE_TEXT = "multi_line_text_field"
    NUMBER_INTEGER = "number_integer"
    NUMBER_DECIMAL = "number_decimal"
    BOOLEAN = "boolean"
    DATE = "date"
    DATE_TIME = "date_time"
    URL = "url"
    JSON = "json"
    COLOR = "color"
    WEIGHT = "weight"
    VOLUME = "volume"
    DIMENSION = "dimension"
    RATING = "rating"
    REFERENCE = "reference"


@dataclass
class MetafieldDefinition:
    """Definición de un metafield."""
    namespace: str
    key: str
    name: str
    type: MetafieldType
    description: str
    validation: Optional[Dict[str, Any]] = None


@dataclass
class TaxonomyMapping:
    """Mapeo de categoría RMS a taxonomía Shopify."""
    rms_familia: str
    rms_categoria: str
    shopify_taxonomy_id: Optional[str]
    shopify_product_type: str
    search_terms: List[str]
    fallback_category: str


class RMSTaxonomyMapper:
    """
    Mapea datos de RMS a taxonomías y metafields de Shopify.
    """
    
    # Mapeo de familias RMS a categorías principales de Shopify
    FAMILIA_TO_SHOPIFY_MAPPING = {
        "Accesorios": {
            "product_type": "Accessories",
            "search_terms": ["accessories", "fashion accessories"],
            "taxonomy_base": "Apparel & Accessories > Accessories"
        },
        "Ropa": {
            "product_type": "Apparel",
            "search_terms": ["apparel", "clothing", "fashion"],
            "taxonomy_base": "Apparel & Accessories > Clothing"
        },
        "Zapatos": {
            "product_type": "Footwear", 
            "search_terms": ["shoes", "footwear"],
            "taxonomy_base": "Apparel & Accessories > Shoes"
        },
        "Miscelaneos": {
            "product_type": "Miscellaneous",
            "search_terms": ["miscellaneous", "other"],
            "taxonomy_base": "Other"
        },
        "n/d": {
            "product_type": "Unspecified",
            "search_terms": ["unspecified", "general"],
            "taxonomy_base": "Other"
        }
    }
    
    # Mapeo detallado de categorías RMS a taxonomías específicas de Shopify
    CATEGORIA_TO_TAXONOMY_MAPPING = {
        # Calzado - Zapatos
        "Tenis": {
            "taxonomy_search": ["Athletic Shoes", "Sneakers", "Sports Shoes"],
            "product_type": "Athletic Footwear",
            "taxonomy_id": None  # Se resolverá dinámicamente
        },
        "Botas": {
            "taxonomy_search": ["Boots", "Ankle Boots"],
            "product_type": "Boots",
            "taxonomy_id": None
        },
        "Botines": {
            "taxonomy_search": ["Ankle Boots", "Booties"],
            "product_type": "Ankle Boots",
            "taxonomy_id": None
        },
        "Sandalias": {
            "taxonomy_search": ["Sandals", "Summer Shoes"],
            "product_type": "Sandals",
            "taxonomy_id": None
        },
        "Flats": {
            "taxonomy_search": ["Flats", "Ballet Flats"],
            "product_type": "Flats",
            "taxonomy_id": None
        },
        "Tacones": {
            "taxonomy_search": ["High Heels", "Dress Shoes"],
            "product_type": "High Heels",
            "taxonomy_id": None
        },
        "Cuñas": {
            "taxonomy_search": ["Wedges", "Platform Shoes"],
            "product_type": "Wedges",
            "taxonomy_id": None
        },
        "Casual": {
            "taxonomy_search": ["Casual Shoes", "Everyday Shoes"],
            "product_type": "Casual Footwear",
            "taxonomy_id": None
        },
        "Vestir": {
            "taxonomy_search": ["Dress Shoes", "Formal Shoes"],
            "product_type": "Dress Shoes",
            "taxonomy_id": None
        },
        
        # Ropa
        "Ropa": {
            "taxonomy_search": ["Clothing", "Apparel"],
            "product_type": "Clothing",
            "taxonomy_id": None
        },
        "NIÑA-CASU-CERR": {
            "taxonomy_search": ["Girls Clothing", "Kids Casual Wear"],
            "product_type": "Girls Casual Clothing",
            "taxonomy_id": None
        },
        "NIÑO-CASU-CERR": {
            "taxonomy_search": ["Boys Clothing", "Kids Casual Wear"],
            "product_type": "Boys Casual Clothing",
            "taxonomy_id": None
        },
        "MUJER-VEST-CERR-TA16": {
            "taxonomy_search": ["Women's Dresses", "Women's Formal Wear"],
            "product_type": "Women's Dresses",
            "taxonomy_id": None
        },
        "MUJER-CERR-PLATA": {
            "taxonomy_search": ["Women's Formal Wear", "Women's Evening Wear"],
            "product_type": "Women's Formal Wear",
            "taxonomy_id": None
        },
        "MUJER-SAND-PLATA": {
            "taxonomy_search": ["Women's Sandals", "Women's Summer Shoes"],
            "product_type": "Women's Sandals",
            "taxonomy_id": None
        },
        
        # Accesorios
        "Accesorios": {
            "taxonomy_search": ["Fashion Accessories", "Accessories"],
            "product_type": "Accessories",
            "taxonomy_id": None
        },
        "ACCESORIOS CALZADO": {
            "taxonomy_search": ["Shoe Care", "Footwear Accessories"],
            "product_type": "Shoe Accessories",
            "taxonomy_id": None
        },
        "Bolsos": {
            "taxonomy_search": ["Handbags", "Bags", "Purses"],
            "product_type": "Handbags",
            "taxonomy_id": None
        },
        
        # Categorías especiales
        "Mixto": {
            "taxonomy_search": ["Unisex", "Mixed"],
            "product_type": "Unisex",
            "taxonomy_id": None
        },
        "Transito": {
            "taxonomy_search": ["Transit", "Temporary"],
            "product_type": "Transit",
            "taxonomy_id": None
        },
        "Miscelaneos": {
            "taxonomy_search": ["Miscellaneous", "Other"],
            "product_type": "Miscellaneous",
            "taxonomy_id": None
        },
        "n/d": {
            "taxonomy_search": ["Unspecified", "Not Defined"],
            "product_type": "Unspecified",
            "taxonomy_id": None
        }
    }
    
    # Definiciones de metafields para RMS
    METAFIELD_DEFINITIONS = {
        "rms_familia": MetafieldDefinition(
            namespace="rms",
            key="familia",
            name="RMS Familia",
            type=MetafieldType.SINGLE_LINE_TEXT,
            description="Familia del producto en RMS (ej: Zapatos, Ropa, Accesorios)"
        ),
        "rms_categoria": MetafieldDefinition(
            namespace="rms",
            key="categoria",
            name="RMS Categoría",
            type=MetafieldType.SINGLE_LINE_TEXT,
            description="Categoría específica del producto en RMS"
        ),
        "rms_talla": MetafieldDefinition(
            namespace="rms",
            key="talla",
            name="Talla",
            type=MetafieldType.SINGLE_LINE_TEXT,
            description="Talla del producto (normalizada)"
        ),
        "rms_color": MetafieldDefinition(
            namespace="rms",
            key="color",
            name="Color",
            type=MetafieldType.SINGLE_LINE_TEXT,
            description="Color del producto"
        ),
        "rms_talla_original": MetafieldDefinition(
            namespace="rms",
            key="talla_original",
            name="Talla Original",
            type=MetafieldType.SINGLE_LINE_TEXT,
            description="Talla original del producto en RMS sin normalizar"
        ),
        "rms_extended_category": MetafieldDefinition(
            namespace="rms",
            key="extended_category",
            name="Categoría Extendida",
            type=MetafieldType.SINGLE_LINE_TEXT,
            description="Categoría extendida construida desde familia y categoría"
        ),
        "rms_product_attributes": MetafieldDefinition(
            namespace="rms",
            key="product_attributes",
            name="Atributos del Producto",
            type=MetafieldType.JSON,
            description="Todos los atributos RMS en formato JSON estructurado"
        )
    }
    
    def __init__(self):
        """Inicializa el mapeador."""
        self._taxonomy_cache: Dict[str, str] = {}
        
    def normalize_size(self, talla: str) -> Tuple[str, str]:
        """
        Normaliza las tallas para formato estándar.
        
        Args:
            talla: Talla original (ej: "23½", "24.5", "M", "L")
            
        Returns:
            Tuple con (talla_normalizada, talla_original)
        """
        if not talla or talla.strip() == "":
            return "", ""
            
        original = talla.strip()
        normalized = original
        
        # Convertir ½ a .5
        if "½" in normalized:
            normalized = normalized.replace("½", ".5")
            
        # Normalizar fracciones comunes
        normalized = normalized.replace("¼", ".25")
        normalized = normalized.replace("¾", ".75")
        normalized = normalized.replace("⅓", ".33")
        normalized = normalized.replace("⅔", ".67")
        
        # Limpiar espacios extra
        normalized = normalized.strip()
        
        logger.debug(f"Normalized size: '{original}' -> '{normalized}'")
        return normalized, original
    
    def get_taxonomy_mapping(self, familia: str, categoria: str) -> TaxonomyMapping:
        """
        Obtiene el mapeo de taxonomía para una familia y categoría.
        
        Args:
            familia: Familia RMS
            categoria: Categoría RMS
            
        Returns:
            TaxonomyMapping con la información de mapeo
        """
        # Buscar mapeo específico de categoría
        categoria_mapping = self.CATEGORIA_TO_TAXONOMY_MAPPING.get(categoria)
        familia_mapping = self.FAMILIA_TO_SHOPIFY_MAPPING.get(familia, {})
        
        if categoria_mapping:
            return TaxonomyMapping(
                rms_familia=familia,
                rms_categoria=categoria,
                shopify_taxonomy_id=categoria_mapping.get("taxonomy_id"),
                shopify_product_type=categoria_mapping["product_type"],
                search_terms=categoria_mapping["taxonomy_search"],
                fallback_category=familia_mapping.get("product_type", "Other")
            )
        
        # Fallback a familia si no hay mapeo específico de categoría
        return TaxonomyMapping(
            rms_familia=familia,
            rms_categoria=categoria,
            shopify_taxonomy_id=None,
            shopify_product_type=familia_mapping.get("product_type", "Other"),
            search_terms=familia_mapping.get("search_terms", ["other"]),
            fallback_category="Other"
        )
    
    def create_metafields(self, familia: str, categoria: str, talla: str, color: str, 
                         additional_data: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Crea metafields estructurados para los datos RMS.
        
        Args:
            familia: Familia RMS
            categoria: Categoría RMS
            talla: Talla del producto
            color: Color del producto
            additional_data: Datos adicionales para incluir
            
        Returns:
            Lista de metafields para crear en Shopify
        """
        metafields = []
        
        # Normalizar talla
        talla_normalizada, talla_original = self.normalize_size(talla)
        
        # Metafield familia
        if familia:
            metafields.append({
                "namespace": self.METAFIELD_DEFINITIONS["rms_familia"].namespace,
                "key": self.METAFIELD_DEFINITIONS["rms_familia"].key,
                "type": self.METAFIELD_DEFINITIONS["rms_familia"].type.value,
                "value": familia
            })
        
        # Metafield categoría
        if categoria:
            metafields.append({
                "namespace": self.METAFIELD_DEFINITIONS["rms_categoria"].namespace,
                "key": self.METAFIELD_DEFINITIONS["rms_categoria"].key,
                "type": self.METAFIELD_DEFINITIONS["rms_categoria"].type.value,
                "value": categoria
            })
        
        # Metafield talla normalizada
        if talla_normalizada:
            metafields.append({
                "namespace": self.METAFIELD_DEFINITIONS["rms_talla"].namespace,
                "key": self.METAFIELD_DEFINITIONS["rms_talla"].key,
                "type": self.METAFIELD_DEFINITIONS["rms_talla"].type.value,
                "value": talla_normalizada
            })
        
        # Metafield talla original (si es diferente)
        if talla_original and talla_original != talla_normalizada:
            metafields.append({
                "namespace": self.METAFIELD_DEFINITIONS["rms_talla_original"].namespace,
                "key": self.METAFIELD_DEFINITIONS["rms_talla_original"].key,
                "type": self.METAFIELD_DEFINITIONS["rms_talla_original"].type.value,
                "value": talla_original
            })
        
        # Metafield color
        if color:
            metafields.append({
                "namespace": self.METAFIELD_DEFINITIONS["rms_color"].namespace,
                "key": self.METAFIELD_DEFINITIONS["rms_color"].key,
                "type": self.METAFIELD_DEFINITIONS["rms_color"].type.value,
                "value": color
            })
        
        # Categoría extendida
        extended_category = f"{familia} > {categoria}" if familia and categoria else familia or categoria
        if extended_category:
            metafields.append({
                "namespace": self.METAFIELD_DEFINITIONS["rms_extended_category"].namespace,
                "key": self.METAFIELD_DEFINITIONS["rms_extended_category"].key,
                "type": self.METAFIELD_DEFINITIONS["rms_extended_category"].type.value,
                "value": extended_category
            })
        
        # Atributos estructurados en JSON
        attributes = {
            "familia": familia,
            "categoria": categoria,
            "talla": talla_normalizada,
            "talla_original": talla_original,
            "color": color,
            "extended_category": extended_category
        }
        
        # Agregar datos adicionales
        if additional_data:
            attributes.update(additional_data)
        
        # Remover valores vacíos
        attributes = {k: v for k, v in attributes.items() if v}
        
        if attributes:
            metafields.append({
                "namespace": self.METAFIELD_DEFINITIONS["rms_product_attributes"].namespace,
                "key": self.METAFIELD_DEFINITIONS["rms_product_attributes"].key,
                "type": self.METAFIELD_DEFINITIONS["rms_product_attributes"].type.value,
                "value": attributes
            })
        
        return metafields
    
    def get_search_terms_for_taxonomy_resolution(self, familia: str, categoria: str) -> List[str]:
        """
        Obtiene términos de búsqueda para resolver taxonomía en Shopify.
        
        Args:
            familia: Familia RMS
            categoria: Categoría RMS
            
        Returns:
            Lista de términos de búsqueda ordenados por prioridad
        """
        mapping = self.get_taxonomy_mapping(familia, categoria)
        
        # Combinar términos específicos y generales
        search_terms = mapping.search_terms.copy()
        
        # Agregar términos alternativos basados en familia
        familia_mapping = self.FAMILIA_TO_SHOPIFY_MAPPING.get(familia, {})
        familia_terms = familia_mapping.get("search_terms", [])
        
        # Evitar duplicados manteniendo orden
        for term in familia_terms:
            if term not in search_terms:
                search_terms.append(term)
        
        return search_terms
    
    def validate_metafield_value(self, metafield_type: MetafieldType, value: Any) -> bool:
        """
        Valida que un valor sea compatible con el tipo de metafield.
        
        Args:
            metafield_type: Tipo de metafield
            value: Valor a validar
            
        Returns:
            True si el valor es válido
        """
        if value is None:
            return False
            
        try:
            if metafield_type == MetafieldType.SINGLE_LINE_TEXT:
                return isinstance(value, str) and len(value.strip()) > 0
            elif metafield_type == MetafieldType.NUMBER_INTEGER:
                return isinstance(value, int) or (isinstance(value, str) and value.isdigit())
            elif metafield_type == MetafieldType.JSON:
                return isinstance(value, (dict, list))
            else:
                return isinstance(value, str) and len(value.strip()) > 0
        except Exception:
            return False