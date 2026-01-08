"""
Configuración avanzada del sistema de logging.

Este módulo configura un sistema de logging robusto con:
- Múltiples handlers (consola, archivo, rotación)
- Formateo personalizado con colores
- Filtros por nivel y módulo
- Logging estructurado para monitoreo
- Integración con sistemas externos
"""

import logging
import logging.config
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from app.core.config import get_settings

settings = get_settings()


class ColoredFormatter(logging.Formatter):
    """
    Formatter personalizado que agrega colores a los logs en consola.
    """

    # Códigos de color ANSI
    COLORS = {
        "DEBUG": "\033[36m",  # Cyan
        "INFO": "\033[32m",  # Verde
        "WARNING": "\033[33m",  # Amarillo
        "ERROR": "\033[31m",  # Rojo
        "CRITICAL": "\033[35m",  # Magenta
        "RESET": "\033[0m",  # Reset
    }

    def format(self, record):
        """
        Formatea el record con colores si es para consola.

        Args:
            record: LogRecord a formatear

        Returns:
            str: Mensaje formateado con colores
        """
        # Formatear el mensaje base
        formatted = super().format(record)

        # Agregar color solo si es TTY (terminal)
        if hasattr(sys.stderr, "isatty") and sys.stderr.isatty():
            color = self.COLORS.get(record.levelname, self.COLORS["RESET"])
            reset = self.COLORS["RESET"]

            # Colorear solo el nivel de log
            formatted = formatted.replace(record.levelname, f"{color}{record.levelname}{reset}")

        return formatted


class StructuredFormatter(logging.Formatter):
    """
    Formatter para logging estructurado en JSON.
    Útil para sistemas de monitoreo como ELK Stack.
    """

    def format(self, record):
        """
        Formatea el record como JSON estructurado.

        Args:
            record: LogRecord a formatear

        Returns:
            str: Mensaje en formato JSON
        """
        import json

        # Datos base del log
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
            "process": record.process,
            "thread": record.thread,
            "app_name": settings.APP_NAME,
            "app_version": settings.APP_VERSION,
            "environment": settings.ENVIRONMENT,
        }

        # Agregar información adicional si existe
        if hasattr(record, "request_id"):
            log_entry["request_id"] = record.request_id  # type: ignore

        if hasattr(record, "user_id"):
            log_entry["user_id"] = record.user_id  # type: ignore

        if hasattr(record, "correlation_id"):
            log_entry["correlation_id"] = record.correlation_id  # type: ignore

        # Agregar información de excepción si existe
        if record.exc_info:
            log_entry["exception"] = {
                "type": record.exc_info[0].__name__,
                "message": str(record.exc_info[1]),
                "traceback": self.formatException(record.exc_info),
            }

        # Agregar campos extra del record
        extra_fields = {}
        for key, value in record.__dict__.items():
            if key not in [
                "name",
                "msg",
                "args",
                "levelname",
                "levelno",
                "pathname",
                "filename",
                "module",
                "exc_info",
                "exc_text",
                "stack_info",
                "lineno",
                "funcName",
                "created",
                "msecs",
                "relativeCreated",
                "thread",
                "threadName",
                "processName",
                "process",
                "message",
            ]:
                extra_fields[key] = value

        if extra_fields:
            log_entry["extra"] = extra_fields

        return json.dumps(log_entry, ensure_ascii=False)


class RequestContextFilter(logging.Filter):
    """
    Filtro que agrega contexto de request a los logs.
    """

    def filter(self, record):
        """
        Agrega información de contexto al record.

        Args:
            record: LogRecord a filtrar

        Returns:
            bool: True para permitir el log
        """
        # Intentar obtener contexto de request actual
        try:
            from contextvars import copy_context

            context = copy_context()

            # Buscar variables de contexto conocidas
            for var_name in ["request_id", "user_id", "correlation_id"]:
                for var in context:
                    if hasattr(var, "name") and var.name == var_name:
                        setattr(record, var_name, context[var])
                        break
        except Exception:
            pass  # No crítico si no hay contexto

        return True


class SyncOperationFilter(logging.Filter):
    """
    Filtro específico para operaciones de sincronización.
    """

    def filter(self, record):
        """
        Agrega información específica de sincronización.

        Args:
            record: LogRecord a filtrar

        Returns:
            bool: True para permitir el log
        """
        # Marcar logs relacionados con sincronización
        sync_modules = ["sync", "shopify", "rms", "webhook"]

        if any(module in record.name.lower() for module in sync_modules):
            record.operation_type = "sync"

            # Agregar timestamp de sync si no existe
            if not hasattr(record, "sync_timestamp"):
                record.sync_timestamp = datetime.now(timezone.utc).isoformat()

        return True


