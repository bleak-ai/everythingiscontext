Run ad-hoc Python source in the project's .venv with secrets as env vars.
Use this for one-off exploration and smoke tests. When the code has proven
itself, save it with write_file under a scripts/ folder and run it with
run_script by path instead of pasting it again.

The .venv has all connection deps pre-installed. Access secrets with
os.environ["SECRET_NAME"]; secret values are scrubbed from the output.

The result starts with a status line `[exit N | M ms]` (plus `timed out` or
`truncated` when they apply), then stdout, then `[stderr]` when present, and
`[hint]` when a required package is missing.

Args:
    code: Python source code to execute.
    params: Optional named parameters; each becomes a PARAM_<NAME> env var
        (e.g. {"email": "x@y.z"} -> PARAM_EMAIL).
