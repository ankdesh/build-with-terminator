"""Run isolated Bedrock acceptance cases. No user project is read or changed.

Usage: .venv/bin/python -m scripts.evaluate_agent --repeats 3 --output /tmp/agent-evaluation.json
"""
from __future__ import annotations
import argparse
import asyncio
import json
import tempfile
import threading
import time
from pathlib import Path
from typing import Any
from backend.services.agent_controller import AgentController
from backend.services.agent_store import AgentStore
from backend.services.project_service import ProjectService
from backend.services.project_store import ProjectStore
from backend.services.llm_gateway import LLMGateway
from pipeline_core.models import ProjectRevision
from config import config

REFERENCE = {
 'title':'Acceptance reference','summary':'Remove exact duplicates and missing readings.',
 'input_contract':{'columns':[{'name':'zone','dtype':'string'},{'name':'value','dtype':'number'}]},
 'steps':[
  {'id':'cleanup','title':'Clean readings','stage':'cleanup','function':'clean','inputs':['data'],'outputs':['cleaned'],
   'code':"def clean(inputs, parameters, context):\n    return {'cleaned': inputs['data'].drop_duplicates().dropna(subset=['value']).copy()}\n"},
  {'id':'totals','title':'Totals','stage':'analysis','function':'calculate','inputs':['cleaned'],'outputs':['total','records'],
   'code':"def calculate(inputs, parameters, context):\n    df = inputs['cleaned'].copy()\n    return {'total': float(df['value'].sum()), 'records': df}\n"}],
 'dashboard':{'title':'Reference','widgets':[{'id':'total','kind':'metric','title':'Total','output':'total'},
   {'id':'records','kind':'table','title':'Records','output':'records'}]}}
# Numeric checks inspect executed artifacts, not the model's prose.
CASES: list[dict[str,Any]] = [
 {'name':name,'query':query,'kind':'analysis','expected':expected}
 for name,query,expected in [
 ('clean_sum','What is the sum of value after the current cleaning?',30),
 ('clean_mean','Calculate the mean value after cleaning.',15),
 ('clean_count','How many rows remain after cleaning?',2),
 ('clean_max','Calculate the maximum value in cleaned data.',20),
 ('clean_min','Calculate the minimum value in cleaned data.',10),
 ('clean_median','Calculate the median value after cleaning.',15),
 ('raw_sum','Calculate the sum of value from the raw CSV, before cleaning.',40),
 ('raw_rows','Count every row in the raw CSV, including rows with missing values.',4),
 ('raw_missing','How many rows have a missing value in the raw CSV?',1),
 ('filtered_sum','Using cleaned data, calculate the sum of value for zone B only.',20),
 ('empty_count','Using cleaned data, count the rows where zone equals Z.',0),
 ('above_threshold','How many cleaned readings have value greater than 15?',1),
 ('range','Calculate maximum minus minimum value in cleaned data.',10),
 ('squares','Calculate the sum of squared values in cleaned data.',500),
 ('distinct_zones','Count distinct zones after cleaning.',2),
 ('raw_nonnull','Count non-missing entries in the value column of raw data.',3),
 ('raw_mean','Calculate mean value in raw data, ignoring missing values.',40/3),
 ('raw_duplicates','Count exact duplicate rows in raw data, counting repeats after the first.',1),
 ]]