def setup_logging() -> None:
    """
    Configura el sistema de logging completo de la aplicación.
    """
    # Crear directorio de logs si no existe
    if settings.LOG_FILE_PATH:
        log_dir = Path(settings.LOG_FILE_PATH).parent
        log_dir.mkdir(parents=True, exist_ok=True)

    # Configuración de logging
    logging_config = get_logging_configuration()

    # Aplicar configuración
    logging.config.dictConfig(logging_config)

    # Configurar logger raíz
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, settings.LOG_LEVEL))

    # Agregar filtros personalizados
    request_filter = RequestContextFilter()
    sync_filter = SyncOperationFilter()

    for handler in root_logger.handlers:
        handler.addFilter(request_filter)
        handler.addFilter(sync_filter)

    # Configurar loggers específicos
    configure_specific_loggers()

    # Log inicial
    logger = logging.getLogger(__name__)
    logger.info(f"Sistema de logging configurado - Nivel: {settings.LOG_LEVEL}")
    logger.info(f"Logs guardándose en: {settings.LOG_FILE_PATH}")


def get_logging_configuration() -> Dict[str, Any]:
    """
    Genera configuración completa de logging.

    Returns:
        Dict: Configuración de logging
    """
    config = {
        "version": 1,
        "disable_existing_loggers": False,
        # Formatters
        "formatters": {
            "standard": {
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S",
            },
            "detailed": {
                "format": ("%(asctime)s - %(name)s - %(levelname)s - %(module)s.%(funcName)s:%(lineno)d - %(message)s"),
                "datefmt": "%Y-%m-%d %H:%M:%S",
            },
            "colored": {
                "()": ColoredFormatter,
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S",
            },
            "json": {"()": StructuredFormatter},
        },
        # Handlers
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "level": settings.LOG_LEVEL,
                "formatter": "colored" if settings.DEBUG else "standard",
                "stream": "ext://sys.stdout",
            }
        },
        # Loggers
        "loggers": {
            "uvicorn.access": {
                "level": "INFO",
                "handlers": ["console"],
                "propagate": False,
            },
            "uvicorn.error": {
                "level": "INFO",
                "handlers": ["console"],
                "propagate": False,
            },
        },
        # Root logger
        "root": {"level": settings.LOG_LEVEL, "handlers": ["console"]},
    }

    # Agregar handler de archivo si está configurado
    if settings.LOG_FILE_PATH:
        # Handler principal de archivo
        config["handlers"]["file"] = {
            "class": "logging.handlers.RotatingFileHandler",
            "level": settings.LOG_LEVEL,
            "formatter": "detailed",
            "filename": settings.LOG_FILE_PATH,
            "maxBytes": settings.LOG_MAX_SIZE_MB * 1024 * 1024,
            "backupCount": settings.LOG_BACKUP_COUNT,
            "encoding": "utf-8",
        }

        # Handler de errores separado
        error_log_path = settings.LOG_FILE_PATH.replace(".log", "_errors.log")
        config["handlers"]["error_file"] = {
            "class": "logging.handlers.RotatingFileHandler",
            "level": "ERROR",
            "formatter": "detailed",
            "filename": error_log_path,
            "maxBytes": settings.LOG_MAX_SIZE_MB * 1024 * 1024,
            "backupCount": settings.LOG_BACKUP_COUNT,
            "encoding": "utf-8",
        }

        # Handler JSON para monitoreo
        if settings.ENVIRONMENT == "production":
            json_log_path = settings.LOG_FILE_PATH.replace(".log", ".json")
            config["handlers"]["json_file"] = {
                "class": "logging.handlers.RotatingFileHandler",
                "level": "INFO",
                "formatter": "json",
                "filename": json_log_path,
                "maxBytes": settings.LOG_MAX_SIZE_MB * 1024 * 1024,
                "backupCount": settings.LOG_BACKUP_COUNT,
                "encoding": "utf-8",
            }
            config["root"]["handlers"].extend(["json_file"])

        # Agregar handlers al root
        config["root"]["handlers"].extend(["file", "error_file"])

    return config


def configure_specific_loggers() -> None:
    """
    Configura loggers específicos para diferentes módulos.
    """
    # Logger para operaciones de sincronización
    sync_logger = logging.getLogger("app.sync")
    sync_logger.setLevel(logging.DEBUG if settings.DEBUG else logging.INFO)

    # Logger para APIs externas
    api_logger = logging.getLogger("app.api")
    api_logger.setLevel(logging.INFO)

    # Logger para base de datos
    db_logger = logging.getLogger("app.db")
    db_logger.setLevel(logging.WARNING)  # Solo warnings y errores por defecto

    # Logger para webhooks
    webhook_logger = logging.getLogger("app.webhooks")
    webhook_logger.setLevel(logging.INFO)

    # Reducir verbosidad de librerías externas
    external_loggers = [
        "urllib3.connectionpool",
        "requests.packages.urllib3",
        "httpx",
        "sqlalchemy.engine",
        "aiohttp.access",
    ]

    for logger_name in external_loggers:
        logger = logging.getLogger(logger_name)
        logger.setLevel(logging.WARNING)


