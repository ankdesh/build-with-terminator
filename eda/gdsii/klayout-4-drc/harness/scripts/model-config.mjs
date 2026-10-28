/** Public model settings. Never include credentials in this object or its output. */
import {pathToFileURL} from 'node:url';

export function modelConfig(env = process.env) {
  const provider = env.KLAYOUT_DRC_MODEL_PROVIDER || 'openai';
  if (!['openai', 'bedrock'].includes(provider)) {
    throw new Error('KLAYOUT_DRC_MODEL_PROVIDER must be openai or bedrock');
  }
  const bedrock = provider === 'bedrock';
  const region = bedrock ? (env.BEDROCK_REGION || 'ap-southeast-2') : null;
  if (region && !/^[a-z]{2}(?:-[a-z]+)+-\d+$/.test(region)) {
    throw new Error('Invalid BEDROCK_REGION');
  }
  const temperatureText = bedrock ? env.BEDROCK_TEMPERATURE : env.OPENAI_TEMPERATURE;
  const temperature = temperatureText ? Number(temperatureText) : null;
  if (temperature !== null && !Number.isFinite(temperature)) {
    throw new Error(`Invalid ${bedrock ? 'BEDROCK' : 'OPENAI'}_TEMPERATURE`);
  }
  return {
    provider, region,
    endpoint: bedrock
      ? `https://bedrock-runtime.${region}.amazonaws.com/openai/v1/chat/completions`
      : 'https://api.openai.com/v1/chat/completions',
    model: (bedrock ? env.BEDROCK_MODEL : env.OPENAI_MODEL) || null,
    temperature,
  };
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  console.log(JSON.stringify(modelConfig()));
}
