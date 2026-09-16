# ASD Harness sample

A focused local assistant with Bash and Python execution. The UI, prompts, tool, and profile live here. DeepSeek Harness supplies the normal `dsh` launcher, agent loop, model adapter, tool registry, and durable sessions.

## Development

Use Node 22.19+ in the 22 series, or Node 24+, Bash, Python 3.11+, and uv. Build the sibling Harness checkout using its pinned pnpm version:

```sh
cd ../../../deepseek-harness
corepack pnpm install --frozen-lockfile
corepack pnpm run build:native-system
corepack pnpm run build:lib:host
```

From this sample directory:

```sh
uv sync
cp .env.example .env
# Edit .env to configure OPENAI_API_KEY. Do not commit this file.
npm run dev
```

Open the access link printed in the terminal. `HARNESS_SOURCE` selects another local checkout. `SAMPLE_PORT` defaults to 6020. `SAMPLE_STATE` defaults to `.dev`; each conversation gets a separate workspace beneath it. Restart the app after changing host code or the profile; refresh the browser after changing UI files.

The API requires a local access token. The service listens on loopback. Tool execution has the service user's filesystem and network access; the workspace is a working directory, not a sandbox. Do not expose this sample as a public multi-user service.

## Verification

```sh
npm test
```

The integration test uses a local OpenAI-compatible protocol fixture with the real `dsh` process, pi-ai adapter, agent loop, execution tool, and persistence backend. It verifies Bash/Python execution, streamed text, authenticated endpoints, and conversation reload after restart. It does not evaluate a live model's reasoning.

## Native release

After the development setup, build an archive into an unused output directory:

```sh
npm run package -- /tmp/asd-sample-release
```

The output contains the required JavaScript packages and launch scripts. Follow the [deployment guide](docs/deployment.md) to provision Python and launch the extracted release. State and credentials remain outside the release directory.

## Preview

[Welcome screen](docs/screenshots/welcome.png) · [Chat and tool results](docs/screenshots/chat.png) · [Mobile layout](docs/screenshots/mobile.png)

The chat screenshot uses the local test fixture; it shows real Bash/Python execution through Harness.

See [architecture](docs/architecture.md),
[Cordis and Harness components](docs/cordis-harness-components.md), and
[native deployment](docs/deployment.md) for runtime composition, ownership,
and release maintenance.
