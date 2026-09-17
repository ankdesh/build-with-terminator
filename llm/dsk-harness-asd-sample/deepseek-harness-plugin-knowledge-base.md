# DeepSeek Harness: Comprehensive Plugin & Profile Development Knowledge Base

> **Purpose**: Exhaustive reference for creating custom plugins, tools, profiles, and extensions in DeepSeek Harness (DSH). Intended for distillation into reusable skills.

---

## Table of Contents

1. [Foundational Architecture](#1-foundational-architecture)
2. [Plugin Basics](#2-plugin-basics)
3. [Tool Creation](#3-tool-creation)
4. [Plugin Configuration (Schemastery)](#4-plugin-configuration-schemastery)
5. [Services and Dependencies](#5-services-and-dependencies)
6. [Event System](#6-event-system)
7. [Capability Seams (Three-Role Pattern)](#7-capability-seams-three-role-pattern)
8. [Profiles, Bundles, and Composition](#8-profiles-bundles-and-composition)
9. [cordis.yml Syntax Reference](#9-cordisyml-syntax-reference)
10. [Runtime Integration: Shell, Python, Binary, E2B](#10-runtime-integration-shell-python-binary-e2b)
11. [Custom Mode / Dynamic Plugins (Self-Modification)](#11-custom-mode--dynamic-plugins-self-modification)
12. [Hooks and Interception Points](#12-hooks-and-interception-points)
13. [MCP Integration](#13-mcp-integration)
14. [LLM Adapter Creation](#14-llm-adapter-creation)
15. [Skills and Agent Instructions](#15-skills-and-agent-instructions)
16. [Publishing and Packaging](#16-publishing-and-packaging)
17. [Plugin Lifecycle and HMR](#17-plugin-lifecycle-and-hmr)
18. [Tool Execution Pipeline (Complete)](#18-tool-execution-pipeline-complete)
19. [Defensive Patterns (Mandatory)](#19-defensive-patterns-mandatory)
20. [UI Presentation Cards](#20-ui-presentation-cards)
21. [Presets (Per-Session Agent Composition)](#21-presets-per-session-agent-composition)
22. [Complete Dos and Don'ts](#22-complete-dos-and-donts)
23. [Quick Reference Templates](#23-quick-reference-templates)

---

## 1. Foundational Architecture

### Core Philosophy: Everything is a Plugin

DeepSeek Harness is built on **Cordis**, an all-plugin microkernel framework. Every capability — the agent loop, LLM adapters, tool registry, file access, session persistence, the agent loop itself — is a plugin mounted into a shared `Context` (`ctx`).

There is **no privileged core** to monkey-patch. Extensions mount beside existing plugins. All registrations are reversible effects that unwind automatically on plugin disposal.

### Key Architectural Principles

| Principle | Description |
|-----------|-------------|
| **Plugins, not loop changes** | New behavior attaches to documented extension points, never modifies `agent-loop` |
| **Registrations are effects** | Every contribution via `ctx.effect()` / `ctx.on()` auto-cleans on unload |
| **Dependency injection via `inject`** | Framework defers plugin activation until all required services are ready |
| **Model-visible ⟺ Logged** | Anything reaching the model must be reconstructable from session log |
| **Canonical JSON outcomes** | Tools return validated JSON; prose for model and UI are derived projections |

### Three Event Domains

1. **Session Events**: Durable facts appended to the log, broadcast via `session/event`. Survives reloads.
2. **Agent Events (`agent/*`)**: Live in-flight coordination carrying active `Agent` handle.
3. **Capability Events (`fs/*`, `tools/*`)**: Policy and adapter attachment to capability seams.

### Core Services on `ctx`

| Key | Package | Purpose |
|-----|---------|---------|
| `ctx.sessions` | `dsh-session` | Append-only SessionEvent log |
| `ctx.systemPrompt` | `dsh-system-prompt` | Prompt sections, context injection, tool schema assembly |
| `ctx.tools` | `dsh-tools` | Scoped tool registry, guarded execution pipeline |
| `ctx.agents` | `dsh-agent` | Live agent handle registry and lifecycle factory |
| `ctx.agentLoop` | `dsh-agent-loop` | Concrete loop driver |
| `ctx.llm` | `dsh-llm` | Model streaming vocabulary and adapter registry |
| `ctx.shell` | `dsh-shell` | Shell execution abstraction |
| `ctx.subprocess` | `dsh-subprocess` | Process spawning |
| `ctx.fs` | `dsh-fs` | Filesystem access and policy |
| `ctx.approval` | `dsh-user-approval` | Permission request/response |
| `ctx.commands` | `dsh-commands` | Human slash commands |
| `ctx.jobs` | `dsh-jobs` | Background work management |
| `ctx.subagents` | `dsh-subagent` | Sub-agent delegation |
| `ctx.compaction` | `dsh-compaction` | Context compaction |
| `ctx.web` | `dsh-web` | Web search/fetch |

### Where New Behavior Goes

| Goal | Mechanism |
|------|-----------|
| Add model provider | Register adapter on `ctx.llm` |
| Add model-facing tool | Register on `ctx.tools` |
| Add shell execution | Register backend on `ctx.shell` |
| Add human command | Register on `ctx.commands` |
| Add background work | Register on `ctx.jobs` |
| Intercept request/tool/turn | Listen to `agent/*` or `tools/*` waterfalls |
| Add model-facing context | Call `agent.inject()` |
| Add durable session state | Extend `SessionEventMap` |
| Different capability set per session | Compose agent preset `cordis.yml` with `isolate` |
| Add filesystem access/policy | Register provider on `ctx.fs` or listen to `fs/*` |

---

## 2. Plugin Basics

### Three Plugin Shapes

#### 1. Function Plugin (Most Common)

```ts
import type { Context } from '@deepseek-ai/cordis'

export const name = 'my-plugin'       // Optional display name for diagnostics
export const inject = ['tools']        // Required Cordis services

export function apply(ctx: Context) {
  // Executed when all injected services are active
  console.log('[my-plugin] loaded!')
}
```

#### 2. Object Plugin

```ts
import type { Context } from '@deepseek-ai/cordis'

export default {
  name: 'my-object-plugin',
  inject: ['tools'],
  apply(ctx: Context) {
    // Initialization logic
  },
}
```

#### 3. Class Plugin / Service Provider

Used when a plugin provides a named service to other plugins.

```ts
import { Service, type Context } from '@deepseek-ai/cordis'

declare module '@deepseek-ai/cordis' {
  interface Context {
    myService: MyService
  }
}

export class MyService extends Service {
  static inject = ['tools']

  constructor(ctx: Context) {
    super(ctx, 'myService')  // Registers under ctx.myService
  }

  doSomething() {
    return 'result'
  }
}
```

### Fiber State Machine

Every loaded plugin owns a **Fiber** tracking its lifecycle:

```
PENDING → LOADING → ACTIVE
                 ↘ FAILED
ACTIVE → UNLOADING → DISPOSED
```

| State | Meaning |
|-------|---------|
| PENDING | Declared, but required `inject` services not ready |
| LOADING | Dependencies ready, `apply` running |
| ACTIVE | `apply` completed successfully |
| FAILED | `apply` or config validation threw |
| UNLOADING | Disposers running |
| DISPOSED | Fully unloaded |

### Automatic Cleanup with `ctx.effect()`

Built-in Cordis APIs (`ctx.on()`, `ctx.tools.register()`, `ctx.plugin()`) are already effects. For external resources:

```ts
export function apply(ctx: Context) {
  ctx.effect(() => {
    const timer = setInterval(() => console.log('tick'), 1000)
    // Returned disposer runs automatically on plugin unload/HMR
    return () => clearInterval(timer)
  })
}
```

> **Ordering caveat**: Synchronous disposers run in reverse registration order; multiple async disposers run concurrently. Put order-dependent cleanup in one disposer.

### Loading a Local Plugin

Create a patch overlay file (`cordis.patch.yml`):

```yaml
- insert:
    - id: hello
      name: '/absolute/path/to/my-plugin.ts'
```

> **Plugin paths must be absolute** in patch files.

Start with the overlay:

```sh
pnpm dsh web --patch ./scratch-plugin/cordis.yml
```

---

## 3. Tool Creation

### The Minimal Tool Shape

```ts
import { readFile } from 'node:fs/promises'
import type { Context } from '@deepseek-ai/cordis'
import { defineTool } from '@deepseek-ai/dsh-tools'

export const name = 'my-tool'
export const inject = ['tools']

export function apply(ctx: Context) {
  ctx.tools.register(defineTool({
    name: 'read_file',
    description: 'Read a file from disk.',          // what the model sees
    parameters: {
      path: { type: 'string', required: true, description: 'Absolute path' },
      limit: { type: 'number' },                     // optional by default
    },
    output: {
      schema: { type: 'string' },
      render: (_args, value) => [{ type: 'text', text: value }],
    },
    async execute(args, exec) {
      // args is TYPED from the schema: { path: string; limit?: number }
      return readFile(args.path, { encoding: 'utf8', signal: exec.signal })
    },
  }))
}
```

### Simple Greet Tool (Tutorial Example)

```ts
import type { Context } from '@deepseek-ai/cordis'
import { defineTool } from '@deepseek-ai/dsh-tools'

export const name = 'greet-tool'
export const inject = ['tools']

export function apply(ctx: Context) {
  ctx.tools.register(defineTool({
    name: 'greet',
    description: 'Greet someone by name.',
    parameters: {
      name: { type: 'string', required: true, description: 'The name to greet' },
    },
    output: {
      schema: { type: 'string' },
      render: (_args, value) => [{ type: 'text', text: value }],
    },
    async execute(args) {
      return `Hello, ${args.name}!`
    },
  }))
}
```

### Rules of the execute() Contract

1. **Args are pre-validated**: `defineTool` validates model JSON arguments before `execute` runs
2. **Return canonical JSON**: Must match `output.schema`. Registry validates, snapshots, feeds to `output.render(args, value)`
3. **Honor `exec.signal`**: Cancel in-flight work when abort fires
4. **Throwing means `isError`**: Throw for infrastructure failures. Return canonical value for domain failures (e.g., non-zero exit)
5. **Registration is effect-based**: Disposing the plugin fiber unregisters the tool
6. **Schemas flow into system-prompt assembly automatically**

### Background Jobs

```ts
async execute(args, exec) {
  if (args.run_in_background) {
    const job = await ctx.jobs.start({
      kind: 'bash',
      label: `bash: ${args.command}`,
      owner: exec.agent,
      run: async (jobControl) => {
        // Run long-running process using jobControl.signal
        return { exitCode: 0 }
      },
    })
    return { kind: 'background', jobId: job.id }
  }
  // Foreground execution...
}
```

### PTC (Programmatic Tool Calling) Mode

In PTC mode, registered tools are automatically exposed as `await tools.<name>(args)`:
- Arguments and returns are statically typed from schemas
- Resolves to canonical JSON value, not rendered text
- Failed calls throw `ToolCallError`

---

## 4. Plugin Configuration (Schemastery)

### Config Pattern (Type + Schema)

```ts
import type { Context } from '@deepseek-ai/cordis'
import Schema from '@deepseek-ai/schemastery'

export const name = 'my-configurable-plugin'

export interface Config {
  apiKey: string
  retries?: number
  timeoutMs?: number
  mode?: 'fast' | 'accurate'
}

export const Config: Schema<Config> = Schema.object({
  apiKey: Schema.string().required(),
  retries: Schema.number().default(3),
  timeoutMs: Schema.number().default(30000),
  mode: Schema.union(['fast', 'accurate']).default('fast'),
})

export function apply(ctx: Context, config: Config) {
  // config is statically typed, defaulted, and guaranteed valid
  console.log(`Mode: ${config.mode}, retries: ${config.retries}`)
}
```

### YAML Configuration

```yaml
- id: my-plugin
  name: './src/my-plugin.ts'
  config:
    apiKey: !!js process.env.API_KEY ?? 'fallback'
    retries: 5
    mode: 'accurate'
```

### Config Design Principles

- **No hardcoded tunables**: Anything two deployments might vary must be a Config field
- **Fail loud**: Invalid config fails the load immediately with `ValidationError`
- **HMR-safe**: Config edit triggers plugin unload→reload cycle
- Do NOT export a plain object as `Config` — it must implement Standard Schema

---

## 5. Services and Dependencies

### Consuming a Service

```ts
export const inject = ['tools']

export function apply(ctx: Context) {
  // ctx.tools is guaranteed ready here
  ctx.tools.register(/* ... */)
}
```

### Providing a Service

```ts
import { Service, type Context } from '@deepseek-ai/cordis'

declare module '@deepseek-ai/cordis' {
  interface Context {
    metrics: MetricsService
  }
}

export default class MetricsService extends Service {
  constructor(ctx: Context) {
    super(ctx, 'metrics')
  }

  record(event: string, value: number) {
    console.log(`[metric] ${event}: ${value}`)
  }
}
```

### Optional Dependencies

```ts
export function apply(ctx: Context) {
  const metrics = ctx.get('metrics')  // undefined if provider absent
  metrics?.record('optional_event', 1)
}
```

### Service Isolation

```yaml
- id: group-a
  name: '@deepseek-ai/cordis-plugin-group'
  group: true
  isolate:
    shell: true
  config:
    - name: '@deepseek-ai/dsh-bash-local'
      config:
        timeoutMs: 5000
    - name: './src/plugin-a.ts'
```

### Dependency Tracking

If a required service disappears (provider unloads):
1. Dependent plugins dispose automatically
2. They load again when service returns
3. Prevents calling unavailable services

---

## 6. Event System

### Five Dispatch Modes

| Mode | Invocation | Semantics |
|------|------------|-----------|
| `emit` | `ctx.emit(name, ...args)` | Synchronous broadcast; returns ignored |
| `parallel` | `await ctx.parallel(name, ...args)` | All listeners concurrent |
| `serial` | `await ctx.serial(name, ...args)` | Ordered; first non-null wins |
| `bail` | `ctx.bail(name, ...args)` | Synchronous serial |
| `waterfall` | `await ctx.waterfall(name, ...args, next)` | Around-middleware chain |

### Declaring Typed Events

```ts
declare module '@deepseek-ai/cordis' {
  interface Events {
    'my-plugin/ready': (payload: { id: string }) => void
    'my-plugin/check': (input: string) => boolean | undefined
    'my-plugin/transform': (input: string, next: () => Promise<string>) => Promise<string>
  }
}
```

### Waterfall Pattern (Critical)

```ts
ctx.on('my-plugin/transform', async (_input, next) => {
  const downstream = await next()
  return downstream.trim()
})
```

> **CRITICAL RULE**: A waterfall listener **MUST call `next()`** to delegate. Returning without it short-circuits the pipeline.

### Event Listener Example

```ts
export const name = 'tool-logger'

export function apply(ctx: Context) {
  ctx.on('tools/result', (exec, result) => {
    console.log(`[tool] ${exec.name}(${JSON.stringify(exec.arguments)})`)
    const text = result.content
      .map(block => block.type === 'text' ? block.text : '')
      .join('')
    console.log(`[tool result] ${text.slice(0, 100)}`)
  })
}
```

### Key Harness Events

| Event | Mode | Purpose |
|-------|------|---------|
| `agent/pre-step` | waterfall | Rewrite messages, inject instructions, reject step |
| `agent/request` | waterfall | Replace model-call config |
| `tools/pre-execute` | waterfall | Permission checks, sandboxing |
| `tools/execute` | waterfall | Around-dispatch (timeout, retry, metrics) |
| `tools/post-execute` | waterfall | Result inspection, rewriting |
| `tools/result` | emit | Observe immutable final outcome |
| `agent/turn-stopping` | serial | Turn boundary; listeners can steer another step |
| `session/event` | emit | All durable session events |

---

## 7. Capability Seams (Three-Role Pattern)

### The Three Roles

```
┌─────────────────────────┐
│   Service Definition    │  (e.g., @deepseek-ai/dsh-shell)
│ - Abstract Service      │  Declares Context interface, request/result types
└─────────────────────────┘
         ▲           ▲
         │           │
┌────────┴──────┐ ┌──┴─────────────┐
│Service Provider│ │   Consumer      │  (e.g., @deepseek-ai/dsh-tool-bash)
│(dsh-bash-local)│ │Exposes tool/UI │  Consumes ctx.shell, registers defineTool
└────────────────┘ └─────────────────┘
```

### Step 1: Service Definition

```ts
import { Service, type Context } from '@deepseek-ai/cordis'

declare module '@deepseek-ai/cordis' {
  interface Context {
    myCap: MyCapService
  }
}

export abstract class MyCapService extends Service {
  constructor(ctx: Context) {
    super(ctx, 'myCap')
  }
  abstract execute(request: MyCapRequest): Promise<MyCapResult>
}

export interface MyCapRequest { input: string }
export interface MyCapResult { output: string }
```

### Step 2: Service Provider

```ts
import type { Context } from '@deepseek-ai/cordis'
import { MyCapService, type MyCapRequest, type MyCapResult } from '@deepseek-ai/dsh-my-cap'

class MyCapLocal extends MyCapService {
  async execute(request: MyCapRequest): Promise<MyCapResult> {
    return { output: request.input.toUpperCase() }
  }
}

export const name = 'my-cap-local'
export function apply(ctx: Context) { ctx.plugin(MyCapLocal) }
```

### Step 3: Consumer (Tool)

```ts
import type { Context } from '@deepseek-ai/cordis'
import { defineTool } from '@deepseek-ai/dsh-tools'

export const name = 'tool-my-cap'
export const inject = ['tools', 'myCap']

export function apply(ctx: Context) {
  ctx.tools.register(defineTool({
    name: 'my_cap',
    description: 'Execute my capability.',
    parameters: { input: { type: 'string', required: true } },
    output: {
      schema: { type: 'string' },
      render: (_args, value) => [{ type: 'text', text: value }],
    },
    async execute(args) {
      const result = await ctx.myCap.execute({ input: args.input })
      return result.output
    },
  }))
}
```

### Design Points

- **Do not split preemptively** — only when roles evolve independently
- **Service Definition owns Request/Result types**
- **Provider and Consumer do not depend on each other**
- **Explicit > implicit** — resolve defaults in `resolve(request): Spec`, not hidden `?? default`

---

## 8. Profiles, Bundles, and Composition

### Two Concepts

- **Bundle**: An npm package shipping a configuration layer. Declares `dsh.bundle` in `package.json`.
- **Profile**: A directory under `$DSH_HOME/profiles/<name>` describing one runnable composition. Declares `dsh.profile`.

A bundle is what you author and distribute; a profile is what a user boots with `dsh --profile <name>`.

### Loading Order (Layer Precedence)

1. Each bundle patch in profile's `dsh.profile.bundles` list, in list order
2. Profile's own `cordis.patch.yml`
3. Home-level `$DSH_HOME/cordis.patch.yml` (machine-local, shared by all profiles)
4. Each `--patch <path>` overlay, in argv order

> Later layers win per row. A patch replaces a row's entire `config` value (no deep-merge).

### Shipped Profiles

| Profile | Type |
|---------|------|
| `web` | Browser UI, live patch reload |
| `headless` | One-shot CLI, no live reload |
| `sdk` | JSON-RPC server for SDK clients |
| `sdk-minimal` | Minimal SDK (bash + editor only) |
| `acp` | Agent Client Protocol (automation) |

### Inspecting Configuration

```sh
dsh --profile web --dump-config
```

---

## 9. cordis.yml Syntax Reference

### Basic Entry

```yaml
- id: my-plugin           # Stable identity for patch operations
  name: './src/my-plugin.ts'  # Module specifier (path or package name)
  config:
    greeting: 'Hello'
    timeout: 30000
  disabled: false          # Keep entry, skip mounting
```

### Dynamic JS in Config

```yaml
- id: my-plugin
  name: './src/my-plugin.ts'
  config:
    apiKey: !!js process.env.API_KEY ?? 'fallback'
    greeting: !!js process.env.DEMO_GREETING ?? 'Hello'
  disabled: !!js process.platform === 'win32'  # Evaluated at mount time
```

> Use `!!js` (double bang), NEVER `!js`. Only works in `config` and `disabled` fields.

### Group and Isolation

```yaml
- id: group-isolated
  name: '@deepseek-ai/cordis-plugin-group'
  group: true
  isolate:
    shell: true
  config:
    - name: '@deepseek-ai/dsh-bash-local'
    - name: './src/worker.ts'
```

### Patch Overlay (cordis.patch.yml)

```yaml
# Insert new plugins
- insert:
    - id: custom-logger
      name: '/absolute/path/to/my-plugin.ts'
      config:
        verbose: true

# Override existing row by id
- id: session-title
  name: '@deepseek-ai/dsh-session-title'
  config:
    fallbackMaxWords: 6

# Disable a row
- id: tool-bash
  disabled: true
```

### Entry Metadata Fields

| Field | Purpose |
|-------|---------|
| `id` | Stable identity (for patching/diffing) |
| `name` | Module specifier (path or package) |
| `config` | Plugin configuration object |
| `disabled` | Skip mounting without removing |
| `group` | Nest sub-entries |
| `isolate` | Per-service instance isolation |
| `inject` | Additional YAML-level service dependencies |

---

## 10. Runtime Integration: Shell, Python, Binary, E2B

### Shell Execution (Bash)

The shell capability is a three-package seam:
- `dsh-shell` — Service Definition (abstract)
- `dsh-bash-local` — Provider (local bash execution)
- `dsh-tool-bash` — Consumer (model-facing tool)

**Tool bash schema** (model sees):
```json
{
  "command": "string (required)",
  "description": "string (required)",
  "timeoutMs": "number",
  "workdir": "string",
  "run_in_background": "boolean"
}
```

### PowerShell (Windows)

- `dsh-pwsh-local` — Provider
- `dsh-tool-pwsh` — Consumer
- Same pattern as bash, with Windows-native paths

### Persistent Shell (PTY)

- `dsh-tool-bash-persistent` — Persistent bash with state across calls
- `dsh-tool-pwsh-persistent` — Persistent PowerShell
- Uses `ctx.terminals` backend

### Python SDK Integration

The Python SDK (`deepseek-harness-sdk`) runs DSH as a subprocess:

```python
from deepseek_harness import DeepSeekHarness

with DeepSeekHarness(
    provider="deepseek-official",
    model="deepseek-v4-flash",
    max_tokens=49_152,
    cwd=str(workspace),
    dsh_home=str(dsh_home),
    profile="sdk-minimal",
) as harness:
    result = harness.run(
        "Inspect the repository and fix the failing tests.",
        session_id="example-001",
    )
print(result.final_response)
```

Key characteristics:
- Starts bundled `dsh --profile sdk-minimal` lazily
- Normal execution needs no system Node.js
- The `sdk-minimal` profile provides bash + str_replace_editor

### Code Runtime (PTC Mode)

The `ctx.codeRuntime` seam provides sandboxed code execution:
- `dsh-code-runtime-worker-thread` — TypeScript in worker thread
- `dsh-experimental-code-runtime-python` — Python execution (experimental)
- Tools automatically exposed as `await tools.<name>(args)` in code

### E2B Sandbox (Remote)

The `packages/e2b/` group provides remote execution:
- `dsh-e2b` — Core E2B client
- `dsh-fs-e2b` — Remote filesystem provider
- `dsh-subprocess-e2b` — Remote subprocess provider

### Subprocess

- `dsh-subprocess` — Service Definition
- `dsh-subprocess-local` — Local process provider
- `dsh-subprocess-e2b` — Remote E2B provider

### Workflow (Structured Multi-Step)

- `dsh-workflow` — Service Definition
- `dsh-workflow-worker-thread` — Worker thread engine
- `dsh-tool-workflow` — Model-facing tool

---

## 11. Custom Mode / Dynamic Plugins (Self-Modification)

### What is "Custom Mode"?

The **"Creation Mode" (`cordis` preset)** enables runtime plugin creation. The model can inspect, define, run, stop, and remove dynamic plugins.

### Enabling Custom Mode

```sh
pnpm dsh web --patch apps/cli/config/examples/cordis/cordis.yml
```

### The 7 Model-Facing Tools

| Tool | Purpose |
|------|---------|
| `cordis_inspect_list` | Discover available Inspect Providers |
| `cordis_inspect_query` | Query service contracts, events, tools |
| `cordis_inspect_self` | Inspect current session's dynamic plugins |
| `cordis_define` | Submit plain JS for host/client halves |
| `cordis_run` | Activate a package version |
| `cordis_stop` | Pause effects while retaining definitions |
| `cordis_undefine` | Permanently destroy a dynamic plugin |

### Dynamic Plugin Code (Host Half)

Dynamic code is **plain JavaScript** — no TypeScript, JSX, or ES imports:

```javascript
// Host half (code.host) — passed as a string
return {
  name: 'my-custom-plugin',
  inject: ['timer', 'tools'],
  apply(ctx) {
    harness.registerTool(ctx, harness.defineTool({
      name: 'calculate_hash',
      description: 'Hash input text.',
      parameters: {
        text: { type: 'string', required: true }
      },
      output: {
        schema: { type: 'object' },
        render(args, value) {
          return [{ type: 'text', text: `Result: ${JSON.stringify(value)}` }]
        }
      },
      async execute(args) {
        return { hash: btoa(args.text) }
      }
    }))
  }
}
```

### Sandbox Constraints

**Available globals**: `ctx` (guarded façade), `harness` (`defineTool`, `registerTool`, `handle`), `console`, `btoa`, `atob`, `TextEncoder`, `TextDecoder`

**Blocked with teaching errors**:
- `require` → "Use inject/services"
- `setTimeout`/`setInterval` → "Use `inject: ['timer']` + `ctx.timeout`"
- `fetch` → "Use `inject: ['web']` + `ctx.web`"
- Filesystem → "Use `inject: ['fs']` + `ctx.fs`"

Definitions live only in process memory — DSH restart clears them.

---

## 12. Hooks and Interception Points

### Native Cordis Hooks

A "native hook" is simply a Cordis plugin subscribing to lifecycle events. No special framework required.

### Canonical Interception Points

| Event | Mode | Contract |
|-------|------|----------|
| `agent/session-start` | emit | Pure notification |
| `agent/pre-step` | waterfall | Returns `PreStepDecision`: `enter` or `reject` |
| `tools/pre-execute` | waterfall | Returns `PreToolDecision`: `allow`, `deny`, or `ask` |
| `ctx.tools.guard()` | guard | Monotonic deny or abstain (cannot force-allow) |
| `tools/execute` | waterfall | Around-dispatch (timeout, retry) |
| `tools/post-execute` | waterfall | Accept, block, replace, add context |
| `agent/turn-stopping` | serial | Listeners can steer another step |

### Permission Gate Example

```ts
import type { Context } from '@deepseek-ai/cordis'
import type { PreToolDecision, ToolExecution } from '@deepseek-ai/dsh-tools'

export const name = 'permission-gate'

export function apply(ctx: Context) {
  ctx.on('tools/pre-execute', async (exec, next): Promise<PreToolDecision> => {
    if (!(await isAllowed(exec))) {
      return { kind: 'deny', reason: 'Denied by policy.' }
    }
    return next()
  })
}
```

### Monotonic Guard

```ts
ctx.tools.guard((exec) => {
  if (isReadOnlyMode() && isMutationTool(exec.name)) {
    return 'Mutations disabled in read-only mode.'
  }
  return undefined  // Allowed
})
```

### Hook Bridges (External)

- `dsh-hooks-claude-code` — Maps Claude Code `hooks.json` to Cordis events
- `dsh-hooks-codex` — Maps Codex hooks

Mapping:
- `SessionStart` → `agent/session-start`
- `UserPromptSubmit` → `agent/pre-step`
- `PreToolUse` → `tools/pre-execute`
- `PostToolUse` → `tools/post-execute`
- `Stop` → `agent/turn-stopping`

---

## 13. MCP Integration

### How MCP Works in DSH

`@deepseek-ai/dsh-mcp-client` mounts external MCP servers as native tools.

- **Tool naming**: `mcp__<serverName>__<rawToolName>`
- **Transports**: `stdio` (local subprocess) and `streamable-http` (remote)
- **Environment scrubbing**: Strips ambient credentials automatically
- **Auto-reconnect**: Exponential backoff (configurable max attempts)

### Stdio Configuration

```yaml
- id: mcp-github
  name: '@deepseek-ai/dsh-mcp-client'
  config:
    serverName: github
    transport: stdio
    command: npx
    args: ['-y', '@modelcontextprotocol/server-github']
    env:
      GITHUB_TOKEN: !!js process.env.GITHUB_TOKEN
    toolCallTimeoutMs: 60000
    reconnect:
      enabled: true
      maxAttempts: 10
```

### HTTP Configuration

```yaml
- id: mcp-remote-service
  name: '@deepseek-ai/dsh-mcp-client'
  config:
    serverName: custom_api
    transport: streamable-http
    url: http://127.0.0.1:4000/mcp
    headers:
      Authorization: !!js '`Bearer ${process.env.API_KEY}`'
```

### Generic Template

```yaml
- insert:
    - id: memory-my-server
      name: '@deepseek-ai/dsh-mcp-client'
      config:
        serverName: my-memory
        transport: stdio
        command: my-memory-mcp
        args: []
        env: {}
        cwd: !!js process.cwd()
```

---

## 14. LLM Adapter Creation

### Minimal Implementation

```ts
import type { Context } from '@deepseek-ai/cordis'
import Schema from '@deepseek-ai/schemastery'
import { LlmAdapter, type GenerateOptions, type StreamChunk } from '@deepseek-ai/dsh-llm'

class MyAdapter extends LlmAdapter {
  private apiKey: string
  constructor(apiKey: string) {
    super()
    this.apiKey = apiKey
  }

  async *stream(options: GenerateOptions): AsyncIterable<StreamChunk> {
    // Convert options.messages → provider format
    // Call streaming API
    // Yield StreamChunk values
  }
}

export interface Config { apiKey: string; providers: string[] }
export const Config: Schema<Config> = Schema.object({
  apiKey: Schema.string().required(),
  providers: Schema.array(Schema.string()).required(),
})

export const name = 'my-llm-adapter'
export const inject = ['llm']

export function apply(ctx: Context, config: Config) {
  ctx.llm.registerAdapter(config.providers, new MyAdapter(config.apiKey))
}
```

### StreamChunk Protocol

```ts
async function* exampleChunks(): AsyncIterable<StreamChunk> {
  yield { type: 'block-start', index: 0, blockType: 'text' }
  yield { type: 'text-delta', index: 0, text: 'Hello' }
  yield { type: 'text-delta', index: 0, text: ' world' }
  yield { type: 'block-end', index: 0, block: { type: 'text', text: 'Hello world' } }

  yield { type: 'block-start', index: 1, blockType: 'tool-call' }
  yield { type: 'tool-call-delta', index: 1,
    id: brandString<ToolCallId>('call-123'),
    name: 'bash',
    argumentsDelta: '{"command":"ls"}' }
  yield { type: 'block-end', index: 1,
    block: { type: 'tool-call',
      id: brandString<ToolCallId>('call-123'),
      name: 'bash',
      arguments: '{"command":"ls"}' } }

  yield { type: 'usage', usage: { inputTokens: 100, outputTokens: 50 } }
  yield { type: 'finish', reason: { kind: 'stop' } }
}
```

### Protocol Rules

- Every `block-start` has matching `block-end`
- `index` increases from 0
- Tool call `arguments` are RAW JSON strings
- Emit `usage` BEFORE `finish`
- Emit NOTHING after `finish`
- Honor `options.signal` for cancellation
- Throw `LlmError` with stable code for unsupported options

### Error Handling

```ts
import { attributionHeaders, LlmError } from '@deepseek-ai/dsh-llm'

const response = await fetch(this.endpoint, {
  method: 'POST',
  headers: { 'content-type': 'application/json', ...attributionHeaders() },
  body: JSON.stringify({ model: options.model, messages: options.messages }),
  ...options.signal ? { signal: options.signal } : {},
})
if (!response.ok) {
  throw new LlmError(`Provider API error: ${response.status}`, 'PROVIDER_HTTP_ERROR')
}
```

### cordis.yml Integration

```yaml
- id: my-llm
  name: './src/my-llm-adapter.ts'
  config:
    apiKey: !!js process.env.MY_API_KEY
    providers: ['my-provider']

- id: agent-loop
  name: '@deepseek-ai/dsh-agent-loop'
  config:
    agents:
      - id: main
        provider: my-provider
        model: my-model-v1
```

---

## 15. Skills and Agent Instructions

### Skills

Skills provide reusable, on-demand instructions. Format:

```markdown
---
name: code-refactoring
description: Standard instructions for refactoring modules cleanly.
whenToUse: Use when breaking down large functions or migrating APIs.
disable-model-invocation: false
user-invocable: true
---

# Code Refactoring Instructions
1. Inspect tests first.
2. Maintain single responsibility per file.
```

### Discovery Priority

1. `<projectRoot>/.dsh/skills` (Rank 100)
2. `<projectRoot>/.agents/skills` (Rank 200)
3. `Config.customSkillDirs` (Rank 300)
4. `<dshHome>/skills` (Rank 400)
5. `<agentsHome>/skills` (Rank 500)
6. Optional bundled root (Rank 600)

### Agent Instructions (AGENTS.md / CLAUDE.md)

- Scanned files: `AGENTS.md`, `CLAUDE.md`, plus `.local.md` variants
- Hierarchy: user global → directory ancestors → working directory
- Budget: 65,536 bytes default
- Injected as durable `<system-reminder>` at step 1
- Refreshed dynamically when tools touch deeper folders

---

## 16. Publishing and Packaging

### Bundle Manifest (`package.json`)

```json
{
  "name": "dsh-hello-plugin",
  "version": "0.1.0",
  "type": "module",
  "main": "index.js",
  "files": ["index.js", "cordis.patch.yml"],
  "dsh": { "bundle": { "patch": "./cordis.patch.yml" } }
}
```

### Bundle Patch (`cordis.patch.yml`)

```yaml
- insert:
    - id: hello
      name: dsh-hello-plugin
```

### Installing into a Profile

```sh
dsh plugin --profile demo add ./hello-plugin
# Creates profile with @deepseek-ai/dsh-base + your bundle
```

### Distribution Options

| Method | Command |
|--------|---------|
| Local checkout | `dsh plugin add ./hello-plugin` |
| npm registry | `dsh plugin add your-package` |
| GitHub | `dsh plugin add github:you/hello-plugin` |
| Tarball | `dsh plugin add ./hello-plugin-0.1.0.tgz` |

### GitHub Install Catch

Git installs fetch sources, not built artifacts. Authors must:
1. Ship a `prepare` script (pnpm runs after git install)
2. Users must allowlist builds in `pnpm-workspace.yaml`:
   ```yaml
   allowBuilds:
     dsh-hello-plugin: true
   ```

---

## 17. Plugin Lifecycle and HMR

### Hot Module Replacement

With `@deepseek-ai/cordis-plugin-hmr` loaded:

```yaml
- id: hmr
  name: '@deepseek-ai/cordis-plugin-hmr'
  config:
    root: ['.']
```

On file save:
1. Old plugin unloads (all effects unwound)
2. New code loads
3. New `apply` runs

### Diagnosing PENDING Plugins

```ts
import { FiberState, type Context } from '@deepseek-ai/cordis'

export function apply(ctx: Context) {
  setTimeout(() => {
    for (const runtime of ctx.registry.values()) {
      for (const fiber of runtime.fibers) {
        if (fiber.state === FiberState.PENDING) {
          console.log(`${fiber.name} is PENDING — a required service is missing`)
        }
      }
    }
  }, 500)
}
```

### Entry `id` Matters for HMR

Always use explicit `id`s in `cordis.yml`:
```yaml
- id: my-plugin    # Stable identity for diffing
  name: './my-plugin.ts'
```

Without `id`, every config edit treats the entry as removed+added and remounts it.

---

## 18. Tool Execution Pipeline (Complete)

```
ToolExecutionInput
       │
       ▼ (Materialize & Freeze JSON args, assign Token)
1. tools/pre-execute (Waterfall: allow | deny | ask)
       │
       ▼
2. ctx.tools.guard() (Monotonic final denial checks)
       │
       ▼
3. tools/execute (Waterfall: Around-dispatch wrappers)
       │
       ▼ [Tool execute() body runs]
4. tools/post-execute (Waterfall: accept | replace | block)
       │
       ▼
5. finalizeContent() (Definition-level last-mile transform)
       │
       ▼
6. tools/result (Emit: Authoritative immutable broadcast)
```

Full 16-stage pipeline:

1. `tool/call` event logged to session
2. `presentCall(args)` generates UI pending card
3. `tools/pre-execute` waterfall (hooks, permissions, sandbox)
4. Monotonic guards (`ctx.tools.guard()`)
5. `ctx.approval` one-shot prompt (if ask)
6. `tools/execute` waterfall (around-dispatch)
7. Tool's `execute(args, exec)` runs
8. Inner event gates (`fs/write-intent`, etc.)
9. `tools/post-execute` waterfall
10. Registry outer normalization
11. `ToolDefinition.finalizeContent`
12. `tools/result` synchronous notification
13. Active-batch `additionalContexts` FIFO
14. `tool/result` event logged to session
15. `presentResult(args, result)` generates UI card
16. Tool batch settled

---

## 19. Defensive Patterns (Mandatory)

Seven rules from real post-mortems:

### 1. Report Orthogonal Outcomes Independently

```ts
// WRONG: nested status
if (timedOut) { /* can't report exitCode */ }

// CORRECT: independent fields
return { timedOut: boolean, signal: string | null, exitCode: number | null }
```

### 2. Honor Public Contracts on BOTH Sides

Normalize provider-specific variations into a unified contract before returning.

### 3. Async State Is Not Synchronous State

- `agent.followup()` has no per-message completion promise
- Don't treat `whenIdle()` as outcome of a single message

### 4. Dispose Must Reach Quiescence

```ts
ctx.effect(() => {
  return async () => {
    proc.kill('SIGTERM')
    await proc.done  // MUST await completion!
  }
})
```

### 5. Contain Callback Exceptions in the Dispatcher

```ts
for (const listener of listeners) {
  try { listener(payload) }
  catch (err) { console.error('[Event] Error in listener:', err) }
}
```

### 6. Never Hand Untrusted Output Ambient Environment

```ts
const SENSITIVE = /KEY|SECRET|TOKEN|PASSWORD|AUTH|CREDENTIAL/i
for (const [k, v] of Object.entries(env)) {
  if (v !== undefined && !SENSITIVE.test(k)) clean[k] = v
}
```

### 7. Unlink Link-Shaped Paths

```ts
const stat = lstatSync(targetPath, { throwIfNoEntry: false })
if (stat?.isSymbolicLink()) unlinkSync(targetPath)
else if (stat?.isDirectory()) rmSync(targetPath, { recursive: true, force: true })
else if (stat) unlinkSync(targetPath)
```

---

## 20. UI Presentation Cards

### Card Types

| Card | Purpose |
|------|---------|
| `generic` | Default card with title, kind, content, locations |
| `terminal` | Shell command display |
| `diff` | File create/edit diff view |
| `read` | File viewer window |
| `search` | Discovery results (matches or paths) |
| `web` | Web search/fetch results |

### presentCall Example

```ts
presentCall(args) {
  return {
    card: 'generic',
    title: `Read ${args.path}`,
    kind: 'read',
    locations: [{ path: args.path }],
  }
}
```

### presentResult Example

```ts
presentResult(args, result) {
  return {
    card: 'generic',
    title: `Read ${args.path} (${result.isError ? 'failed' : 'ok'})`,
  }
}
```

### Hard Rules

- **Purity**: Pure functions of `args` + result only. NO I/O, NO clock/random, NO session state
- **UI-only formatting stays out of model result**: No fenced blocks in canonical value
- `defineTool` soft-validates: malformed args return `undefined` (generic fallback) rather than throw

---

## 21. Presets (Per-Session Agent Composition)

### Preset Directory Layout

```
~/.dsh/.agent-presets/<id>/
├── agent.cordis.yml   # Per-session plugin composition
├── preset.yml         # Display metadata (name, description)
└── skills/            # Optional preset-specific skills
```

### Roster API

- `ctx.agentPresets.list()` — All presets with ID and trust level
- `ctx.agentPresets.read(id)` — YAML content
- `ctx.agentPresets.copy(fromId, newId, displayName?)` — Clone preset

### Group Isolation Rule

A preset MUST NOT publish a service into the global root realm:

```yaml
- id: delegation
  name: cordis:group
  group: true
  isolate:
    workflowEngine: true
  config:
    - id: workflow-worker-thread
      name: '@deepseek-ai/dsh-workflow-worker-thread'
    - id: tool-workflow
      name: '@deepseek-ai/dsh-tool-workflow'
```

---

## 22. Complete Dos and Don'ts

### DO

- ✅ Attach new behavior to documented extension points, not `agent-loop`
- ✅ Log a durable session event for any data that reaches the model
- ✅ Use `ctx.effect()` for all non-Cordis resources (timers, connections)
- ✅ Call `next()` in waterfall listeners (unless intentionally short-circuiting)
- ✅ Use `defineTool` for tool creation (not raw JSON-schema unless bridging MCP)
- ✅ Keep `presentCall`/`presentResult` pure (no I/O, no clock)
- ✅ Use Schemastery schemas to validate config at startup
- ✅ Honor `exec.signal` for cancellation
- ✅ Use `declare module '@deepseek-ai/cordis'` for custom Context services and Events
- ✅ Make plugin paths absolute in patch files
- ✅ Use `!!js` (double bang) for dynamic config values
- ✅ Hoist all deployment tunables to Config fields
- ✅ Await async quiescence on disposal
- ✅ Use `agent.ctx` when registering tools/sections that belong to one agent
- ✅ Use abstract/concrete classes extending `Service` for Service Definitions
- ✅ Return disposers from registrations
- ✅ Declare dependencies via `inject` instead of manual sequencing
- ✅ Give entries explicit `id`s in cordis.yml for stable patching/HMR

### DON'T

- ❌ Create standalone launcher scripts or package bins (only `dsh` profiles)
- ❌ Modify core packages when a plugin beside them achieves the goal
- ❌ Let side effects escape `ctx.effect()` — causes leaks on reload
- ❌ Forget `next()` in waterfall listeners (silently kills downstream pipeline)
- ❌ Put UI markdown in `output.render` (use card presenters instead)
- ❌ Mutate registered tool definitions (dispose and re-register instead)
- ❌ Hardcode tunables (use Config fields)
- ❌ Silently swallow config errors or fall back for missing required credentials
- ❌ Preemptively split into three packages if roles won't be swapped independently
- ❌ Use `!js` (single bang) — always use `!!js`
- ❌ Let consumers import concrete provider packages
- ❌ Design single-role "seams" (interface without consumer or provider is incomplete)
- ❌ Write hierarchical scope inheritance trees (scopes are flat)
- ❌ Drive an agent or send messages inside the `setup` window (only register)
- ❌ Throw unhandled exceptions in event listeners
- ❌ Write temporary files to predictable global paths without exclusive flags
- ❌ Issue un-awaited abort/kill in teardown hooks

---

## 23. Quick Reference Templates

### Template: Function Plugin with Config

```ts
import type { Context } from '@deepseek-ai/cordis'
import Schema from '@deepseek-ai/schemastery'

export const name = 'my-plugin'
export const inject = ['tools']

export interface Config {
  setting: string
  timeout?: number
}

export const Config: Schema<Config> = Schema.object({
  setting: Schema.string().required(),
  timeout: Schema.number().default(30000),
})

export function apply(ctx: Context, config: Config) {
  // Plugin logic here
}
```

### Template: Tool Plugin

```ts
import type { Context } from '@deepseek-ai/cordis'
import { defineTool } from '@deepseek-ai/dsh-tools'

export const name = 'my-tool'
export const inject = ['tools']

export function apply(ctx: Context) {
  ctx.tools.register(defineTool({
    name: 'tool_name',
    description: 'What the model sees.',
    parameters: {
      input: { type: 'string', required: true, description: 'Input text' },
    },
    output: {
      schema: { type: 'string' },
      render: (_args, value) => [{ type: 'text', text: value }],
    },
    async execute(args, exec) {
      return `Result: ${args.input}`
    },
  }))
}
```

### Template: Service Provider

```ts
import { Service, type Context } from '@deepseek-ai/cordis'

declare module '@deepseek-ai/cordis' {
  interface Context { myService: MyService }
}

export default class MyService extends Service {
  constructor(ctx: Context) { super(ctx, 'myService') }
  doWork(input: string) { return input.toUpperCase() }
}
```

### Template: Event Observer

```ts
import type { Context } from '@deepseek-ai/cordis'

export const name = 'my-observer'
export const inject = ['tools']

export function apply(ctx: Context) {
  ctx.on('tools/result', (exec, result) => {
    console.log(`Tool ${exec.name} completed. Error: ${result.isError}`)
  })
}
```

### Template: Permission Gate

```ts
import type { Context } from '@deepseek-ai/cordis'
import type { PreToolDecision } from '@deepseek-ai/dsh-tools'

export const name = 'my-gate'

export function apply(ctx: Context) {
  ctx.on('tools/pre-execute', async (exec, next): Promise<PreToolDecision> => {
    if (exec.name === 'dangerous_tool') {
      return { kind: 'deny', reason: 'Not allowed.' }
    }
    return next()
  })
}
```

### Template: Patch Overlay

```yaml
# cordis.patch.yml
- insert:
    - id: my-plugin
      name: '/absolute/path/to/plugin.ts'
      config:
        setting: 'value'
```

### Template: Bundle package.json

```json
{
  "name": "dsh-my-bundle",
  "version": "0.1.0",
  "type": "module",
  "main": "index.js",
  "files": ["index.js", "cordis.patch.yml"],
  "dsh": { "bundle": { "patch": "./cordis.patch.yml" } }
}
```

### Template: System Prompt Section

```ts
export const inject = ['systemPrompt']

export function apply(ctx: Context) {
  ctx.systemPrompt.section({
    id: 'my-custom-guidelines',
    header: 'Custom Policy Guidelines',
    order: 50,
    render: (agent) => 'Always format responses with brevity.',
  })
}
```

### Template: Human Command

```ts
export const inject = ['commands']

export function apply(ctx: Context) {
  ctx.commands.register({
    name: 'status',
    description: 'Display system status',
    input: { hint: '[optional filter]' },
    async handler(invocation) {
      return { kind: 'success', text: `System OK: ${invocation.rawInput}` }
    },
  })
}
```

### Template: MCP Client

```yaml
- insert:
    - id: mcp-my-server
      name: '@deepseek-ai/dsh-mcp-client'
      config:
        serverName: my_server
        transport: stdio
        command: my-mcp-binary
        args: ['--flag']
        env:
          API_KEY: !!js process.env.MY_API_KEY
```

---

> **Source**: Compiled from the DeepSeek Harness repository at `/home/ankdesh/explore/deepseek-harness/deepseek-harness/`, including `docs/`, `packages/`, `apps/`, and web research. All code examples are extracted from or modeled after actual DSH documentation and source.

<!-- GOAL_COMPLETE -->