CASES += [
 {'name':'bar','query':'Show a temporary bar chart of cleaned value totals by zone. Do not save changes.','kind':'analysis','chart':True},
 {'name':'table','query':'Show all cleaned rows as a temporary table.','kind':'analysis','rows':2},
 {'name':'selected_question','query':'Calculate the mean cleaned value for me.','stage':'step:cleanup','kind':'analysis','expected':15},
 {'name':'page_advisory','query':'Calculate the sum of cleaned value.','page':'dashboard','kind':'analysis','expected':30},
]
CASES += [{'name':name,'query':query,'kind':'answer'} for name,query in [
 ('explain_cleanup','Explain what the cleaning stage does. Do not change anything.'),
 ('explain_inputs','Explain the inputs and outputs of the Totals stage. Do not change anything.'),
 ('explain_missing','Does the current cleaning remove missing values? Explain from the source.'),
 ('explain_duplicates','Does the current cleaning remove duplicate rows? Explain from the source.'),
 ('explain_dashboard','Explain which outputs the dashboard widgets display.'),
]]
CASES += [{'name':name,'query':query,'kind':'clarification'} for name,query in [
 ('ambiguous_best','Which zone is best?'),
 ('ambiguous_growth','Calculate the growth rate.'),
 ('missing_business_rule','Save a stage that classifies good and bad readings. Ask me for the thresholds.'),
 ('missing_column','Calculate total revenue. Do not assume value means revenue; ask me which column to use.'),
]]
CASES += [{'name':name,'query':query,'stage':stage,'kind':'proposal'} for name,query,stage in [
 ('rename_widget','Rename this metric widget to Reviewed total.','widget:total'),
 ('rename_step','Rename this cleaning stage to Reviewed cleaning. Preserve the calculation.','step:cleanup'),
 ('rename_dashboard','Set the dashboard title to Reviewed dashboard. Do not change calculations.',None),
 ('rewrite_mean','Change this analysis to calculate the mean value instead of the sum, keeping the total output name and records output. Handle empty data.','step:totals'),
 ('add_count','Add an analysis stage that counts cleaned rows and outputs row_count. Do not add widgets.','category:analysis'),
 ('add_table','Add a second table widget titled Reviewed records for the existing records output. Keep the original table widget and preserve calculations.','category:visualization'),
 ('rename_project','Rename the project to Reviewed project. Preserve all stages.',None),
]]
CASES += [{'name':'scope_expansion','query':'Rename this metric widget to Reviewed total and rename the project to Reviewed project. Both edits are required.','stage':'widget:total','kind':'clarification','scope':True}]
CASES += [{'name':'new_project','kind':'proposal','new_project':True,'query':
 'Create an overview dashboard. Define the input contract for zone (string) and value (nullable number). '
 'Clean exact duplicates and remove rows missing value. Calculate total value, grouped total value by zone, '
 'and the full cleaned table. Add a total metric, a bar chart by zone and a table widget. Add a zone filter '
 'with All as its default. Handle empty filtered data. These cleaning rules are approved for this proposal.'}]
assert len(CASES)==40


def numbers(value: Any) -> list[float]:
 if isinstance(value,bool): return []
 if isinstance(value,(int,float)): return [float(value)]
 if isinstance(value,dict): return [n for v in value.values() for n in numbers(v)]
 if isinstance(value,list): return [n for v in value for n in numbers(v)]
 return []


