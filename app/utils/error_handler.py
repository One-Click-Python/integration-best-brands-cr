"""
Sistema de manejo de errores personalizado.

Este módulo define todas las excepciones personalizadas de la aplicación
y proporciona utilidades para manejo consistente de errores.
"""

import logging
import traceback
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Union

logger = logging.getLogger(__name__)


class ErrorCode(Enum):
    """
    Códigos de error estandardizados para la aplicación.
    """

    # Errores generales
    UNKNOWN_ERROR = "UNKNOWN_ERROR"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    CONFIGURATION_ERROR = "CONFIGURATION_ERROR"

    # Errores de conexión
    RMS_CONNECTION_FAILED = "RMS_CONNECTION_FAILED"
    RMS_QUERY_FAILED = "RMS_QUERY_FAILED"
    SHOPIFY_CONNECTION_FAILED = "SHOPIFY_CONNECTION_FAILED"
    SHOPIFY_API_ERROR = "SHOPIFY_API_ERROR"
    REDIS_CONNECTION_FAILED = "REDIS_CONNECTION_FAILED"

    # Errores de sincronización
    SYNC_FAILED = "SYNC_FAILED"
    SYNC_TIMEOUT = "SYNC_TIMEOUT"
    SYNC_VALIDATION_FAILED = "SYNC_VALIDATION_FAILED"
    SYNC_MAPPING_ERROR = "SYNC_MAPPING_ERROR"
    SYNC_DUPLICATE_ERROR = "SYNC_DUPLICATE_ERROR"

    # Errores de API
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"
    INVALID_API_KEY = "INVALID_API_KEY"
    INVALID_WEBHOOK_SIGNATURE = "INVALID_WEBHOOK_SIGNATURE"

    # Errores de datos
    INVALID_SKU = "INVALID_SKU"
    INVALID_PRODUCT_DATA = "INVALID_PRODUCT_DATA"
    INVALID_ORDER_DATA = "INVALID_ORDER_DATA"
    MISSING_REQUIRED_FIELD = "MISSING_REQUIRED_FIELD"

    # Errores de sistema
    DISK_SPACE_LOW = "DISK_SPACE_LOW"
    MEMORY_LIMIT_EXCEEDED = "MEMORY_LIMIT_EXCEEDED"
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"


class ErrorSeverity(Enum):
    """
    Niveles de severidad para errores.
    """

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AppException(Exception):
    """
    Excepción base para todas las excepciones personalizadas de la aplicación.
    """

    def __init__(
        self,
        message: str,
        error_code: ErrorCode = ErrorCode.UNKNOWN_ERROR,
        details: Optional[Dict[str, Any]] = None,
        status_code: int = 500,
        severity: ErrorSeverity = ErrorSeverity.MEDIUM,
        is_retryable: bool = False,
        is_critical: bool = False,
    ):
        """
        Inicializa la excepción.

        Args:
            message: Mensaje de error
            error_code: Código de error estandardizado
            details: Información adicional del error
            status_code: Código HTTP asociado
            severity: Severidad del error
            is_retryable: Si la operación puede reintentarse
            is_critical: Si requiere alerta inmediata
        """
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        self.status_code = status_code
        self.severity = severity
        self.is_retryable = is_retryable
        self.is_critical = is_critical
        self.timestamp = datetime.now(timezone.utc)
        self.traceback_str = traceback.format_exc()

    def to_dict(self) -> Dict[str, Any]:
        """
        Convierte la excepción a diccionario.

        Returns:
            Dict: Representación de la excepción
        """
        return {
            "error_type": self.__class__.__name__,
            "message": self.message,
            "error_code": self.error_code.value,
            "details": self.details,
            "status_code": self.status_code,
            "severity": self.severity.value,
            "is_retryable": self.is_retryable,
            "is_critical": self.is_critical,
            "timestamp": self.timestamp.isoformat(),
            "traceback": self.traceback_str,
        }

    def __str__(self) -> str:
        """String representation del error."""
        return f"{self.error_code.value}: {self.message}"


