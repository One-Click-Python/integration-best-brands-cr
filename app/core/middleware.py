"""
Configuración de Middleware para la aplicación FastAPI.

Este módulo centraliza toda la configuración de middleware incluyendo:
- CORS
- TrustedHost
- Request logging
- Rate limiting
- Security headers
"""

import logging
import time
from datetime import datetime, timezone

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse

from app.core.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)


def configure_cors_middleware(app: FastAPI) -> None:
    """
    Configura middleware CORS para permitir requests cross-origin.

    Args:
        app: Instancia de FastAPI
    """
    allowed_origins = settings.ALLOWED_HOSTS or ["*"]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
        allow_headers=[
            "Accept",
            "Accept-Language",
            "Content-Language",
            "Content-Type",
            "Authorization",
            "X-API-Key",
            "X-Request-ID",
        ],
        expose_headers=[
            "X-Process-Time",
            "X-Request-ID",
            "X-Rate-Limit-Remaining",
            "X-Rate-Limit-Reset",
        ],
    )

    logger.info(f"✅ CORS configurado - Origins permitidos: {allowed_origins}")


def configure_trusted_host_middleware(app: FastAPI) -> None:
    """
    Configura middleware TrustedHost para validar hosts permitidos.
    Solo se aplica en producción.

    Args:
        app: Instancia de FastAPI
    """
    if not settings.DEBUG and settings.ALLOWED_HOSTS:
        allowed_hosts = settings.ALLOWED_HOSTS + ["localhost", "127.0.0.1"]

        app.add_middleware(TrustedHostMiddleware, allowed_hosts=allowed_hosts)

        logger.info(f"✅ TrustedHost configurado - Hosts permitidos: {allowed_hosts}")


def configure_request_logging_middleware(app: FastAPI) -> None:
    """
    Configura middleware para logging de todas las requests/responses.

    Args:
        app: Instancia de FastAPI
    """

    @app.middleware("http")
    async def log_requests_middleware(request: Request, call_next):
        """
        Middleware que loggea información de cada request/response.

        Args:
            request: Request de FastAPI
            call_next: Siguiente middleware en la cadena

        Returns:
            Response con headers adicionales
        """
        logger.info("🔧 Configurando middleware de request logging", request)
        # Generar ID único para la request
        request_id = generate_request_id()

        # Información de la request
        start_time = time.time()
        client_ip = get_client_ip(request)
        user_agent = request.headers.get("user-agent", "unknown")

        # Log de entrada
        logger.info(
            f"📨 [{request_id}] {request.method} {request.url.path} - "
            f"Client: {client_ip} - "
            f"User-Agent: {user_agent[:100]}..."
        )

        # Log de query params si existen
        if request.url.query:
            logger.debug(f"🔍 [{request_id}] Query params: {request.url.query}")

        try:
            # Procesar request
            response = await call_next(request)

            # Calcular tiempo de procesamiento
            process_time = time.time() - start_time

            # Log de salida
            status_emoji = get_status_emoji(response.status_code)
            logger.info(
                f"{status_emoji} [{request_id}] {request.method} {request.url.path} - "
                f"Status: {response.status_code} - "
                f"Time: {process_time:.3f}s"
            )

            # Agregar headers informativos
            response.headers["X-Process-Time"] = f"{process_time:.3f}"
            response.headers["X-Request-ID"] = request_id

            # Log de warning para requests lentas
            if process_time > settings.SLOW_REQUEST_THRESHOLD:
                logger.warning(
                    f"🐌 [{request_id}] Slow request detected: {process_time:.3f}s > {settings.SLOW_REQUEST_THRESHOLD}s"
                )

            return response

        except Exception as e:
            # Log de error
            process_time = time.time() - start_time
            logger.error(
                f"❌ [{request_id}] {request.method} {request.url.path} - Error: {str(e)} - Time: {process_time:.3f}s"
            )
            raise


def configure_security_headers_middleware(app: FastAPI) -> None:
    """
    Configura middleware para agregar headers de seguridad.

    Args:
        app: Instancia de FastAPI
    """

    @app.middleware("http")
    async def security_headers_middleware(request: Request, call_next):
        """
        Middleware que agrega headers de seguridad a todas las responses.

        Args:
            request: Request de FastAPI
            call_next: Siguiente middleware en la cadena

        Returns:
            Response con headers de seguridad
        """
        response = await call_next(request)

        # Headers de seguridad
        security_headers = {
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "X-XSS-Protection": "1; mode=block",
            "Referrer-Policy": "strict-origin-when-cross-origin",
            "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
        }

        # Solo agregar HSTS en producción con HTTPS
        if not settings.DEBUG and request.url.scheme == "https":
            security_headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

        # Aplicar headers
        for header, value in security_headers.items():
            response.headers[header] = value

        return response


