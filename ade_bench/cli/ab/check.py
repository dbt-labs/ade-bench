"""Commands for checking ADE-bench state."""

import os
from dotenv import load_dotenv
import typer
from rich import print
from rich.console import Console

stderr = Console(stderr=True)

container_runtime_available = False
macro_available = False
anthropic_available = False
openai_available = False
gemini_available = False
failurequeue = []
successqueue = []


def add_failure(message):
    failurequeue.append(message)


def add_success(message):
    successqueue.append(message)


def print_failure():
    if len(failurequeue) == 0 and len(successqueue) > 0:
        print("[✅] No failures to report.")
    for message in failurequeue:
        stderr.print("[❌] "+message)


def print_success():
    if len(successqueue) == 0:
        pass
    for message in successqueue:
        print("[✅] "+message)


def print_ade_summary():
    if container_runtime_available:
        macro_str = ', macro' if macro_available else ''
        claude_str = ', claude' if anthropic_available else ''
        codex_str = ', codex' if openai_available else ''
        gemini_str = ', gemini' if gemini_available else ''
        print(f"[bold blue]ADE is in a good state to run! Assuming API keys are correct and valid, you have access to the following agents: none, sage{macro_str}{claude_str}{codex_str}{gemini_str}.[/bold blue]")
    else:
        error_msg = '' if container_runtime_available else 'No container runtime to work with, currently ADE needs Docker.'
        stderr.print(f"[bold red]ADE is not in a good state to run! {error_msg}[/bold red]")


app = typer.Typer(
    help="Check ADE-bench's state",
    no_args_is_help=True,
)


def check_result_callback(result):
    """Print check results."""
    print_success()
    print_failure()
    print_ade_summary()

    
@app.callback(result_callback=check_result_callback)
def check_callback():
    pass


@app.command("all")
def check_all():
    """
    Just run all of the checks.
    """
    if is_dotenv_available():
        check_macro_key()
        check_anthropic_key()
        check_openai_key()
        check_gemini_key()

    is_docker_available()
    is_podman_available()


environmentapp = typer.Typer(
    help="Check ADE-bench's .env state",
    no_args_is_help=True,
)


def check_provider_key(keyname):
    value = os.getenv(keyname)
    if value is None or value.strip() == "":
        add_failure(f"{keyname} is missing or empty.")
        return False
    else:
        add_success(f"{keyname} is set.")
        return True


@environmentapp.command("env-file")
def is_dotenv_available():
    """
    Check if .env exists and is loadable.
    """
    if not os.path.exists(".env"):
        add_failure(".env file not found.")
        return False

    try:
        load_dotenv(".env")
        add_success(".env file loaded successfully.")
        return True
    except:  # noqa: E722
        add_failure("Failed to load .env file.")
        return False


@environmentapp.command("macro")
def check_macro_key():
    """
    Check MACRO_API_KEY.
    """
    global macro_available
    if check_provider_key("MACRO_API_KEY"):
        macro_available = True


@environmentapp.command("anthropic")
def check_anthropic_key():
    """
    Check ANTHROPIC_API_KEY.
    """
    global anthropic_available
    if check_provider_key("ANTHROPIC_API_KEY"):
        anthropic_available = True


@environmentapp.command("openai")
def check_openai_key():
    """
    Check OPENAI_API_KEY.
    """
    global openai_available
    if check_provider_key("OPENAI_API_KEY"):
        openai_available = True


@environmentapp.command("gemini")
def check_gemini_key():
    """
    Check GEMINI_API_KEY.
    """
    global gemini_available
    if check_provider_key("GEMINI_API_KEY"):
        gemini_available = True


containerapp = typer.Typer(
    help="Check ADE-bench's containerization state",
    no_args_is_help=True,
)


@containerapp.command("docker")
def is_docker_available():
    """
    Check if python can connect to an actively running docker daemon.
    """
    global container_runtime_available
    import docker
    try:
        docker.from_env()
        add_success("Connected to a running docker daemon.")
        container_runtime_available = True
    except:  # noqa: E722
        add_failure("Could not connect to a running docker daemon.")


@containerapp.command("podman")
def is_podman_available():
    """
    Check if python can connect to an actively running podman daemon.
    """
    import podman
    try:
        podman.from_env()
        add_success("Connected to a running podman daemon.")
        add_failure("Note: ADE does not support podman, yet. This message will be removed when it is supported.")
    except:  # noqa: E722
        add_failure("Could not connect to a running podman daemon.")


app.add_typer(environmentapp, name="environment")
app.add_typer(containerapp, name="container")
