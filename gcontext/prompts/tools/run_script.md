Run a saved Python script from the project by path, in the project's .venv
with secrets as env vars (e.g. 'connections/stripe/scripts/refund.py').
For ad-hoc code use run_adhoc_script instead; once code has proven itself, save it
with write_file under a scripts/ folder and run it here by path so it is
reused instead of rewritten.

The .venv has all connection deps pre-installed. Scripts access secrets with
os.environ["SECRET_NAME"]; secret values are scrubbed from the output.

The result starts with a status line `[exit N | M ms]` (plus `timed out` or
`truncated` when they apply), then stdout, then `[stderr]` when present, and
`[hint]` when a required package is missing.

Args:
    path: Project-relative path of a saved .py script to run.
    args: Optional argv list passed to the script.
    params: Optional named parameters; each becomes a PARAM_<NAME> env var
        (e.g. {"email": "x@y.z"} -> PARAM_EMAIL).
    timeout: Optional timeout in seconds (default 60, max 600). Use a
        larger value for long browser runs.
