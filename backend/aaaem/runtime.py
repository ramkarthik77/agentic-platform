"""Materialize injected configuration for containers without committing tenant files."""
import json
import os
import tempfile
from pathlib import Path


def prepare_config():
    workspace = os.environ.pop('AAAEM_WORKSPACE_JSON', '')
    registry = os.environ.pop('AAAEM_REGISTRY_JSON', '')
    if not workspace and not registry:
        return
    if not workspace:
        raise ValueError('AAAEM_WORKSPACE_JSON is required when injecting a registry')
    config = json.loads(workspace)
    directory = Path(tempfile.mkdtemp(prefix='aaaem-config-'))
    directory.chmod(0o700)
    def write(name, value):
        path = directory / name
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'w') as stream:
            json.dump(value, stream)
        return str(path)
    if registry:
        config['registry_file'] = write('registry.json', json.loads(registry))
    os.environ['AAAEM_CONFIG_FILE'] = write('workspace.json', config)
