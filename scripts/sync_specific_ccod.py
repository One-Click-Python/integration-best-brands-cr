#!/usr/bin/env python3
"""
Script para sincronizar un CCOD específico desde RMS a Shopify.
Útil para diagnóstico y sincronización manual de productos específicos.
"""

import asyncio
import sys
import os
import argparse

# Agregar el directorio padre al path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.rms_to_shopify import sync_rms_to_shopify


async def sync_specific_ccod(ccod: str, force_update: bool = True):
    """
    Sincroniza un CCOD específico.
    
    Args:
        ccod: El CCOD del producto a sincronizar
        force_update: Si forzar la actualización aunque el producto exista
    """
    print(f"\n{'='*60}")
    print(f"Sincronizando CCOD específico: {ccod}")
    print(f"Force update: {force_update}")
    print(f"{'='*60}\n")
    
    try:
        # Ejecutar sincronización con el CCOD específico
        result = await sync_rms_to_shopify(
            force_update=force_update,
            batch_size=1,  # Procesar de uno en uno para mejor debugging
            ccod=ccod,
            include_zero_stock=False  # No incluir variantes sin stock
        )
        
        print(f"\n{'='*60}")
        print("RESULTADO DE LA SINCRONIZACIÓN:")
        print(f"{'='*60}")
        print(f"Sync ID: {result.get('sync_id')}")
        print(f"\nEstadísticas:")
        stats = result.get('statistics', {})
        print(f"  - Total procesados: {stats.get('total_processed', 0)}")
        print(f"  - Creados: {stats.get('created', 0)}")
        print(f"  - Actualizados: {stats.get('updated', 0)}")
        print(f"  - Saltados: {stats.get('skipped', 0)}")
        print(f"  - Errores: {stats.get('errors', 0)}")
        print(f"  - Inventario actualizado: {stats.get('inventory_updated', 0)}")
        
        if result.get('errors'):
            print(f"\n⚠️ Errores encontrados:")
            print(result.get('errors'))
            
        if result.get('recommendations'):
            print(f"\n💡 Recomendaciones:")
            for rec in result.get('recommendations', []):
                print(f"  - {rec}")
                
        print(f"\n✅ Sincronización completada")
        print(f"{'='*60}\n")
        
        return result
        
    except Exception as e:
        print(f"\n❌ Error durante la sincronización: {e}")
        print(f"{'='*60}\n")
        raise


def main():
    """Función principal del script."""
    parser = argparse.ArgumentParser(
        description='Sincronizar un CCOD específico desde RMS a Shopify'
    )
    parser.add_argument(
        'ccod',
        type=str,
        help='El CCOD del producto a sincronizar (ej: 27DL81)'
    )
    parser.add_argument(
        '--no-force',
        action='store_true',
        help='No forzar actualización si el producto ya existe'
    )
    
    args = parser.parse_args()
    
    # Ejecutar sincronización
    asyncio.run(sync_specific_ccod(
        ccod=args.ccod.upper(),
        force_update=not args.no_force
    ))


if __name__ == "__main__":
    main()