"""
Configuración centralizada de la aplicación.

Este módulo maneja todas las variables de entorno y configuraciones
de la aplicación usando Pydantic Settings para validación automática.
"""

from functools import lru_cache
from typing import List, Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings

from app.version import VERSION


class Settings(BaseSettings):
    """
    Configuración de la aplicación usando Pydantic Settings.

    Todas las configuraciones se cargan desde variables de entorno
    con valores por defecto apropiados para desarrollo.
    """

    # === CONFIGURACIÓN BÁSICA DE LA APP ===
    APP_NAME: str = "RMS-Shopify Integration"
    APP_VERSION: str = VERSION
    ENVIRONMENT: str = Field(default="development", env="ENV")
    DEBUG: bool = Field(default=True, env="DEBUG")

    # === CONFIGURACIÓN DEL SERVIDOR ===
    HOST: str = Field(default="0.0.0.0", env="HOST")
    PORT: int = Field(default=8080, env="PORT")
    WORKERS: int = Field(default=1, env="WORKERS")
    LOG_LEVEL: str = Field(default="INFO", env="LOG_LEVEL")

    # === CONFIGURACIÓN DE SEGURIDAD ===
    ALLOWED_HOSTS: Optional[List[str]] = Field(default=None, env="ALLOWED_HOSTS")
    API_BASE_URL: Optional[str] = Field(default=None, env="API_BASE_URL")
    STAGING_URL: Optional[str] = Field(default=None, env="STAGING_URL")
    SECRET_KEY: str = Field(default="your-secret-key-change-in-production", env="SECRET_KEY")

    # === CONFIGURACIÓN DE RMS (SQL SERVER) ===
    RMS_DB_HOST: str = Field(default="190.106.75.222", env="RMS_DB_HOST")
    RMS_DB_PORT: int = Field(default=1438, env="RMS_DB_PORT")
    RMS_DB_NAME: str = Field(default="BB57_TempSF", env="RMS_DB_NAME")
    RMS_DB_USER: str = Field(default="Shop1fy5428", env="RMS_DB_USER")
    RMS_DB_PASSWORD: str = Field(default="sh0pqfy10736!", env="RMS_DB_PASSWORD")
    RMS_DB_DRIVER: str = Field(default="ODBC Driver 17 for SQL Server", env="RMS_DB_DRIVER")
    RMS_CONNECTION_TIMEOUT: int = Field(default=60, env="RMS_CONNECTION_TIMEOUT")
    RMS_MAX_POOL_SIZE: int = Field(default=10, env="RMS_MAX_POOL_SIZE")
    # Configuraciones específicas para RMS
    RMS_VIEW_ITEMS_TABLE: str = Field(default="View_Items", env="RMS_VIEW_ITEMS_TABLE")
    RMS_STORE_ID: int = Field(default=40, env="RMS_STORE_ID")  # StoreID fijo para tienda virtual
    RMS_SYNC_INCREMENTAL_HOURS: int = Field(default=24, env="RMS_SYNC_INCREMENTAL_HOURS")

    # === CONFIGURACIÓN DE SHOPIFY ===
    SHOPIFY_SHOP_URL: str = Field(default="your-shop.myshopify.com", env="SHOPIFY_SHOP_URL")
    SHOPIFY_ACCESS_TOKEN: str = Field(default="your-access-token", env="SHOPIFY_ACCESS_TOKEN")
    SHOPIFY_API_VERSION: str = Field(default="2025-04", env="SHOPIFY_API_VERSION")
    SHOPIFY_WEBHOOK_SECRET: Optional[str] = Field(default=None, env="SHOPIFY_WEBHOOK_SECRET")
    SHOPIFY_RATE_LIMIT_PER_SECOND: int = Field(default=2, env="SHOPIFY_RATE_LIMIT_PER_SECOND")
    SHOPIFY_MAX_RETRIES: int = Field(default=3, env="SHOPIFY_MAX_RETRIES")

    # === CONFIGURACIÓN DE REDIS ===
    REDIS_URL: Optional[str] = Field(default=None, env="REDIS_URL")
    REDIS_MAX_CONNECTIONS: int = Field(default=10, env="REDIS_MAX_CONNECTIONS")
    REDIS_SOCKET_TIMEOUT: int = Field(default=5, env="REDIS_SOCKET_TIMEOUT")

    # === CONFIGURACIÓN DE SINCRONIZACIÓN ===
    ENABLE_SCHEDULED_SYNC: bool = Field(default=True, env="ENABLE_SCHEDULED_SYNC")
    SYNC_INTERVAL_MINUTES: int = Field(default=15, env="SYNC_INTERVAL_MINUTES")
    SYNC_BATCH_SIZE: int = Field(default=25, env="SYNC_BATCH_SIZE")  # Aumentado para mejor rendimiento
    DEFAULT_BATCH_SIZE: int = Field(default=25, env="DEFAULT_BATCH_SIZE")
    SYNC_MAX_CONCURRENT_JOBS: int = Field(default=3, env="SYNC_MAX_CONCURRENT_JOBS")
    SYNC_TIMEOUT_MINUTES: int = Field(default=30, env="SYNC_TIMEOUT_MINUTES")
    SYNC_CHECKPOINT_INTERVAL: int = Field(default=100, env="SYNC_CHECKPOINT_INTERVAL")
    SYNC_PARALLEL_WORKERS: int = Field(default=3, env="SYNC_PARALLEL_WORKERS")
    SYNC_HANDLE_BATCH_SIZE: int = Field(default=25, env="SYNC_HANDLE_BATCH_SIZE")

    # === CONFIGURACIÓN DE UPDATE CHECKPOINT ===
    USE_UPDATE_CHECKPOINT: bool = Field(default=False, env="USE_UPDATE_CHECKPOINT")
    CHECKPOINT_SUCCESS_THRESHOLD: float = Field(default=0.95, env="CHECKPOINT_SUCCESS_THRESHOLD")
    CHECKPOINT_DEFAULT_DAYS: int = Field(default=30, env="CHECKPOINT_DEFAULT_DAYS")

    # === CONFIGURACIÓN DE PRODUCTOS CON STOCK 0 ===
    SYNC_UPDATE_ZERO_STOCK_PRODUCTS: bool = Field(default=True, env="SYNC_UPDATE_ZERO_STOCK_PRODUCTS")
    SYNC_CREATE_ZERO_STOCK_PRODUCTS: bool = Field(default=False, env="SYNC_CREATE_ZERO_STOCK_PRODUCTS")

    # === CONFIGURACIÓN DE LIMPIEZA DE VARIANTES CON STOCK 0 ===
    ENABLE_ZERO_STOCK_CLEANUP: bool = Field(
        default=True,
        env="ENABLE_ZERO_STOCK_CLEANUP",
        description="Habilitar limpieza automática de variantes con stock 0 en RMS durante sincronización",
    )

    # === CONFIGURACIÓN DE CATEGORÍAS Y COLLECTIONS ===
    SYNC_INCLUDE_CATEGORY_TAGS: bool = Field(
        default=False,
        env="SYNC_INCLUDE_CATEGORY_TAGS",
        description="Si True, agrega tags de categoría mapeados y tags de género para collections automáticas",
    )
    SYNC_ENABLE_COLLECTIONS: bool = Field(
        default=False,
        env="SYNC_ENABLE_COLLECTIONS",
        description="Si True, habilita la sincronización de collections basadas en género y categoría",
    )

    # === CONFIGURACIÓN DE SINCRONIZACIÓN COMPLETA PROGRAMADA ===
    ENABLE_FULL_SYNC_SCHEDULE: bool = Field(default=False, env="ENABLE_FULL_SYNC_SCHEDULE")
    # Hora del día (0-23)
    FULL_SYNC_HOUR: int = Field(default=2, env="FULL_SYNC_HOUR")
    # Minuto de la hora (0-59)
    FULL_SYNC_MINUTE: int = Field(default=0, env="FULL_SYNC_MINUTE")
    # Zona horaria para la sincronización
    FULL_SYNC_TIMEZONE: str = Field(default="UTC", env="FULL_SYNC_TIMEZONE")
    # Días de la semana (0=Lunes, 6=Domingo)
    FULL_SYNC_DAYS: Optional[List[int]] = Field(default=None, env="FULL_SYNC_DAYS")

    # === CONFIGURACIÓN DE PEDIDOS SIN CLIENTE ===
    ALLOW_ORDERS_WITHOUT_CUSTOMER: bool = Field(default=True, env="ALLOW_ORDERS_WITHOUT_CUSTOMER")
    DEFAULT_CUSTOMER_ID_FOR_GUEST_ORDERS: Optional[int] = Field(
        default=None, env="DEFAULT_CUSTOMER_ID_FOR_GUEST_ORDERS"
    )
    REQUIRE_CUSTOMER_EMAIL: bool = Field(default=False, env="REQUIRE_CUSTOMER_EMAIL")
    GUEST_CUSTOMER_NAME: str = Field(default="Cliente Invitado", env="GUEST_CUSTOMER_NAME")
    GUEST_CUSTOMER_ACCOUNT_NUMBER: str = Field(
        default="SHOPIFY-GUEST",
        env="GUEST_CUSTOMER_ACCOUNT_NUMBER",
        description="Account number for auto-created guest customer in RMS",
    )

    # === CONFIGURACIÓN DE ESTADOS FINANCIEROS DE PEDIDOS ===
    ALLOWED_ORDER_FINANCIAL_STATUSES: str | list[str] = Field(
        default=["PAID", "PARTIALLY_PAID", "AUTHORIZED", "PENDING"],
        env="ALLOWED_ORDER_FINANCIAL_STATUSES",
        description="Lista de estados financieros permitidos para sincronizar pedidos de Shopify a RMS",
    )

    # === CONFIGURACIÓN DE ORDER POLLING (MÉTODO PRIMARY PARA SINCRONIZACIÓN DE ÓRDENES) ===
    ENABLE_ORDER_POLLING: bool = Field(
        default=True,
        env="ENABLE_ORDER_POLLING",
        description="Habilita polling de órdenes de Shopify (MÉTODO PRIMARY: más confiable que webhooks)",
    )
    ENABLE_WEBHOOKS: bool = Field(
        default=False,
        env="ENABLE_WEBHOOKS",
        description="Habilita procesamiento de webhooks de Shopify (OPCIONAL: puede usarse como complemento a polling)",
    )
    ORDER_POLLING_INTERVAL_MINUTES: int = Field(
        default=10,
        env="ORDER_POLLING_INTERVAL_MINUTES",
        description="Intervalo en minutos para polling de órdenes (default: 10 minutos)",
    )
    ORDER_POLLING_LOOKBACK_MINUTES: int = Field(
        default=15,
        env="ORDER_POLLING_LOOKBACK_MINUTES",
        description="Ventana de tiempo en minutos para buscar órdenes (default: 15 minutos)",
    )
    ORDER_POLLING_BATCH_SIZE: int = Field(
        default=50, env="ORDER_POLLING_BATCH_SIZE", description="Número de órdenes por página en GraphQL (max 250)"
    )
    ORDER_POLLING_MAX_PAGES: int = Field(
        default=10, env="ORDER_POLLING_MAX_PAGES", description="Máximo número de páginas a consultar en cada polling"
    )

    # === CONFIGURACIÓN DE ORDERENTRY PARA ENVÍOS ===
    SHIPPING_ITEM_ID: int = Field(
        default=481461,
        env="SHIPPING_ITEM_ID",
        description="ItemID de VIEW_Items para costos de envío (OrderEntry automático)",
    )

    # === CONFIGURACIÓN DE RATE LIMITING ===
    ENABLE_RATE_LIMITING: bool = Field(default=True, env="ENABLE_RATE_LIMITING")
    RATE_LIMIT_PER_MINUTE: int = Field(default=60, env="RATE_LIMIT_PER_MINUTE")
    RATE_LIMIT_BURST: int = Field(default=10, env="RATE_LIMIT_BURST")

    # === CONFIGURACIÓN DE LOGGING ===
    LOG_FILE_PATH: Optional[str] = Field(default="logs/app.log", env="LOG_FILE_PATH")
    LOG_MAX_SIZE_MB: int = Field(default=10, env="LOG_MAX_SIZE_MB")
    LOG_BACKUP_COUNT: int = Field(default=5, env="LOG_BACKUP_COUNT")
    LOG_FORMAT: str = Field(default="%(asctime)s - %(name)s - %(levelname)s - %(message)s", env="LOG_FORMAT")

    # === CONFIGURACIÓN DE MÉTRICAS Y MONITOREO ===
    METRICS_ENABLED: bool = Field(default=True, env="METRICS_ENABLED")
    # Reducido para endpoints
    HEALTH_CHECK_TIMEOUT: int = Field(default=5, env="HEALTH_CHECK_TIMEOUT")
    # Timeout por servicio
    HEALTH_CHECK_INDIVIDUAL_TIMEOUT: int = Field(default=3, env="HEALTH_CHECK_INDIVIDUAL_TIMEOUT")
    # Cache en segundos
    HEALTH_CHECK_CACHE_TTL: int = Field(default=60, env="HEALTH_CHECK_CACHE_TTL")
    SLOW_REQUEST_THRESHOLD: float = Field(default=5.0, env="SLOW_REQUEST_THRESHOLD")

    # === CONFIGURACIÓN DE ALERTAS ===
    ALERT_EMAIL_ENABLED: bool = Field(default=False, env="ALERT_EMAIL_ENABLED")
    ALERT_EMAIL_SMTP_HOST: Optional[str] = Field(default=None, env="ALERT_EMAIL_SMTP_HOST")
    ALERT_EMAIL_SMTP_PORT: int = Field(default=587, env="ALERT_EMAIL_SMTP_PORT")
    ALERT_EMAIL_FROM: Optional[str] = Field(default=None, env="ALERT_EMAIL_FROM")
    ALERT_EMAIL_TO: Optional[str] = Field(default=None, env="ALERT_EMAIL_TO")
    ALERT_EMAIL_PASSWORD: Optional[str] = Field(default=None, env="ALERT_EMAIL_PASSWORD")
    ALERT_EMAIL_USE_TLS: bool = Field(default=True, env="ALERT_EMAIL_USE_TLS")

    # === CONFIGURACIÓN DE DOCUMENTACIÓN ===
    ENABLE_DOCS: bool = Field(default=True, env="ENABLE_DOCS")

    # === CONFIGURACIÓN DE SISTEMA ===
    DISK_SPACE_THRESHOLD: int = Field(default=10, env="DISK_SPACE_THRESHOLD")  # Porcentaje
    MEMORY_USAGE_THRESHOLD: int = Field(default=90, env="MEMORY_USAGE_THRESHOLD")  # Porcentaje
    CPU_USAGE_THRESHOLD: int = Field(default=95, env="CPU_USAGE_THRESHOLD")  # Porcentaje

    # === CONFIGURACIÓN DE SINCRONIZACIÓN REVERSA (SHOPIFY → RMS STOCK) ===
    ENABLE_REVERSE_STOCK_SYNC: bool = Field(
        default=True,
        env="ENABLE_REVERSE_STOCK_SYNC",
        description="Habilita sincronización complementaria de inventario Shopify → RMS",
    )
    REVERSE_SYNC_DELAY_MINUTES: int = Field(
        default=5,
        env="REVERSE_SYNC_DELAY_MINUTES",
        description="Minutos de espera después de RMS→Shopify antes de ejecutar reverse sync",
    )
    REVERSE_SYNC_DELETE_ZERO_STOCK: bool = Field(
        default=True,
        env="REVERSE_SYNC_DELETE_ZERO_STOCK",
        description="Si True, elimina variantes con stock 0 durante reverse sync",
    )
    REVERSE_SYNC_BATCH_SIZE: int = Field(
        default=50,
        env="REVERSE_SYNC_BATCH_SIZE",
        description="Número de productos a procesar por batch en reverse sync",
    )
    REVERSE_SYNC_PRESERVE_SINGLE_VARIANT: bool = Field(
        default=True,
        env="REVERSE_SYNC_PRESERVE_SINGLE_VARIANT",
        description="Si True, no elimina la última variante de un producto",
    )

    # === CONFIGURACIÓN DE RETRIES ===
    MAX_RETRIES: int = Field(default=3, env="MAX_RETRIES")
    RETRY_DELAY_SECONDS: int = Field(default=1, env="RETRY_DELAY_SECONDS")
    RETRY_BACKOFF_FACTOR: float = Field(default=2.0, env="RETRY_BACKOFF_FACTOR")

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": True,
        "extra": "allow",  # Permitir valores extra para flexibilidad futura
    }

    @field_validator("ALLOWED_HOSTS", mode="before")
    @classmethod
    def parse_allowed_hosts(cls, v):
        """Parsea ALLOWED_HOSTS como lista separada por comas."""
        if isinstance(v, str):
            return [host.strip() for host in v.split(",") if host.strip()]
        return v

    @field_validator("FULL_SYNC_DAYS", mode="before")
    @classmethod
    def parse_full_sync_days(cls, v):
        """Parsea FULL_SYNC_DAYS como lista de enteros separados por comas."""
        if isinstance(v, str):
            if not v.strip():
                return None
            try:
                days = [int(day.strip()) for day in v.split(",") if day.strip()]
                # Validar que los días estén en rango 0-6
                for day in days:
                    if not 0 <= day <= 6:
                        raise ValueError(f"Día {day} fuera de rango (0-6)")
                return days
            except ValueError as e:
                raise ValueError(
                    f"FULL_SYNC_DAYS debe ser una lista de números entre 0-6 separados por comas: {e}"
                ) from e
        return v

    @field_validator("FULL_SYNC_HOUR")
    @classmethod
    def validate_full_sync_hour(cls, v):
        """Valida que la hora esté en rango válido (0-23)."""
        if not 0 <= v <= 23:
            raise ValueError("FULL_SYNC_HOUR debe estar entre 0 y 23")
        return v

    @field_validator("FULL_SYNC_MINUTE")
    @classmethod
    def validate_full_sync_minute(cls, v):
        """Valida que el minuto esté en rango válido (0-59)."""
        if not 0 <= v <= 59:
            raise ValueError("FULL_SYNC_MINUTE debe estar entre 0 y 59")
        return v

    @field_validator("CHECKPOINT_SUCCESS_THRESHOLD")
    @classmethod
    def validate_checkpoint_threshold(cls, v):
        """Valida que el umbral de éxito esté en rango válido (0.0-1.0)."""
        if not 0.0 <= v <= 1.0:
            raise ValueError("CHECKPOINT_SUCCESS_THRESHOLD debe estar entre 0.0 y 1.0")
        return v

    @field_validator("CHECKPOINT_DEFAULT_DAYS")
    @classmethod
    def validate_checkpoint_days(cls, v):
        """Valida que los días por defecto sean positivos."""
        if v < 1:
            raise ValueError("CHECKPOINT_DEFAULT_DAYS debe ser al menos 1")
        if v > 365:
            raise ValueError("CHECKPOINT_DEFAULT_DAYS no debe ser mayor a 365")
        return v

    @field_validator("ALLOWED_ORDER_FINANCIAL_STATUSES", mode="before")
    @classmethod
    def parse_allowed_financial_statuses(cls, v):
        """
        Parsea ALLOWED_ORDER_FINANCIAL_STATUSES como lista separada por comas.

        Estados financieros válidos de Shopify:
        - PENDING: Pendiente de pago
        - AUTHORIZED: Autorizado pero no capturado
        - PARTIALLY_PAID: Pagado parcialmente
        - PAID: Pagado completamente
        - PARTIALLY_REFUNDED: Reembolsado parcialmente
        - REFUNDED: Reembolsado completamente
        - VOIDED: Anulado
        """
        if isinstance(v, str):
            if not v.strip():
                # Si está vacío, usar valor por defecto
                return ["PAID", "PARTIALLY_PAID", "AUTHORIZED", "PENDING"]
            statuses = [status.strip().upper() for status in v.split(",") if status.strip()]

            # Validar que los estados sean válidos
            valid_statuses = {
                "PENDING",
                "AUTHORIZED",
                "PARTIALLY_PAID",
                "PAID",
                "PARTIALLY_REFUNDED",
                "REFUNDED",
                "VOIDED",
            }
            invalid = [s for s in statuses if s not in valid_statuses]
            if invalid:
                raise ValueError(
                    f"Estados financieros inválidos: {invalid}. " f"Estados válidos: {sorted(valid_statuses)}"
                )

            return statuses
        return v

    @field_validator("SHOPIFY_SHOP_URL")
    @classmethod
    def validate_shopify_url(cls, v):
        """Valida que la URL de Shopify tenga el formato correcto."""
        # Skip validation for default/placeholder values
        if v in ["your-shop.myshopify.com"]:
            return v
        if not v.endswith(".myshopify.com"):
            raise ValueError("SHOPIFY_SHOP_URL debe terminar en .myshopify.com")
        if not v.startswith("https://") and not v.startswith("http://"):
            v = f"https://{v}"
        return v

    @field_validator("LOG_LEVEL")
    @classmethod
    def validate_log_level(cls, v):
        """Valida que el nivel de log sea válido."""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in valid_levels:
            raise ValueError(f"LOG_LEVEL debe ser uno de: {valid_levels}")
        return v.upper()

    @field_validator("ENVIRONMENT")
    @classmethod
    def validate_environment(cls, v):
        """Valida que el entorno sea válido."""
        valid_envs = ["development", "staging", "production", "testing"]
        if v.lower() not in valid_envs:
            raise ValueError(f"ENVIRONMENT debe ser uno de: {valid_envs}")
        return v.lower()

    @field_validator("PORT")
    @classmethod
    def validate_port(cls, v):
        """Valida que el puerto esté en rango válido."""
        if not 1 <= v <= 65535:
            raise ValueError("PORT debe estar entre 1 y 65535")
        return v

    @property
    def is_production(self) -> bool:
        """Verifica si está en entorno de producción."""
        return self.ENVIRONMENT == "production"

    @property
    def is_development(self) -> bool:
        """Verifica si está en entorno de desarrollo."""
        return self.ENVIRONMENT == "development"

    @property
    def rms_connection_string(self) -> str:
        """Genera string de conexión para RMS/SQL Server."""
        # If host already includes port (with comma), use it as is
        if "," in self.RMS_DB_HOST:
            host_part = self.RMS_DB_HOST
        else:
            host_part = f"{self.RMS_DB_HOST}:{self.RMS_DB_PORT}"

        return (
            f"mssql+pyodbc://{self.RMS_DB_USER}:{self.RMS_DB_PASSWORD}"
            f"@{host_part}/{self.RMS_DB_NAME}"
            f"?driver={self.RMS_DB_DRIVER.replace(' ', '+')}"
            f"&TrustServerCertificate=yes"
            f"&connect_timeout={self.RMS_CONNECTION_TIMEOUT}"
        )

    @property
    def rms_connection_string_async(self) -> str:
        """String de conexión asíncrona para RMS."""
        return self.rms_connection_string.replace("mssql+pyodbc://", "mssql+aioodbc://")

    @property
    def RMS_CONNECTION_STRING(self) -> str:
        """Alias para rms_connection_string."""
        return self.rms_connection_string

    @property
    def SHOPIFY_API_KEY(self) -> str:
        """Alias para SHOPIFY_ACCESS_TOKEN."""
        return self.SHOPIFY_ACCESS_TOKEN

    @property
    def shopify_api_base_url(self) -> str:
        """Genera URL base de la API de Shopify."""
        shop_name = self.SHOPIFY_SHOP_URL.replace("https://", "").replace("http://", "")
        if not shop_name.endswith(".myshopify.com"):
            shop_name = f"{shop_name}.myshopify.com"
        return f"https://{shop_name}/admin/api/{self.SHOPIFY_API_VERSION}"

    @property
    def redis_config(self) -> dict:
        """Genera configuración para Redis."""
        if not self.REDIS_URL:
            return {}

        return {
            "url": self.REDIS_URL,
            "max_connections": self.REDIS_MAX_CONNECTIONS,
            "socket_timeout": self.REDIS_SOCKET_TIMEOUT,
            "decode_responses": True,
        }

    def get_database_url(self, async_driver: bool = False) -> str:
        """
        Obtiene URL de conexión a base de datos.

        Args:
            async_driver: Si usar driver asíncrono

        Returns:
            str: URL de conexión
        """
        if async_driver:
            return self.rms_connection_string.replace("mssql+pyodbc://", "mssql+aioodbc://")
        return self.rms_connection_string

    def get_shopify_headers(self) -> dict:
        """
        Obtiene headers para requests a Shopify.

        Returns:
            dict: Headers de autenticación
        """
        return {
            "X-Shopify-Access-Token": self.SHOPIFY_ACCESS_TOKEN,
            "Content-Type": "application/json",
            "User-Agent": f"{self.APP_NAME}/{self.APP_VERSION}",
        }

    def get_logging_config(self) -> dict:
        """
        Obtiene configuración completa de logging.

        Returns:
            dict: Configuración de logging
        """
        return {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "default": {"format": self.LOG_FORMAT},
                "detailed": {
                    "format": "%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s"
                },
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "formatter": "default",
                    "level": self.LOG_LEVEL,
                },
                "file": {
                    "class": "logging.handlers.RotatingFileHandler",
                    "filename": self.LOG_FILE_PATH,
                    "maxBytes": self.LOG_MAX_SIZE_MB * 1024 * 1024,
                    "backupCount": self.LOG_BACKUP_COUNT,
                    "formatter": "detailed",
                    "level": self.LOG_LEVEL,
                },
            },
            "root": {
                "level": self.LOG_LEVEL,
                "handlers": ["console", "file"] if self.LOG_FILE_PATH else ["console"],
            },
        }

    def model_post_init(self, __context):
        """
        Sanitize system environment variables that may override .env settings.

        This method executes AFTER Pydantic loads settings from .env,
        preventing system-level environment variables from accidentally
        overriding the application's configuration.
        """
        import logging
        import os

        logger = logging.getLogger(__name__)

        # Critical environment variables that should only come from .env
        protected_vars = [
            "RMS_DB_NAME",
            "RMS_DB_HOST",
            "RMS_DB_PORT",
            "RMS_DB_USER",
            "RMS_DB_PASSWORD",
            "SHOPIFY_ACCESS_TOKEN",
            "SHOPIFY_SHOP_URL",
        ]

        cleared_vars = []
        for var in protected_vars:
            if var in os.environ:
                # Get value from .env (already loaded by Pydantic)
                loaded_value = str(getattr(self, var, None))
                system_value = os.environ[var]

                # If system value differs from .env, clear it
                if system_value != loaded_value:
                    # Mask sensitive values in logs
                    display_system = system_value[:10] + "..." if len(system_value) > 10 else system_value
                    display_loaded = loaded_value[:10] + "..." if len(loaded_value) > 10 else loaded_value

                    logger.warning(
                        f"⚠️  System environment variable '{var}' "
                        f"(value: '{display_system}') "
                        f"was overriding .env configuration. "
                        f"Clearing to use .env value: '{display_loaded}'"
                    )
                    del os.environ[var]
                    cleared_vars.append(var)

        if cleared_vars:
            logger.info(f"✅ Sanitized {len(cleared_vars)} environment variables: " f"{', '.join(cleared_vars)}")

        # Log database being used (for verification)
        logger.info(f"🗄️  Using RMS database: {self.RMS_DB_NAME} @ {self.RMS_DB_HOST}:{self.RMS_DB_PORT}")


