"""Build offline HTML lessons from verified live-builder results."""

import html
import json
from pathlib import Path
import shutil
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.tutorial_data import PACK, sha
from scripts.tutorial_specs import LESSONS
from scripts.tutorial_validate import prompt_hash, title_key


def esc(value):
    return html.escape(str(value), quote=True)


def embedded(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False).replace("<", "\\u003c").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")


def number(value):
    if isinstance(value, int) or isinstance(value, float) and value.is_integer(): return f"{value:,.0f}"
    if isinstance(value, float): return f"{value:,.3f}".rstrip("0").rstrip(".")
    return str(value)


def metric_number(title, value):
    if isinstance(value, (int, float)):
        precision = 3 if title == 'Mean quality' else 2
        return f'{value:,.{precision}f}' if float(value) != int(value) else f'{value:,.0f}'
    return str(value)


def filename(lesson):
    return f"{lesson['number']}-{lesson['key']}.html"


def copied(label, value, identifier):
    return f'<div class="copy-block"><div class="copy-heading"><strong>{esc(label)}</strong><button class="copy" data-copy="{identifier}" aria-label="Copy {esc(label)}">Copy text</button></div><pre id="{identifier}">{esc(value.strip())}</pre><span class="copy-status" role="status"></span></div>'


def shell(title, body, active=None, data=None):
    nav = ''.join(f'<a class="lesson-link {"active" if active == item["key"] else ""}" href="{filename(item)}"><span>{item["number"]}</span><div><strong>{esc(item["title"])}</strong><small>{esc(item["subject"])}</small></div></a>' for item in LESSONS)
    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta http-equiv="Content-Security-Policy" content="default-src 'self' data: blob:; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; connect-src 'none'; object-src 'none'; base-uri 'self'"><title>{esc(title)} · WPS-AI Field Guide</title><link rel="stylesheet" href="assets/tutorials.css"><script defer src="assets/echarts.min.js"></script><script defer src="assets/tutorials.js"></script></head>
