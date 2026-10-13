import os
import signal
import shutil
import subprocess
import tempfile
import uuid
from pathlib import Path
from dotenv import load_dotenv

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field


load_dotenv(Path(__file__).parent / ".env")

research_bearer = HTTPBearer(
    scheme_name="InsuranceResearchBearer",
    auto_error=False,
)


class InsuranceMarketResearchRequest(BaseModel):
    country: str = Field(default="Nepal", min_length=1, max_length=100)
    company: str | None = Field(default=None, max_length=200)
    topic: str | None = Field(default=None, max_length=300)
    max_results_per_query: int = Field(default=5, ge=1, le=10)


def require_insurance_research_token(
    credentials: HTTPAuthorizationCredentials | None,
):
    import hmac

    expected = os.environ.get("INSURANCE_RESEARCH_TOKEN", "")
    if not expected:
        raise HTTPException(
            status_code=503,
            detail="Insurance research authentication is not configured.",
        )

    if (
        credentials is None
        or credentials.scheme.lower() != "bearer"
        or not hmac.compare_digest(credentials.credentials, expected)
    ):
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing bearer token.",
        )

    return True


app = FastAPI(
    title="Prarambha Code Adapter",
    version="0.4.0",
    servers=[
        {
            "url": "http://host.docker.internal:9000"
        }
    ],
)


# ============================================================
# Configuration
# ============================================================

SANDBOX_IMAGE = "prarambha-code-sandbox:latest"

# Maximum time allowed for user code.
EXECUTION_TIMEOUT = 30

# Maximum amount of code accepted.
MAX_CODE_SIZE = 50_000

# Maximum stdout/stderr returned.
MAX_OUTPUT_SIZE = 100_000

# Docker sandbox resources.
SANDBOX_MEMORY = "1g"
SANDBOX_CPUS = "1"
SANDBOX_PIDS_LIMIT = "128"
# LibreChat Code API session settings.
SESSION_CONTAINER_PREFIX = "prarambha-session-"
SESSION_WORKSPACE_PREFIX = "prarambha-session-workspace-"

# In-memory session registry.
# session_id -> {
#     "container_name": str,
#     "workspace": Path,
#     "files": dict[file_id, metadata],
# }
SESSIONS = {}

# Temporary directory used for task workspaces.
TASK_WORKSPACE_PREFIX = "prarambha-workspace-"

# Directory where generated files are stored after task execution.
OUTPUT_DIRECTORY = Path(
    os.environ.get(
        "PRARAMBHA_OUTPUT_DIRECTORY",
        "./outputs",
    )
).resolve()

OUTPUT_DIRECTORY.mkdir(
    parents=True,
    exist_ok=True,
)

# ============================================================
# Request model
# ============================================================


# ============================================================
# Health check
# ============================================================

@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "code-adapter",
        "version": "0.4.0",
    }

# ============================================================
# Download generated files
# ============================================================
# ============================================================
# LibreChat file download
# ============================================================

@app.get("/download/{session_id}/{file_id}")
def download_session_file(
    session_id: str,
    file_id: str,
):
    """
    Download a file generated inside a LibreChat code session.
    """

    metadata = get_session_file(
        session_id,
        file_id,
    )

    if metadata is None:
        raise HTTPException(
            status_code=404,
            detail="Session file not found.",
        )

    file_path = metadata["path"]

    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(
            status_code=404,
            detail="File no longer exists.",
        )

    return FileResponse(
        path=file_path,
        filename=metadata["filename"],
    )

# ============================================================
# LibreChat session object metadata
# ============================================================

@app.get("/sessions/{session_id}/objects/{file_id}")
def get_session_object(
    session_id: str,
    file_id: str,
):
    """
    Return metadata for a file stored in a LibreChat
    code execution session.
    """

    metadata = get_session_file(
        session_id,
        file_id,
    )

    if metadata is None:
        raise HTTPException(
            status_code=404,
            detail="Session file not found.",
        )

    file_path = metadata["path"]

    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(
            status_code=404,
            detail="File no longer exists.",
        )

    return {
        "id": metadata["id"],
        "name": metadata["name"],
        "filename": metadata["filename"],
        "storage_session_id": metadata[
            "storage_session_id"
        ],
        "size": file_path.stat().st_size,
    }
    
