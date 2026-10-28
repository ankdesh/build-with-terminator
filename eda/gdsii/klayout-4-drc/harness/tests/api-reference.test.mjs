import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtempSync, readFileSync, rmSync, existsSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {dirname, join, resolve} from 'node:path';
import {fileURLToPath} from 'node:url';
import {Context} from '@deepseek-ai/cordis';
import {registerDrcOperations} from '../lib/drc-operations.js';
import {generateCandidate} from '../scripts/baseline-contract.mjs';
import {candidatePython} from '../scripts/api-reference.mjs';

const projectRoot=resolve(dirname(fileURLToPath(import.meta.url)),'../..');
function withModelEnvironment() {
  const names=['KLAYOUT_DRC_MODEL_PROVIDER','OPENAI_API_KEY','OPENAI_MODEL','KLAYOUT_DRC_PYTHON'];
  const previous=Object.fromEntries(names.map(name=>[name,process.env[name]]));
  const python=candidatePython();
  Object.assign(process.env,{KLAYOUT_DRC_MODEL_PROVIDER:'openai',OPENAI_API_KEY:'test-only-key',
    OPENAI_MODEL:'api-reference-test',KLAYOUT_DRC_PYTHON:python});
  return ()=>{for (const name of names) {
    if(previous[name]===undefined) delete process.env[name]; else process.env[name]=previous[name];
  }};
}
function operations() {
  const ctx=new Context(); const registered=new Map();
  ctx.provide('flows',{registerOperation(op){registered.set(op.id,op);return ()=>{};}});
  registerDrcOperations(ctx,projectRoot);
  return registered;
}

test('standalone contract and declarative synthesis receive identical verified reference',async()=>{
  const restore=withModelEnvironment(); const previousFetch=globalThis.fetch;
  const directory=mkdtempSync(join(tmpdir(),'drc-api-routes-'));
  const requests=[];
  globalThis.fetch=async(_url,options)=>{
    requests.push(JSON.parse(options.body));
    return {ok:true,text:async()=>JSON.stringify({model:'returned-test-model',
      choices:[{message:{content:JSON.stringify({python_script:'pass',rationale:'test'})}}]})};
  };
  try {
    const ops=operations();
    const knowledge=await ops.get('klayout.load_knowledge').execute({profile_name:'asap7_curated'});
    assert.ok(knowledge.knowledge_text.includes('=== Verified KLayout Python API Reference ==='));
    const context={violations:'v',drc_rules:'d',gds_sections:'g',knowledge:knowledge.knowledge_text};
    const instructions=readFileSync(join(projectRoot,'harness/profile/catalog/flows/generate_fix.md'),'utf8');
    const direct=join(directory,'direct'); const flow=join(directory,'flow');
    const {mkdirSync}=await import('node:fs'); mkdirSync(direct); mkdirSync(flow);
    await generateCandidate(instructions,context,direct,'asap7_curated');
    await ops.get('klayout.synthesize_candidate').execute({...context,profile_name:'asap7_curated',
      output_script_path:join(flow,'candidate.py')});
    assert.equal(requests.length,2);
    assert.deepEqual(requests[0],requests[1]);
    assert.match(requests[0].messages[0].content,/Use only the KLayout API forms explicitly supplied/);
    assert.match(requests[0].messages[0].content,/Do not add KLayout methods, properties, constructors, overloads, or conversions from memory/);
    assert.match(requests[0].messages[1].content,/complete allowed\nKLayout API surface/);
    assert.match(requests[0].messages[1].content,/Final API check: use only KLayout API forms/);
    const metadata=JSON.parse(readFileSync(join(direct,'generation_manifest.json'))).api_reference;
    assert.ok(metadata.runtime_version && metadata.reference_sha256);
    assert.equal(metadata.examples_checked,12);
    assert.equal(metadata.contracts_checked,63);
    const document=readFileSync(join(projectRoot,'knowledge/klayout_api_patterns.md'),'utf8');
    assert.ok(document.length<=18000);
    assert.equal(requests[0].messages[1].content.split(document).length-1,1);
    assert.deepEqual(metadata,JSON.parse(readFileSync(join(flow,'generation_manifest.json'))).api_reference);
    assert.equal(requests[0].messages[1].content.split('=== Verified KLayout Python API Reference ===').length-1,1);
  } finally {
    globalThis.fetch=previousFetch; restore(); rmSync(directory,{recursive:true});
  }
});

test('both routes send zero requests when reference runtime is unavailable',async()=>{
  const restore=withModelEnvironment(); const previousFetch=globalThis.fetch;
  const directory=mkdtempSync(join(tmpdir(),'drc-api-blocked-'));
  let calls=0;globalThis.fetch=async()=>{calls++;throw new Error('network must not be used');};
  process.env.KLAYOUT_DRC_PYTHON=join(directory,'missing-python');
  const context={violations:'v',drc_rules:'d',gds_sections:'g',knowledge:'k'};
  try {
    const ops=operations();
    await assert.rejects(()=>generateCandidate('instructions',context,directory,'asap7_curated'),
      error=>error.stage==='api_reference');
    assert.equal(JSON.parse(readFileSync(join(directory,'generation_error.json'))).stage,'api_reference');
    await assert.rejects(()=>ops.get('klayout.synthesize_candidate').execute({...context,
      profile_name:'asap7_curated',output_script_path:join(directory,'candidate.py')}),
      error=>error.stage==='api_reference');
    assert.equal(calls,0);
    assert.equal(existsSync(join(directory,'model_attempt.json')),false);
    assert.equal(existsSync(join(directory,'model_request.json')),false);
  } finally {
    globalThis.fetch=previousFetch; restore(); rmSync(directory,{recursive:true});
  }
});

test('stale reference is rejected before a model request',async()=>{
  const restore=withModelEnvironment();
  const directory=mkdtempSync(join(tmpdir(),'drc-api-stale-'));
  let calls=0;
  try {
    await assert.rejects(()=>generateCandidate('instructions',{
      violations:'v',drc_rules:'d',gds_sections:'g',
      knowledge:'=== Verified KLayout Python API Reference ===\nRuntime: stale'},directory,'asap7_curated',
      async()=>{calls++;}),/stale or incompatible/);
    assert.equal(calls,0);
    assert.equal(existsSync(join(directory,'model_attempt.json')),false);
  } finally { restore(); rmSync(directory,{recursive:true}); }
});
