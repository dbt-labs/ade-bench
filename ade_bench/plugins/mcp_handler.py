"""Handler for configuring MCP servers."""

import logging
from ade_bench.models.plugin_set import PluginSet
from ade_bench.terminal.docker_compose_manager import DockerComposeManager

logger = logging.getLogger(__name__)


class McpHandler:
    """Configures MCP servers from plugin set configuration."""

    def configure(self, plugin_set: PluginSet, agent_name: str, terminal: DockerComposeManager) -> None:
        """Configure MCP servers for the agent.

        Args:
            plugin_set: The plugin set configuration
            agent_name: The agent CLI name (claude, gemini, codex)
            terminal: The Docker container manager
        """
        if not plugin_set.mcp_servers:
            logger.debug(f"[McpHandler] No MCP servers to configure for '{plugin_set.name}'")
            return

        for server_name, config in plugin_set.mcp_servers.items():
            logger.info(f"[McpHandler] Configuring MCP server '{server_name}'...")

            # Write env file if env vars specified
            env_file_path = None
            if config.env:
                env_file_path = f"/tmp/{server_name}.env"
                env_content = "\n".join(f"{k}={v}" for k, v in config.env.items())
                write_cmd = f"cat > {env_file_path} << 'ENVEOF'\n{env_content}\nENVEOF"

                result = terminal.container.exec_run(
                    ["sh", "-c", write_cmd],
                    workdir=str(DockerComposeManager.CONTAINER_APP_DIR)
                )
                if result.exit_code != 0:
                    logger.warning(f"[McpHandler] Failed to write env file: {result.output.decode('utf-8')}")

            # Build mcp add command
            args_str = " ".join(config.args)
            if env_file_path:
                mcp_cmd = f"{agent_name} mcp add {server_name} -- {config.command} --env-file {env_file_path} {args_str}"
            else:
                mcp_cmd = f"{agent_name} mcp add {server_name} -- {config.command} {args_str}"

            logger.info(f"[McpHandler] Running: {mcp_cmd}")
            result = terminal.container.exec_run(
                ["sh", "-c", mcp_cmd],
                workdir=str(DockerComposeManager.CONTAINER_APP_DIR)
            )

            if result.exit_code != 0:
                logger.warning(
                    f"[McpHandler] MCP server registration failed for {server_name}: "
                    f"{result.output.decode('utf-8')}"
                )
            else:
                logger.info(f"[McpHandler] MCP server '{server_name}' configured successfully")
