"""
Utilidades compartidas para Shopify.

Este módulo contiene funciones utilitarias que son usadas por múltiples
servicios para generar handles, normalizar datos, etc.
"""

import re
from typing import Optional


def generate_shopify_handle(ccod: str, family: Optional[str] = None) -> str:
    """
    Genera un handle determinístico para Shopify basado en CCOD.

    Handle format: {ccod}-{family_prefix}

    Args:
        ccod: CCOD del producto (requerido)
        family: Familia del producto (opcional, para contexto adicional)

    Returns:
        str: Handle válido para Shopify (max 100 chars)

    Examples:
        >>> generate_shopify_handle("26XJ05")
        '26xj05'
        >>> generate_shopify_handle("26XJ05", "Zapatos")
        '26xj05-zapatos'
        >>> generate_shopify_handle("26XJ05", "Zapatos Deportivos")
        '26xj05-zapatos-de'
    """
    if not ccod:
        raise ValueError("CCOD is required for handle generation")

    # Normalizar CCOD: lowercase, remover espacios, caracteres especiales
    handle = ccod.strip().lower()
    handle = re.sub(r"[^a-z0-9-]", "-", handle)
    handle = re.sub(r"-+", "-", handle)  # Remover múltiples guiones
    handle = handle.strip("-")  # Remover guiones al inicio/final

    # Agregar prefijo de familia si se proporciona
    if family and family.strip():
        # Normalizar familia: lowercase, solo primeras 10 letras
        family_prefix = family.lower().replace(" ", "-")[:10]
        family_prefix = re.sub(r"[^a-z0-9-]", "-", family_prefix)
        family_prefix = re.sub(r"-+", "-", family_prefix)
        family_prefix = family_prefix.strip("-")

        if family_prefix:
            handle = f"{handle}-{family_prefix}"

    # Shopify handle limit is 100 characters
    return handle[:100]


def normalize_size(size: str) -> str:
    """
    Normaliza una talla para consistencia.

    Args:
        size: Talla a normalizar

    Returns:
        str: Talla normalizada

    Examples:
        >>> normalize_size("23½")
        '23.5'
        >>> normalize_size(" XL ")
        'XL'
        >>> normalize_size("23 1/2")
        '23.5'
    """
    if not size:
        return ""

    # Trim espacios
    normalized = size.strip()

    # Convertir fracciones Unicode a decimales
    normalized = normalized.replace("½", ".5")
    normalized = normalized.replace("¼", ".25")
    normalized = normalized.replace("¾", ".75")

    # Convertir fracciones textuales
    normalized = normalized.replace(" 1/2", ".5")
    normalized = normalized.replace(" 1/4", ".25")
    normalized = normalized.replace(" 3/4", ".75")

    # Limpiar espacios múltiples
    normalized = re.sub(r"\s+", " ", normalized)

    return normalized.strip()