class ValidationException(AppException):
    """
    Excepción para errores de validación de datos.
    """

    def __init__(
        self,
        message: str,
        field: str,
        invalid_value: Any = None,
        expected_format: Optional[str] = None,
        **kwargs,
    ):
        """
        Inicializa la excepción de validación.

        Args:
            message: Mensaje de error
            field: Campo que falló la validación
            invalid_value: Valor que causó el error
            expected_format: Formato esperado
            **kwargs: Argumentos adicionales para AppException
        """
        super().__init__(
            message=message,
            error_code=ErrorCode.VALIDATION_ERROR,
            status_code=422,
            severity=ErrorSeverity.LOW,
            **kwargs,
        )
        self.field = field
        self.invalid_value = invalid_value
        self.expected_format = expected_format

        # Agregar detalles específicos
        self.details.update(
            {
                "field": field,
                "invalid_value": str(invalid_value) if invalid_value is not None else None,
                "expected_format": expected_format,
            }
        )


class RMSConnectionException(AppException):
    """
    Excepción para errores de conexión con RMS.
    """

    def __init__(
        self,
        message: str,
        db_host: Optional[str] = None,
        connection_type: str = "database",
        **kwargs,
    ):
        """
        Inicializa la excepción de conexión RMS.

        Args:
            message: Mensaje de error
            db_host: Host de la base de datos
            connection_type: Tipo de conexión
            **kwargs: Argumentos adicionales para AppException
        """
        super().__init__(
            message=message,
            error_code=ErrorCode.RMS_CONNECTION_FAILED,
            status_code=503,
            severity=ErrorSeverity.HIGH,
            is_retryable=True,
            is_critical=True,
            **kwargs,
        )
        self.db_host = db_host
        self.connection_type = connection_type

        self.details.update({"db_host": db_host, "connection_type": connection_type})


class ShopifyAPIException(AppException):
    """
    Excepción para errores de la API de Shopify.
    """

    def __init__(
        self,
        message: str,
        api_response_code: Optional[int] = None,
        endpoint: Optional[str] = None,
        rate_limited: bool = False,
        retry_after: Optional[int] = None,
        **kwargs,
    ):
        """
        Inicializa la excepción de Shopify API.

        Args:
            message: Mensaje de error
            api_response_code: Código de respuesta de Shopify
            endpoint: Endpoint que falló
            rate_limited: Si es por rate limiting
            retry_after: Segundos para reintentar
            **kwargs: Argumentos adicionales para AppException
        """
        # Determinar código de error y configuración
        error_code = ErrorCode.SHOPIFY_API_ERROR
        is_retryable = True
        severity = ErrorSeverity.MEDIUM

        if rate_limited:
            error_code = ErrorCode.RATE_LIMIT_EXCEEDED
            severity = ErrorSeverity.LOW
        elif api_response_code and api_response_code >= 500:
            severity = ErrorSeverity.HIGH

        super().__init__(
            message=message,
            error_code=error_code,
            status_code=api_response_code or 503,
            severity=severity,
            is_retryable=is_retryable,
            **kwargs,
        )

        self.api_response_code = api_response_code
        self.endpoint = endpoint
        self.rate_limited = rate_limited
        self.retry_after = retry_after

        self.details.update(
            {
                "api_response_code": api_response_code,
                "endpoint": endpoint,
                "rate_limited": rate_limited,
                "retry_after": retry_after,
            }
        )


