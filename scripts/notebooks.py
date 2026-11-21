"""Execute the five checked-in notebooks against the generated full snapshot."""
import sys
from pathlib import Path

import nbformat
from nbclient import NotebookClient
from jupyter_client import KernelManager

ROOT = Path(__file__).resolve().parents[1]


class CurrentPythonKernel(KernelManager):
    """Use the interpreter running this command, including its virtualenv."""

    def format_kernel_cmd(self, extra_arguments=None):
        command = super().format_kernel_cmd(extra_arguments)
        command[0] = sys.executable
        return command


for path in sorted((ROOT/"notebooks").glob("*.ipynb")):
    notebook = nbformat.read(path, as_version=4)
    manager = CurrentPythonKernel(kernel_name="python3")
    client = NotebookClient(notebook, km=manager, timeout=180,
                            resources={"metadata":{"path": str(ROOT)}})
    client.execute(cleanup_kc=True)
    nbformat.write(notebook, path)
    print(f"Executed {path.name}")
