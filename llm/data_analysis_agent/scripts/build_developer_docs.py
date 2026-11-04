"""Build the local developer handbook without importing the application or calling a model."""

import ast
from datetime import datetime, timezone
import hashlib
import html
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import shutil
import subprocess
import tomllib

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / 'docs' / 'developer'


def inspect_source():
    files = sorted([*ROOT.glob('backend/**/*.py'), *ROOT.glob('pipeline_core/**/*.py'),
                    *ROOT.glob('frontend/src/**/*.ts'), *ROOT.glob('frontend/src/**/*.tsx'),
                    *[ROOT / name for name in ['config.py','launcher.py','offline_app.py','runtime_launcher.py','pyproject.toml','requirements-runtime.txt','frontend/package.json','frontend/vite.config.ts']]])
    files = [p for p in files if '__pycache__' not in p.parts]
    hashes = {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    imports = []
    for path in files:
        if path.suffix != '.py': continue
        module = path.relative_to(ROOT).with_suffix('').as_posix().replace('/', '.')
        for node in ast.walk(ast.parse(path.read_text())):
            names = [alias.name for alias in node.names] if isinstance(node, ast.Import) else [node.module or ''] if isinstance(node, ast.ImportFrom) else []
            for name in names:
                if name.split('.')[0] in {'backend','pipeline_core','config','offline_app','runtime_launcher'}:
                    imports.append({'from': module, 'to': name, 'line': node.lineno})
    routes = []
    owners = {'backend/routes/project_routes.py':'Builder project API', 'pipeline_core/runtime_http.py':'Shared runtime API',
              'backend/routes/session_routes.py':'Compatibility session API', 'backend/app.py':'Builder application'}
    for filename, owner in owners.items():
        tree = ast.parse((ROOT / filename).read_text())
        prefixes = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Name) and node.value.func.id == 'APIRouter':
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        prefixes[target.id] = next((ast.literal_eval(k.value) for k in node.value.keywords if k.arg == 'prefix'), '')
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for dec in node.decorator_list:
                    if not (isinstance(dec, ast.Call) and isinstance(dec.func, ast.Attribute) and isinstance(dec.func.value, ast.Name) and dec.func.attr in {'get','post','patch','put','delete'} and dec.args and isinstance(dec.args[0], ast.Constant)): continue
                    prefix = prefixes.get(dec.func.value.id, '')
                    routes.append({'owner': 'Internal target broker' if dec.func.value.id == 'internal_router' else owner,
                        'method': dec.func.attr.upper(), 'path': prefix + str(dec.args[0].value), 'handler': node.name,
                        'source': filename, 'line': node.lineno})
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == 'add_api_route' and node.args and isinstance(node.args[0], ast.Constant):
                for method in next((ast.literal_eval(k.value) for k in node.keywords if k.arg == 'methods'), ['GET']):
                    routes.append({'owner':'Compatibility data export','method':method,'path':node.args[0].value,
                        'handler':ast.unparse(node.args[1]),'source':filename,'line':node.lineno})
    python = tomllib.loads((ROOT / 'pyproject.toml').read_text())['project']
    frontend = json.loads((ROOT / 'frontend/package.json').read_text())
    return {'generated_at':datetime.now(timezone.utc).isoformat(), 'scope':'Static declarations and selected source hashes, not a complete runtime call graph',
            'source_sha256':hashes,'python_internal_imports':imports,'routes':sorted(routes,key=lambda r:(r['owner'],r['path'],r['method'])),
            'python_dependencies':python['dependencies'],'python_optional_dependencies':python['optional-dependencies'],
            'frontend_dependencies':frontend['dependencies'],'frontend_dev_dependencies':frontend['devDependencies']}


def replace_generated(path, marker, generated):
    source = path.read_text()
    start, stop = f'<!-- {marker} -->', f'<!-- END_{marker} -->'
    if stop in source:
        a,b = source.index(start) + len(start),source.index(stop)
        source = source[:a]+'\n\n'+generated+'\n\n'+source[b:]
    else:
        source = source.replace(start,start+'\n\n'+generated+'\n\n'+stop)
    path.write_text(source)


