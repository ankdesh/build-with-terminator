#!/usr/bin/env python3
"""Ten A3 pages: actual inputs, verified reference fixes and saved attempts.

No model, checker or repair is run. Read original campaign evidence only.
Run with the project Python and bundled PDF packages on PYTHONPATH.
"""
from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path
from klayout_drc.handoff.report_paths import ROOT, FONTS, resolve_record

import klayout.db as db
from PIL import Image, ImageDraw
from pypdf import PdfReader
from reportlab.lib.colors import HexColor, white
from reportlab.lib.pagesizes import A3, landscape
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

from build_c2c3_snapshot_atlas import (BASE, BORDER, FONTS, INK, LAYERS, LEVELS,
    MUTED, ROOT, font, native_snapshot, permitted_regions, sha)
from klayout_drc.edit_policy import direct_region, validate_edit_policy
from klayout_drc.parser import DRCParser

DEST = ROOT/'docs/reports/c2_c3_selected10_review'
PDF = ROOT/'output/pdf/c2_c3_selected10_repair_review.pdf'
SELECTION = [
    ('l1_g0_c0', 'A narrow M1 waist',
     'The blue M1 route has a 12 nm waist between wider ends. M1.W.1 marks the narrow section.',
     'Restore the waist from 12 to 24 nm. Keep both end anchors fixed. The reference adds 600 nm2 of M1.'),
    ('l1_g1_c2', 'Too little M2 enclosure around V1',
     'The V1 via has only 2 nm of M2 extension on the checked opposite sides. The enclosure check requires more metal around it.',
     'Extend M2 on both checked sides: enclosure grows from 2 to 7 nm. The via stays in place. The reference adds 180 nm2 of M2.'),
    ('l2_g0_c1', 'A small gap and a narrow M3 route',
     'Two M1 shapes have a 12 nm gap. A separate M3 shape is also only 12 nm wide. Both defects must be repaired in the correct instance.',
     'Move one M1 shape by 8 nm to give a 20 nm gap. Widen M3 from 12 to 24 nm. Preserve the repeated masters and all instance transforms.'),
    ('l2_g1_c1', 'Small M1 area inside rotated hierarchy',
     'The M1 pad has area 288 nm2 and a 12 nm short dimension. M1 area and width fail. A nearby M3 route also fails width.',
     'Grow the M1 pad to 576 nm2 with an 18 nm short dimension. Widen M3 from 12 to 24 nm. Apply the change to the permitted route instance.'),
    ('l3_g0_c1', 'A narrow section on real GCD routing',
     'A controlled 4 nm cut leaves a locally narrow M3 section in the routed GCD block. Nearby layers are protected obstacles.',
     'Restore the removed 4 x 20 nm M3 strip, adding 80 nm2. This returns the local route to its legal reference geometry.'),
    ('l3_g1_c2', 'A V2 cut is too narrow',
     'A V2 via in the second GCD source is reduced from 18 to 14 nm in one direction. V2.W.1 identifies the narrow cut.',
     'Restore a 4 x 18 nm V2 strip, adding 72 nm2. The via returns to an 18 nm width in the affected direction. Preserve the surrounding metal.'),
    ('l4_g0_c0', 'A local M2 notch in a UART block',
     'The amber M2 route has a controlled notch that leaves a 14 nm local width. The full UART block contains many unrelated routes.',
     'Restore the removed 4 x 20 nm M2 strip, adding 80 nm2. The local width returns to 18 nm. Keep the route anchor and all unrelated geometry fixed.'),
    ('l4_g1_c2', 'A narrow via in a dense UART neighborhood',
     'The V2 via is reduced from 18 to 14 nm in one direction. Multiple nearby layers make indiscriminate expansion unsuitable.',
     'Restore the 4 x 18 nm V2 strip, adding 72 nm2. Only the owned via geometry changes; the surrounding signal, power and clock structures stay fixed.'),
    ('l5_g0_c0', 'One M2 landing, two rule failures',
     'The same local M2 landing fails width and V2 enclosure. A repair must clear both checks without violating the nearby routing constraints.',
     'Restore a 4 x 17 nm M2 strip, adding 68 nm2. This clears both M2.W.1 and V2.M2.EN.1 while leaving the V2 cut and surrounding routes in place.'),
    ('l5_g1_c1', 'Coupled repair in the second congested source',
     'A controlled M2 landing defect triggers both width and V2 enclosure checks in the second congestion-qualified UART source.',
     'Restore the 4 x 17 nm M2 strip, adding 68 nm2. Both target categories clear together. The saved agent attempt fails before it writes an output.'),
]


