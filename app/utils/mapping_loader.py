"""
Utilidad para cargar y gestionar mapeos desde archivos JSON.

Este módulo proporciona una forma eficiente de cargar mapeos de configuración,
como el de categorías RMS a colecciones de Shopify, y los cachea en memoria
para un acceso rápido y evitar lecturas repetidas del disco.
"""

import json
import logging
from functools import lru_cache
from pathlib import Path
from typing import Dict, Optional

logger = logging.getLogger(__name__)

# Ruta base del proyecto
BASE_DIR = Path(__file__).resolve().parent.parent.parent
CONFIG_FILE_PATH = BASE_DIR / "config" / "category_collection_mapping.json"


@lru_cache(maxsize=1)
def get_category_to_collection_map() -> Dict[str, str]:
    """
    Carga el mapeo de categorías RMS a colecciones de Shopify desde el archivo JSON.

    Lee el archivo de configuración, lo invierte para un acceso O(1) y lo cachea.

    El formato esperado del JSON es:
    {
        "Nombre Coleccion Shopify": ["Categoria RMS 1", "Categoria RMS 2"],
        ...
    }

    Retorna:
        Un diccionario mapeando cada categoría de RMS a su colección de Shopify.
        Ej: {"Categoria RMS 1": "Nombre Coleccion Shopify", "Categoria RMS 2": "Nombre Coleccion Shopify"}
    """
    if not CONFIG_FILE_PATH.is_file():
        logger.warning(f"Archivo de mapeo de colecciones no encontrado en: {CONFIG_FILE_PATH}")
        return {}

    try:
        with open(CONFIG_FILE_PATH, "r", encoding="utf-8") as f:
            mapping_data = json.load(f)

        # Invertir el mapa para búsqueda rápida de categoría -> colección
        inverted_map: Dict[str, str] = {}
        for collection_name, rms_categories in mapping_data.items():
            if isinstance(rms_categories, list):
                for category in rms_categories:
                    inverted_map[category] = collection_name

        logger.info(f"Mapeo de colecciones cargado exitosamente. {len(inverted_map)} categorías mapeadas.")
        return inverted_map

    except (json.JSONDecodeError, IOError) as e:
        logger.error(f"Error cargando o procesando el archivo de mapeo de colecciones: {e}")
        return {}


def find_collection_for_category(rms_category: str) -> Optional[str]:
    """
    Busca el nombre de la colección de Shopify para una categoría RMS dada.

    Args:
        rms_category: El nombre de la categoría de RMS.

    Returns:
        El nombre de la colección de Shopify si se encuentra en el mapeo, de lo contrario None.
    """
    if not rms_category:
        return None

    category_map = get_category_to_collection_map()
    return category_map.get(rms_category)
