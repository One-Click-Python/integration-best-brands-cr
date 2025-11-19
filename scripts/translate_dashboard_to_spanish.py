#!/usr/bin/env python3
"""
Script to translate dashboard from Portuguese to Spanish.
"""

import os
from pathlib import Path

# Mapping of Portuguese/mixed to Spanish translations
TRANSLATIONS = {
    # Common UI terms
    "Não foi possível": "No se pudo",
    "não disponível": "no disponible",
    "não disponíveis": "no disponibles",
    "Não há": "No hay",
    "Nenhum": "Ningún",
    "Nenhuma": "Ninguna",
    "dados de": "datos de",
    "informações de": "información de",
    "Informações": "Información",
    "disponível": "disponible",
    "disponíveis": "disponibles",

    # Time related
    "Última": "Última",
    "Último": "Último",
    "Próxima": "Próxima",
    "Próximo": "Próximo",
    "Última Atualização": "Última Actualización",
    "últimos": "últimos",

    # Actions
    "Atualizar": "Actualizar",
    "Atualizando": "Actualizando",
    "Executar": "Ejecutar",
    "Executando": "Ejecutando",
    "Iniciar": "Iniciar",
    "Parar": "Detener",
    "Resetar": "Reiniciar",
    "Limpar": "Limpiar",
    "Buscar": "Buscar",
    "Filtrar": "Filtrar",
    "Exportar": "Exportar",
    "Baixar": "Descargar",

    # Status
    "Saudável": "Saludable",
    "Ativo": "Activo",
    "Inativo": "Inactivo",
    "Habilitado": "Habilitado",
    "Desabilitado": "Deshabilitado",
    "Aguardando": "Esperando",
    "Concluído": "Completado",
    "Falha": "Falla",

    # Metrics
    "Taxa de Sucesso": "Tasa de Éxito",
    "Itens Sincronizados": "Ítems Sincronizados",
    "Mudanças Detectadas": "Cambios Detectados",
    "Verificações": "Verificaciones",
    "Verificação": "Verificación",
    "Estatísticas": "Estadísticas",
    "Métricas": "Métricas",

    # System
    "Sistema": "Sistema",
    "Recursos do Sistema": "Recursos del Sistema",
    "Uso de Recursos": "Uso de Recursos",
    "Detalhado": "Detallado",
    "Detalhes": "Detalles",
    "Configuração": "Configuración",
    "Configurações": "Configuraciones",

    # Sync
    "Sincronização": "Sincronización",
    "Sincronizações": "Sincronizaciones",
    "Sincronizar": "Sincronizar",
    "Sincronizando": "Sincronizando",
    "Sincronizado": "Sincronizado",
    "Sincronizados": "Sincronizados",

    # Orders/Pedidos
    "Pedidos": "Pedidos",
    "Pedido": "Pedido",
    "Consultado": "Consultado",
    "Consultados": "Consultados",
    "Novos": "Nuevos",
    "Novo": "Nuevo",
    "Atualizados": "Actualizados",
    "Atualizado": "Actualizado",

    # Messages
    "bem-sucedida": "exitosa",
    "bem-sucedido": "exitoso",
    "com sucesso": "con éxito",
    "Deseja realmente": "¿Desea realmente",
    "Isso vai": "Esto va a",
    "Clique novamente para confirmar": "Haga clic nuevamente para confirmar",

    # Portuguese specific words
    "há": "hace",
    "em": "en",
    "de": "de",
    "para": "para",
    "com": "con",
    "sem": "sin",
    "sobre": "sobre",
    "agora": "ahora",

    # Tech terms
    "Intervalo": "Intervalo",
    "intervalo": "intervalo",
    "minutos": "minutos",
    "segundos": "segundos",
    "horas": "horas",
    "dias": "días",
}

def translate_file(file_path: Path):
    """Translate a single file from Portuguese to Spanish."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        original_content = content

        # Apply translations
        for pt, es in TRANSLATIONS.items():
            content = content.replace(pt, es)

        # Only write if content changed
        if content != original_content:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"✅ Translated: {file_path}")
            return True
        else:
            print(f"⏭️  No changes: {file_path}")
            return False

    except Exception as e:
        print(f"❌ Error translating {file_path}: {e}")
        return False

def main():
    """Main translation function."""
    dashboard_dir = Path("dashboard")

    if not dashboard_dir.exists():
        print("❌ Dashboard directory not found!")
        return

    print("🌍 Starting translation from Portuguese to Spanish...\n")

    # Find all Python files in dashboard
    files_to_translate = list(dashboard_dir.rglob("*.py"))

    translated_count = 0
    for file_path in files_to_translate:
        if translate_file(file_path):
            translated_count += 1

    print(f"\n✅ Translation complete!")
    print(f"📊 Files translated: {translated_count}/{len(files_to_translate)}")

if __name__ == "__main__":
    main()