@app.get("/files/{task_id}/{filename:path}")
def download_file(
    task_id: str,
    filename: str,
):
    """
    Safely download a file generated by a task.
    """

    # Resolve the task output directory.
    task_directory = (
        OUTPUT_DIRECTORY / task_id
    ).resolve()

    # Reject invalid task IDs that somehow escape
    # the main output directory.
    if (
        task_directory != OUTPUT_DIRECTORY
        and OUTPUT_DIRECTORY not in task_directory.parents
    ):
        raise HTTPException(
            status_code=400,
            detail="Invalid task ID.",
        )

    # Resolve the requested file.
    file_path = (
        task_directory / filename
    ).resolve()

    # Make sure the requested file remains inside
    # this task's output directory.
    if (
        file_path != task_directory
        and task_directory not in file_path.parents
    ):
        raise HTTPException(
            status_code=400,
            detail="Invalid file path.",
        )

    # File must actually exist.
    if not file_path.is_file():
        raise HTTPException(
            status_code=404,
            detail="File not found.",
        )

    return FileResponse(
        path=file_path,
        filename=file_path.name,
    )


# ============================================================
# Docker availability
# ============================================================

def docker_is_available():
    """
    Check whether the Docker CLI is available.
    """

    try:
        result = subprocess.run(
            [
                "docker",
                "info",
            ],
            capture_output=True,
            text=True,
            timeout=5,
        )

        return result.returncode == 0

    except (
        subprocess.TimeoutExpired,
        FileNotFoundError,
    ):
        return False


# ============================================================
# Sandbox image check
# ============================================================

def sandbox_image_exists():
    """
    Check whether the expected sandbox image exists locally.
    """

    try:
        result = subprocess.run(
            [
                "docker",
                "image",
                "inspect",
                SANDBOX_IMAGE,
            ],
            capture_output=True,
            text=True,
            timeout=5,
        )

        return result.returncode == 0

    except (
        subprocess.TimeoutExpired,
        FileNotFoundError,
    ):
        return False


# ============================================================
# Create temporary sandbox
# ============================================================

def create_sandbox(container_name, workspace, session_mode=False):
    """
    Create and start a sandbox container.

    Normal execution:
        /tmp is an isolated tmpfs.

    LibreChat session execution:
        /tmp and /mnt/data are backed by the persistent
        session workspace so files survive between /exec calls.
    """

    workspace = Path(workspace)

    command = [
        "docker",
        "run",
        "-d",

        # Unique container name.
        "--name",
        container_name,

        # No network access.
        "--network",
        "none",

        # Root filesystem cannot be modified.
        "--read-only",

        # Remove all Linux capabilities.
        "--cap-drop",
        "ALL",

        # Prevent privilege escalation.
        "--security-opt",
        "no-new-privileges:true",

        # Resource limits.
        "--memory",
        SANDBOX_MEMORY,

        "--cpus",
        SANDBOX_CPUS,

        "--pids-limit",
        SANDBOX_PIDS_LIMIT,
    ]

    if session_mode:
        # LibreChat needs files created through /tmp or /mnt/data
        # to survive between /exec calls and be discoverable by
        # the adapter.
        command.extend([
            "-v",
            f"{workspace}:/workspace:rw",

            "-v",
            f"{workspace}:/tmp:rw",

            "-v",
            f"{workspace}:/mnt/data:rw",
        ])
    else:
        # Keep the stronger isolated tmpfs for standalone execution.
        command.extend([
            "--tmpfs",
            "/tmp:rw,noexec,nosuid,nodev,size=64m",

            # Only the task workspace is writable.
            "-v",
            f"{workspace}:/workspace:rw",
        ])

    # Sandbox image.
    command.append(SANDBOX_IMAGE)

    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        raise RuntimeError(
            f"Failed to create sandbox: {result.stderr.strip()}"
        )

    return result.stdout.strip()


# ============================================================
# Execute code inside sandbox
# ============================================================