class SyncException(AppException):
    """
    Excepción para errores de sincronización.
    """

    def __init__(
        self,
        message: str,
        service: str,
        operation: str,
        failed_records: Optional[List[Dict]] = None,
        sync_stats: Optional[Dict[str, Any]] = None,
        retry_suggested: bool = True,
        **kwargs,
    ):
        """
        Inicializa la excepción de sincronización.

        Args:
            message: Mensaje de error
            service: Servicio involucrado (rms, shopify)
            operation: Operación que falló
            failed_records: Registros que fallaron
            sync_stats: Estadísticas de la sincronización
            retry_suggested: Si se sugiere reintentar
            **kwargs: Argumentos adicionales para AppException
        """
        super().__init__(
            message=message,
            error_code=ErrorCode.SYNC_FAILED,
            status_code=500,
            severity=ErrorSeverity.HIGH,
            is_retryable=retry_suggested,
            **kwargs,
        )

        self.service = service
        self.operation = operation
        self.failed_records = failed_records or []
        self.sync_stats = sync_stats or {}
        self.retry_suggested = retry_suggested

        self.details.update(
            {
                "service": service,
                "operation": operation,
                "failed_count": len(self.failed_records),
                "sync_stats": sync_stats,
                "retry_suggested": retry_suggested,
            }
        )


class RateLimitException(AppException):
    """
    Excepción para errores de rate limiting.
    """

    def __init__(self, message: str, limit: int, reset_time: int, retry_after: int, **kwargs):
        """
        Inicializa la excepción de rate limiting.

        Args:
            message: Mensaje de error
            limit: Límite de requests
            reset_time: Timestamp de reset
            retry_after: Segundos para reintentar
            **kwargs: Argumentos adicionales para AppException
        """
        super().__init__(
            message=message,
            error_code=ErrorCode.RATE_LIMIT_EXCEEDED,
            status_code=429,
            severity=ErrorSeverity.LOW,
            is_retryable=True,
            **kwargs,
        )

        self.limit = limit
        self.reset_time = reset_time
        self.retry_after = retry_after

        self.details.update({"limit": limit, "reset_time": reset_time, "retry_after": retry_after})


# === FUNCIONES DE UTILIDAD ===


def handle_exception(
    exception: Exception, context: Optional[Dict[str, Any]] = None, reraise: bool = True
) -> Optional[AppException]:
    """
    Maneja una excepción de manera consistente.

    Args:
        exception: Excepción a manejar
        context: Contexto adicional
        reraise: Si relanzar la excepción

    Returns:
        AppException: Excepción procesada (si no se relanzan)

    Raises:
        AppException: Si reraise=True
    """
    context = context or {}

    # Si ya es una AppException, solo agregar contexto
    if isinstance(exception, AppException):
        exception.details.update(context)
        if reraise:
            raise exception
        return exception

    # Convertir excepciones conocidas
    app_exception = convert_to_app_exception(exception, context)

    # Log del error
    logger.error(
        f"Exception handled: {type(exception).__name__}: {str(exception)}",
        extra={
            "exception_type": type(exception).__name__,
            "exception_message": str(exception),
            "context": context,
            "traceback": traceback.format_exc(),
        },
    )

    if reraise:
        raise app_exception

    return app_exception


def convert_to_app_exception(exception: Exception, context: Optional[Dict[str, Any]] = None) -> AppException:
    """
    Convierte una excepción estándar a AppException.

    Args:
        exception: Excepción a convertir
        context: Contexto adicional

    Returns:
        AppException: Excepción convertida
    """
    context = context or {}
    exception_type = type(exception).__name__
    message = str(exception)

    # Mapear excepciones conocidas
    if "connection" in message.lower() or "timeout" in message.lower():
        if "rms" in message.lower() or "sql" in message.lower():
            return RMSConnectionException(message=f"RMS connection error: {message}", details=context)
        elif "shopify" in message.lower():
            return ShopifyAPIException(message=f"Shopify connection error: {message}", details=context)

    elif "validation" in message.lower() or "invalid" in message.lower():
        return ValidationException(
            message=message,
            field=context.get("field", "unknown"),
            invalid_value=context.get("value"),
            details=context,
        )

    elif "rate limit" in message.lower():
        return RateLimitException(
            message=message,
            limit=context.get("limit", 0),
            reset_time=context.get("reset_time", 0),
            retry_after=context.get("retry_after", 60),
            details=context,
        )

    # Excepción genérica
    return AppException(
        message=f"{exception_type}: {message}",
        details={"original_exception": exception_type, **context},
    )


