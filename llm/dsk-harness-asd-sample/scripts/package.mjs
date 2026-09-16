/** Delegate release assembly to the pinned local Harness fork. */
import { existsSync } from 'node:fs';
import { resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawnSync } from 'node:child_process';
const root = fileURLToPath(new URL('..', import.meta.url));
if (existsSync(resolve(root, '.env'))) process.loadEnvFile(resolve(root, '.env'));
const harness = resolve(process.env.HARNESS_SOURCE || resolve(root, '../../../deepseek-harness'));
const output = process.argv[2];
if (!output) throw new Error('Usage: npm run package -- NEW_OUTPUT_DIRECTORY');
const result = spawnSync(process.execPath, [resolve(harness, 'scripts/product-pack.mjs'), root, resolve(output)], { stdio: 'inherit' });
if (result.error) throw result.error;
process.exitCode = result.status || (result.signal ? 1 : 0);