def execute_in_sandbox(container_name, code):
    """
    Execute Python code inside the temporary sandbox.

    The code is sent through stdin so we don't need to create
    a Python file inside the container.
    """

    command = [
        "docker",
        "exec",
        "-i",

        "-w",
        "/workspace",

        container_name,

        # Inner execution timeout.
        "timeout",
        "--signal=TERM",
        "--kill-after=5",
        f"{EXECUTION_TIMEOUT}s",

        # Isolated Python mode.
        "python",
        "-I",
        "-",
    ]

    process = None

    try:
        process = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,

            # Give this process its own process group.
            start_new_session=True,
        )

        stdout, stderr = process.communicate(
            input=code,
            timeout=EXECUTION_TIMEOUT + 10,
        )

    except subprocess.TimeoutExpired:

        # Outer safety timeout.
        if process is not None:

            try:
                os.killpg(
                    process.pid,
                    signal.SIGTERM,
                )
            except ProcessLookupError:
                pass

            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:

                try:
                    os.killpg(
                        process.pid,
                        signal.SIGKILL,
                    )
                except ProcessLookupError:
                    pass

                process.wait()

        return {
            "status": "timeout",
            "returncode": None,
            "stdout": "",
            "stderr": "Execution exceeded the adapter time limit.",
        }

    except Exception as exc:

        return {
            "status": "error",
            "returncode": None,
            "stdout": "",
            "stderr": f"Execution failed: {exc}",
        }

    # GNU timeout returns 124 when the command reaches
    # its configured timeout.
    if process.returncode == 124:
        return {
            "status": "timeout",
            "returncode": process.returncode,
            "stdout": stdout[:MAX_OUTPUT_SIZE],
            "stderr": (
                stderr[:MAX_OUTPUT_SIZE]
                if stderr.strip()
                else "Execution exceeded the time limit."
            ),
        }

    return {
        "status": (
            "success"
            if process.returncode == 0
            else "error"
        ),
        "returncode": process.returncode,
        "stdout": stdout[:MAX_OUTPUT_SIZE],
        "stderr": stderr[:MAX_OUTPUT_SIZE],
    }


# ============================================================
# Collect files created by the task
# ============================================================

def collect_files(workspace):
    """
    Return information about files created inside /workspace.

    At this stage we return metadata only.
    Actual file download/upload handling will be added next.
    """

    files = []

    if not workspace.exists():
        return files

    for path in workspace.rglob("*"):

        if not path.is_file():
            continue

        try:
            relative_path = path.relative_to(workspace)

            files.append(
                {
                    "name": str(relative_path),
                    "size": path.stat().st_size,
                }
            )

        except (
            OSError,
            ValueError,
        ):
            continue

    return files

def save_output_files(
    workspace: Path,
    task_id: str,
):
    """
    Copy generated files from the temporary task workspace
    into the persistent output directory.

    Returns metadata for the saved files.
    """

    task_output_directory = (
        OUTPUT_DIRECTORY / task_id
    )

    task_output_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    saved_files = []

    for source in workspace.rglob("*"):

        if not source.is_file():
            continue

        relative_path = source.relative_to(
            workspace
        )

        # Prevent unexpected path traversal.
        destination = (
            task_output_directory / relative_path
        ).resolve()

        if (
            destination != task_output_directory
            and task_output_directory
            not in destination.parents
        ):
            raise RuntimeError(
                "Generated file escaped the output directory."
            )

        destination.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        shutil.copy2(
            source,
            destination,
        )

        saved_files.append(
            {
                "name": str(relative_path),
                "size": destination.stat().st_size,
                "url": (
                    f"/files/{task_id}/"
                    f"{relative_path.as_posix()}"
                ),
            }
        )

    return saved_files


# ============================================================
# Remove sandbox
# ============================================================

