"""Targeted refinements preserve source and protect immutable identity."""

from unittest.mock import AsyncMock
from types import SimpleNamespace
import pytest

from backend.services.project_agent import ProjectAgent, ProposalValidationError, apply_changes
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


@pytest.mark.asyncio
async def test_plain_chat_accepts_fenced_json_without_provider_output_modes(simple_revision):
    client = AsyncMock()
    payload = simple_revision.model_dump()
    client.chat.completions.create.return_value = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(
        content='```json\n' + json.dumps(payload) + '\n```'))])
    revised = await ProjectAgent(client).propose({'profile': {}, 'description': ''}, None, 'Build dashboard', [])
    assert revised.steps == simple_revision.steps
    assert 'response_format' not in client.chat.completions.create.await_args.kwargs


@pytest.mark.asyncio
async def test_plain_chat_patch_keeps_run_diagnostics_and_local_validation(simple_revision):
    client = AsyncMock()
    client.chat.completions.create.return_value = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(
        content='{"summary":"Renamed","changes":[{"op":"replace","path":"/dashboard/title","value":"Fixed"}]}'))])
    diagnostics = {'runs': [{'status': 'failed', 'error': 'Invalid values in column value'}]}
    revised = await ProjectAgent(client).propose({'profile': {}, 'description': ''}, simple_revision,
        'Repair the last run', [], run_diagnostics=diagnostics)
    kwargs = client.chat.completions.create.await_args.kwargs
    assert 'response_format' not in kwargs
    assert json.loads(kwargs['messages'][1]['content'])['run_diagnostics'] == diagnostics
    assert revised.dashboard.title == 'Fixed'


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
async def test_legacy_encoded_patch_decodes_json_value(simple_revision):
    client = AsyncMock()
    client.chat.completions.create.return_value = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(
        content=json.dumps({'summary': 'Rename', 'changes': [{'op': 'replace', 'path': '/dashboard/title', 'value_json': json.dumps('Strict title')}]})))])
    revised = await ProjectAgent(client).propose({'profile': {}, 'description': ''}, simple_revision, 'Rename', [])
    assert revised.dashboard.title == 'Strict title'
    assert revised.steps == simple_revision.steps


@pytest.mark.asyncio
async def test_patch_accepts_compatible_model_plain_string_for_existing_string_field(simple_revision):
    client = AsyncMock()
    code = simple_revision.steps[0].code + "\n# Retain original observations according to the saved rule.\n"
    client.chat.completions.create.return_value = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(
        content=json.dumps({'summary': 'Refine', 'changes': [
            {'op': 'replace', 'path': '/dashboard/title', 'value_json': 'Plain title'},
            {'op': 'replace', 'path': '/steps/0/code', 'value_json': code},
        ]})))])
    revised = await ProjectAgent(client).propose({'profile': {}, 'description': ''}, simple_revision, 'Refine', [])
    assert revised.dashboard.title == 'Plain title'
    assert revised.steps[0].code == code


@pytest.mark.asyncio
async def test_patch_does_not_guess_malformed_non_string_values(simple_revision):
    client = AsyncMock()
    client.chat.completions.create.return_value = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(
        content=json.dumps({'summary': 'Bad array', 'changes': [
            {'op': 'replace', 'path': '/steps/0/outputs', 'value_json': '[broken'},
        ]})))])
    with pytest.raises(ValueError, match='must be valid JSON'):
        await ProjectAgent(client).propose({'profile': {}, 'description': ''}, simple_revision, 'Refine', [])


@pytest.mark.parametrize('content', ['[]', 'null', 'not JSON', '```json\n[1,2]\n```'])
def test_model_text_parser_rejects_invalid_objects(content):
    from backend.services.model_output import parse_model_object
    with pytest.raises(ValueError):
        parse_model_object(content)