async def evaluate(case: dict, repeat: int, semaphore: asyncio.Semaphore) -> dict:
 async with semaphore:
  started=time.monotonic();report={'name':case['name'],'repeat':repeat,'query':case['query'],'passed':False}
  with tempfile.TemporaryDirectory(prefix='wps-agent-eval-') as directory:
   root=Path(directory);store=ProjectStore(root/'projects');pid=store.create()['id']
   source=root/'source.csv';source.write_text('zone,value\nA,10\nA,10\nB,20\nC,\n')
   store.save_dataset(pid,source,'source.csv',{'columns':[{'name':'zone','data_type':'string'},{'name':'value','data_type':'float'}]},'')
   if not case.get('new_project'): store.save_revision(pid,ProjectRevision.model_validate(REFERENCE))
   before=store.view(pid)
   service=ProjectService(store);chat=AgentController(service);events=[]
   try:
    result=await chat.respond(pid,case['query'],case.get('stage'),before['workspace']['version'],events.append,threading.Event(),page_context=case.get('page'))
    report['kind']=result['kind']
    assert result['kind']==case['kind'],f"Expected {case['kind']}, got {result['kind']}"
    if result['kind']=='analysis':
     artifact=AgentStore(store).artifact(pid,result['artifact_id']);report['artifact']=artifact['result'];report['provenance']=artifact['provenance']
     if 'expected' in case:
      values=numbers(artifact['result'].get('rows',artifact['result'].get('value')))
      assert any(abs(v-case['expected'])<1e-7 for v in values),f"Expected {case['expected']}, got {values}"
     if case.get('chart'): assert artifact['result'].get('chart'),'Chart missing'
     if 'rows' in case: assert artifact['result'].get('total_rows')==case['rows']
    if result['kind']=='proposal':
     report['validation']=result.get('validation');assert result.get('validation',{}).get('status')=='passed','Candidate did not pass execution'
     assert result.get('changes'),'No proposed changes'
     if case.get('new_project'):
      from backend.services.workspace_service import Workspaces
      from pipeline_core.partial import execution_plan
      from pipeline_core.workspace import WorkspaceDocument
      from backend.services.agent_runner import AgentRunner
      candidate=chat.items.get(pid,result['id'])['document']
      snapshot,blocked=execution_plan(WorkspaceDocument.model_validate(candidate));assert not blocked
      response=await AgentRunner().run(snapshot,store.dataset_path(pid),snapshot.default_parameters(),root/'verify',threading.Event())
      assert response['success'],response.get('error')
      assert any(value.get('kind')=='metric' and value.get('value')==30 for value in response['result']['outputs'].values()),'New project total must equal 30'
      report['creation_result_verified']=True
     if case['name']=='rename_widget': assert any(c['field']=='title' and c['after']=='Reviewed total' for c in result['changes'])
    if result['kind']=='clarification':
     item=chat.items.get(pid,result['id']);assert item.get('questions'),'No question card'
     if case.get('scope'): assert item['phase']=='scope'
     report['questions']=item['questions']
    after=store.view(pid)
    assert after['workspace']==before['workspace'],'Chat changed the workspace before Apply'
    assert after['display_run']==before['display_run'],'Chat changed saved results'
    assert after['revisions']==before['revisions'],'Chat created a revision'
    report['passed']=True
   except Exception as exc: report['error']=str(exc)
   finally:
    with store.connect() as db:
     row=db.execute('SELECT record FROM agent_turns WHERE project_id=? ORDER BY rowid DESC',(pid,)).fetchone()
    if row:
     turn=json.loads(row['record']);report['trace']=turn['trace'];report['model_steps']=turn['model_steps'];report['route']=turn.get('route');report['analysis_plan']=turn.get('analysis_plan')
     if not report['passed']: report['failed_candidate']=turn.get('candidate')
    await service.agent.llm.close()
  report['seconds']=round(time.monotonic()-started,2)
  print(json.dumps({k:report[k] for k in ['name','repeat','passed','seconds','error'] if k in report}),flush=True)
  return report


async def main(args: argparse.Namespace) -> None:
 if config.llm_provider!='bedrock': raise SystemExit('Live acceptance requires llm_provider=bedrock')
 cases=[c for c in CASES if not args.case or c['name'] in args.case]
 semaphore=asyncio.Semaphore(args.concurrency)
 reports=[]
 tasks=[asyncio.create_task(evaluate(case,repeat,semaphore)) for repeat in range(1,args.repeats+1) for case in cases]
 for future in asyncio.as_completed(tasks):
  reports.append(await future)
  Path(args.output).write_text(json.dumps({'provider':'bedrock','model':config.bedrock_model_id,'passed':sum(r['passed'] for r in reports),'total':len(reports),'results':reports},indent=2))
 print(f"Passed {sum(r['passed'] for r in reports)}/{len(reports)}; report: {args.output}")
 if not all(r['passed'] for r in reports): raise SystemExit(1)

if __name__=='__main__':
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--repeats',type=int,default=3);parser.add_argument('--concurrency',type=int,default=1);parser.add_argument('--output',default='/tmp/wps-agent-evaluation.json');parser.add_argument('--case',action='append')
 asyncio.run(main(parser.parse_args()))