def remove_sandbox(container_name):
    """
    Force-remove the temporary sandbox container.
    """

    try:
        subprocess.run(
            [
                "docker",
                "rm",
                "-f",
                container_name,
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )

    except (
        subprocess.TimeoutExpired,
        FileNotFoundError,
    ):
        pass

# ============================================================
# LibreChat session helpers
# ============================================================

def get_session(session_id: str):
    """
    Return an existing LibreChat code session.
    """
    return SESSIONS.get(session_id)


def create_session():
    """
    Create a persistent Docker sandbox for a LibreChat session.
    """

    session_id = uuid.uuid4().hex
    container_name = (
        f"{SESSION_CONTAINER_PREFIX}{session_id}"
    )

    workspace = Path(
        tempfile.mkdtemp(
            prefix=SESSION_WORKSPACE_PREFIX
        )
    )

    try:
        create_sandbox(
            container_name,
            workspace,
            session_mode=True,
        )

    except Exception:
        shutil.rmtree(
            workspace,
            ignore_errors=True,
        )
        raise

    SESSIONS[session_id] = {
        "container_name": container_name,
        "workspace": workspace,
        "files": {},
    }

    return session_id, SESSIONS[session_id]


def register_session_file(
    session_id: str,
    file_path: Path,
):
    """
    Register a file generated inside a LibreChat session.

    LibreChat identifies files using an ID rather than
    directly using the filename.
    """

    session = get_session(session_id)

    if session is None:
        raise RuntimeError(
            "LibreChat session does not exist."
        )

    file_id = uuid.uuid4().hex

    relative_path = file_path.relative_to(
        session["workspace"]
    )

    metadata = {
        "id": file_id,
        "name": str(relative_path),
        "filename": str(relative_path),
        "storage_session_id": session_id,
        "path": file_path,
    }

    session["files"][file_id] = metadata

    return metadata


def get_session_file(
    session_id: str,
    file_id: str,
):
    """
    Return a registered session file.
    """

    session = get_session(session_id)

    if session is None:
        return None

    return session["files"].get(file_id)

@app.post("/upload")
async def upload_file(request: Request):
    form = await request.form()

    entity_id = form.get("entity_id")
    uploaded = form.get("files")

    if uploaded is None:
        uploaded = form.get("file")

    if uploaded is None:
        raise HTTPException(
            status_code=400,
            detail="No file uploaded."
        )

    # LibreChat may send `files` as a list.
    if isinstance(uploaded, list):
        if not uploaded:
            raise HTTPException(
                status_code=400,
                detail="No file uploaded."
            )
        uploaded = uploaded[0]

    if not hasattr(uploaded, "filename"):
        raise HTTPException(
            status_code=400,
            detail="Invalid uploaded file."
        )

    # Use LibreChat's entity/session ID when available.
    session_id = str(entity_id) if entity_id else None

    if session_id:
        session = get_session(session_id)

        if session is None:
            # LibreChat may upload before /exec creates a session.
            session_id, session = create_session()
    else:
        session_id, session = create_session()

    workspace = session["workspace"]

    filename = Path(
        uploaded.filename or "uploaded_file"
    ).name

    if not filename:
        filename = "uploaded_file"

    destination = (
        workspace / filename
    ).resolve()

    if (
        destination != workspace
        and workspace not in destination.parents
    ):
        raise HTTPException(
            status_code=400,
            detail="Invalid uploaded filename."
        )

    try:
        file_size = 0

        with destination.open("wb") as output_file:
            while True:
                chunk = await uploaded.read(1024 * 1024)

                if not chunk:
                    break

                file_size += len(chunk)

                if file_size > 50 * 1024 * 1024:
                    destination.unlink(missing_ok=True)

                    raise HTTPException(
                        status_code=413,
                        detail="Uploaded file is too large."
                    )

                output_file.write(chunk)

        metadata = register_session_file(
            session_id,
            destination
        )

        return {
            "message": "success",
            "storage_session_id": session_id,
            "files": [
                {
                    "fileId": metadata["id"],
                    "filename": metadata["filename"],
                }
            ],
        }

    except HTTPException:
        raise

    except OSError as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to save uploaded file: {exc}"
        ) from exc

    finally:
        await uploaded.close()
        

class InternalDataRequest(BaseModel):
    query: str


@app.post("/tools/internal-data")
async def internal_data(request: InternalDataRequest):
    query = request.query.strip().lower()

    data = {
        "departments": [
            "Engineering",
            "Sales",
            "Research",
        ],
        "company_name": "Prarambha",
        "employee_count": 42,
    }

    if "department" in query:
        return {
            "success": True,
            "data": {
                "departments": data["departments"],
            },
        }

    if "employee" in query or "staff" in query:
        return {
            "success": True,
            "data": {
                "employee_count": data["employee_count"],
            },
        }

    return {
        "success": True,
        "data": data,
    }