@lru_cache()
def get_settings() -> Settings:
    """
    Obtiene instancia singleton de configuración.

    Usa LRU cache para evitar recrear la configuración
    múltiples veces durante la ejecución.

    Returns:
        Settings: Instancia de configuración
    """
    return Settings()


# Instancia global para uso directo
settings = get_settings()


def reload_settings() -> Settings:
    """
    Recarga la configuración (útil para testing).

    Returns:
        Settings: Nueva instancia de configuración
    """
    get_settings.cache_clear()
    return get_settings()


def validate_required_settings() -> bool:
    """
    Valida que todas las configuraciones requeridas estén presentes.

    Returns:
        bool: True si todas las configuraciones están presentes

    Raises:
        ValueError: Si alguna configuración requerida falta
    """
    try:
        settings = get_settings()

        # Validar configuraciones críticas
        required_fields = [
            "RMS_DB_HOST",
            "RMS_DB_NAME",
            "RMS_DB_USER",
            "RMS_DB_PASSWORD",
            "SHOPIFY_SHOP_URL",
            "SHOPIFY_ACCESS_TOKEN",
        ]

        missing_fields = []
        for field in required_fields:
            value = getattr(settings, field, None)
            if not value or (isinstance(value, str) and not value.strip()):
                missing_fields.append(field)

        if missing_fields:
            raise ValueError(f"Configuraciones requeridas faltantes: {missing_fields}")

        return True

    except Exception as e:
        raise ValueError(f"Error validando configuración: {e}") from e


def get_environment_info() -> dict:
    """
    Obtiene información del entorno actual.

    Returns:
        dict: Información del entorno
    """
    settings = get_settings()

    return {
        "app_name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
        "debug": settings.DEBUG,
        "is_production": settings.is_production,
        "is_development": settings.is_development,
        "host": settings.HOST,
        "port": settings.PORT,
        "log_level": settings.LOG_LEVEL,
        "features": {
            "scheduled_sync": settings.ENABLE_SCHEDULED_SYNC,
            "rate_limiting": settings.ENABLE_RATE_LIMITING,
            "metrics": settings.METRICS_ENABLED,
            "alerts": settings.ALERT_EMAIL_ENABLED,
            "docs": settings.ENABLE_DOCS,
            "redis": bool(settings.REDIS_URL),
        },
    }
