import io
import subprocess
import tarfile
from contextlib import contextmanager
from pathlib import Path
from typing import Generator

import docker
import docker.errors
from docker.models.containers import Container

from ade_bench.utils.env_model import EnvModel
from ade_bench.utils.logger import logger

# Repo root is always two levels up from this file (ade_bench/terminal/docker_compose_manager.py)
REPO_ROOT = Path(__file__).parent.parent.parent.resolve()


class DockerComposeEnvVars(EnvModel):
    task_docker_client_container_name: str | None = None
    task_docker_client_image_name: str | None = None
    task_docker_name_prefix: str | None = None
    container_logs_path: str | None = None
    test_dir: str | None = None
    task_build_context_dir: str | None = None
    task_logs_path: str | None = None
    repo_root: str | None = None


class DockerComposeManager:
    CONTAINER_LOGS_PATH = Path("/logs")
    CONTAINER_TEST_DIR = Path("/tests")
    CONTAINER_SCRIPTS_DIR = Path("/scripts")
    CONTAINER_SEEDS_DIR = Path("/seeds")
    CONTAINER_SOLUTIONS_DIR = Path("/solutions")
    CONTAINER_APP_DIR = Path("/app")
    CONTAINER_SETUP_DIR = Path("/app/setup")
    CONTAINER_MIGRATION_DIR = Path("/app/migrations")

    def __init__(
        self,
        client_container_name: str,
        client_image_name: str,
        docker_compose_path: Path,
        docker_name_prefix: str | None = None,
        no_rebuild: bool = False,
        cleanup: bool = False,
        logs_path: Path | None = None,
        build_context_dir: Path | None = None,
    ):
        try:
            self._client = docker.from_env()
        except docker.errors.DockerException as e:
            raise RuntimeError(
                (
                    f"Error creating docker client: {e}",
                    "Please ensure that Docker is installed and running.",
                )
            )

        self._client_container_name = client_container_name
        self._client_image_name = client_image_name
        self._docker_name_prefix = docker_name_prefix
        self._docker_compose_path = docker_compose_path
        self._no_rebuild = no_rebuild
        self._cleanup = cleanup
        self._client_container: Container | None = None
        self._logs_path = logs_path
        self._build_context_dir = build_context_dir
        self._logger = logger.getChild(__name__)

    def _run_docker_compose_command(
        self, command: list[str]
    ) -> subprocess.CompletedProcess:
        """Run a docker-compose command with the appropriate environment variables."""
        env = DockerComposeEnvVars(
            task_docker_client_image_name=self._client_image_name,
            task_docker_client_container_name=self._client_container_name,
            task_docker_name_prefix=self._docker_name_prefix,
            container_logs_path=str(self.CONTAINER_LOGS_PATH),
            test_dir=str(self.CONTAINER_TEST_DIR),
            task_build_context_dir=(
                str(self._build_context_dir.absolute())
                if self._build_context_dir
                else None
            ),
            task_logs_path=(
                str(self._logs_path.absolute()) if self._logs_path is not None else None
            ),
            repo_root=str(REPO_ROOT),
        ).to_env_dict(include_os_env=True)

        full_command = [
            "docker",
            "compose",
            "-p",
            self._client_container_name,
            "-f",
            str(self._docker_compose_path.resolve().absolute()),
            *command,
        ]
        self._logger.debug(f"Running docker compose command: {' '.join(full_command)}")

        try:
            result = subprocess.run(
                full_command,
                env=env,
                check=True,
                capture_output=True,
                text=True,
            )
            return result
        except subprocess.CalledProcessError as e:
            self._logger.error(
                f"Docker compose command failed with exit code {e.returncode}"
            )

            self._logger.error(f"Command: {' '.join(full_command)}")

            if e.stdout:
                self._logger.error(f"STDOUT: {e.stdout}")

            if e.stderr:
                self._logger.error(f"STDERR: {e.stderr}")

            raise

    def start(self) -> Container:
        if not self._no_rebuild:
            self._run_docker_compose_command(["build"])

        self._run_docker_compose_command(["up", "-d"])

        self._client_container = self._client.containers.get(
            self._client_container_name
        )

        return self._client_container

    def stop(self) -> None:
        """Stop and remove the docker compose services."""
        try:
            self._run_docker_compose_command(["down"])

            if self._cleanup:
                self._run_docker_compose_command(["down", "--rmi", "all", "--volumes"])
        except Exception as e:
            self._logger.error(f"Error cleaning up docker compose services: {e}")

    def stop_services_only(self) -> None:
        """Keep containers alive for debugging without stopping services."""
        try:
            # Don't stop anything, just log that we're keeping the container running
            if self._client_container:
                container_id = self._client_container.id[:12]
                container_name = self._client_container.name
                self._logger.info(f"Container kept alive for debugging: {container_name} (ID: {container_id})")
                self._logger.info(f"To connect to the container: docker exec -it {container_name} bash")
            else:
                self._logger.info("Containers kept alive for debugging.")
        except Exception as e:
            self._logger.error(f"Error in stop_services_only: {e}")

    @staticmethod
    def _create_tar_archive(
        paths: list[Path], container_filename: str | None
    ) -> io.BytesIO:
        tar_stream = io.BytesIO()
        with tarfile.open(fileobj=tar_stream, mode="w") as tar:
            for path in paths:
                if path.is_file():
                    arcname = container_filename if container_filename else path.name
                    tar.add(path, arcname=arcname)
                elif path.is_dir():
                    for item in path.rglob("*"):
                        tar.add(item, arcname=item.relative_to(path))
                else:
                    raise ValueError(f"Path {path} is neither a file nor directory")

        tar_stream.seek(0)
        return tar_stream

    @staticmethod
    def copy_to_container(
        container: Container,
        paths: list[Path] | Path,
        container_dir: str | None = None,
        container_filename: str | None = None,
    ) -> None:
        """Copy files or directories to a running docker container."""
        container_dir = container_dir or container.attrs["Config"]["WorkingDir"]

        if container_dir is None:
            raise ValueError("Container working directory not found")

        if isinstance(paths, Path):
            paths = [paths]

        tar_stream = DockerComposeManager._create_tar_archive(paths, container_filename)
        container.put_archive(container_dir, tar_stream.read())
        tar_stream.close()

@contextmanager
def spin_up_container(
    client_container_name: str,
    client_image_name: str,
    docker_compose_path: Path,
    docker_name_prefix: str | None = None,
    no_rebuild: bool = False,
    cleanup: bool = False,
    logs_path: Path | None = None,
) -> Generator[Container, None, None]:
    container_manager = DockerComposeManager(
        client_container_name=client_container_name,
        client_image_name=client_image_name,
        docker_compose_path=docker_compose_path,
        no_rebuild=no_rebuild,
        cleanup=cleanup,
        logs_path=logs_path,
        docker_name_prefix=docker_name_prefix,
    )

    try:
        container = container_manager.start()
        yield container
    finally:
        container_manager.stop()
