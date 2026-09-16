# Native development and deployment

## Build a release

The builder needs the tested Harness checkout with dependencies installed and its host runtime built. The sample's `harness.lock.json` pins the Harness commit; the packager refuses a different HEAD. `harness.product.json` selects product-owned deployment files. The packager reads the actual installed production dependency graph, including required peers and available platform-compatible optional dependencies.

From the sample directory, choose an unused output directory:

```sh
npm run package -- /tmp/asd-sample-release
```

The output is a release directory and a sibling `.tar.gz`. It includes the unmodified built `dsh` launcher with a trimmed deployment manifest, the product bundle/UI, required runtime packages, relative internal links, Python dependency files, launch/provisioning scripts, license notices, `release.json`, and `SHA256SUMS`.

This is a complete application archive, unlike an npm package tarball. No npm install or JavaScript build runs on the target. Node, Bash, Python, and uv are platform prerequisites; uv provisions the external Python environment before first launch. The archive targets the builder's OS, CPU architecture, and libc. This sample is verified on Linux x64 with glibc.

## Try the unpacked release

Extract the archive into a new directory. First create an owner-only environment file at `~/.config/asd-sample/environment` and configure `OPENAI_API_KEY`. From the extracted release directory:

```sh
sha256sum --check SHA256SUMS
export SAMPLE_STATE="$HOME/.local/state/asd-sample"
sh deployment/provision.sh
export SAMPLE_ENV_FILE="$HOME/.config/asd-sample/environment"
node deployment/launch.mjs
```

Create the environment file with owner-only permissions and configure `OPENAI_API_KEY`, optionally `OPENAI_MODEL`, `OPENAI_BASE_URL`, and `SAMPLE_PORT`. Never place credentials inside the release directory. Open the access link printed by the launcher. The same state directory retains sessions, conversation workspaces, and the Python environment across release upgrades.

## Run as a user service

The included `deployment/asd-sample.service` is a systemd user-service template. It uses `~/apps/asd-sample/current` as a symlink to an immutable extracted release, `~/.config/asd-sample/environment` for configuration, and `~/.local/state/asd-sample` for writable state. Configure the service's PATH or use an absolute Node executable when Node is installed through nvm. Provision Python before starting the service.

Review the template for the host, copy it into `~/.config/systemd/user/`, and use the ordinary systemd user-service workflow. Installation/enabling is an operator step; the build and tests do not change system services. For remote use, keep the service on loopback and forward its port through SSH. Public multi-user hosting needs additional authentication and execution isolation.

## Upgrade and reuse

1. Merge an upstream candidate into the shared Harness integration branch.
2. Reinstall using the fork's lockfile and rebuild the host runtime.
3. Test this product against the candidate using `HARNESS_SOURCE`.
4. Update `harness.lock.json` only after the product checks pass.
5. Build a new release, unpack it elsewhere, and run the integration test with `SAMPLE_RELEASE` pointing at it.
6. Stop the service, back up its state, change `current`, and restart. Roll back only when the old runtime supports the stored session format.

Each other project owns its own bundle, profile, UI, dependency locks, release recipe, and deployment files. Reuse the fork's three `product-*.mjs` scripts. No product needs a private agent loop or a copied Harness source tree.

## Verification evidence

The native-release integration test launches the real bundled CLI and performs Bash/Python tool calls through a local OpenAI-compatible protocol fixture. It tests streamed text and conversation persistence across restart. It requires no model key. Actual model responses require the operator's configured API key.
