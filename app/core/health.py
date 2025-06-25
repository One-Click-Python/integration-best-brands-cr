"""
Sistema de health checks para monitoreo de servicios.

Este módulo proporciona funciones para verificar el estado de todos los servicios
críticos y dependencias externas de la aplicación.
"""

import asyncio
import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

import psutil

from app.core.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)

# Variable global para tracking de uptime
_app_start_time = datetime.now(timezone.utc)


async def get_health_status() -> Dict[str, Any]:
    """
    Obtiene el estado de salud completo de todos los servicios.

    Returns:
        Dict: Estado de salud completo del sistema
    """
    health_results = {}
    overall_healthy = True

    # Lista de verificaciones de salud
    health_checks = [
        ("rms", check_rms_health),
        ("shopify", check_shopify_health),
        ("redis", check_redis_health),
        ("database", check_database_health),
        ("disk_space", check_disk_space),
        ("memory", check_memory_usage),
        ("cpu", check_cpu_usage),
    ]

    # Ejecutar verificaciones en paralelo
    tasks = []
    for service_name, check_func in health_checks:
        task = asyncio.create_task(
            run_health_check(service_name, check_func),
            name=f"health_check_{service_name}",
        )
        tasks.append(task)

    # Esperar resultados con timeout
    try:
        results = await asyncio.wait_for(
            asyncio.gather(*tasks, return_exceptions=True),
            timeout=settings.HEALTH_CHECK_TIMEOUT,
        )

        # Procesar resultados
        for i, (service_name, _) in enumerate(health_checks):
            result = results[i]
            if isinstance(result, Exception):
                health_results[service_name] = {
                    "status": "unhealthy",
                    "error": str(result),
                    "latency_ms": None,
                }
                overall_healthy = False
            elif isinstance(result, dict):
                health_results[service_name] = result
                if result.get("status") != "healthy":
                    overall_healthy = False
            else:
                # Handle unexpected result type
                health_results[service_name] = {
                    "status": "unhealthy",
                    "error": f"Unexpected result type: {type(result)}",
                    "latency_ms": None,
                }
                overall_healthy = False

    except asyncio.TimeoutError:
        logger.error("Health check timeout exceeded")
        overall_healthy = False
        for service_name, _ in health_checks:
            if service_name not in health_results:
                health_results[service_name] = {
                    "status": "timeout",
                    "error": "Health check timeout",
                    "latency_ms": None,
                }

    return {
        "overall": overall_healthy,
        "services": health_results,
        "uptime": get_uptime_info(),
        "system": get_system_info(),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


async def run_health_check(service_name: str, check_func) -> Dict[str, Any]:
    """
    Ejecuta una verificación de salud individual con medición de latencia.

    Args:
        service_name: Nombre del servicio
        check_func: Función de verificación

    Returns:
        Dict: Resultado de la verificación
    """
    start_time = time.time()

    try:
        result = await check_func()
        latency_ms = (time.time() - start_time) * 1000

        return {
            "status": "healthy" if result else "unhealthy",
            "latency_ms": round(latency_ms, 2),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    except Exception as e:
        latency_ms = (time.time() - start_time) * 1000
        logger.error(f"Health check failed for {service_name}: {e}")

        return {
            "status": "unhealthy",
            "error": str(e),
            "latency_ms": round(latency_ms, 2),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


async def check_rms_health() -> bool:
    """
    Verifica la conectividad con la base de datos RMS.

    Returns:
        bool: True si RMS está disponible
    """
    try:
        from app.db.connection import get_db_connection

        conn_db = get_db_connection()

        # Si no está inicializada, intentar inicializar
        if not conn_db.is_initialized():
            try:
                await conn_db.initialize()
            except Exception as e:
                logger.error(f"Failed to initialize RMS connection for health check: {e}")
                return False

        # Realizar test de conexión
        return await conn_db.test_connection()

    except ImportError:
        logger.warning("RMS connection module not available")
        return False
    except Exception as e:
        logger.error(f"RMS health check failed: {e}")
        return False


async def check_shopify_health() -> bool:
    """
    Verifica la conectividad con la API de Shopify.

    Returns:
        bool: True si Shopify está disponible
    """
    try:
        from app.db.shopify_client import test_shopify_connection

        return await test_shopify_connection()
    except ImportError:
        logger.warning("Shopify client not available")
        return False


async def check_redis_health() -> bool:
    """
    Verifica la conectividad con Redis.

    Returns:
        bool: True si Redis está disponible
    """
    if not settings.REDIS_URL:
        return True  # Redis es opcional

    try:
        from app.core.redis_client import test_redis_connection

        return await test_redis_connection()
    except ImportError:
        logger.warning("Redis client not available")
        return True  # No es crítico


async def check_database_health() -> bool:
    """
    Verificación general de conectividad de base de datos.

    Returns:
        bool: True si las bases de datos están disponibles
    """
    try:
        from app.db.connection import get_db_connection

        conn_db = get_db_connection()

        # Realizar health check completo de la base de datos
        health_info = await conn_db.health_check()

        return health_info.get("test_passed", False) and health_info.get("connection_initialized", False)

    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return False


async def check_disk_space() -> bool:
    """
    Verifica el espacio en disco disponible.

    Returns:
        bool: True si hay suficiente espacio
    """
    try:
        disk_usage = psutil.disk_usage("/")
        free_percent = (disk_usage.free / disk_usage.total) * 100

        # Alerta si queda menos del 10% de espacio
        threshold = settings.DISK_SPACE_THRESHOLD or 10
        return free_percent > threshold

    except Exception as e:
        logger.error(f"Error checking disk space: {e}")
        return True  # No es crítico para la app


async def check_memory_usage() -> bool:
    """
    Verifica el uso de memoria del sistema.

    Returns:
        bool: True si el uso de memoria está dentro de límites
    """
    try:
        memory = psutil.virtual_memory()
        memory_percent = memory.percent

        # Alerta si se usa más del 90% de memoria
        threshold = settings.MEMORY_USAGE_THRESHOLD or 90
        return memory_percent < threshold

    except Exception as e:
        logger.error(f"Error checking memory usage: {e}")
        return True  # No es crítico para la app


async def check_cpu_usage() -> bool:
    """
    Verifica el uso de CPU del sistema.

    Returns:
        bool: True si el uso de CPU está dentro de límites
    """
    try:
        # Promediar durante 1 segundo
        cpu_percent = psutil.cpu_percent(interval=1)

        # Alerta si se usa más del 95% de CPU
        threshold = settings.CPU_USAGE_THRESHOLD or 95
        return cpu_percent < threshold

    except Exception as e:
        logger.error(f"Error checking CPU usage: {e}")
        return True  # No es crítico para la app


def get_uptime_info() -> Dict[str, Any]:
    """
    Obtiene información de uptime de la aplicación.

    Returns:
        Dict: Información de uptime
    """
    current_time = datetime.now(timezone.utc)
    uptime_delta = current_time - _app_start_time

    return {
        "start_time": _app_start_time.isoformat(),
        "current_time": current_time.isoformat(),
        "uptime_seconds": int(uptime_delta.total_seconds()),
        "uptime_human": format_uptime(uptime_delta),
    }


def get_system_info() -> Dict[str, Any]:
    """
    Obtiene información del sistema.

    Returns:
        Dict: Información del sistema
    """
    try:
        # Información básica del sistema
        system_info = {
            "platform": psutil.WINDOWS if psutil.WINDOWS else "unix",
            "python_version": None,  # Se puede agregar si es necesario
            "cpu_count": psutil.cpu_count(),
            "memory_total_gb": round(psutil.virtual_memory().total / (1024**3), 2),
        }

        # Información de CPU
        cpu_percent = psutil.cpu_percent(interval=0.1)
        system_info["cpu_usage_percent"] = cpu_percent

        # Información de memoria
        memory = psutil.virtual_memory()
        system_info["memory_usage_percent"] = memory.percent
        system_info["memory_available_gb"] = round(memory.available / (1024**3), 2)

        # Información de disco
        disk = psutil.disk_usage("/")
        system_info["disk_total_gb"] = round(disk.total / (1024**3), 2)
        system_info["disk_free_gb"] = round(disk.free / (1024**3), 2)
        system_info["disk_usage_percent"] = round(((disk.total - disk.free) / disk.total) * 100, 2)

        return system_info

    except Exception as e:
        logger.error(f"Error getting system info: {e}")
        return {"error": "Unable to retrieve system information"}


def format_uptime(uptime_delta: timedelta) -> str:
    """
    Formatea el uptime en formato legible.

    Args:
        uptime_delta: Delta de tiempo de uptime

    Returns:
        str: Uptime formateado
    """
    days = uptime_delta.days
    hours, remainder = divmod(uptime_delta.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)

    parts = []
    if days:
        parts.append(f"{days}d")
    if hours:
        parts.append(f"{hours}h")
    if minutes:
        parts.append(f"{minutes}m")
    if seconds or not parts:
        parts.append(f"{seconds}s")

    return " ".join(parts)


async def get_service_dependencies() -> List[str]:
    """
    Obtiene lista de servicios críticos para la aplicación.

    Returns:
        List: Lista de servicios críticos
    """
    critical_services = ["rms", "shopify"]

    if settings.REDIS_URL:
        critical_services.append("redis")

    return critical_services


async def is_system_healthy() -> bool:
    """
    Verifica si el sistema está completamente saludable.

    Returns:
        bool: True si todos los servicios críticos están saludables
    """
    health_status = await get_health_status()

    # Verificar servicios críticos
    critical_services = await get_service_dependencies()

    for service in critical_services:
        service_status = health_status["services"].get(service, {})
        if service_status.get("status") != "healthy":
            return False

    return True


def reset_uptime() -> None:
    """
    Resetea el contador de uptime (útil para testing).
    """
    global _app_start_time
    _app_start_time = datetime.now(timezone.utc)
    logger.info("Uptime counter reset")


async def get_detailed_service_health(service_name: str) -> Dict[str, Any]:
    """
    Obtiene información detallada de salud de un servicio específico.

    Args:
        service_name: Nombre del servicio

    Returns:
        Dict: Información detallada del servicio
    """
    health_checks = {
        "rms": check_rms_health,
        "shopify": check_shopify_health,
        "redis": check_redis_health,
        "database": check_database_health,
    }

    check_func = health_checks.get(service_name)
    if not check_func:
        return {
            "error": f"Unknown service: {service_name}",
            "available_services": list(health_checks.keys()),
        }

    # Ejecutar múltiples checks para obtener estadísticas
    results = []
    for i in range(3):
        result = await run_health_check(service_name, check_func)
        results.append(result)
        if i < 2:  # No esperar en la última iteración
            await asyncio.sleep(0.5)

    # Calcular estadísticas
    latencies = [r["latency_ms"] for r in results if r["latency_ms"] is not None]
    statuses = [r["status"] for r in results]

    return {
        "service": service_name,
        "current_status": results[-1]["status"],
        "checks_performed": len(results),
        "success_rate": (statuses.count("healthy") / len(statuses)) * 100,
        "average_latency_ms": round(sum(latencies) / len(latencies), 2) if latencies else None,
        "min_latency_ms": min(latencies) if latencies else None,
        "max_latency_ms": max(latencies) if latencies else None,
        "checks": results,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
