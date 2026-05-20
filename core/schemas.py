import re

_VALID_MODULE_NAME = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_-]*$")


def validate_module_name(name: str) -> str:
    name = name.strip()
    if not name or not _VALID_MODULE_NAME.match(name):
        raise ValueError(
            f"Invalid module name: '{name}'. "
            "Must start with a letter or number, then letters, numbers, hyphens, underscores."
        )
    return name


def validate_module_file_path(file_path: str) -> str:
    file_path = file_path.strip().strip("/")
    if not file_path:
        raise ValueError("File path cannot be empty")
    if ".." in file_path:
        raise ValueError("File path cannot contain '..'")
    return file_path