def update_tables(inventory):
    parts = []
    for owner in sorted({r['owner'] for r in inventory['routes']}):
        rows = ['### '+owner, '', '| Method | Path | Handler/source |','| --- | --- | --- |']
        for route in inventory['routes']:
            if route['owner'] == owner:
                rows.append(f"| {route['method']} | `{route['path']}` | [{route['handler']}](../../{route['source']}) · line {route['line']} |")
        parts.append('\n'.join(rows))
    replace_generated(DOCS/'08-api.md','API_TABLES','\n\n'.join(parts))
    rows = ['| Group | Declared package requirement |','| --- | --- |']
    for requirement in inventory['python_dependencies']: rows.append(f'| Python application | `{requirement}` |')
    for group, requirements in inventory['python_optional_dependencies'].items():
        for requirement in requirements: rows.append(f'| Python optional: {group} | `{requirement}` |')
    for field, group in [('frontend_dependencies','Frontend'),('frontend_dev_dependencies','Frontend build/dev')]:
        for name, requirement in inventory[field].items(): rows.append(f'| {group} | `{name}` `{requirement}` |')
    replace_generated(DOCS/'09-dependencies.md','PACKAGE_TABLES','\n'.join(rows))


def inline(source, chapters):
    # Controlled Markdown subset used by this handbook: escaped text, code, links and emphasis.
    tokens = []
    def keep(value):
        tokens.append(value); return f'@@DOC_TOKEN_{len(tokens)-1}@@'
    def destination(value):
        return '#chapter-'+Path(value).stem if value in chapters else value
    source = re.sub(r'`([^`]+)`',lambda m:keep('<code>'+html.escape(m[1])+'</code>'),source)
    source = re.sub(r'!\[([^\]]*)\]\(([^)]+)\)', lambda m:keep('<figure><a href="'+html.escape(m[2],quote=True)+'" target="_blank"><img src="'+html.escape(m[2],quote=True)+'" alt="'+html.escape(m[1],quote=True)+'"></a><figcaption>'+html.escape(m[1])+' · Open diagram for full size; editable DOT source is in diagrams/.</figcaption></figure>'),source)
    source = re.sub(r'\[([^\]]+)\]\(([^)]+)\)',lambda m:keep('<a href="'+html.escape(destination(m[2]),quote=True)+'">'+html.escape(m[1])+'</a>'),source)
    source = html.escape(source)
    source = re.sub(r'\*\*([^*]+)\*\*',r'<strong>\1</strong>',source)
    for index,value in enumerate(tokens): source = source.replace(f'@@DOC_TOKEN_{index}@@',value)
    return source


def render_markdown(source, chapter, chapters):
    lines = source.splitlines(); output=[]; index=0
    while index < len(lines):
        line = lines[index]
        if not line.strip() or line.startswith('<!--'): index+=1;continue
        if line.startswith('```'):
            language=line[3:].strip(); index+=1; code=[]
            while index < len(lines) and not lines[index].startswith('```'): code.append(lines[index]);index+=1
            output.append('<pre><code class="language-'+html.escape(language)+'">'+html.escape('\n'.join(code))+'</code></pre>');index+=1;continue
        heading=re.match(r'^(#{1,6}) (.+)',line)
        if heading:
            level=min(6,len(heading[1])+1)
            output.append(f'<h{level}>'+inline(heading[2],chapters)+f'</h{level}>');index+=1;continue
        if line.startswith('|'):
            rows=[]
            while index < len(lines) and lines[index].startswith('|'):
                cells=[cell.strip() for cell in lines[index].strip().strip('|').split('|')]
                if not all(re.fullmatch(r':?-+:?',cell) for cell in cells): rows.append(cells)
                index+=1
            output.append('<div class="table-scroll"><table><thead><tr>'+''.join('<th>'+inline(c,chapters)+'</th>' for c in rows[0])+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+inline(c,chapters)+'</td>' for c in row)+'</tr>' for row in rows[1:])+'</tbody></table></div>');continue
        listing=re.match(r'^(\d+\.|-) (.+)',line)
        if listing:
            ordered=listing[1]!='-';tag='ol' if ordered else 'ul';items=[]
            while index < len(lines) and (match:=re.match(r'^(\d+\.|-) (.+)',lines[index])) and (match[1]!='-')==ordered:
                items.append('<li>'+inline(match[2],chapters)+'</li>');index+=1
            output.append('<'+tag+'>'+''.join(items)+'</'+tag+'>');continue
        output.append(inline(line,chapters) if line.startswith('![') else '<p>'+inline(line,chapters)+'</p>');index+=1
    return '<section class="chapter" id="chapter-'+chapter+'">'+''.join(output)+'</section>'



