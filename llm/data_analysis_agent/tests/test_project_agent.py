"""Targeted refinements preserve source and protect immutable identity."""

from unittest.mock import AsyncMock
from types import SimpleNamespace
import pytest

from backend.services.project_agent import ProjectAgent, ProposalValidationError, apply_changes, strict_schema
from pipeline_core.models import ProjectRevision
import json


@pytest.mark.asyncio
async def test_title_refinement_preserves_all_analysis_code(simple_revision):
    client = AsyncMock()
    client.chat.completions.create.return_value = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(
        content='{"summary":"Rename the dashboard", "changes":[{"op":"replace","path":"/dashboard/title","value":"Facility Energy Review"}]}'))])
    revised = await ProjectAgent(client).propose({"profile": {}, "description": ""}, simple_revision, "Change dashboard title", [])
    assert revised.dashboard.title == "Facility Energy Review"
    assert revised.title == simple_revision.title
    assert revised.steps == simple_revision.steps
    assert revised.parameters == simple_revision.parameters
    assert revised.parent_revision_id == simple_revision.revision_id
    assert revised.revision_id != simple_revision.revision_id


def test_strict_schema_preserves_parameter_default_property():
    schema = strict_schema(ProjectRevision.model_json_schema())
    parameters = schema['$defs']['ParameterSpec']
    assert 'default' in parameters['properties']
    assert set(parameters['required']) == set(parameters['properties'])
    assert 'default' not in parameters['properties']['default']


@pytest.mark.parametrize('change', [
    {'op': 'replace', 'path': '/revision_id', 'value': 'changed'},
    {'op': 'replace', 'path': '/steps/999/code', 'value': 'bad'},
    {'op': 'remove', 'path': '/steps/-1'},
])
def test_patch_rejects_invalid_or_identity_changes(simple_revision, change):
    with pytest.raises(ValueError): apply_changes(simple_revision.model_dump(), [change])


@pytest.mark.asyncio
async def test_invalid_proposal_retains_source_for_repair(simple_revision):
    payload = simple_revision.model_dump()
    payload['dashboard']['widgets'][0]['value'] = 30
    client = AsyncMock()
    client.chat.completions.create.return_value = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(payload)))])
    with pytest.raises(ProposalValidationError) as error:
        await ProjectAgent(client).propose({'profile': {}, 'description': ''}, None, 'Create dashboard', [])
    assert error.value.proposal['dashboard']['widgets'][0]['value'] == 30
    client.chat.completions.create.return_value = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(
        content='{"summary":"Fix widget contract", "changes":[{"op":"remove","path":"/dashboard/widgets/0/value"}]}'))])
    repaired = await ProjectAgent(client).propose({'profile': {}, 'description': ''}, None, 'Create dashboard', [], str(error.value), error.value.proposal)
    assert repaired.steps == simple_revision.steps


@pytest.mark.asyncio
async def test_strict_patch_decodes_json_value(simple_revision):
    client = AsyncMock()
    client.chat.completions.create.return_value = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(
        content=json.dumps({'summary': 'Rename', 'changes': [{'op': 'replace', 'path': '/dashboard/title', 'value_json': json.dumps('Strict title')}]})))])
    revised = await ProjectAgent(client).propose({'profile': {}, 'description': ''}, simple_revision, 'Rename', [])
    assert revised.dashboard.title == 'Strict title'
    assert revised.steps == simple_revision.steps