def configure_rate_limiting_middleware(app: FastAPI) -> None:
    """
    Configura middleware básico de rate limiting.
    Para producción se recomienda usar Redis + slowapi.

    Args:
        app: Instancia de FastAPI
    """
    if not settings.ENABLE_RATE_LIMITING:
        return

    # Cache simple en memoria para desarrollo
    # En producción usar Redis
    request_cache = {}

    @app.middleware("http")
    async def rate_limiting_middleware(request: Request, call_next):
        """
        Middleware básico de rate limiting.

        Args:
            request: Request de FastAPI
            call_next: Siguiente middleware en la cadena

        Returns:
            Response o error 429 si excede límite
        """
        client_ip = get_client_ip(request)
        current_time = time.time()

        # Limpiar cache antiguo (cada 5 minutos)
        cleanup_time = current_time - 300
        nonlocal request_cache
        cleaned_cache = {
            ip: requests
            for ip, requests in request_cache.items()
            if any(req_time > cleanup_time for req_time in requests)
        }
        request_cache.clear()
        request_cache.update(cleaned_cache)

        # Verificar requests del cliente
        if client_ip not in request_cache:
            request_cache[client_ip] = []

        # Filtrar requests del último minuto
        minute_ago = current_time - 60
        recent_requests = [req_time for req_time in request_cache[client_ip] if req_time > minute_ago]

        # Verificar límite
        if len(recent_requests) >= settings.RATE_LIMIT_PER_MINUTE:
            logger.warning(f"🚫 Rate limit exceeded for {client_ip}: {len(recent_requests)} requests in last minute")

            return JSONResponse(
                status_code=429,
                content={
                    "error": "Rate limit exceeded",
                    "message": f"Maximum {settings.RATE_LIMIT_PER_MINUTE} requests per minute allowed",
                    "retry_after": 60,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
                headers={
                    "Retry-After": "60",
                    "X-Rate-Limit-Limit": str(settings.RATE_LIMIT_PER_MINUTE),
                    "X-Rate-Limit-Remaining": "0",
                    "X-Rate-Limit-Reset": str(int(current_time + 60)),
                },
            )

        # Registrar request actual
        request_cache[client_ip] = recent_requests + [current_time]

        # Procesar request
        response = await call_next(request)

        # Agregar headers de rate limiting
        remaining = settings.RATE_LIMIT_PER_MINUTE - len(request_cache[client_ip])
        response.headers["X-Rate-Limit-Limit"] = str(settings.RATE_LIMIT_PER_MINUTE)
        response.headers["X-Rate-Limit-Remaining"] = str(max(0, remaining))
        response.headers["X-Rate-Limit-Reset"] = str(int(current_time + 60))

        return response


def configure_all_middleware(app: FastAPI) -> None:
    """
    Configura todos los middlewares de la aplicación.
    El orden importa: se ejecutan en orden inverso al que se agregan.

    Args:
        app: Instancia de FastAPI
    """
    logger.info("🔧 Configurando middlewares...")

    # 1. Rate limiting (primero en ejecutarse)
    configure_rate_limiting_middleware(app)

    # 2. Security headers
    configure_security_headers_middleware(app)

    # 3. Request logging
    configure_request_logging_middleware(app)

    # 4. TrustedHost (solo producción)
    configure_trusted_host_middleware(app)

    # 5. CORS (último en agregarse, primero en ejecutarse para OPTIONS)
    configure_cors_middleware(app)

    logger.info("✅ Todos los middlewares configurados correctamente")


# Funciones auxiliares


def generate_request_id() -> str:
    """
    Genera un ID único para cada request.

    Returns:
        str: ID único de 8 caracteres
    """
    import uuid

    return str(uuid.uuid4())[:8]


def get_client_ip(request: Request) -> str:
    """
    Obtiene la IP real del cliente considerando proxies.

    Args:
        request: Request de FastAPI

    Returns:
        str: IP del cliente
    """
    # Verificar headers de proxy
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        # Tomar la primera IP en caso de múltiples proxies
        return forwarded_for.split(",")[0].strip()

    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip

    # Fallback a la IP directa
    if request.client:
        return request.client.host

    return "unknown"


def get_status_emoji(status_code: int) -> str:
    """
    Obtiene emoji apropiado según el código de estado HTTP.

    Args:
        status_code: Código de estado HTTP

    Returns:
        str: Emoji representativo
    """
    if 200 <= status_code < 300:
        return "✅"
    elif 300 <= status_code < 400:
        return "↩️"
    elif 400 <= status_code < 500:
        return "⚠️"
    elif 500 <= status_code < 600:
        return "❌"
    else:
        return "📤"