def get_logger(name: str, **kwargs) -> logging.Logger:
    """
    Obtiene un logger con configuración adicional.

    Args:
        name: Nombre del logger
        **kwargs: Atributos adicionales para el logger

    Returns:
        logging.Logger: Logger configurado
    """
    logger = logging.getLogger(name)

    # Agregar atributos adicionales al logger
    for key, value in kwargs.items():
        setattr(logger, key, value)

    return logger


def log_sync_operation(operation: str, service: str, **kwargs):
    """
    Logger específico para operaciones de sincronización.

    Args:
        operation: Tipo de operación (create, update, delete, etc.)
        service: Servicio involucrado (rms, shopify)
        **kwargs: Datos adicionales
    """
    logger = get_logger("app.sync.operation")

    extra_data = {
        "sync_operation": operation,  # Cambiado de "operation" a "sync_operation"
        "service": service,
        "sync_timestamp": datetime.now(timezone.utc).isoformat(),
        **kwargs,
    }

    # Log con datos estructurados
    logger.info(f"Sync operation: {operation} on {service}", extra=extra_data)


def log_api_call(method: str, url: str, status_code: int, duration: float, **kwargs):
    """
    Logger específico para llamadas a APIs externas.

    Args:
        method: Método HTTP
        url: URL de la API
        status_code: Código de respuesta
        duration: Duración en segundos
        **kwargs: Datos adicionales
    """
    logger = get_logger("app.api.call")

    extra_data = {
        "method": method,
        "url": url,
        "status_code": status_code,
        "duration_ms": round(duration * 1000, 2),
        "api_timestamp": datetime.now(timezone.utc).isoformat(),
        **kwargs,
    }

    # Determinar nivel según status code
    if 200 <= status_code < 300:
        level = logging.INFO
    elif 400 <= status_code < 500:
        level = logging.WARNING
    else:
        level = logging.ERROR

    logger.log(
        level,
        f"API call: {method} {url} -> {status_code} ({duration * 1000:.1f}ms)",
        extra=extra_data,
    )


def log_webhook_received(webhook_type: str, shop: str, **kwargs):
    """
    Logger específico para webhooks recibidos.

    Args:
        webhook_type: Tipo de webhook
        shop: Shop de Shopify
        **kwargs: Datos adicionales
    """
    logger = get_logger("app.webhook.received")

    extra_data = {
        "webhook_type": webhook_type,
        "shop": shop,
        "webhook_timestamp": datetime.now(timezone.utc).isoformat(),
        **kwargs,
    }

    logger.info(f"Webhook received: {webhook_type} from {shop}", extra=extra_data)


class LogContext:
    """
    Context manager para agregar contexto temporal a los logs.
    """

    def __init__(self, **context):
        """
        Inicializa el context manager.

        Args:
            **context: Datos de contexto a agregar
        """
        self.context = context
        self.old_factory = None

    def __enter__(self):
        """Entra al contexto."""
        # Guardar factory anterior
        self.old_factory = logging.getLogRecordFactory()

        # Crear nueva factory que agrega contexto
        def record_factory(*args, **kwargs):
            if self.old_factory:
                record = self.old_factory(*args, **kwargs)
            else:
                record = logging.LogRecord(*args, **kwargs)
            for key, value in self.context.items():
                setattr(record, key, value)
            return record

        # Aplicar nueva factory
        logging.setLogRecordFactory(record_factory)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Sale del contexto."""
        # Restaurar factory anterior
        logging.setLogRecordFactory(self.old_factory)


# Ejemplo de uso del context manager
def sync_with_context(sync_id: str, operation: str):
    """
    Ejemplo de uso de LogContext para operaciones de sync.

    Args:
        sync_id: ID de la sincronización
        operation: Tipo de operación
    """
    with LogContext(sync_id=sync_id, operation=operation):
        logger = logging.getLogger("app.sync")
        logger.info("Iniciando sincronización")  # Incluirá sync_id y operation
        # ... lógica de sync ...
        logger.info("Sincronización completada")


def configure_external_logging():
    """
    Configura logging para librerías externas.
    """
    # Configurar SQLAlchemy
    sqlalchemy_logger = logging.getLogger("sqlalchemy.engine")
    if settings.DEBUG:
        sqlalchemy_logger.setLevel(logging.INFO)  # Mostrar queries en debug
    else:
        sqlalchemy_logger.setLevel(logging.WARNING)

    # Configurar requests/httpx
    requests_logger = logging.getLogger("urllib3.connectionpool")
    requests_logger.setLevel(logging.WARNING)

    # Configurar Uvicorn
    uvicorn_logger = logging.getLogger("uvicorn")
    uvicorn_logger.setLevel(logging.INFO)


# Inicializar configuración si se importa directamente
if __name__ != "__main__":
    configure_external_logging()
