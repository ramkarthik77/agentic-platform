"""Deterministic site bundles from reviewed templates; no AEM or repository writes."""
import json
from pathlib import Path
from string import Template
from . import db
from .config import ROOT
from .contracts import SiteSpec
from .http import ConnectionProblem
from .setup import safe_path


def render_site(request, settings):
    spec = SiteSpec.model_validate(request['site_spec'])
    config = settings.workspace
    fixture = settings.integration_mode == 'fixture'
    if not fixture and (not config.templates_directory or not config.templates_approved):
        raise ConnectionProblem('reviewed_site_templates_required')
    directory = Path(config.templates_directory) if config.templates_directory else ROOT / 'templates' / 'site'
    manifest = json.loads((directory / 'manifest.json').read_text())
    if manifest.get('version') != 1 or not isinstance(manifest.get('files'), dict) or not 1 <= len(manifest['files']) <= 29:
        raise ConnectionProblem('invalid_template_manifest')
    values = spec.model_dump() | {'environment': request['environment']}
    rendered = []
    for path, source in manifest['files'].items():
        if not isinstance(source, str) or len(source) > 100_000:
            raise ConnectionProblem('template_size_limit')
        filename = safe_path(Template(path).substitute(values))
        content = Template(source).substitute(values)
        rendered.append({'path': filename, 'content': content})
    if len({f['path'] for f in rendered}) != len(rendered):
        raise ConnectionProblem('duplicate_template_path')
    plan = {'site': spec.model_dump(), 'environment': request['environment'],
            'steps': ['Review configuration and run project validation', 'Merge the reviewed PR through normal controls',
                      'Create the MSM live copy through the approved AEM provisioning process',
                      'Configure domain and certificate', 'Verify author, publish, and CDN routes'],
            'aem_write_executed': False, 'publishing_executed': False}
    rendered.append({'path': f'docs/sites/{spec.slug}/provisioning.json', 'content': json.dumps(plan, indent=2) + '\n'})
    if len({f['path'] for f in rendered}) != len(rendered) or sum(len(f['content']) for f in rendered) > 500_000:
        raise ConnectionProblem('bundle_path_or_size_limit')
    return {'source': 'fixture' if fixture else 'reviewed_templates', 'files': rendered, 'site': spec.model_dump(),
            'template_digest': db.digest(manifest), 'templates_approved': config.templates_approved and not fixture,
            'coverage_note': 'Generated configuration and provisioning plan. A merged PR alone does not provision or publish a site.'}
