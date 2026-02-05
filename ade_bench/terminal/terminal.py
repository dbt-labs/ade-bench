from contextlib import contextmanager
from pathlib import Path
from typing import Generator

from ade_bench.terminal.docker_compose_manager import DockerComposeManager
from ade_bench.terminal.tmux_session import TmuxSession
from ade_bench.utils.logger import logger


class Terminal:
    def __init__(
        self,
        client_container_name: str,
        client_image_name: str,
        docker_compose_path: Path,
        docker_name_prefix: str | None = None,
        sessions_path: Path | None = None,
        commands_path: Path | None = None,
        no_rebuild: bool = False,
        cleanup: bool = False,
        build_context_dir: Path | None = None,
    ):
        self._client_container_name = client_container_name
        self._docker_name_prefix = docker_name_prefix
        self._docker_compose_path = docker_compose_path
        self._sessions_path = sessions_path
        self._commands_path = commands_path
        self._build_context_dir = build_context_dir

        self._logger = logger.getChild(__name__)
        self._sessions: dict[str, TmuxSession] = {}

        self._compose_manager = DockerComposeManager(
            client_container_name=client_container_name,
            client_image_name=client_image_name,
            docker_name_prefix=docker_name_prefix,
            docker_compose_path=docker_compose_path,
            no_rebuild=no_rebuild,
            cleanup=cleanup,
            logs_path=sessions_path,
            build_context_dir=build_context_dir,
        )

        self.container = None

    def create_session(self, session_name: str) -> TmuxSession:
        """Create a new tmux session with the given name."""
        if self.container is None:
            raise ValueError("Container not started. Run start() first.")

        if session_name in self._sessions:
            raise ValueError(f"Session {session_name} already exists")

        session = TmuxSession(
            session_name=session_name,
            container=self.container,
            commands_path=self._commands_path,
        )

        self._sessions[session_name] = session

        session.start()

        return session

    def get_session(self, session_name: str) -> TmuxSession:
        """Get an existing tmux session by name."""
        if session_name not in self._sessions:
            raise ValueError(f"Session {session_name} does not exist")
        return self._sessions[session_name]

    def start(self) -> None:
        self.container = self._compose_manager.start()

    def stop(self) -> None:
        for session in self._sessions.values():
            session.stop()

        self._compose_manager.stop()

        self._sessions.clear()

    def stop_services_only(self) -> None:
        """Stop docker compose services but keep containers alive for debugging."""
        self._compose_manager.stop_services_only()
        self._sessions.clear()

    def copy_to_container(
        self,
        paths: list[Path] | Path,
        container_dir: str | None = None,
        container_filename: str | None = None,
    ):
        DockerComposeManager.copy_to_container(
            container=self.container,
            paths=paths,
            container_dir=container_dir,
            container_filename=container_filename,
        )


@contextmanager
def spin_up_terminal(
    client_container_name: str,
    client_image_name: str,
    docker_compose_path: Path,
    docker_name_prefix: str | None = None,
    sessions_path: Path | None = None,
    commands_path: Path | None = None,
    no_rebuild: bool = False,
    cleanup: bool = False,
    build_context_dir: Path | None = None,
    keep_alive: bool = False,
) -> Generator[Terminal, None, None]:
    terminal = Terminal(
        client_container_name=client_container_name,
        client_image_name=client_image_name,
        docker_name_prefix=docker_name_prefix,
        docker_compose_path=docker_compose_path,
        sessions_path=sessions_path,
        commands_path=commands_path,
        no_rebuild=no_rebuild,
        cleanup=cleanup,
        build_context_dir=build_context_dir,
    )

    try:
        terminal.start()
        yield terminal
    finally:
        # Only cleanup if keep_alive is False
        if not keep_alive:
            terminal.stop()
        else:
            # If keep_alive is True, just stop the services but don't remove containers
            logger.info(
                f"Keeping container {client_container_name} alive for debugging (--persist flag was used)"
            )
            terminal.stop_services_only()
