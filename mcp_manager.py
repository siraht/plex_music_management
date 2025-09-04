import subprocess
import logging
import json
from typing import Dict, Any, Optional

class MCPManager:
    """Manages MCP server processes and client interactions."""

    def __init__(self, mcp_servers_config: Dict[str, Any]):
        self.mcp_servers_config = mcp_servers_config
        self.processes: Dict[str, subprocess.Popen] = {}

    def start_server(self, server_name: str) -> bool:
        """Starts a configured MCP server if not already running."""
        if server_name in self.processes and self.processes[server_name].poll() is None:
            logging.info(f"MCP server '{server_name}' is already running.")
            return True

        if server_name not in self.mcp_servers_config:
            logging.error(f"MCP server '{server_name}' not found in configuration.")
            return False

        config = self.mcp_servers_config[server_name]
        command = [config['command']] + config.get('args', [])
        cwd = config.get('cwd')

        try:
            logging.info(f"Starting MCP server '{server_name}' with command: {' '.join(command)}")
            self.processes[server_name] = subprocess.Popen(
                command, 
                cwd=cwd, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE,
                text=True
            )
            logging.info(f"MCP server '{server_name}' started with PID: {self.processes[server_name].pid}")
            return True
        except (FileNotFoundError, PermissionError) as e:
            logging.error(f"Failed to start MCP server '{server_name}': {e}")
            return False

    def stop_server(self, server_name: str) -> bool:
        """Stops a running MCP server."""
        if server_name in self.processes and self.processes[server_name].poll() is None:
            logging.info(f"Stopping MCP server '{server_name}'...")
            self.processes[server_name].terminate()
            try:
                self.processes[server_name].wait(timeout=5)
                logging.info(f"MCP server '{server_name}' stopped.")
            except subprocess.TimeoutExpired:
                logging.warning(f"MCP server '{server_name}' did not terminate gracefully, killing.")
                self.processes[server_name].kill()
            del self.processes[server_name]
            return True
        logging.warning(f"MCP server '{server_name}' is not running.")
        return False

    def stop_all_servers(self):
        """Stops all managed MCP servers."""
        for server_name in list(self.processes.keys()):
            self.stop_server(server_name)

    def get_server_status(self, server_name: str) -> str:
        """Returns the status of a specific MCP server."""
        if server_name in self.processes and self.processes[server_name].poll() is None:
            return f"Running (PID: {self.processes[server_name].pid})"
        return "Stopped"

    def list_servers(self):
        """Lists all configured MCP servers and their statuses."""
        return {
            server_name: self.get_server_status(server_name) 
            for server_name in self.mcp_servers_config
        }