@app.get("/tools/internal-data/openapi.json")
def internal_data_openapi():
    return {
        "openapi": "3.0.0",
        "info": {
            "title": "Prarambha Internal Data Tools",
            "version": "1.0.0",
        },
        "servers": [
            {
                "url": "http://host.docker.internal:9000"
            }
        ],
        "paths": {
            "/tools/internal-data": {
                "post": {
                    "operationId": "internal_data",
                    "summary": "Query Prarambha internal data",
                    "description": "Use this tool to retrieve information from Prarambha's internal data source.",
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "required": ["query"],
                                    "properties": {
                                        "query": {
                                            "type": "string",
                                            "description": "The information to retrieve from the internal data source."
                                        }
                                    }
                                }
                            }
                        }
                    },
                    "responses": {
                        "200": {
                            "description": "Internal data result",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object"
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }

# ============================================================
# LibreChat /exec endpoint
# ============================================================

@app.post("/exec")
async def librechat_exec(request: Request):
    """
    LibreChat-compatible code execution endpoint.

    A session keeps the same Docker sandbox alive across
    multiple executions.
    """
        # --------------------------------------------------------
    # Parse LibreChat JSON or multipart requests
    # --------------------------------------------------------

    content_type = request.headers.get("content-type", "").lower()
    
    print("=== LIBRECHAT EXEC REQUEST ===")
    print("Content-Type:", content_type)

    lang = "python"
    code = ""
    session_id = None
    files = None
    file = None

    if "application/json" in content_type:
        payload = await request.json()
        print("Payload:", payload)

        lang = payload.get("lang", "python")
        code = payload.get("code", "")
        session_id = payload.get("session_id")
        files = payload.get("files")

    elif "multipart/form-data" in content_type:
        form = await request.form()

        lang = form.get("lang", "python")
        code = form.get("code", "")
        session_id = form.get("session_id")
        files = form.get("files")
        file = form.get("file")

    else:
        raise HTTPException(
            status_code=415,
            detail="Unsupported Content-Type. Use application/json or multipart/form-data.",
        )
    # --------------------------------------------------------
    # Validate code
    # --------------------------------------------------------

    if not code.strip():
        raise HTTPException(
            status_code=400,
            detail="Code cannot be empty.",
        )

    if len(code) > MAX_CODE_SIZE:
        raise HTTPException(
            status_code=413,
            detail="Code is too large.",
        )

    # --------------------------------------------------------
    # Validate language
    # --------------------------------------------------------

    normalized_lang = lang.strip().lower()

    if normalized_lang not in {
        "python",
        "py",
        "bash",
        "sh",
        "shell",
    }:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported language: {lang}",
        )

    # --------------------------------------------------------
    # Check Docker
    # --------------------------------------------------------

    if not docker_is_available():
        raise HTTPException(
            status_code=503,
            detail="Docker is not available.",
        )

    if not sandbox_image_exists():
        raise HTTPException(
            status_code=503,
            detail=(
                f"Sandbox image '{SANDBOX_IMAGE}' "
                "does not exist."
            ),
        )

    # --------------------------------------------------------
    # Create or retrieve session
    # --------------------------------------------------------

    if not session_id and files:
        for file_info in files:
            if isinstance(file_info, dict):
                storage_session_id = file_info.get("storage_session_id")
                if storage_session_id and get_session(str(storage_session_id)):
                    session_id = str(storage_session_id)
                    break

    if session_id:
        session = get_session(session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="Code session not found.")
    else:
        try:
            session_id, session = create_session()
        except Exception as exc:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to create code session: {exc}",
            ) from exc

    container_name = session["container_name"]
    workspace = session["workspace"]

    # --------------------------------------------------------
    # Handle uploaded file
    # --------------------------------------------------------

    if file is not None:
        filename = Path(file.filename or "uploaded_file").name

        if not filename:
            filename = "uploaded_file"

        destination = (
            workspace / filename
        ).resolve()

        # Prevent the uploaded file from escaping /workspace.
        if (
            destination != workspace
            and workspace not in destination.parents
        ):
            raise HTTPException(
                status_code=400,
                detail="Invalid uploaded filename.",
            )

        try:
            file_size = 0

            with destination.open("wb") as output_file:
                while True:
                    chunk = await file.read(1024 * 1024)

                    if not chunk:
                        break

                    file_size += len(chunk)

                    if file_size > 50 * 1024 * 1024:
                        destination.unlink(
                            missing_ok=True
                        )

                        raise HTTPException(
                            status_code=413,
                            detail="Uploaded file is too large.",
                        )

                    output_file.write(chunk)

            # Register the uploaded file so LibreChat can
            # identify it through the session.
            existing_file = None

            for metadata in session["files"].values():
                if metadata["path"] == destination:
                    existing_file = metadata
                    break

            if existing_file is None:
                register_session_file(
                    session_id,
                    destination,
                )

        except HTTPException:
            raise

        except OSError as exc:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to save uploaded file: {exc}",
            ) from exc

        finally:
            await file.close()

    # --------------------------------------------------------
    # Prepare execution code
    # --------------------------------------------------------

    if normalized_lang in {
        "bash",
        "sh",
        "shell",
    }:
        command = [
            "docker",
            "exec",
            "-i",
            "-w",
            "/workspace",
            container_name,
            "timeout",
            "--signal=TERM",
            "--kill-after=5",
            f"{EXECUTION_TIMEOUT}s",
            "bash",
            "-s",
        ]

    else:
        command = [
            "docker",
            "exec",
            "-i",
            "-w",
            "/workspace",
            container_name,
            "timeout",
            "--signal=TERM",
            "--kill-after=5",
            f"{EXECUTION_TIMEOUT}s",
            "python",
            "-I",
            "-",
        ]

    # --------------------------------------------------------
    # Execute
    # --------------------------------------------------------

    try:
        process = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            start_new_session=True,
        )

        try:
            stdout, stderr = process.communicate(
                input=code,
                timeout=EXECUTION_TIMEOUT + 10,
            )

        except subprocess.TimeoutExpired:
            try:
                os.killpg(
                    process.pid,
                    signal.SIGKILL,
                )
            except ProcessLookupError:
                pass

            stdout, stderr = process.communicate()

            stderr = (
                (stderr or "")
                + "\nExecution timed out."
            )

        return_code = process.returncode

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Execution failed: {exc}",
        ) from exc

    # --------------------------------------------------------
    # Truncate output
    # --------------------------------------------------------

    stdout = stdout or ""
    stderr = stderr or ""

    if len(stdout) > MAX_OUTPUT_SIZE:
        stdout = (
            stdout[:MAX_OUTPUT_SIZE]
            + "\n[stdout truncated]"
        )

    if len(stderr) > MAX_OUTPUT_SIZE:
        stderr = (
            stderr[:MAX_OUTPUT_SIZE]
            + "\n[stderr truncated]"
        )

    # --------------------------------------------------------
    # Register generated files
    # --------------------------------------------------------

    response_files = []

    for path in workspace.rglob("*"):

        if not path.is_file():
            continue

        try:
            relative_path = path.relative_to(
                workspace
            )

            # Skip files already registered.
            existing = None

            for metadata in session["files"].values():
                if metadata["path"] == path:
                    existing = metadata
                    break

            if existing:
                response_files.append(
                    {
                        "id": existing["id"],
                        "name": existing["name"],
                        "storage_session_id": session_id,
                    }
                )
                continue

            metadata = register_session_file(
                session_id,
                path,
            )

            response_files.append(
                {
                    "id": metadata["id"],
                    "name": metadata["name"],
                    "storage_session_id": session_id,
                }
            )

        except (
            OSError,
            ValueError,
        ):
            continue

    # --------------------------------------------------------
    # Return LibreChat-compatible response
    # --------------------------------------------------------

    return {
        "stdout": stdout,
        "stderr": stderr,
        "session_id": session_id,
        "files": response_files,
        "return_code": return_code,
    }