def create_error_response(exception: Union[AppException, Exception], include_traceback: bool = False) -> Dict[str, Any]:
    """
    Crea respuesta de error estandardizada.

    Args:
        exception: Excepción a convertir
        include_traceback: Si incluir traceback

    Returns:
        Dict: Respuesta de error
    """
    if isinstance(exception, AppException):
        error_dict = exception.to_dict()
    else:
        app_exc = convert_to_app_exception(exception)
        error_dict = app_exc.to_dict()

    # Remover traceback si no se solicita
    if not include_traceback:
        error_dict.pop("traceback", None)

    return {"error": True, **error_dict}


def log_error(
    exception: Exception,
    context: Optional[Dict[str, Any]] = None,
    level: int = logging.ERROR,
) -> None:
    """
    Loggea un error de manera consistente.

    Args:
        exception: Excepción a loggear
        context: Contexto adicional
        level: Nivel de logging
    """
    context = context or {}

    # Preparar datos para log
    log_data = {
        "exception_type": type(exception).__name__,
        "exception_message": str(exception),
        "traceback": traceback.format_exc(),
        **context,
    }

    # Determinar mensaje
    if isinstance(exception, AppException):
        message = f"{exception.error_code.value}: {exception.message}"
        log_data.update(
            {
                "error_code": exception.error_code.value,
                "severity": exception.severity.value,
                "is_retryable": exception.is_retryable,
                "is_critical": exception.is_critical,
            }
        )
    else:
        message = f"Unhandled exception: {type(exception).__name__}: {str(exception)}"

    # Log con nivel apropiado
    logger.log(level, message, extra=log_data)


class ErrorAggregator:
    """
    Agregador de errores para procesos batch.
    """

    def __init__(self):
        """Inicializa el agregador."""
        self.errors: List[AppException] = []
        self.warnings: List[AppException] = []
        self.total_processed = 0
        self.start_time = datetime.now(timezone.utc)

    def add_error(self, exception: Union[AppException, Exception], context: Optional[Dict] = None):
        """
        Agrega un error al agregador.

        Args:
            exception: Excepción a agregar
            context: Contexto adicional
        """
        if not isinstance(exception, AppException):
            exception = convert_to_app_exception(exception, context)

        if exception.severity in [ErrorSeverity.LOW, ErrorSeverity.MEDIUM]:
            self.warnings.append(exception)
        else:
            self.errors.append(exception)

        # Log inmediato para errores críticos
        if exception.is_critical:
            log_error(exception, context, logging.CRITICAL)

    def increment_processed(self):
        """Incrementa contador de procesados."""
        self.total_processed += 1

    def has_errors(self) -> bool:
        """Verifica si hay errores."""
        return len(self.errors) > 0

    def has_warnings(self) -> bool:
        """Verifica si hay warnings."""
        return len(self.warnings) > 0

    def get_summary(self) -> Dict[str, Any]:
        """
        Obtiene resumen de errores.

        Returns:
            Dict: Resumen de errores
        """
        end_time = datetime.now(timezone.utc)
        duration = (end_time - self.start_time).total_seconds()

        return {
            "total_processed": self.total_processed,
            "error_count": len(self.errors),
            "warning_count": len(self.warnings),
            "success_count": self.total_processed - len(self.errors) - len(self.warnings),
            "duration_seconds": duration,
            "start_time": self.start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "errors": [error.to_dict() for error in self.errors],
            "warnings": [warning.to_dict() for warning in self.warnings],
        }

    def raise_if_errors(self):
        """
        Lanza excepción si hay errores críticos.

        Raises:
            SyncException: Si hay errores que impiden continuar
        """
        if self.has_errors():
            critical_errors = [e for e in self.errors if e.is_critical]
            if critical_errors:
                raise SyncException(
                    message=f"Process failed with {len(critical_errors)} critical errors",
                    service="batch_process",
                    operation="aggregate",
                    failed_records=[],
                    sync_stats=self.get_summary(),
                )
