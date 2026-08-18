import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
from google.antigravity.types import McpStdioServer, McpStreamableHttpServer
from src.config import settings

logger = logging.getLogger(__name__)

# Список серверов, требующих специфического окружения или временно недоступных
IGNORED_MCP_SERVERS = {"mcp-excel-server"}


def load_mcp_servers(config_path: Optional[str] = None) -> List[Any]:
    path_str = config_path or settings.MCP_CONFIG_PATH
    path = Path(path_str)

    if not path.exists():
        logger.warning(f"Файл конфигурации MCP не найден по пути: {path}")
        return []

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        logger.error(f"Ошибка чтения JSON из {path}: {e}")
        return []

    mcp_servers_dict = data.get("mcpServers", {})
    servers: List[Any] = []

    for name, s_config in mcp_servers_dict.items():
        if name in IGNORED_MCP_SERVERS:
            continue

        try:
            # Если сервер указан с URL (HTTP / SSE)
            if "url" in s_config:
                server = McpStreamableHttpServer(
                    name=name,
                    url=s_config["url"],
                    headers=s_config.get("headers", {})
                )
                servers.append(server)
            # Если сервер указан с командой (Stdio)
            elif "command" in s_config:
                server = McpStdioServer(
                    name=name,
                    command=s_config["command"],
                    args=s_config.get("args", []),
                    env=s_config.get("env", {})
                )
                servers.append(server)
        except Exception as e:
            logger.warning(f"Не удалось инициализировать MCP сервер '{name}': {e}")

    logger.info(f"Загружено {len(servers)} проверенных MCP-серверов из {path}")
    return servers


def get_mcp_summary(config_path: Optional[str] = None) -> Dict[str, str]:
    path_str = config_path or settings.MCP_CONFIG_PATH
    path = Path(path_str)

    if not path.exists():
        return {}

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        servers = data.get("mcpServers", {})
        summary = {}
        for name, cfg in servers.items():
            if name in IGNORED_MCP_SERVERS:
                continue
            if "command" in cfg:
                summary[name] = f"stdio: <code>{cfg['command']}</code>"
            elif "url" in cfg:
                summary[name] = f"http: <code>{cfg['url']}</code>"
            else:
                summary[name] = "custom"
        return summary
    except Exception as e:
        logger.error(f"Ошибка формирования сводки MCP: {e}")
        return {}
