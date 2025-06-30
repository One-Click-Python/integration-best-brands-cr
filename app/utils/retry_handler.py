"""
Sistema de manejo de reintentos y circuit breaker.

Este módulo implementa estrategias sofisticadas de retry con backoff exponencial,
circuit breaker pattern y manejo específico para diferentes tipos de errores.
"""

import asyncio
import logging
import random
import time
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Type

from app.core.config import get_settings
from app.utils.error_handler import (
    AppException,
    RateLimitException,
    ShopifyAPIException,
)

settings = get_settings()
logger = logging.getLogger(__name__)


class CircuitState(Enum):
    """Estados del circuit breaker."""

    CLOSED = "closed"  # Funcionamiento normal
    OPEN = "open"  # Circuito abierto, fallar rápido
    HALF_OPEN = "half_open"  # Probando si se recuperó


class RetryPolicy:
    """
    Política de reintentos configurable.
    """

    def __init__(
        self,
        max_attempts: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        exponential_base: float = 2.0,
        jitter: bool = True,
        retry_on: Optional[List[Type[Exception]]] = None,
        stop_on: Optional[List[Type[Exception]]] = None,
    ):
        """
        Inicializa la política de reintentos.

        Args:
            max_attempts: Número máximo de intentos
            base_delay: Delay base en segundos
            max_delay: Delay máximo en segundos
            exponential_base: Base para backoff exponencial
            jitter: Si agregar jitter aleatorio
            retry_on: Excepciones en las que reintentar
            stop_on: Excepciones que detienen inmediatamente
        """
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter
        self.retry_on = retry_on or [AppException]
        self.stop_on = stop_on or []

    def should_retry(self, exception: Exception, attempt: int) -> bool:
        """
        Determina si debe reintentar la operación.

        Args:
            exception: Excepción que ocurrió
            attempt: Número de intento actual

        Returns:
            bool: True si debe reintentar
        """
        # Verificar límite de intentos
        if attempt >= self.max_attempts:
            return False

        # Verificar excepciones que detienen
        for stop_exc in self.stop_on:
            if isinstance(exception, stop_exc):
                return False

        # Verificar excepciones retryables
        if isinstance(exception, AppException):
            return exception.is_retryable

        # Verificar si está en la lista de retry
        for retry_exc in self.retry_on:
            if isinstance(exception, retry_exc):
                return True

        return False

    def calculate_delay(self, attempt: int, exception: Optional[Exception] = None) -> float:
        """
        Calcula el delay antes del siguiente intento.

        Args:
            attempt: Número de intento
            exception: Excepción que causó el retry (opcional)

        Returns:
            float: Segundos a esperar
        """
        # Delay específico para rate limiting
        if isinstance(exception, (RateLimitException, ShopifyAPIException)):
            if hasattr(exception, "retry_after") and exception.retry_after:
                return min(exception.retry_after, self.max_delay)

        # Backoff exponencial
        delay = self.base_delay * (self.exponential_base ** (attempt - 1))

        # Aplicar jitter
        if self.jitter:
            jitter_range = delay * 0.1
            delay += random.uniform(-jitter_range, jitter_range)

        # Limitar delay máximo
        delay = min(delay, self.max_delay)

        return max(delay, 0)


