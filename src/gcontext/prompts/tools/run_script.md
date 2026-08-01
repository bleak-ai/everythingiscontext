Run Python in the project's .venv with secrets as env vars.

Two modes, pass exactly one of `code` or `path`:
- code: ad-hoc Python source, written to a temp file and executed.
- path: a saved script inside the project (e.g. 'connections/stripe/scripts/refund.py').
  Save proven procedures with write_file under a scripts/ folder, then run
  them by path so they are reused instead of rewritten.

The .venv has all connection deps pre-installed. Access secrets with
os.environ["SECRET_NAME"]. Secret values are scrubbed from stdout/stderr
before returning. The result starts with a status line: mode, exit code,
duration.

Args:
    code: Python source code to execute (ad-hoc mode).
    path: Project-relative path of a saved .py script to run.
    args: Optional argv list passed to the script.
    params: Optional named parameters; each becomes a PARAM_<NAME> env var
        (e.g. {"email": "x@y.z"} -> PARAM_EMAIL).