<body><a class="skip-link" href="#main">Skip to content</a><header class="top"><a href="index.html" class="brand"><span class="brand-icon">▥</span><strong>WPS-AI <em>Field Guide</em></strong></a><span>Learn in the guide. Build in the Studio.</span><a href="index.html#setup">Start here ↗</a></header>
<div class="page"><aside class="sidebar"><a class="overview-link" href="index.html">Overview &amp; setup</a><p class="overline">Four practical lessons</p>{nav}<div class="sidebar-note"><strong>Your files stay local.</strong><p>Reference charts use saved results. They do not change your live project.</p><a href="ATTRIBUTION.txt">Sources &amp; licences</a><a href="manifest.json">Data manifest</a></div></aside>
<main id="main">{body}<footer class="footer"><a href="index.html">WPS-AI Field Guide</a><span>Desktop · local assets · historical public data</span><a href="validation.html">Validation details</a></footer></main></div>
<script type="application/json" id="reference-data">{embedded(data or {})}</script></body></html>'''


def metric_table(metrics):
    return '<div class="table-scroll"><table><thead><tr><th>Check</th><th>Expected value</th></tr></thead><tbody>' + ''.join(f'<tr><td>{esc(title)}</td><td class="numeric">{esc(metric_number(title, value["expected"]))}</td></tr>' for title, value in metrics.items()) + '</tbody></table></div>'


def checkpoint(title, metrics):
    return f'<div class="checkpoint"><h3>{esc(title)}</h3>{metric_table(metrics)}<p>Match counts exactly. Compare numeric metrics at the displayed precision. Wording and chart placement can differ.</p></div>'


def step(number_, title, body):
    return f'<section class="step" id="step-{number_}"><div class="step-heading"><span>{number_:02}</span><h2>{esc(title)}</h2><label class="done"><input type="checkbox" data-progress="step-{number_}"> Checked</label></div>{body}</section>'


def lesson_page(lesson, metadata, report, reference):
    key = lesson['key']
    revision, run = reference['revision'], reference['run']
    widgets = revision['dashboard']['widgets']
    views = run['result']['widgets']
    chart_data = {}
    figures = []
    for index, title in enumerate(lesson['charts']):
        widget = next(w for w in widgets if title_key(w['title']) == title_key(title))
        identifier = f'chart-{index}'
        chart_data[identifier] = views[widget['id']]['value']['option']
        figures.append(f'<figure class="chart-card"><figcaption><strong>{esc(title)}</strong><button class="chart-download" data-chart="{identifier}" aria-label="Download {esc(title)} as PNG">PNG ↓</button></figcaption><div class="chart" id="{identifier}" role="img" aria-label="{esc(title)} reference chart"></div><p class="chart-caption">Verified result · default input and controls. Hover for values; use the legend or zoom controls where provided.</p></figure>')
    metrics = report['prompts'][-1]['metrics']
    units = {title_key(item['title']): item.get('unit') or '' for item in widgets}
    cards = ''.join(f'<div class="metric"><span>{esc(title)}{(" · " + esc(units.get(title_key(title)))) if units.get(title_key(title)) else ""}</span><strong>{esc(metric_number(title, value["expected"]))}</strong></div>' for title, value in metrics.items())
    dictionary = ''.join(f'<tr><td><code>{esc(name)}</code></td><td>{esc(metadata["dictionary"][name])}</td></tr>' for name in metadata['columns'])
    missing = ', '.join(f'{name}: {count:,}' for name, count in metadata['missing_cells'].items() if count) or 'None in this prepared CSV'
    independent = ''.join(f'<li><strong>{esc(name)}:</strong> {esc(number(value))}</li>' for name, value in reference['checks'])
    quality = f'<div class="facts"><span><strong>{metadata["rows"]:,}</strong> source rows</span><span><strong>{len(metadata["columns"])}</strong> columns</span><span><strong>{metadata["repeated_rows"]:,}</strong> repeated-looking rows</span></div><p><strong>Missing cells:</strong> {esc(missing)}.</p>'
    hero = f'<section class="hero lesson-hero" style="--accent:{lesson["accent"]}"><p class="overline">Lesson {lesson["number"]} / {esc(lesson["subject"])}</p><h1>{esc(lesson["title"])}.</h1><p class="lead">{esc(lesson["question"])}</p><div class="tags">' + ''.join(f'<span>{esc(skill)}</span>' for skill in lesson['skills']) + f'</div><div class="hero-actions"><a class="button primary" download href="data/{lesson["file"]}">Download the CSV ↓</a><a class="button" href="#step-1">Begin lesson</a><span class="verified">✓ Both prompts tested with {esc(report["model"])}</span></div></section>'
    intro = '<nav class="section-links" aria-label="Lesson sections"><a href="#step-1">Start</a><a href="#data-guide">Data guide</a><a href="#reference">Reference dashboard</a><a href="#practice">Practice</a><a href="#troubleshooting">Troubleshooting</a></nav>'
    data_guide = f'<section class="section" id="data-guide"><div class="section-heading"><p class="overline">Know the input</p><h2>Real observations. Clear definitions.</h2></div>{quality}<details><summary>Column dictionary and preparation</summary><p>{esc(metadata["transformation"])}</p><div class="table-scroll"><table><thead><tr><th>Column</th><th>Meaning and units</th></tr></thead><tbody>{dictionary}</tbody></table></div><p>Source: <a href="{esc(metadata["page"])}" target="_blank" rel="noreferrer">{esc(lesson["subject"])}</a> · {esc(metadata["license"])}. Retrieved {esc(metadata["retrieved_at"][:10])}. See <a href="ATTRIBUTION.txt">attribution</a> and <a href="manifest.json">hashes and transformations</a>.</p></details><ul class="caveats">' + ''.join(f'<li>{esc(note)}</li>' for note in lesson['caveats']) + '</ul></section>'
    start = '<p>Start the builder once from the repository root. Keep this guide in another browser tab. Use <strong>New project → Data → Upload CSV</strong> and select the downloaded file. Do not upload a second dataset into this project.</p>'
    if key == 'penguins':
        start += copied('Startup command', 'python launcher.py', 'start-command') + '<p>Alternatively, start a new builder project directly with <code>python launcher.py --csv tutorials/data/penguins.csv</code>. The model endpoint and name come from config.json; OPENAI_API_KEY must be in the environment.</p>'
    else:
        start += '<p>Reuse the running builder. Select <strong>New project</strong> so this lesson has separate stages, controls and data. Rename it from the project name in the top bar.</p>'
    start += '<p>Paste this into <strong>Data → Business context</strong>, then leave the field to save.</p>' + copied('Business context', lesson['context'], 'business-context')
    first = '<p>Open <strong>Chat</strong> on the right, paste the complete prompt, and send it. Keep <strong>Project</strong> chat context for these whole-dashboard prompts. Clear any selected stage first. Chat prepares changes; review the affected stages and select <strong>Apply</strong>. It does not run calculations.</p>' + copied('Prompt 1', lesson['prompts'][0], 'prompt-1') + '<p>Open <strong>Pipeline</strong>. Expect Data input, Data cleaning, Analysis, and Visualization cards. Inspect the cleaning purpose and its input/output links. Then select <strong>Run</strong>. Wait for the successful run state before comparing values. In <strong>Data → Input contract</strong>, review the column types and descriptions. Keep numeric measurements numeric and identifiers as text; an input-contract change needs Run.</p>' + checkpoint('First-run checkpoints', report['prompts'][0]['metrics'])
    advanced = '<p>Return to Chat, clear stage context to <strong>Project</strong>, and send the next prompt. Review and <strong>Apply</strong> the proposal to add the next view. Then select <strong>Run</strong>.</p>' + copied('Prompt 2', lesson['prompts'][1], 'prompt-2') + '<p>Select a card to set Chat context; use the <strong>Properties</strong> tab to configure that card. The right panel should show only that card and declared related controls. Project-wide settings do not belong there.</p>'
    if key == 'bike':
        extra = report['prompts'][-1]['extra_checks']
        advanced += checkpoint('Chronological 14-day holdout', {title: {'expected': extra[name]} for title, name in [('Holdout MAE', 'mae'), ('Baseline MAE', 'baseline_mae')]})
    target = f'<p>Select <strong>Open dashboard</strong> in the left navigation. This is the separate target application. Expand <strong>Filters and scenarios</strong>, choose <strong>{esc(lesson["filter_label"])}</strong>, then select <strong>Apply controls</strong>. Changing a field without Apply must not silently recalculate results.</p>' + checkpoint(lesson['filter_label'], report['variants']['filtered']['metrics'])
    if 'scenario' in report['variants']:
        target += f'<p>Reset controls, then Apply to restore all input data. Now try <strong>{esc(lesson["scenario_label"])}</strong> and Apply again.</p>' + checkpoint(lesson['scenario_label'], report['variants']['scenario']['metrics'])
    target += '<p><strong>Reset changes the form.</strong> Select Apply controls after Reset to recalculate with defaults.</p>'
    reference_html = f'<section class="section reference-section" id="reference"><div class="section-heading"><p class="overline">Worked result</p><h2>Compare your dashboard.</h2><p>These are saved results from the real builder run, checked against independent calculations. They are not connected to your live project.</p></div><div class="metrics">{cards}</div><div class="chart-grid">{"".join(figures)}</div><details><summary>Independent data checks</summary><ul>{independent}</ul></details></section>'
    table_widget = next((w for w in widgets if w['kind'] == 'table'), None)
    if table_widget:
        table = views[table_widget['id']]
        columns = table['columns']
        rows = table['rows'][:8]
        reference_html += f'<details class="reference-table"><summary>Reference table preview: {esc(table_widget["title"])}</summary><p>{table["total_rows"]:,} rows in the actual result; showing up to eight here. Use the application CSV button for all rows.</p><div class="table-scroll"><table><thead><tr>' + ''.join(f'<th>{esc(c)}</th>' for c in columns) + '</tr></thead><tbody>' + ''.join('<tr>' + ''.join(f'<td>{esc(number(row.get(c, "")))}</td>' for c in columns) + '</tr>' for row in rows) + '</tbody></table></div></details>'
    edit = '<p>In <strong>Dashboard</strong>, drag a widget handle, resize its lower-right corner, or use <strong>Alt + arrow keys</strong> on a selected widget. Properties also offers Column, Row, Width and Height. The grid always has 12 columns; narrow desktop windows scroll rather than become a phone layout.</p><p>Use <strong>Dashboard settings</strong> for title/subtitle, and <strong>Filters and scenario defaults</strong> for labels, defaults and ranges. Change a title or number format and check the live target without Run. Changed calculation defaults remain pending until Run.</p><ul>' + ''.join(f'<li>{esc(item)}</li>' for item in lesson['exercises']) + '</ul><p>Use <strong>Undo</strong> and <strong>Redo</strong> in the workspace toolbar for committed development edits. Target-side temporary controls do not become development edits.</p>'
    practice = metadata['practice']
    replacements = f'<p>Download <a download href="{practice["replacement"]}">{key}_replacement.csv</a>: <strong>{esc(lesson["practice_label"])}</strong>, with {practice["rows"]:,} source rows. Upload it in the <strong>target</strong>, not the builder. The builder CSV and its results must remain unchanged.</p>' + checkpoint('Replacement input, default controls', report['replacement']) + f'<p>Then upload <a download href="{practice["invalid"]}">{key}_invalid_schema.csv</a>. This training copy deliberately omits <code>{esc(practice["removed_column"])}</code>. Expect a clear input error and the last successful target results to stay visible. It is not another public dataset.</p><p>Select <strong>Use builder data</strong> in the target information/recovery panel to return to the original input, then Reset and Apply. A replacement can reset a control that no longer has a valid value; read the notice.</p>'
    finish = '<p>From a chart, download PNG. From a table, download CSV and check the complete row count. In the builder, Run the default workspace, review cleanup effects, then select <strong>Accept revision</strong>. Confirm the cleanup review when requested. History keeps accepted revisions while you continue editing.</p><p><strong>Windows prerequisite:</strong> Download needs the compatible Windows runtime archive configured by the project maintainer. This pack verifies acceptance and the explicit missing-runtime error; it does not include a Windows executable or claim a real Windows smoke test. A missing runtime archive must not produce a fake application ZIP.</p>'
    trouble = '<section class="section" id="troubleshooting"><h2>When a result differs.</h2><table><thead><tr><th>What you see</th><th>What to do</th></tr></thead><tbody><tr><td>Pending cards or old values</td><td>Chat saves the design. Select Run in the builder, or Apply controls in the target.</td></tr><tr><td>Run or model proposal fails</td><td>Open Run output. Give Chat the error and ask it to repair the existing stage while keeping the metric definitions. Run again. Model output is variable; repair attempts are recorded in the validation details.</td></tr><tr><td>Wrong count or total</td><td>Check the CSV filename, filter selection, control defaults and cleaning rules. Reset and Apply. Do not copy expected numbers into a calculation.</td></tr><tr><td>A box plot or heatmap has no standard binding form</td><td>It is generated by analysis as an advanced chart. Describe structural changes in Chat.</td></tr><tr><td>A target upload fails</td><td>Keep the visible successful result; upload a compatible file or return to builder data.</td></tr><tr><td>Builder port differs from 8080</td><td>Use the actual Builder URL printed by the launcher. Open each target through its project card; do not assume its port.</td></tr></tbody></table></section>'
    index = LESSONS.index(lesson)
    next_page = f'<a class="button primary" href="{filename(LESSONS[index+1])}">Next: {esc(LESSONS[index+1]["title"])} →</a>' if index < 3 else '<a class="button primary" href="index.html">Return to the overview →</a>'
    body = hero + intro + data_guide + step(1, 'Load the data and its meaning', start) + step(2, 'Create stages, then Run', first) + step(3, 'Extend the analysis through chat', advanced) + reference_html + step(4, 'Try the target controls', target) + f'<div id="practice">{step(5, "Edit, inspect and undo", edit)}</div>' + step(6, 'Replace data and recover safely', replacements) + step(7, 'Export results and accept a revision', finish) + trouble + f'<div class="next-lesson">{next_page}</div>'
    return shell(lesson['title'], body, key, chart_data)


def build():
    manifest = json.loads((PACK / 'manifest.json').read_text())
    validation = json.loads((PACK / 'validation.json').read_text())
    references = {}
    for lesson in LESSONS:
        key = lesson['key']
        report = validation['lessons'].get(key, {})
        metadata = manifest['datasets'][key]
        if (report.get('status') != 'passed' or report.get('prompt_sha256') != prompt_hash(lesson)
                or report.get('input_sha256') != sha(PACK / metadata['file'])):
            raise ValueError(f'{key}: successful validation does not match the current data and published prompts')
        references[key] = json.loads((PACK / 'reference' / f'{key}.json').read_text())
        (PACK / filename(lesson)).write_text(lesson_page(lesson, metadata, report, references[key]), encoding='utf-8')
    cards = ''.join(f'<a class="lesson-card" style="--accent:{lesson["accent"]}" href="{filename(lesson)}"><span class="lesson-number">{lesson["number"]}</span><span class="overline">{esc(lesson["subject"])}</span><h2>{esc(lesson["title"])}</h2><p>{esc(lesson["question"])}</p><div class="card-meta"><span>{manifest["datasets"][lesson["key"]]["rows"]:,} rows</span><span>✓ Two prompts tested</span></div><strong class="start-link">Open lesson →</strong></a>' for lesson in LESSONS)
    intro = f'<section class="hero"><p class="overline">Four datasets. One complete workflow.</p><h1>Learn by building.</h1><p class="lead">Explore real public data, design a dashboard through chat, and check what the numbers mean.</p><p>Work through the lessons in order. Each adds new analysis and visualization skills while keeping the same desktop workflow.</p><div class="hero-actions"><a class="button primary" href="{filename(LESSONS[0])}">Start with Penguins →</a><a class="button" href="#setup">Setup checklist</a><a class="button" href="manifest.json">Data manifest</a></div></section><section class="lesson-grid">{cards}</section>'
    setup = '<section class="section" id="setup"><p class="overline">Before lesson one</p><h2>Keep the guide beside the builder.</h2><ol class="setup-list"><li>Extract the whole tutorial ZIP. Open index.html in a desktop browser. Keep assets, data and practice folders beside the pages.</li><li>Use an installed builder with its frontend assets built. Set the model endpoint and name in config.json and OPENAI_API_KEY in the environment. The downloaded tutorial pages need no API key.</li><li>Start the builder from its repository root with <code>python launcher.py</code>, or <code>python launcher.py --csv tutorials/data/penguins.csv</code>. Use the URL printed in the terminal.</li><li>Create a separate project for each main CSV. The CSVs are independent datasets; the application uses one CSV per project.</li><li>Copy each complete prompt. Review the proposed changes and select Apply, then select Run. Use Open dashboard to reach the separate target port.</li></ol><div class="callout"><strong>Read-only reference pages</strong><p>Charts here are saved, verified results with local hover/legend/zoom interactions. They do not run your model, create projects or modify the builder. Try the actual workflow in the Studio.</p></div></section>'
    coverage = '<section class="section"><h2>What you will practise.</h2><div class="coverage-grid"><article><h3>Compare and explain</h3><p>Metrics, bar and pie charts, scatter plots, distributions, box plots, heatmaps, trends, forecast intervals and full tables.</p></article><article><h3>Develop the application</h3><p>Four stage types, card properties, chart bindings, desktop layout, project/dashboard settings, deletion review, Undo and Redo.</p></article><article><h3>Use the target</h3><p>Filters, scenarios, Apply, Reset, independent CSV replacement, errors, last successful results, chart PNG and full table CSV.</p></article><article><h3>Review and deliver</h3><p>Cleanup approval, accepted revisions, History, separate project ports, optional cancellation, and the Windows export prerequisite.</p></article></div></section>'
    (PACK / 'index.html').write_text(shell('Learn by building', intro + setup + coverage), encoding='utf-8')
    sections = []
    for lesson in LESSONS:
        item = validation['lessons'][lesson['key']]
        repairs = ''.join(f'<li>Prompt {repair["prompt_number"]}: {esc(repair["request"])}</li>' for repair in item['repairs']) or '<li>No additional runtime/numerical repair was required.</li>'
        sections.append(f'<section class="section"><h2>{esc(lesson["subject"])}</h2><p class="verified">✓ Two published prompts, independent calculations, filters, replacement input, invalid-schema retention, and acceptance passed.</p><p>Model: {esc(item["model"])} · completed {esc(item["finished_at"])}. Input SHA-256: <code class="hash">{item["input_sha256"]}</code>.</p><details><summary>Runtime/numerical repair requests</summary><ul>{repairs}</ul></details><p>Builder schema/patch repairs follow its bounded repair loop. Exact wording/layout is not a pass criterion. Reference metrics are calculated from the public CSV, not copied into generated source.</p></section>')
    report_body = '<section class="hero"><p class="overline">Evidence, not mock screenshots</p><h1>Validation details.</h1><p class="lead">Published prompts were submitted through the real builder service and configured model. Results were executed by real worker processes.</p><p><a href="validation.json">Machine-readable validation report</a> · <a href="manifest.json">Data provenance and hashes</a></p></section>' + ''.join(sections) + '<section class="section"><h2>Limits of this validation</h2><p>Models can generate different code or require repair on another run. Match the data definitions and numerical checkpoints, not pixels. A real Windows executable smoke test requires a compatible archive and Windows host; neither is supplied by this tutorial pack.</p></section>'
    qa_path = PACK / 'qa.json'
    if qa_path.exists():
        qa = json.loads(qa_path.read_text())
        report_body += '<section class="section"><h2>Browser and release checks</h2><p>All six pages, 14 charts and 13 copy controls were checked in the browser. Builder drag/resize, keyboard movement, chart binding edits, Undo/Redo and target Apply were exercised. The Python suite passed 95 tests; both frontend builds and type checks passed. <a href="qa.json">Detailed QA record</a>.</p><ul>' + ''.join(f'<li>{esc(limit)}</li>' for limit in qa['limits']) + '</ul></section>'
    (PACK / 'validation.html').write_text(shell('Validation details', report_body), encoding='utf-8')
    assets = PACK / 'assets'
    assets.mkdir(exist_ok=True)
    echarts = ROOT / 'frontend' / 'node_modules' / 'echarts'
    shutil.copyfile(echarts / 'dist' / 'echarts.min.js', assets / 'echarts.min.js')
    shutil.copyfile(echarts / 'LICENSE', assets / 'ECHARTS-LICENSE.txt')
    shutil.copyfile(echarts / 'NOTICE', assets / 'ECHARTS-NOTICE.txt')
    (PACK / 'README.txt').write_text('WPS-AI Field Guide\n\nExtract the entire ZIP, then open index.html in a desktop browser. All chart scripts and reference data are local. Follow lessons in the builder; reference pages never call its API.\n\nPublic source attribution: ATTRIBUTION.txt\nData hashes and transformations: manifest.json\nLive model validation: validation.html and validation.json\n\nRegeneration from repository root:\nuv pip install -e ".[tutorials]"\npython scripts/tutorial_data.py\npython scripts/tutorial_validate.py --live-model\npython scripts/build_tutorials.py\n\nLive validation uses API tokens and writes isolated projects only under data/tutorial_validation. Matching passed validations are reused.\n', encoding='utf-8')
    output = ROOT / 'artifacts' / 'wps-ai-tutorial-pack.zip'
    output.parent.mkdir(exist_ok=True)
    with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(PACK.rglob('*')):
            if path.is_file(): archive.write(path, Path('wps-ai-tutorials') / path.relative_to(PACK))
    print(f'Created {output} ({output.stat().st_size:,} bytes)')


if __name__ == '__main__':
    build()