class CircuitBreaker:
    """
    Implementa el patrón Circuit Breaker para prevenir cascadas de fallas.
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        success_threshold: int = 3,
        timeout: float = 60.0,
        reset_timeout: float = 300.0,
    ):
        """
        Inicializa el circuit breaker.

        Args:
            failure_threshold: Fallas consecutivas para abrir circuito
            success_threshold: Éxitos necesarios para cerrar circuito
            timeout: Timeout para operaciones individuales
            reset_timeout: Tiempo antes de intentar half-open
        """
        self.failure_threshold = failure_threshold
        self.success_threshold = success_threshold
        self.timeout = timeout
        self.reset_timeout = reset_timeout

        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[datetime] = None
        self.last_success_time: Optional[datetime] = None

    def can_execute(self) -> bool:
        """
        Determina si la operación puede ejecutarse.

        Returns:
            bool: True si puede ejecutarse
        """
        now = datetime.now(timezone.utc)

        if self.state == CircuitState.CLOSED:
            return True

        elif self.state == CircuitState.OPEN:
            # Verificar si es tiempo de probar half-open
            if self.last_failure_time and now - self.last_failure_time >= timedelta(seconds=self.reset_timeout):
                self.state = CircuitState.HALF_OPEN
                self.success_count = 0
                logger.info("Circuit breaker moving to HALF_OPEN state")
                return True
            return False

        elif self.state == CircuitState.HALF_OPEN:
            return True

        return False

    def record_success(self):
        """Registra una ejecución exitosa."""
        self.last_success_time = datetime.now(timezone.utc)
        self.failure_count = 0

        if self.state == CircuitState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= self.success_threshold:
                self.state = CircuitState.CLOSED
                logger.info("Circuit breaker CLOSED - service recovered")

    def record_failure(self):
        """Registra una falla."""
        self.last_failure_time = datetime.now(timezone.utc)
        self.failure_count += 1

        if self.state == CircuitState.CLOSED:
            if self.failure_count >= self.failure_threshold:
                self.state = CircuitState.OPEN
                logger.warning(f"Circuit breaker OPEN - {self.failure_count} consecutive failures")

        elif self.state == CircuitState.HALF_OPEN:
            self.state = CircuitState.OPEN
            logger.warning("Circuit breaker OPEN again - test failed")

    def get_state_info(self) -> Dict[str, Any]:
        """
        Obtiene información del estado del circuit breaker.

        Returns:
            Dict: Estado actual
        """
        return {
            "state": self.state.value,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "last_failure": self.last_failure_time.isoformat() if self.last_failure_time else None,
            "last_success": self.last_success_time.isoformat() if self.last_success_time else None,
            "failure_threshold": self.failure_threshold,
            "success_threshold": self.success_threshold,
        }


class RetryHandler:
    """
    Manejador principal de reintentos con circuit breaker integrado.
    """

    def __init__(
        self,
        name: str,
        retry_policy: Optional[RetryPolicy] = None,
        circuit_breaker: Optional[CircuitBreaker] = None,
        enable_circuit_breaker: bool = True,
    ):
        """
        Inicializa el manejador de reintentos.

        Args:
            name: Nombre identificativo del handler
            retry_policy: Política de reintentos
            circuit_breaker: Circuit breaker personalizado
            enable_circuit_breaker: Si habilitar circuit breaker
        """
        self.name = name
        self.retry_policy = retry_policy or RetryPolicy()

        if enable_circuit_breaker:
            self.circuit_breaker = circuit_breaker or CircuitBreaker()
        else:
            self.circuit_breaker = None

        self.metrics = {
            "total_attempts": 0,
            "total_successes": 0,
            "total_failures": 0,
            "total_retries": 0,
            "avg_duration": 0.0,
        }

    async def execute(self, func: Callable, *args, context: Optional[Dict[str, Any]] = None, **kwargs) -> Any:
        """
        Ejecuta una función con reintentos y circuit breaker.

        Args:
            func: Función a ejecutar
            *args: Argumentos posicionales
            context: Contexto adicional para logging
            **kwargs: Argumentos con nombre

        Returns:
            Any: Resultado de la función

        Raises:
            Exception: La última excepción si todos los reintentos fallan
        """
        context = context or {}
        start_time = time.time()
        last_exception = None

        # Verificar circuit breaker
        if self.circuit_breaker and not self.circuit_breaker.can_execute():
            raise AppException(
                message=f"Circuit breaker is OPEN for {self.name}",
                details={"circuit_state": self.circuit_breaker.state.value, "context": context},
            )

        for attempt in range(1, self.retry_policy.max_attempts + 1):
            self.metrics["total_attempts"] += 1

            try:
                logger.debug(
                    f"Executing {self.name} - Attempt {attempt}/{self.retry_policy.max_attempts}",
                    extra={"context": context},
                )

                # Ejecutar con timeout si hay circuit breaker
                if self.circuit_breaker:
                    result = await asyncio.wait_for(
                        self._execute_func(func, *args, **kwargs), timeout=self.circuit_breaker.timeout
                    )
                else:
                    result = await self._execute_func(func, *args, **kwargs)

                # Registrar éxito
                duration = time.time() - start_time
                self._record_success(duration)

                if self.circuit_breaker:
                    self.circuit_breaker.record_success()

                logger.debug(
                    f"Successfully executed {self.name} in {duration:.2f}s",
                    extra={"attempt": attempt, "context": context},
                )

                return result

            except asyncio.TimeoutError:
                last_exception = AppException(
                    message=f"Operation {self.name} timed out",
                    details={"timeout": self.circuit_breaker.timeout if self.circuit_breaker else "unknown"},
                )
                self._record_failure()
                if self.circuit_breaker:
                    self.circuit_breaker.record_failure()

            except Exception as e:
                last_exception = e
                self._record_failure()
                if self.circuit_breaker:
                    self.circuit_breaker.record_failure()

                # Verificar si debe reintentar
                if not self.retry_policy.should_retry(e, attempt):
                    logger.warning(
                        f"Not retrying {self.name} - Exception: {type(e).__name__}: {str(e)}",
                        extra={"attempt": attempt, "context": context},
                    )
                    break

                # Si no es el último intento, esperar antes del retry
                if attempt < self.retry_policy.max_attempts:
                    delay = self.retry_policy.calculate_delay(attempt, e)
                    self.metrics["total_retries"] += 1

                    logger.info(
                        f"Retrying {self.name} in {delay:.2f}s - "
                        f"Attempt {attempt + 1}/{self.retry_policy.max_attempts}",
                        extra={"exception": str(e), "delay": delay, "context": context},
                    )

                    await asyncio.sleep(delay)

        # Todos los reintentos fallaron
        self._record_failure()

        logger.error(
            f"All retry attempts failed for {self.name}",
            extra={
                "attempts": self.retry_policy.max_attempts,
                "last_exception": str(last_exception),
                "context": context,
            },
        )

        raise last_exception  # type: ignore

    async def _execute_func(self, func: Callable, *args, **kwargs) -> Any:
        """
        Ejecuta la función, manejando tanto sync como async.

        Args:
            func: Función a ejecutar
            *args: Argumentos posicionales
            **kwargs: Argumentos con nombre

        Returns:
            Any: Resultado de la función
        """
        if asyncio.iscoroutinefunction(func):
            return await func(*args, **kwargs)
        else:
            return func(*args, **kwargs)

    def _record_success(self, duration: float):
        """Registra una ejecución exitosa."""
        self.metrics["total_successes"] += 1
        self._update_avg_duration(duration)

    def _record_failure(self):
        """Registra una falla."""
        self.metrics["total_failures"] += 1

    def _update_avg_duration(self, duration: float):
        """Actualiza la duración promedio."""
        total_ops = self.metrics["total_successes"]
        if total_ops == 1:
            self.metrics["avg_duration"] = duration
        else:
            self.metrics["avg_duration"] = (self.metrics["avg_duration"] * (total_ops - 1) + duration) / total_ops

    def get_metrics(self) -> Dict[str, Any]:
        """
        Obtiene métricas del handler.

        Returns:
            Dict: Métricas actuales
        """
        total = self.metrics["total_attempts"]
        success_rate = (self.metrics["total_successes"] / total * 100) if total > 0 else 0

        metrics = {
            **self.metrics,
            "success_rate": round(success_rate, 2),
            "handler_name": self.name,
        }

        if self.circuit_breaker:
            metrics["circuit_breaker"] = self.circuit_breaker.get_state_info()

        return metrics

    def reset_metrics(self):
        """Reinicia las métricas."""
        self.metrics = {
            "total_attempts": 0,
            "total_successes": 0,
            "total_failures": 0,
            "total_retries": 0,
            "avg_duration": 0.0,
        }


# === FACTORY FUNCTIONS ===


def create_shopify_retry_handler() -> RetryHandler:
    """
    Crea un handler específico para operaciones de Shopify.

    Returns:
        RetryHandler: Handler configurado para Shopify
    """
    retry_policy = RetryPolicy(
        max_attempts=3,
        base_delay=1.0,
        max_delay=30.0,
        exponential_base=2.0,
        jitter=True,
        retry_on=[ShopifyAPIException, RateLimitException],
        stop_on=[],  # No hay excepciones que detengan inmediatamente
    )

    circuit_breaker = CircuitBreaker(
        failure_threshold=10,  # Increased from 3 to allow more failures before opening
        success_threshold=3,   # Increased from 2 to ensure stability before closing
        timeout=180.0,         # Increased to 180s for slow product creation operations
        reset_timeout=60.0,    # Reduced from 120 to recover faster
    )

    return RetryHandler(
        name="shopify_api",
        retry_policy=retry_policy,
        circuit_breaker=circuit_breaker,
    )


def create_rms_retry_handler() -> RetryHandler:
    """
    Crea un handler específico para operaciones de RMS.

    Returns:
        RetryHandler: Handler configurado para RMS
    """
    from app.utils.error_handler import RMSConnectionException

    retry_policy = RetryPolicy(
        max_attempts=3,
        base_delay=2.0,
        max_delay=60.0,
        exponential_base=2.0,
        jitter=True,
        retry_on=[RMSConnectionException],
        stop_on=[],
    )

    circuit_breaker = CircuitBreaker(
        failure_threshold=2,
        success_threshold=1,
        timeout=45.0,
        reset_timeout=300.0,
    )

    return RetryHandler(
        name="rms_database",
        retry_policy=retry_policy,
        circuit_breaker=circuit_breaker,
    )


def create_sync_retry_handler() -> RetryHandler:
    """
    Crea un handler específico para operaciones de sincronización.

    Returns:
        RetryHandler: Handler configurado para sync
    """
    from app.utils.error_handler import SyncException

    retry_policy = RetryPolicy(
        max_attempts=2,  # Menos reintentos para sync completo
        base_delay=5.0,
        max_delay=120.0,
        exponential_base=2.0,
        jitter=True,
        retry_on=[SyncException],
        stop_on=[],
    )

    return RetryHandler(
        name="synchronization",
        retry_policy=retry_policy,
        enable_circuit_breaker=False,  # No circuit breaker para sync
    )


# === DECORADOR UTILITY ===


def with_retry(handler: Optional[RetryHandler] = None, handler_name: str = "default", **handler_kwargs):
    """
    Decorador para agregar reintentos a funciones.

    Args:
        handler: Handler personalizado
        handler_name: Nombre del handler
        **handler_kwargs: Argumentos para crear handler por defecto

    Returns:
        Decorator function
    """

    def decorator(func: Callable) -> Callable:
        nonlocal handler

        if handler is None:
            handler = RetryHandler(name=handler_name, **handler_kwargs)

        async def async_wrapper(*args, **kwargs):
            return await handler.execute(func, *args, **kwargs)

        def sync_wrapper(*args, **kwargs):
            # Para funciones síncronas, crear un loop temporal
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                return loop.run_until_complete(handler.execute(func, *args, **kwargs))
            finally:
                loop.close()

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


# === GLOBAL HANDLERS ===

# Handlers globales para diferentes servicios
SHOPIFY_RETRY_HANDLER = create_shopify_retry_handler()
RMS_RETRY_HANDLER = create_rms_retry_handler()
SYNC_RETRY_HANDLER = create_sync_retry_handler()


def get_handler(service: str) -> RetryHandler:
    """
    Obtiene el handler apropiado para un servicio.

    Args:
        service: Nombre del servicio

    Returns:
        RetryHandler: Handler apropiado
    """
    handlers = {
        "shopify": SHOPIFY_RETRY_HANDLER,
        "rms": RMS_RETRY_HANDLER,
        "sync": SYNC_RETRY_HANDLER,
    }

    return handlers.get(service.lower(), RetryHandler(name=service))


def get_all_metrics() -> Dict[str, Dict[str, Any]]:
    """
    Obtiene métricas de todos los handlers globales.

    Returns:
        Dict: Métricas de todos los handlers
    """
    return {
        "shopify": SHOPIFY_RETRY_HANDLER.get_metrics(),
        "rms": RMS_RETRY_HANDLER.get_metrics(),
        "sync": SYNC_RETRY_HANDLER.get_metrics(),
    }
