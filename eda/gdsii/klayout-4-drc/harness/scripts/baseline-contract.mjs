import {modelConfig} from './model-config.mjs';
import {verifiedAPIContext} from './api-reference.mjs';

/** Frozen candidate contract shared by the standalone runner and flow definition. */
export const SYSTEM_MESSAGE = `You are an expert EDA Physical Verification and DRC Remediation Engineer.
Use only the KLayout API forms explicitly supplied in the prompt's verified API reference.
Do not add KLayout methods, properties, constructors, overloads, or conversions from memory.
Check each KLayout expression's receiver type, accepted arguments, and return type against that reference.
If the reference does not support an operation, preserve the affected geometry and explain the limitation in rationale.
Before returning the script, check that every KLayout API use follows the supplied contract. Python standard-library use is permitted.`;
export function buildPrompt(instructions, context) {
  return [instructions,
    '\n### CONTEXT 1: DRC VIOLATIONS\n', context.violations.replace(/^Source: .*$/gm, 'Source: baseline checker report'),
    '\n### CONTEXT 2: EXTRACTED DRC RULES\n', context.drc_rules,
    '\n### CONTEXT 3: GDS LAYOUT LOCAL SECTIONS\n', context.gds_sections,
    '\n### CONTEXT 4: DOMAIN KNOWLEDGE BASE\n', context.knowledge,
    '\nFinal API check: use only KLayout API forms supplied in the verified reference above. Check receiver and return types; do not invent calls or unwrap geometry values as Shape handles. Preserve geometry and state a limitation when no supported form exists.',
    '\nRespond strictly with a JSON object: {"python_script": "...", "rationale": "..."}'
  ].join('\n');
}
export function validateCandidate(content) {
  const value = JSON.parse(content);
  if (typeof value.python_script !== 'string' || !value.python_script.trim() || typeof value.rationale !== 'string') {
    throw new Error('Model response must contain nonempty python_script and string rationale');
  }
  return value;
}

export async function generateCandidate(instructions, context, artifactDir, profile, fetchImpl = globalThis.fetch) {
  const {writeFileSync} = await import('node:fs');
  const {resolve} = await import('node:path');
  const {createHash} = await import('node:crypto');
  const hash = value => createHash('sha256').update(value).digest('hex');
  const save = (name, data) => writeFileSync(resolve(artifactDir,name), JSON.stringify(data,null,2));
  const config = modelConfig();
  const {model, endpoint, provider} = config;
  const key = provider === 'bedrock' ? process.env.AWS_API_KEY : process.env.OPENAI_API_KEY;
  if (!model || !key) {
    throw new Error(provider === 'bedrock'
      ? 'BEDROCK_MODEL and AWS_API_KEY are required'
      : 'OPENAI_MODEL and OPENAI_API_KEY are required');
  }
  const reference = await verifiedAPIContext(context, artifactDir);
  context = reference.context;
  const payload = {model, response_format:{type:'json_object'}, messages:[
    {role:'system',content:SYSTEM_MESSAGE}, {role:'user',content:buildPrompt(instructions, context)}]};
  if (config.temperature !== null) payload.temperature = config.temperature;
  writeFileSync(resolve(artifactDir, 'model_attempt.json'), JSON.stringify({...config, started_at:new Date().toISOString()}), {flag:'wx'});
  save('model_context.json', context);
  save('model_request.json', payload);
  save('generation_manifest.json', {schema_version:2, profile, ...config, api_reference:reference.metadata, requested_model:model,
    prompt_sha256:hash(payload.messages[1].content), instructions_sha256:hash(instructions),
    context_hashes:Object.fromEntries(Object.entries(context).map(([k,v])=>[k,hash(v)])),
    returned_model:null, usage:null, cost:null, status:'request_started'});
  // A claim is written before dispatch. Resume must never issue this request again.
  const response = await fetchImpl(endpoint, {
    method:'POST', headers:{'Content-Type':'application/json',Authorization:`Bearer ${key}`},
    body:JSON.stringify(payload), redirect:'error', signal:AbortSignal.timeout(90000)});
  const raw = (await response.text()).replaceAll(key, "[REDACTED]");
  writeFileSync(resolve(artifactDir,'model_response.txt'), raw);
  if (!response.ok) throw new Error(`Model HTTP error ${response.status}; see model_response.txt`);
  const data = JSON.parse(raw);
  save('model_response.json',data);
  save('generation_manifest.json', {schema_version:2, profile, ...config, api_reference:reference.metadata, requested_model:model,
    returned_model:data.model ?? null, response_id:data.id ?? null, usage:data.usage ?? null,
    cost:null, status:'response_saved', prompt_sha256:hash(payload.messages[1].content),
    instructions_sha256:hash(instructions), context_hashes:Object.fromEntries(Object.entries(context).map(([k,v])=>[k,hash(v)]))});
  const candidate = validateCandidate(data.choices?.[0]?.message?.content);
  writeFileSync(resolve(artifactDir,'rationale.txt'),candidate.rationale);
  return { ...candidate, returned_model:data.model ?? null };
}
