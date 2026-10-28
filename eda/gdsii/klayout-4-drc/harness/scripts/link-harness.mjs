/** Link compile-time dependencies to the Harness workspaces without modifying the Harness repository. */
import { existsSync, lstatSync, mkdirSync, mkdtempSync, readFileSync, readdirSync, realpathSync, renameSync, statSync, symlinkSync, unlinkSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { updateHarnessSource } from "./harness-env.mjs";

const product = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const requested = resolve(process.argv[2] || process.env.HARNESS_SOURCE || join(product, "../.tools/deepseek-harness"));
if (!existsSync(join(requested, "scripts/product-runtime.mjs"))) {
  throw new Error(`Not a Harness checkout: ${requested}`);
}
const harness = realpathSync(requested);

function requiredPath(path, directory = false) {
  if (!existsSync(path)) {
    throw new Error(`Harness toolchain is incomplete: missing ${path}. Run pnpm install in ${harness} before linking dependencies.`);
  }
  const stat = statSync(path);
  if (directory ? !stat.isDirectory() : !stat.isFile()) {
    throw new Error(`Harness toolchain path is not a ${directory ? "directory" : "file"}: ${path}.`);
  }
  return realpathSync(path);
}

const toolchain = [["tsc", "typescript"], ["tsx", "tsx"]].map(([command, packageName]) => {
  const packageRoot = requiredPath(join(harness, "node_modules", packageName), true);
  const manifest = JSON.parse(readFileSync(requiredPath(join(packageRoot, "package.json")), "utf8"));
  const entry = typeof manifest.bin === "string" ? manifest.bin : manifest.bin?.[command];
  if (typeof entry !== "string" || !entry) {
    throw new Error(`Harness ${packageName} package does not declare ${command} executable.`);
  }
  return { command, packageName, packageRoot, executable: requiredPath(join(packageRoot, entry)) };
});

const types = requiredPath(join(harness, "node_modules", "@types"), true);

const directories = [];
for (const group of ["vendor", "packages"]) {
  const groupPath = join(harness, group);
  if (!existsSync(groupPath)) continue;
  for (const entry of readdirSync(groupPath, { withFileTypes: true })) {
    if (!entry.isDirectory()) continue;
    const directory = join(groupPath, entry.name);
    if (group === "vendor") {
      directories.push(directory);
    } else {
      for (const member of readdirSync(directory, { withFileTypes: true })) {
        if (member.isDirectory()) directories.push(join(directory, member.name));
      }
    }
  }
}

const packages = [];
for (const directory of directories) {
  const manifest = join(directory, "package.json");
  if (!existsSync(manifest)) continue;
  const { name } = JSON.parse(readFileSync(manifest, "utf8"));
  if (name?.startsWith("@deepseek-ai/")) {
    packages.push([name.slice("@deepseek-ai/".length), directory]);
  }
}

const modules = join(product, "node_modules");
mkdirSync(modules, { recursive: true });
const generated = mkdtempSync(join(modules, ".harness-links-"));
const namespace = join(generated, "@deepseek-ai");
mkdirSync(namespace);
for (const [name, directory] of packages) {
  symlinkSync(directory, join(namespace, name), "dir");
}

function replaceLink(local, target, backupName, type) {
  let previous;
  try { previous = lstatSync(local); }
  catch (error) { if (error.code !== "ENOENT") throw error; }
  if (previous?.isSymbolicLink()) unlinkSync(local);
  else if (previous) renameSync(local, join(generated, backupName));
  symlinkSync(target, local, type);
}

replaceLink(join(modules, "@deepseek-ai"), namespace, "previous-installed-scope", "dir");
replaceLink(join(modules, "@types"), types, "previous-installed-types", "dir");
mkdirSync(join(modules, ".bin"), { recursive: true });
for (const { command, packageName, packageRoot, executable } of toolchain) {
  replaceLink(join(modules, packageName), packageRoot, `previous-installed-${packageName}`, "dir");
  replaceLink(join(modules, ".bin", command), executable, `previous-installed-bin-${command}`, "file");
}

// Also link third-party dependencies from harness node_modules needed by cordis/schemastery/yaml
for (const dep of ["yaml"]) {
  const depPath = join(harness, "node_modules", dep);
  if (existsSync(depPath)) {
    replaceLink(join(modules, dep), depPath, `previous-installed-${dep}`, "dir");
  }
}

updateHarnessSource(product, harness);
console.log(`Harness DRC dependencies linked to ${harness}`);
