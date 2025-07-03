#!/usr/bin/env python3
"""
Script para configurar webhooks de Shopify para sincronización automática.

Este script crea los webhooks necesarios en Shopify para que los pedidos
se sincronicen automáticamente con RMS.
"""

import asyncio
import os
from typing import Dict, List

import aiohttp
from app.core.config import get_settings

settings = get_settings()


async def create_webhook(session: aiohttp.ClientSession, webhook_data: Dict) -> Dict:
    """
    Crea un webhook en Shopify.
    
    Args:
        session: Sesión HTTP
        webhook_data: Datos del webhook
        
    Returns:
        Dict: Respuesta de Shopify
    """
    url = f"{settings.SHOPIFY_SHOP_URL}/admin/api/{settings.SHOPIFY_API_VERSION}/webhooks.json"
    headers = {
        "X-Shopify-Access-Token": settings.SHOPIFY_ACCESS_TOKEN,
        "Content-Type": "application/json"
    }
    
    async with session.post(url, json={"webhook": webhook_data}, headers=headers) as response:
        if response.status == 201:
            result = await response.json()
            print(f"✅ Webhook creado exitosamente: {webhook_data['topic']}")
            return result
        else:
            error = await response.text()
            print(f"❌ Error creando webhook {webhook_data['topic']}: {response.status} - {error}")
            return {}


async def list_existing_webhooks(session: aiohttp.ClientSession) -> List[Dict]:
    """
    Lista webhooks existentes en Shopify.
    
    Args:
        session: Sesión HTTP
        
    Returns:
        List[Dict]: Lista de webhooks existentes
    """
    url = f"{settings.SHOPIFY_SHOP_URL}/admin/api/{settings.SHOPIFY_API_VERSION}/webhooks.json"
    headers = {
        "X-Shopify-Access-Token": settings.SHOPIFY_ACCESS_TOKEN,
        "Content-Type": "application/json"
    }
    
    async with session.get(url, headers=headers) as response:
        if response.status == 200:
            result = await response.json()
            return result.get("webhooks", [])
        else:
            print(f"❌ Error listando webhooks: {response.status}")
            return []


async def main():
    """
    Función principal para configurar webhooks.
    """
    print("🔧 Configurando webhooks de Shopify para sincronización con RMS...")
    
    # URL base de tu servicio (cambiar según tu configuración)
    base_url = os.getenv("API_BASE_URL", "https://tu-servidor.com")
    if base_url == "https://tu-servidor.com":
        print("⚠️  ADVERTENCIA: Usando URL de ejemplo. Configura API_BASE_URL en .env")
        base_url = input("Ingresa la URL base de tu servicio (ej: https://tu-servidor.com): ").strip()
    
    webhooks_to_create = [
        {
            "topic": "orders/create",
            "address": f"{base_url}/api/v1/webhooks/order/created",
            "format": "json",
            "fields": [
                "id", "name", "email", "created_at", "updated_at",
                "total_price", "total_tax", "currency", "financial_status",
                "fulfillment_status", "customer", "billing_address", 
                "shipping_address", "line_items"
            ]
        },
        {
            "topic": "orders/updated", 
            "address": f"{base_url}/api/v1/webhooks/order/updated",
            "format": "json",
            "fields": [
                "id", "name", "email", "created_at", "updated_at",
                "total_price", "total_tax", "currency", "financial_status",
                "fulfillment_status", "customer", "billing_address",
                "shipping_address", "line_items"
            ]
        },
        {
            "topic": "orders/paid",
            "address": f"{base_url}/api/v1/webhooks/order/updated", 
            "format": "json",
            "fields": [
                "id", "name", "email", "created_at", "updated_at",
                "total_price", "total_tax", "currency", "financial_status",
                "fulfillment_status", "customer", "billing_address",
                "shipping_address", "line_items"
            ]
        }
    ]
    
    async with aiohttp.ClientSession() as session:
        # Listar webhooks existentes
        print("\n📋 Listando webhooks existentes...")
        existing_webhooks = await list_existing_webhooks(session)
        existing_topics = {wh.get("topic") for wh in existing_webhooks}
        
        if existing_webhooks:
            print(f"Webhooks existentes ({len(existing_webhooks)}):")
            for wh in existing_webhooks:
                print(f"  - {wh.get('topic')}: {wh.get('address')}")
        else:
            print("No hay webhooks configurados actualmente.")
        
        # Crear nuevos webhooks
        print(f"\n🚀 Creando {len(webhooks_to_create)} webhooks...")
        created_count = 0
        
        for webhook_data in webhooks_to_create:
            topic = webhook_data["topic"]
            
            if topic in existing_topics:
                print(f"⏭️  Webhook ya existe: {topic}")
                continue
                
            result = await create_webhook(session, webhook_data)
            if result:
                created_count += 1
        
        print(f"\n✨ Configuración completada: {created_count} webhooks creados")
        
        # Mostrar configuración para verificar
        print(f"\n📝 Configuración aplicada:")
        print(f"Base URL: {base_url}")
        print(f"Shopify Shop: {settings.SHOPIFY_SHOP_URL}")
        print(f"API Version: {settings.SHOPIFY_API_VERSION}")
        
        # Configuración de variables de entorno para pedidos sin cliente
        print(f"\n🔧 Configuración de pedidos sin cliente:")
        print(f"ALLOW_ORDERS_WITHOUT_CUSTOMER: {settings.ALLOW_ORDERS_WITHOUT_CUSTOMER}")
        print(f"DEFAULT_CUSTOMER_ID_FOR_GUEST_ORDERS: {settings.DEFAULT_CUSTOMER_ID_FOR_GUEST_ORDERS}")
        print(f"REQUIRE_CUSTOMER_EMAIL: {settings.REQUIRE_CUSTOMER_EMAIL}")
        
        print(f"\n🎯 Los webhooks enviarán notificaciones a:")
        for webhook_data in webhooks_to_create:
            print(f"  - {webhook_data['topic']} → {webhook_data['address']}")


if __name__ == "__main__":
    asyncio.run(main())