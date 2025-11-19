# Usar imagen base de Python 3.12 slim
FROM python:3.12-slim

# Establecer directorio de trabajo
WORKDIR /app

# Instalar dependencias del sistema necesarias
RUN apt-get update && apt-get install -y \
    curl \
    gnupg \
    apt-transport-https \
    unixodbc \
    unixodbc-dev \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Instalar Microsoft ODBC Driver 17 for SQL Server
RUN curl -fsSL https://packages.microsoft.com/keys/microsoft.asc | gpg --dearmor -o /usr/share/keyrings/microsoft-prod.gpg \
    && curl -fsSL https://packages.microsoft.com/config/debian/12/prod.list | tee /etc/apt/sources.list.d/mssql-release.list \
    && apt-get update \
    && ACCEPT_EULA=Y apt-get install -y msodbcsql17 \
    && rm -rf /var/lib/apt/lists/* \
    && echo 'export PATH="$PATH:/opt/mssql-tools17/bin"' >> ~/.bashrc

# Copiar archivo de requerimientos
COPY requirements.txt ./

# Instalar dependencias de Python
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el código de la aplicación
COPY app ./app

# Copiar el dashboard de Streamlit
COPY dashboard ./dashboard
COPY .streamlit ./.streamlit

# Crear directorio para logs
RUN mkdir -p logs

# Exponer puertos (8000 para API, 8501 para Dashboard)
EXPOSE 8000 8501

# Variables de entorno por defecto
ENV PYTHONUNBUFFERED=1
ENV ENVIRONMENT=production

# Comando para ejecutar la aplicación
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
