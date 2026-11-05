"""Execution snapshots for incomplete workspaces. These are never release revisions."""
from pydantic import Field, model_validator

from pipeline_core.models import DashboardSpec, PipelineStep, ProjectRevision, Widget
from pipeline_core.workspace import WorkspaceDocument


class PartialDashboard(DashboardSpec):
    widgets: list[Widget] = Field(default_factory=list)


class PartialRevision(ProjectRevision):
    steps: list[PipelineStep] = Field(default_factory=list, max_length=40)
    dashboard: PartialDashboard

    @model_validator(mode='after')
    def validate_graph(self) -> 'PartialRevision':
        from pipeline_core.validation import validate_revision
        validate_revision(self, partial=True)
        return self


def execution_plan(document: WorkspaceDocument) -> tuple[PartialRevision, list[dict]]:
    from pipeline_core.validation import validate_source
    if not document.input_enabled or document.input_contract is None:
        raise ValueError('Define the Data input columns before Run')
    outputs = [name for step in document.steps for name in step.outputs]
    if len(set(outputs)) != len(outputs) or 'data' in outputs:
        raise ValueError('Output names must be unique and cannot replace data')
    available = {'data'}
    pending = list(document.steps)
    selected: list[PipelineStep] = []
    blocked = []
    for step in list(pending):
        try:
            validate_source(step.code, step.function)
        except (ValueError, SyntaxError) as exc:
            blocked.append({'step_id': step.id, 'title': step.title, 'status': 'blocked', 'message': str(exc)})
            pending.remove(step)
    while pending:
        ready = [s for s in pending if set(s.inputs) <= available and not (
            s.stage == 'cleanup' and any(v.stage == 'analysis' for v in selected)) and not (
            s.stage == 'analysis' and any(p.filter_column and p.filter_artifact not in available for p in document.parameters))]
        if not ready:
            break
        ready.sort(key=lambda s: s.stage != 'cleanup')
        step = ready[0]
        selected.append(step)
        pending.remove(step)
        available.update(step.outputs)
    blocked.extend({'step_id': s.id, 'title': s.title, 'status': 'blocked',
        'message': 'Missing inputs, a dependency cycle, or an unavailable filter source'} for s in pending)
    widgets = [w for w in document.dashboard.widgets if w.output in available - {'data'}]
    data = document.model_dump(exclude={'input_enabled'})
    data['steps'] = [s.model_dump() for s in selected]
    data['dashboard']['widgets'] = [w.model_dump() for w in widgets]
    return PartialRevision.model_validate(data), blocked
