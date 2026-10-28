import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtempSync,readFileSync,rmSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {buildPrompt,validateCandidate,generateCandidate} from '../scripts/baseline-contract.mjs';

test('candidate contract rejects malformed or empty scripts',()=>{
  assert.throws(()=>validateCandidate('{}'));
  assert.throws(()=>validateCandidate('{"python_script":"","rationale":"x"}'));
  assert.equal(validateCandidate('{"python_script":"pass","rationale":"unchanged"}').python_script,'pass');
  assert.ok(buildPrompt('instructions',{violations:'v',drc_rules:'d',gds_sections:'g',knowledge:'k'}).includes('CONTEXT 4'));
});
test('one request with durable response and no credentials in saved files',async()=>{
  const dir=mkdtempSync(join(tmpdir(),'drc-contract-'));
  const previous={key:process.env.OPENAI_API_KEY,model:process.env.OPENAI_MODEL};
  process.env.OPENAI_API_KEY='sentinel-secret';process.env.OPENAI_MODEL='frozen-test-model';
  let calls=0;
  try {
    const mock=async(url,options)=>{
      calls++; assert.equal(JSON.parse(options.body).model,'frozen-test-model');
      return {ok:true,text:async()=>JSON.stringify({id:'response-1',model:'returned-model',usage:{total_tokens:42},
        choices:[{message:{content:JSON.stringify({python_script:'pass',rationale:'preserve'})}}]})};
    };
    const output=await generateCandidate('instructions',{violations:'v',drc_rules:'d',gds_sections:'g',knowledge:'k'},dir,'asap7_curated',mock);
    assert.equal(output.returned_model,'returned-model');assert.equal(calls,1);
    const request=readFileSync(join(dir,'model_request.json'),'utf8');assert.ok(!request.includes('sentinel-secret'));
    assert.equal(JSON.parse(readFileSync(join(dir,'generation_manifest.json'))).usage.total_tokens,42);
    await assert.rejects(()=>generateCandidate('instructions',{violations:'v',drc_rules:'d',gds_sections:'g',knowledge:'k'},dir,'asap7_curated',mock));
    assert.equal(calls,1,'an existing claim prevents another request');
  } finally {
    for(const [key,value] of [['OPENAI_API_KEY',previous.key],['OPENAI_MODEL',previous.model]]) {
      if(value===undefined)delete process.env[key];else process.env[key]=value;
    }
    rmSync(dir,{recursive:true});
  }
});

test('Bedrock settings use only AWS model settings and validate the region',async()=>{
  const {modelConfig}=await import('../scripts/model-config.mjs');
  const config=modelConfig({KLAYOUT_DRC_MODEL_PROVIDER:'bedrock',BEDROCK_MODEL:'aws-model',
    OPENAI_MODEL:'wrong-model',OPENAI_TEMPERATURE:'0.7',AWS_API_KEY:'secret'});
  assert.deepEqual(config,{provider:'bedrock',region:'ap-southeast-2',
    endpoint:'https://bedrock-runtime.ap-southeast-2.amazonaws.com/openai/v1/chat/completions',
    model:'aws-model',temperature:null});
  assert.equal(modelConfig({KLAYOUT_DRC_MODEL_PROVIDER:'bedrock',OPENAI_MODEL:'wrong'}).model,null);
  assert.equal(modelConfig({KLAYOUT_DRC_MODEL_PROVIDER:'bedrock',BEDROCK_REGION:'us-west-2',BEDROCK_TEMPERATURE:'0'}).temperature,0);
  assert.throws(()=>modelConfig({KLAYOUT_DRC_MODEL_PROVIDER:'other'}));
  assert.throws(()=>modelConfig({KLAYOUT_DRC_MODEL_PROVIDER:'bedrock',BEDROCK_REGION:'host/path'}));
  assert.throws(()=>modelConfig({KLAYOUT_DRC_MODEL_PROVIDER:'bedrock',BEDROCK_TEMPERATURE:'NaN'}));
});

test('Bedrock dispatch records destination, redacts its key and never retries HTTP failures',async()=>{
  const names=['KLAYOUT_DRC_MODEL_PROVIDER','AWS_API_KEY','BEDROCK_MODEL','BEDROCK_REGION','BEDROCK_TEMPERATURE'];
  const previous=Object.fromEntries(names.map(name=>[name,process.env[name]]));
  const dir=mkdtempSync(join(tmpdir(),'drc-bedrock-'));
  Object.assign(process.env,{KLAYOUT_DRC_MODEL_PROVIDER:'bedrock',AWS_API_KEY:'aws-sentinel-secret',
    BEDROCK_MODEL:'openai.gpt-oss-120b-1:0',BEDROCK_REGION:'ap-southeast-2',BEDROCK_TEMPERATURE:'0'});
  let calls=0;
  const context={violations:'v',drc_rules:'d',gds_sections:'g',knowledge:'k'};
  const mock=async(url,options)=>{
    calls++;
    assert.equal(url,'https://bedrock-runtime.ap-southeast-2.amazonaws.com/openai/v1/chat/completions');
    assert.equal(options.headers.Authorization,'Bearer aws-sentinel-secret');
    assert.equal(options.redirect,'error');
    assert.equal(JSON.parse(options.body).temperature,0);
    return {ok:false,status:403,text:async()=>'Denied aws-sentinel-secret'};
  };
  try {
    await assert.rejects(()=>generateCandidate('instructions',context,dir,'asap7_curated',mock),/HTTP error 403/);
    assert.equal(calls,1);
    const manifest=JSON.parse(readFileSync(join(dir,'generation_manifest.json')));
    assert.equal(manifest.provider,'bedrock');
    assert.equal(manifest.requested_model,'openai.gpt-oss-120b-1:0');
    assert.equal(readFileSync(join(dir,'model_response.txt'),'utf8'),'Denied [REDACTED]');
    delete process.env.AWS_API_KEY;
    await assert.rejects(()=>generateCandidate('instructions',context,dir,'asap7_curated',mock),/AWS_API_KEY are required/);
    assert.equal(calls,1);
  } finally {
    for(const name of names) {
      if(previous[name]===undefined) delete process.env[name]; else process.env[name]=previous[name];
    }
    rmSync(dir,{recursive:true});
  }
});