# ============================================================
# Execute endpoint
# ============================================================

@app.post("/execute")
async def execute(
    code: str = Form(...),
    file: UploadFile | None = File(None),
):
    # --------------------------------------------------------
    # Validate code
    # --------------------------------------------------------

    if not code.strip():
        raise HTTPException(
            status_code=400,
            detail="Code cannot be empty.",
        )

    if len(code) > MAX_CODE_SIZE:
        raise HTTPException(
            status_code=413,
            detail="Code is too large.",
        )

    # --------------------------------------------------------
    # Check Docker
    # --------------------------------------------------------

    if not docker_is_available():
        raise HTTPException(
            status_code=503,
            detail="Docker is not available.",
        )

    # --------------------------------------------------------
    # Check sandbox image
    # --------------------------------------------------------

    if not sandbox_image_exists():
        raise HTTPException(
            status_code=503,
            detail=(
                f"Sandbox image '{SANDBOX_IMAGE}' "
                "is not available."
            ),
        )

    # --------------------------------------------------------
    # Create unique task
    # --------------------------------------------------------

    task_id = uuid.uuid4().hex[:12]

    container_name = (
        f"prarambha-task-{task_id}"
    )

    workspace = Path(
        tempfile.mkdtemp(
            prefix=(
                f"{TASK_WORKSPACE_PREFIX}"
                f"{task_id}-"
            )
        )
    )

    print(
        f"[TASK {task_id}] Starting"
    )

    print(
        f"[TASK {task_id}] "
        f"Workspace: {workspace}"
    )

    print(
        f"[TASK {task_id}] "
        f"Container: {container_name}"
    )

    try:

        # ----------------------------------------------------
        # Save uploaded file into workspace
        # ----------------------------------------------------

        uploaded_filename = None

        if file is not None:

            original_name = (
                Path(file.filename or "uploaded_file")
                .name
            )

            # Prevent empty filenames.
            if not original_name:
                raise HTTPException(
                    status_code=400,
                    detail="Invalid uploaded filename.",
                )

            destination = (
                workspace / original_name
            )

            print(
                f"[TASK {task_id}] "
                f"Uploading: {original_name}"
            )

            with destination.open("wb") as output:

                total_size = 0

                while True:

                    chunk = await file.read(1024 * 1024)

                    if not chunk:
                        break

                    total_size += len(chunk)

                    if total_size > 50 * 1024 * 1024:
                        raise HTTPException(
                            status_code=413,
                            detail=(
                                "Uploaded file is too large. "
                                "Maximum size is 50 MB."
                            ),
                        )

                    output.write(chunk)

            uploaded_filename = original_name

            print(
                f"[TASK {task_id}] "
                f"Uploaded {total_size} bytes"
            )

        # ----------------------------------------------------
        # Start fresh sandbox
        # ----------------------------------------------------

        container_id = create_sandbox(
            container_name,
            workspace,
        )

        print(
            f"[TASK {task_id}] "
            f"Sandbox started: {container_id}"
        )

        # ----------------------------------------------------
        # Execute code
        # ----------------------------------------------------

        execution = execute_in_sandbox(
            container_name,
            code,
        )

        print(
            f"[TASK {task_id}] "
            f"Execution status: "
            f"{execution['status']}"
        )

       # ----------------------------------------------------
       # Collect generated files
       # ----------------------------------------------------

        files = collect_files(
            workspace
        )

        # ----------------------------------------------------
        # Save generated files before workspace cleanup
        # ----------------------------------------------------

        saved_files = save_output_files(
            workspace,
            task_id,
        )

        print(
            f"[TASK {task_id}] "
            f"Files created: {len(files)}"
        )

        # ----------------------------------------------------
        # Return result
        # ----------------------------------------------------

        return {
            "task_id": task_id,
            "status": execution["status"],
            "returncode": execution["returncode"],
            "stdout": execution["stdout"],
            "stderr": execution["stderr"],
            "uploaded_file": uploaded_filename,
            "files": files,
            "saved_files": saved_files,
        }

    except RuntimeError as exc:

        raise HTTPException(
            status_code=500,
            detail=str(exc),
        )

    finally:

        # ----------------------------------------------------
        # ALWAYS remove sandbox
        # ----------------------------------------------------

        print(
            f"[TASK {task_id}] "
            "Removing sandbox..."
        )

        remove_sandbox(
            container_name
        )

        # ----------------------------------------------------
        # ALWAYS remove workspace
        # ----------------------------------------------------

        print(
            f"[TASK {task_id}] "
            "Removing workspace..."
        )

        shutil.rmtree(
            workspace,
            ignore_errors=True,
        )

        print(
            f"[TASK {task_id}] "
            "Cleanup complete"
        )
