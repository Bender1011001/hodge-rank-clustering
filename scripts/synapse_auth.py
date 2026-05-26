import os
from pathlib import Path

import synapseclient


TOKEN_ENV_VARS = ("SYNAPSE_AUTH_TOKEN", "SYNAPSE_PAT")


def load_local_env():
    env_path = Path(__file__).resolve().parents[1] / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        name, value = stripped.split("=", 1)
        name = name.strip()
        value = value.strip().strip("\"'")
        if name and name not in os.environ:
            os.environ[name] = value


def login_synapse():
    load_local_env()
    syn = synapseclient.Synapse()
    token = next(
        (
            os.environ[name].strip()
            for name in TOKEN_ENV_VARS
            if os.environ.get(name, "").strip()
        ),
        None,
    )
    if token:
        syn.login(authToken=token, silent=True)
    else:
        syn.login(silent=True)
    return syn