def load(path):
    layout = db.Layout(); layout.read(str(path)); return layout


def counts(path):
    return {k: n for k, n in DRCParser().parse(path).rule_summary.items() if n}


def add_delta_outline(image_path, before, after, bounds):
    """Outline the actual reference delta in original TOP coordinates."""
    picture = Image.open(image_path).convert('RGB'); draw = ImageDraw.Draw(picture)
    left, bottom, right, top = bounds
    project = lambda p: ((p.x*before.dbu-left)/(right-left)*1080,
                         70+(top-p.y*before.dbu)/(top-bottom)*640)
    for layer in ([19, 0], [20, 0], [21, 0], [25, 0], [30, 0]):
        a, b = before.find_layer(*layer), after.find_layer(*layer)
        x = db.Region(before.top_cell().begin_shapes_rec(a)) if a is not None else db.Region()
        y = db.Region(after.top_cell().begin_shapes_rec(b)) if b is not None else db.Region()
        for poly in (x ^ y).each():
            rings = [list(poly.each_point_hull())]+[list(poly.each_point_hole(i)) for i in range(poly.holes())]
            for ring in rings:
                points = [project(p) for p in ring]
                draw.line(points+points[:1], fill='#00A1AF', width=4)
    picture.save(image_path)


def no_output(path):
    image = Image.new('RGB', (1080, 750), 'white'); draw = ImageDraw.Draw(image)
    draw.text((16, 5), 'Saved agent attempt', fill=INK, font=font(28, True))
    draw.text((16, 40), 'NO OUTPUT / Python execution failed', fill='#A42C3D', font=font(21))
    draw.line((16, 67, 1064, 67), fill=BORDER, width=2)
    draw.rounded_rectangle((90, 170, 990, 580), radius=16, fill='#FBECEF', outline='#E6BDCA', width=2)
    for i, line in enumerate(['No output GDS was saved.', 'The script failed before export.',
                               'No after-DRC result is available.', 'This panel is not a repaired layout.']):
        draw.text((125, 225+i*70), line, fill='#8D3041', font=font(29, i==0))
    image.save(path)


