import platform
import shutil
import subprocess


def copy_to_clipboard(text: str) -> bool:
    system = platform.system()
    if system == "Darwin":
        tool_path = shutil.which("pbcopy")
        args = [tool_path] if tool_path else []
    elif system == "Linux":
        tool_path = shutil.which("xclip") or shutil.which("xsel")
        if tool_path and tool_path.endswith("xclip"):
            args = [tool_path, "-selection", "clipboard"]
        elif tool_path:
            args = [tool_path, "--clipboard", "--input"]
        else:
            args = []
    elif system == "Windows":
        tool_path = shutil.which("clip")
        args = [tool_path] if tool_path else []
    else:
        return False
    if not args:
        return False
    try:
        subprocess.run(args, input=text.encode(), check=True)
        return True
    except subprocess.CalledProcessError:
        return False
    except (OSError, FileNotFoundError):
        return False