class WorkbookAnalysisRequest(BaseModel):
    filename: str | None = None


def make_json_safe(value):
    import math

    if isinstance(value, dict):
        return {str(k): make_json_safe(v) for k, v in value.items()}

    if isinstance(value, list):
        return [make_json_safe(v) for v in value]

    if isinstance(value, tuple):
        return [make_json_safe(v) for v in value]

    if isinstance(value, float) and not math.isfinite(value):
        return None

    return value


@app.post(
    "/tools/insurance-market-research",
    operation_id="insurance_market_research",
    summary="Research insurance market sources",
    description=(
        "Discover potential insurance regulator, industry, and company sources. "
        "Search results are leads and are not independently verified financial evidence."
    ),
    tags=["Research Tools"],
)
async def insurance_market_research_tool(
    request: InsuranceMarketResearchRequest,
    credentials: HTTPAuthorizationCredentials | None = Depends(research_bearer),
):
    require_insurance_research_token(credentials)

    from market_research import search_insurance_market

    try:
        result = search_insurance_market(
            country=request.country,
            company=request.company,
            topic=request.topic,
            max_results_per_query=request.max_results_per_query,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {"success": True, "data": result}


@app.get(
    "/tools/insurance-market-research/openapi.json",
    include_in_schema=False,
)
def insurance_market_research_openapi():
    return {
        "openapi": "3.0.3",
        "info": {
            "title": "Prarambha Insurance Market Research",
            "version": "1.0.0",
            "description": (
                "Discover candidate sources for insurance research. "
                "Search results are not independently verified financial evidence."
            ),
        },
        "servers": [{"url": "http://host.docker.internal:9000"}],
        "paths": {
            "/tools/insurance-market-research": {
                "post": {
                    "operationId": "insurance_market_research",
                    "summary": "Research insurance market sources",
                    "security": [{"InsuranceResearchBearer": []}],
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "country": {
                                            "type": "string",
                                            "default": "Nepal",
                                            "maxLength": 100,
                                        },
                                        "company": {
                                            "type": "string",
                                            "nullable": True,
                                            "maxLength": 200,
                                        },
                                        "topic": {
                                            "type": "string",
                                            "nullable": True,
                                            "maxLength": 300,
                                        },
                                        "max_results_per_query": {
                                            "type": "integer",
                                            "default": 5,
                                            "minimum": 1,
                                            "maximum": 10,
                                        },
                                    },
                                }
                            }
                        },
                    },
                    "responses": {
                        "200": {"description": "Research results"},
                        "401": {"description": "Missing or invalid bearer token"},
                        "503": {"description": "Authentication is not configured"},
                    },
                }
            }
        },
        "components": {
            "securitySchemes": {
                "InsuranceResearchBearer": {
                    "type": "http",
                    "scheme": "bearer",
                    "bearerFormat": "opaque token",
                }
            }
        },
    }


@app.post("/tools/analyze-workbook")
async def analyze_workbook_tool(request: WorkbookAnalysisRequest):
    from analyze_workbook import analyze_workbook
    from detect_anomalies import detect_anomalies

    incoming = Path(__file__).parent / "incoming"

    if request.filename:
        filename = Path(request.filename).name
        if not filename.lower().endswith(".xlsx"):
            raise HTTPException(status_code=400, detail="Only .xlsx files are supported")
        workbook = incoming / filename
    else:
        files = sorted(incoming.glob("*.xlsx"))
        if not files:
            raise HTTPException(status_code=404, detail="No Excel workbook found")
        workbook = files[-1]

    if not workbook.exists():
        raise HTTPException(status_code=404, detail="Workbook not found")

    analysis = analyze_workbook(workbook)
    anomalies = detect_anomalies(workbook, analysis)

    return make_json_safe({
        "success": True,
        "data": {
            "file": workbook.name,
            "analysis": analysis,
            "anomalies": anomalies,
        },
    })