def prepare():
    DEST.mkdir(parents=True, exist_ok=True)
    manifest_path = BASE/'manifest.json'; manifest = json.loads(manifest_path.read_text())
    cases = {c['case_id']: c for c in manifest['cases']}
    atlas_path = ROOT/'docs/reports/c2_c3_snapshots/image_manifest.json'
    atlas = {c['case_id']: c for c in json.loads(atlas_path.read_text())['cases']}
    summaries = {mode: json.loads((ROOT/f'reports/runs/c2c3_v1_{mode}/summary.json').read_text()) for mode in ('agent', 'heuristic')}
    assert all(s['repair']['passed']==0 for s in summaries.values())
    runs = {mode: {r['case_id']: r for r in s['results']} for mode, s in summaries.items()}
    analysis_path = ROOT/'docs/reports/c2_c3_benchmark/failure_analysis.csv'
    with analysis_path.open() as handle:
        analysis = {(r['mode'], r['case_id']): r for r in csv.DictReader(handle)}
    verified = {str(p.relative_to(ROOT)): sha(p) for p in (manifest_path, atlas_path, analysis_path)}
    records = []
    for number, (cid, title, issue, fix) in enumerate(SELECTION, 1):
        c = cases[cid]; e = c['evidence']; source, reference = BASE/c['gds'], BASE/e['reference_gds']
        for p, expected in [(source, c['gds_sha256']), (reference, e['reference_sha256']),
                            (BASE/e['input_report'], e['input_report_sha256']),
                            (BASE/e['reference_report'], e['reference_report_sha256'])]:
            assert sha(p)==expected; verified[str(p.relative_to(ROOT))]=expected
        before, after = load(source), load(reference)
        assert not validate_edit_policy(before, after, c['edit_policy'])
        assert not counts(BASE/e['reference_report'])
        allowed = permitted_regions(before, c['edit_policy'])
        bounds, window = atlas[cid]['images']['detail']['camera_um'], atlas[cid]['inspection_window_um']
        images = {role: atlas[cid]['images'][role]['image'] for role in ('full', 'detail')}
        for relative in images.values():
            verified[relative] = sha(ROOT/relative)
        p = DEST/f'{number:02}_{cid}_reference.png'
        native_snapshot(reference, BASE/e['reference_report'], bounds, p, 'Verified reference fix',
                        '0 scored markers / cyan outlines = changed geometry', 'reference', window, allowed)
        add_delta_outline(p, before, after, bounds)
        images['reference'] = str(p.relative_to(ROOT))
        changes = []
        for name in c['edit_policy']['editable_cells']:
            for layer in c['edit_policy']['context_layers']:
                x, y = direct_region(before, before.cell(name), layer), direct_region(after, after.cell(name), layer)
                added, removed = (y-x).area()*(before.dbu*1000)**2, (x-y).area()*(before.dbu*1000)**2
                if added or removed:
                    changes.append({'layer': layer, 'added_nm2': added, 'removed_nm2': removed})
        methods = {}
        for mode in ('agent', 'heuristic'):
            row = runs[mode][cid]; run = resolve_record(row['run_dir']); saved = json.loads((run/'run_manifest.json').read_text())
            for name, expected in saved['artifact_hashes'].items():
                path = run/name
                assert sha(path)==expected, path
                verified[str(path.relative_to(ROOT))] = expected
            assert sha(run/'input.gds')==c['gds_sha256']
            summary_path = ROOT/f'reports/runs/c2c3_v1_{mode}/summary.json'
            verified[str(summary_path.relative_to(ROOT))] = sha(summary_path)
            diagnostic = analysis[(mode, cid)]['diagnostic']
            target = DEST/f'{number:02}_{cid}_{mode}.png'
            candidate, report = run/'patched.gds', run/'after.lyrdb'
            if candidate.exists():
                if report.exists():
                    actual = counts(report)
                    assert sum(actual.values())==row['final_total']
                    label = f'UNRESOLVED / {sum(actual.values())} scored marker(s) remain'
                else:
                    actual = None; label = 'REJECTED / after-DRC not run'
                native_snapshot(candidate, report if report.exists() else None, bounds, target,
                                f'Saved {mode} attempt', label, 'attempt', window, allowed)
            else:
                actual = None; label = 'NO OUTPUT / script failed'; no_output(target)
            if row['verdict']=='unresolved':
                note = 'The saved output is unchanged. The input defect remains. No repair credit.'
                assert row.get('unchanged') is True
            elif row['failure_stage']=='edit_policy':
                note = 'Rejected: protected cell contents changed. After-DRC was not run; no marker count is claimed.'
            else:
                note = 'The Python script failed before export. No output GDS or after-DRC result exists.'
            methods[mode] = {'verdict': row['verdict'], 'passed': row['passed'], 'failure_stage': row['failure_stage'],
                             'label': label, 'note': note, 'diagnostic': diagnostic,
                             'initial_total': row['initial_total'], 'final_total': row['final_total'],
                             'after_markers': actual, 'output_exists': candidate.exists(),
                             'area_added_um2': analysis[(mode, cid)]['area_added_um2'],
                             'area_removed_um2': analysis[(mode, cid)]['area_removed_um2'],
                             'run_dir': str(run.relative_to(ROOT))}
            images[mode] = str(target.relative_to(ROOT))
        records.append({'number': number, 'case_id': cid, 'title': title, 'issue': issue, 'fix': fix,
                        'level': c['level'], 'source_group': c['source_group'], 'metrics': c['metrics'],
                        'input_markers': counts(BASE/e['input_report']), 'reference_markers': {},
                        'reference_policy_pass': True, 'reference_changes': changes,
                        'methods': methods, 'images': images, 'camera_um': bounds})
        print(f'Prepared {number}/10 {cid}', flush=True)
    assert Counter(r['level'] for r in records)=={i:2 for i in range(1,6)}
    return records, verified