def check_links(page):
    class Links(HTMLParser):
        def __init__(self):
            super().__init__(); self.links=[]; self.ids=[]
        def handle_starttag(self, tag, attributes):
            attrs=dict(attributes)
            self.links.extend(attrs[key] for key in ['href','src'] if key in attrs)
            if 'id' in attrs: self.ids.append(attrs['id'])
    parsed=Links(); parsed.feed(page)
    if len(parsed.ids) != len(set(parsed.ids)): raise ValueError('Duplicate handbook anchors')
    for link in parsed.links:
        if link.startswith('#'):
            if link[1:] not in parsed.ids: raise ValueError('Missing handbook anchor: '+link)
        elif not link.startswith(('http:','https:')) and not (DOCS/link).exists():
            raise ValueError('Missing handbook file: '+link)
    for path in DOCS.glob('*.md'):
        for target in re.findall(r'\[[^\]]*\]\(([^)]+)\)',path.read_text()):
            if not target.startswith(('http:','https:','#')) and not (path.parent/target).exists():
                raise ValueError(f'Missing Markdown target in {path.name}: {target}')


def build():
    if not shutil.which('dot'): raise SystemExit('Install Graphviz to render developer diagrams; the application does not need it.')
    for source in sorted((DOCS/'diagrams').glob('*.dot')):
        subprocess.run(['dot','-Tsvg',str(source),'-o',str(source.with_suffix('.svg'))],check=True,capture_output=True,text=True)
    inventory=inspect_source(); update_tables(inventory)
    (DOCS/'inventory.json').write_text(json.dumps(inventory,indent=2)+'\n')
    sources=[DOCS/'README.md',*sorted(DOCS.glob('[0-9][0-9]-*.md'))]
    chapters={path.name for path in sources}
    navigation=[]; content=[]
    for path in sources:
        text=path.read_text();title=text.splitlines()[0].removeprefix('# ')
        navigation.append('<a href="#chapter-'+path.stem+'">'+html.escape(title)+'</a>')
        content.append(render_markdown(text,path.stem,chapters))
    page='''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta http-equiv="Content-Security-Policy" content="default-src 'none'; img-src 'self' data:; style-src 'self'; connect-src 'none'; base-uri 'none'"><title>Developer handbook · WPS-AI</title><link rel="stylesheet" href="assets/handbook.css"></head><body><a class="skip" href="#content">Skip to handbook</a><header><a href="#chapter-README"><strong>WPS-AI</strong> Developer handbook</a><span>Implementation guide · Runtime 0.3.1 · ABI 2</span></header><div class="shell"><nav aria-label="Handbook chapters">'''+''.join(navigation)+'''<a href="inventory.json">Source and dependency inventory</a><a href="README.md">Markdown entry point</a></nav><main id="content"><div class="intro"><p class="eyebrow">Architecture · components · contracts · capabilities</p><h1>Build and maintain the system.</h1><p>A source-backed guide to authoring, execution, live dashboards, and offline delivery.</p></div>'''+''.join(content)+'''<footer>Diagrams are local SVG files. No model, remote fonts, scripts, or application API is used by this handbook.</footer></main></div></body></html>'''
    check_links(page)
    (DOCS/'index.html').write_text(page)
    print(f'Built {len(sources)} handbook chapters, {len(list((DOCS/"diagrams").glob("*.svg")))} diagrams and {len(inventory["routes"])} endpoint declarations.')


if __name__=='__main__': build()