def build(records):
    for name, filename in [('Review', 'DejaVuSans.ttf'), ('ReviewBold', 'DejaVuSans-Bold.ttf')]:
        pdfmetrics.registerFont(TTFont(name, str(FONTS/filename)))
    width, height = landscape(A3)
    pdf = canvas.Canvas(str(PDF), pagesize=(width, height), pageCompression=1, invariant=1)
    pdf.setTitle('C2+C3 - ten cases explained / reference fixes and actual attempts')
    pdf.setAuthor('KLayout DRC project')
    margin, gap = 24, 12
    cw = (width-2*margin-2*gap)/3
    ch, imagew = 324, cw-32
    imageh = imagew*750/1080

    def text(value, x, y, size=9, bold=False, color=INK):
        pdf.setFillColor(HexColor(color)); pdf.setFont('ReviewBold' if bold else 'Review', size)
        pdf.drawString(x, y, value)

    def paragraph(value, x, y, available, size=9.3, leading=13, bold=False, color=MUTED):
        line = ''; start = y
        for word in value.split():
            candidate = f'{line} {word}'.strip()
            if pdfmetrics.stringWidth(candidate, 'ReviewBold' if bold else 'Review', size)>available and line:
                text(line, x, y, size, bold, color); y -= leading; line = word
            else:
                line = candidate
        if line:
            text(line, x, y, size, bold, color); y -= leading
        assert y < start
        return y

    def card(col, top, label, record, role, note, accent=INK):
        x, y = margin+col*(cw+gap), top-ch
        pdf.setFillColor(white); pdf.setStrokeColor(HexColor(BORDER))
        pdf.roundRect(x, y, cw, ch, 6, fill=1, stroke=1)
        text(label, x+10, top-19, 11, True, accent)
        pdf.drawImage(str(ROOT/record['images'][role]), x+(cw-imagew)/2, top-29-imageh, width=imagew, height=imageh)
        bottom = paragraph(note, x+10, top-39-imageh, cw-20, 9.1, 12, color=accent)
        assert bottom > y+5, (record['case_id'], role, bottom, y)

    for record in records:
        level, number = record['level'], record['number']
        pdf.setFillColor(HexColor('#F3F6F8')); pdf.rect(0, 0, width, height, fill=1, stroke=0)
        pdf.setFillColor(HexColor('#167E81')); pdf.rect(0, height-5, width, 5, fill=1, stroke=0)
        text(f'{number:02}  {record["title"]}', margin, height-33, 21, True)
        pdf.setFont('Review', 10); pdf.setFillColor(HexColor(MUTED))
        pdf.drawRightString(width-margin, height-30, f'L{level} / {number} OF 10')
        text(f'{record["case_id"]} / {LEVELS[level]} / two selected repair cases per level', margin, height-51, 10, color=MUTED)
        text('The reference fix is verified. It was not produced by the agent or heuristic. Neither method has an accepted repair in this campaign.',
             margin, height-69, 9.2, True, '#8B5811')
        x=margin
        for name,color,_ in LAYERS.values():
            pdf.setFillColor(HexColor(f'#{color:06x}')); pdf.rect(x,height-87,7,7,fill=1,stroke=0)
            text(name,x+11,height-87,8,color=MUTED); x+=45
        text('Red: DRC marker | Teal: permitted region | Cyan in reference: changed geometry | Matched detail camera / DBU 0.25 nm',
             x+5,height-87,8,color=MUTED)
        top = height-103
        m = record['metrics']
        overview = f'{m["instance_count"]:,} instances; hierarchy depth {m["hierarchy_depth"]}. Cyan locates the inspection window. The full GDS is retained.'
        markertext = ', '.join(f'{k}: {v}' for k,v in record['input_markers'].items())
        card(0,top,'1. Locate the test area',record,'full',overview)
        card(1,top,'2. Input: find the defect',record,'detail',f'Saved scored markers: {markertext}. Read the red marks against the layer colors.')
        card(2,top,'3. After the verified reference fix',record,'reference',
             f'Markers: {sum(record["input_markers"].values())} -> 0. Edit policy: PASS. Cyan outlines locate the actual geometry change.', '#176145')
        bottomtop = top-ch-gap
        card(0,bottomtop,'4. Actual agent attempt',record,'agent',record['methods']['agent']['note'],'#A42C3D')
        card(1,bottomtop,'5. Actual heuristic attempt',record,'heuristic',record['methods']['heuristic']['note'],'#A42C3D')
        x, y = margin+2*(cw+gap), bottomtop-ch
        pdf.setFillColor(white); pdf.setStrokeColor(HexColor(BORDER)); pdf.roundRect(x,y,cw,ch,6,fill=1,stroke=1)
        yy = bottomtop-20
        text('6. What to learn from this case',x+12,yy,11,True); yy-=23
        text('DRC issue',x+12,yy,10,True); yy-=15
        yy=paragraph(record['issue'],x+12,yy,cw-24); yy-=9
        text('What the reference fix changes',x+12,yy,10,True,color='#176145'); yy-=15
        yy=paragraph(record['fix'],x+12,yy,cw-24); yy-=9
        text('Why the attempts receive no repair credit',x+12,yy,10,True,color='#A42C3D'); yy-=15
        details=[]
        for mode in ('agent','heuristic'):
            method=record['methods'][mode]
            label= 'Defect remains.' if method['verdict']=='unresolved' else 'Protected-cell edit.' if method['failure_stage']=='edit_policy' else 'Script failure.'
            if method['failure_stage']=='python_execution' and method['diagnostic']:
                label += ' '+method['diagnostic']
            details.append(f'{mode.capitalize()}: {label}')
        yy=paragraph(' '.join(details),x+12,yy,cw-24,8.9,12)
        assert yy>y+8, (record['case_id'], 'explanation overflow',yy,y)
        text('Read left to right across the top row, then compare the saved attempts below. Rejected outputs can look unchanged in this local window.',
             margin,38,8.3,color=MUTED)
        text('Primary scope: qualified scored profile. Public-deck audits are separate. Electrical connectivity and timing are unverified. No new model calls.',
             margin,24,8.1,color=MUTED)
        pdf.bookmarkPage(record['case_id']); pdf.addOutlineEntry(f'{number:02} {record["case_id"]} - {record["title"]}',record['case_id'])
        pdf.showPage()
    pdf.save()


def main():
    records, verified = prepare(); build(records)
    reader=PdfReader(PDF); assert len(reader.pages)==10
    for page,record in zip(reader.pages,records):
        text=page.extract_text()
        assert record['case_id'] in text and 'reference fix' in text
        assert abs(float(page.mediabox.width)-landscape(A3)[0])<.01
        assert abs(float(page.mediabox.height)-landscape(A3)[1])<.01
    for relative,expected in verified.items():
        assert sha(ROOT/relative)==expected, f'Source evidence changed: {relative}'
    receipt={'case_count':10,'pages':10,'page_format':'A3 landscape','selection':'Two repair cases per level; one from each source group; selected for rule and failure diversity, not success rate estimation.',
             'reference_fixes':10,'accepted_agent_repairs':0,'accepted_heuristic_repairs':0,
             'reference_policy_checks_pass':True,'reference_saved_scored_reports_have_zero_markers':True,
             'new_model_requests':0,'new_repairs':0,'new_checker_runs':0,
             'pdf':str(PDF.relative_to(ROOT)),'pdf_sha256':sha(PDF),'generator_sha256':sha(__file__),
             'verified_sources':verified,'cases':records,
             'images':{relative:sha(ROOT/relative) for r in records for relative in r['images'].values()}}
    (DEST/'image_manifest.json').write_text(json.dumps(receipt,indent=2)+'\n')
    lines=['# Ten selected C2+C3 repair cases','',
           '[Open the 10-page A3 PDF](../../../output/pdf/c2_c3_selected10_repair_review.pdf)','',
           'One case per page. Each page shows the full layout, input defect, verified reference fix, actual agent attempt and actual heuristic attempt.',
           'Reference fixes are evaluator evidence. They are not agent or heuristic successes. Both methods scored 0/30 accepted repairs in the full campaign.',
           'Two repair cases are selected per level, one from each source group. This is an explanatory selection, not a performance sample.','',
           '| Case | Level | Scored input markers | Agent | Heuristic | Reference |','|---|---|---|---|---|---|']
    for r in records:
        lines.append(f'| {r["case_id"]} | L{r["level"]} | {r["input_markers"]} | {r["methods"]["agent"]["verdict"]} | {r["methods"]["heuristic"]["verdict"]} | 0 markers; policy pass |')
    lines += ['', 'Red marks are saved scored checker markers. Teal outlines show spatial edit bounds; cell and layer restrictions also apply.',
              'Cyan outlines on reference views show the actual geometry delta, including additions and removals.',
              'Input, reference and candidate details use the same physical camera and scale.',
              'A rejected output has no after-DRC result; missing red lines do not mean that it passes.',
              'The full public deck is a separate audit. Electrical connectivity and timing are not verified.',
              'No input, reference, campaign artifact, prompt or result was changed. No new checker, model or repair was run.','']
    (DEST/'README.md').write_text('\n'.join(lines))
    print(f'Created {PDF}: 10 pages; sources unchanged.',flush=True)


if __name__=='__main__':
    main()
