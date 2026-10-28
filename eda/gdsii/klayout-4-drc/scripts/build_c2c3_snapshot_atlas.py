#!/usr/bin/env python3
"""Capture all 50 full GDS inputs with native KLayout; build A3 review PDFs.

Use the project Python with bundled Pillow, reportlab and pypdf on PYTHONPATH.
No checker, repair, or model call runs. Frozen source evidence is read only.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
from collections import Counter
from pathlib import Path
from klayout_drc.handoff.report_paths import ROOT, FONTS, resolve_record

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import klayout.db as db
import klayout.lay as lay
from PIL import Image, ImageDraw
from pypdf import PdfReader, PdfWriter
from reportlab.lib.colors import HexColor, white
from reportlab.lib.pagesizes import A3, landscape
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

from capture_c1_examples import FONTS, font, overlays
from klayout_drc.parser import DRCParser

BASE = ROOT / 'test_data/benchmark_c2c3'
IMAGES = ROOT / 'docs/reports/c2_c3_snapshots'
OUTPUT = ROOT / 'output/pdf/c2_c3_gds_snapshot_atlas.pdf'
INK, MUTED, BORDER = '#18364A', '#506779', '#D7E1E7'
LAYERS = {19: ('M1', 0x2476B3, 3), 20: ('M2', 0xBB780D, 5),
          21: ('V1', 0x8654AA, 7), 25: ('V2', 0xCE548B, 7),
          30: ('M3', 0x37824B, 9)}
LEVELS = {1: 'Cell neighborhood', 2: 'Repeated hierarchy', 3: 'Routed GCD',
          4: 'Routed UART', 5: 'Congested UART / coupled rules'}
KINDS = {'repair': ('REPAIR', '#8B5811', '#FFF2D8'),
         'clean_control': ('CLEAN CONTROL', '#176145', '#E8F3ED'),
         'no_edit': ('READ ONLY', '#A42C3D', '#FBECEF')}
W, H = 1080, 640


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def union(boxes):
    return [min(b[0] for b in boxes), min(b[1] for b in boxes),
            max(b[2] for b in boxes), max(b[3] for b in boxes)]


def camera(bounds, padding=.08):
    l, b, r, t = bounds
    cx, cy = (l+r)/2, (b+t)/2
    width, height = max(r-l, .001), max(t-b, .001)
    width = max(width, height*W/H)*(1+2*padding)
    height = width*H/W
    return [cx-width/2, cy-height/2, cx+width/2, cy+height/2]


def permitted_regions(layout, policy):
    """Find editable placements through the native recursive iterator."""
    regions, seen = [], set()
    for layer in policy['context_layers']:
        index = layout.find_layer(*layer)
        if index is None:
            continue
        it = layout.top_cell().begin_shapes_rec(index)
        while not it.at_end():
            name = it.cell().name
            rule = policy['editable_cells'].get(name)
            key = (name, str(it.itrans()))
            if rule and key not in seen:
                seen.add(key)
                box = db.Box(*rule['box_dbu']).transformed(it.itrans())
                regions.append([v*layout.dbu for v in (box.left, box.bottom, box.right, box.top)])
            it.next()
    assert len(regions) == len(policy['editable_cells'])
    return regions


def native_snapshot(path, report, bounds, target, title, subtitle, role,
                    window, allowed):
    view = lay.LayoutView()
    for key, value in [('background-color', '#ffffff'), ('foreground-color', INK),
                       ('grid-visible', 'false'), ('text-visible', 'false')]:
        view.set_config(key, value)
    view.commit_config()
    view.load_layout(str(path), False)
    view.max_hier()
    view.add_missing_layers()
    iterator = view.begin_layers()
    while not iterator.at_end():
        props = iterator.current()
        _, color, pattern = LAYERS.get(props.source_layer, ('Cell', 0xB8C2C8, 3))
        props.visible = role == 'full' or props.source_layer in LAYERS
        props.fill_color = props.frame_color = color
        props.dither_pattern = pattern
        props.width = 1 if role == 'full' else 2
        view.set_layer_properties(iterator, props)
        iterator.next()
    markers = overlays(view, report) if role != 'full' else []
    for box in allowed if role != 'full' else []:
        marker = lay.Marker(view)
        marker.color = marker.frame_color = 0x168D81
        marker.line_width = 2
        marker.dither_pattern = 1  # Hollow; retain the route beneath it.
        marker.set_box(db.DBox(*box))
        markers.append(marker)
    actual = db.DBox(*bounds)
    view.resize(W, H)
    view.zoom_box(actual)
    raw = target.with_suffix('.raw.png')
    view.save_image_with_options(str(raw), W, H, 1, 1, 1, actual, False)
    image = Image.new('RGB', (W, H+110), 'white')
    with Image.open(raw) as source:
        image.paste(source.convert('RGB'), (0, 70))
    raw.unlink()
    view.destroy()
    draw = ImageDraw.Draw(image)
    draw.text((16, 5), title, fill=INK, font=font(28, True))
    draw.text((16, 40), subtitle, fill=MUTED, font=font(21))
    draw.line((16, 67, W-16, 67), fill=BORDER, width=2)
    if role == 'full':
        l, b, r, t = window
        px = lambda x: (x-actual.left)/actual.width()*W
        py = lambda y: 70+(actual.top-y)/actual.height()*H
        cx, cy = px((l+r)/2), py((b+t)/2)
        rw, rh = max(px(r)-px(l), 8), max(py(b)-py(t), 8)
        draw.rectangle((cx-rw/2, cy-rh/2, cx+rw/2, cy+rh/2), outline='#00A1AF', width=4)
        draw.line((cx-14, cy, cx+14, cy), fill='#00A1AF', width=3)
        draw.line((cx, cy-14, cx, cy+14), fill='#00A1AF', width=3)
    # Adaptive physical scale bar. The image uses the exact native camera box.
    limit = actual.width()*.17
    exp = math.floor(math.log10(limit))
    scale = max(v*10**e for e in range(exp-1, exp+1) for v in (1, 2, 5) if v*10**e <= limit)
    label = f'{scale*1000:g} nm' if scale < 1 else f'{scale:g} um'
    length = scale/actual.width()*W
    x, y = W-215, H+54
    draw.rectangle((x-10, y-38, W-12, y+9), fill='white')
    draw.text((x, y-36), label, fill=INK, font=font(21))
    draw.line((x, y, x+length, y), fill=INK, width=4)
    for tick in (x, x+length):
        draw.line((tick, y-5, tick, y+5), fill=INK, width=3)
    draw.text((16, H+80), f'Window: {actual.width():.4g} x {actual.height():.4g} um', fill=MUTED, font=font(21))
    image.save(target)
    return {'image': str(target.relative_to(ROOT)), 'sha256': sha(target),
            'camera_um': bounds, 'render_source': str(path.relative_to(ROOT)),
            'render_source_sha256': sha(path), 'native_pixels': [W, H],
            'scale_bar_um': scale, 'marker_overlay': role != 'full'}


def capture():
    manifest_path = BASE/'manifest.json'
    manifest = json.loads(manifest_path.read_text())
    windows = json.loads((BASE/'windows/manifest.json').read_text())
    assert manifest['complete'] and len(manifest['cases']) == 50
    lookup = {row['case_id']: row for row in windows['windows']}
    verified = {str(manifest_path.relative_to(ROOT)): sha(manifest_path),
                str((BASE/'windows/manifest.json').relative_to(ROOT)): sha(BASE/'windows/manifest.json')}
    records = []
    IMAGES.mkdir(parents=True, exist_ok=True)
    for number, case in enumerate(manifest['cases'], 1):
        cid = case['case_id']
        full, report = BASE/case['gds'], BASE/case['evidence']['input_report']
        clip = BASE/lookup[cid]['inspection_gds']
        for path, expected in [(full, case['gds_sha256']), (clip, lookup[cid]['sha256']),
                               (report, case['evidence']['input_report_sha256'])]:
            assert sha(path) == expected, path
            verified[str(path.relative_to(ROOT))] = expected
        layout = db.Layout()
        layout.read(str(full))
        bbox = layout.top_cell().bbox()
        extent = [v*layout.dbu for v in (bbox.left, bbox.bottom, bbox.right, bbox.top)]
        window = union(case['edit_policy']['windows_um'])
        scope = case['scope_box_um']
        allowed = permitted_regions(layout, case['edit_policy'])
        counts = Counter(m['rule'] for m in case['evidence']['input_markers'])
        observed = {rule: n for rule, n in DRCParser().parse(report).rule_summary.items() if n}
        assert dict(counts) == observed, f'Marker evidence mismatch: {cid}'
        n = sum(counts.values())
        images = {}
        specifications = [
            ('full', full, camera(extent, .04), 'Full GDS input', 'All layers / cyan locates inspection window'),
            ('context', clip, camera(window, .04), 'Inspection window',
             'Routing layers / read-only geometry' if case['kind']=='no_edit' else 'Routing layers / permitted region in teal'),
            ('detail', clip, camera(scope, .32), 'Target detail', f'{n} scored marker(s) / red = saved checker edges')]
        for role, source, bounds, title, subtitle in specifications:
            images[role] = native_snapshot(source, report, bounds, IMAGES/f'{number:02}_{cid}_{role}.png',
                                          title, subtitle, role, window, allowed)
        records.append({'number': number, 'case_id': cid, 'level': case['level'], 'kind': case['kind'],
                        'source_group': case['source_group'], 'full_gds': str(full.relative_to(ROOT)),
                        'gds_sha256': case['gds_sha256'], 'metrics': case['metrics'], 'marker_counts': dict(counts),
                        'target_rules': case['evidence']['target_scope_rules'], 'scope_um': scope,
                        'inspection_window_um': window, 'permitted_regions_um': allowed, 'images': images})
        print(f'Captured {number:02}/50 {cid}', flush=True)
    assert Counter(r['level'] for r in records) == {i: 10 for i in range(1, 6)}
    return records, verified


def build_pdf(records):
    for name, filename in [('Review', 'DejaVuSans.ttf'), ('ReviewBold', 'DejaVuSans-Bold.ttf')]:
        pdfmetrics.registerFont(TTFont(name, str(FONTS/filename)))
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    width, height = landscape(A3)
    pdf = canvas.Canvas(str(OUTPUT), pagesize=(width, height), pageCompression=1, invariant=1)
    pdf.setTitle('C2+C3 - 50 GDS snapshots / five complexity levels')
    pdf.setAuthor('KLayout DRC project')
    pdf.setSubject('Full inputs, routing inspection windows and scored defect details; A3 landscape')

    def text(value, x, y, size=9, bold=False, color=INK):
        pdf.setFillColor(HexColor(color))
        pdf.setFont('ReviewBold' if bold else 'Review', size)
        assert pdfmetrics.stringWidth(value, 'ReviewBold' if bold else 'Review', size) <= width-x-22, value
        pdf.drawString(x, y, value)

    margin, gap = 24, 12
    cardw = width-2*margin
    cardh = (height-85-28-gap)/2
    panelw = (cardw-32)/3
    panelh = panelw*750/1080
    for page, start in enumerate(range(0, 50, 2), 1):
        level = records[start]['level']
        pdf.setFillColor(HexColor('#F3F6F8'))
        pdf.rect(0, 0, width, height, fill=1, stroke=0)
        pdf.setFillColor(HexColor('#167E81'))
        pdf.rect(0, height-5, width, 5, fill=1, stroke=0)
        text('C2+C3 GDS snapshots', margin, height-33, 22, True)
        pdf.setFont('Review', 10)
        pdf.setFillColor(HexColor(MUTED))
        pdf.drawRightString(width-margin, height-30, f'ALL 50 INPUTS  |  {page} / 25')
        text(f'L{level} / {LEVELS[level]} / 6 repair cases + 2 clean controls + 2 read-only cases per level', margin, height-51, 10, color=MUTED)
        x = margin
        for name, color, _ in LAYERS.values():
            pdf.setFillColor(HexColor(f'#{color:06x}'))
            pdf.rect(x, height-71, 7, 7, fill=1, stroke=0)
            text(name, x+12, height-71, 8.5, color=MUTED)
            x += 50
        text('Red: scored DRC marker   |   Teal: permitted region (cell/layer policy still applies)   |   DBU: 0.25 nm', x+10, height-71, 8.5, color=MUTED)
        for slot, record in enumerate(records[start:start+2]):
            x, y = margin, height-85-(slot+1)*cardh-slot*gap
            top = y+cardh
            pdf.setFillColor(white)
            pdf.setStrokeColor(HexColor(BORDER))
            pdf.roundRect(x, y, cardw, cardh, 6, fill=1, stroke=1)
            label, color, fill = KINDS[record['kind']]
            text(f'{record["number"]:02}  {record["case_id"]}  /  {record["source_group"]}', x+10, top-19, 11, True)
            sw = pdfmetrics.stringWidth(label, 'ReviewBold', 8)+18
            pdf.setFillColor(HexColor(fill))
            pdf.roundRect(x+cardw-sw-10, top-25, sw, 18, 4, fill=1, stroke=0)
            text(label, x+cardw-sw-1, top-20, 8, True, color)
            m = record['metrics']
            stats = f'Instances: {m["instance_count"]:,}   |   Hierarchy depth: {m["hierarchy_depth"]}   |   Context shapes: {m["context_shapes"]}'
            if 'route_segment_count' in m:
                stats += f'   |   Signal-route segments: {m["route_segment_count"]:,}   |   Vias: {m["via_count"]:,}'
            text(stats, x+10, top-36, 9, color=MUTED)
            image_y = top-49-panelh
            for col, role in enumerate(('full', 'context', 'detail')):
                pdf.drawImage(str(ROOT/record['images'][role]['image']), x+10+col*(panelw+6), image_y, width=panelw, height=panelh)
            markers = ', '.join(f'{rule}: {n}' for rule, n in record['marker_counts'].items()) or 'No scored target defect'
            text(f'Saved input markers: {markers}', x+10, y+43, 9, True, color)
            policy = ('All geometry is immutable. Accepted action: leave the layout unchanged.' if record['kind']=='no_edit' else
                      'Clean control: leave geometry unchanged. No target defect is present.' if record['kind']=='clean_control' else
                      'Repair only the listed signal-route cells, layers and regions. Protect cells, other routes and boundary anchors.')
            text(policy, x+10, y+27, 9, color=MUTED)
            if level == 5:
                bottom = f'Local route occupancy: {m["local_routing_occupancy"]:.1%}   |   Coupled rule categories: {m["coupled_rules"]}   |   GDS SHA-256: {record["gds_sha256"][:16]}'
            else:
                bottom = f'Full source: {record["full_gds"]}   |   SHA-256: {record["gds_sha256"][:16]}'
            text(bottom, x+10, y+11, 8, color=MUTED)
            pdf.bookmarkHorizontalAbsolute(record['case_id'], top)
            pdf.addOutlineEntry(f'{record["number"]:02} {record["case_id"]} - {label}', record['case_id'])
        text('Qualified scored profile only. Public-deck audits are separate. Geometry views do not prove electrical connectivity.', margin, 13, 8, color=MUTED)
        pdf.setFont('Review', 8)
        pdf.drawRightString(width-margin, 13, '28 October 2026  |  A3 landscape')
        pdf.showPage()
    pdf.save()
    reader = PdfReader(OUTPUT)
    assert len(reader.pages) == 25
    outputs = [OUTPUT]
    for level in range(1, 6):
        writer = PdfWriter()
        for p in reader.pages[(level-1)*5:level*5]:
            writer.add_page(p)
        writer.add_metadata({'/Title': f'C2+C3 L{level} - {LEVELS[level]} / 10 GDS inputs'})
        target = OUTPUT.with_name(f'c2_c3_l{level}_gds_snapshots.pdf')
        with target.open('wb') as stream:
            writer.write(stream)
        outputs.append(target)
    return outputs


def main():
    records, verified = capture()
    outputs = build_pdf(records)
    for relative, expected in verified.items():
        assert sha(ROOT/relative) == expected, f'Source changed: {relative}'
    for output in outputs:
        reader = PdfReader(output)
        for page in reader.pages:
            assert abs(float(page.mediabox.width)-landscape(A3)[0]) < .01
            assert abs(float(page.mediabox.height)-landscape(A3)[1]) < .01
        contents = '\n'.join(page.extract_text() for page in reader.pages)
        selected = records if output == OUTPUT else [r for r in records if f'_l{r["level"]}_' in output.name]
        for record in selected:
            heading = f'{record["number"]:02}  {record["case_id"]}  /'
            assert sum(line.startswith(heading) for line in contents.splitlines()) == 1, record['case_id']
    receipt = {'case_count': len(records), 'snapshot_count': 150, 'page_count': 25,
               'scope': 'Frozen full input GDS; no model outputs or reference repairs',
               'rendering': 'Native offscreen KLayout; full source all layers; clips retain original TOP coordinates',
               'renderer_version': db.__version__, 'generator_sha256': sha(__file__),
               'style_reference': {'path': 'output/pdf/c1_bedrock_quick_review.pdf',
                                   'sha256': sha(ROOT/'output/pdf/c1_bedrock_quick_review.pdf')},
               'notes': ['Cyan overview window has a minimum size of 8 pixels for visibility.',
                         'Teal outlines show spatial permission only; cell and layer restrictions still apply.',
                         'Scored marker overlays use saved flat TOP-coordinate reports; public audit markers are excluded.',
                         'Clean controls have no target defect; read-only cases permit no geometry edits.'],
               'verified_sources': verified, 'cases': records,
               'pdfs': [{'path': str(p.relative_to(ROOT)), 'sha256': sha(p), 'pages': len(PdfReader(p).pages)} for p in outputs]}
    (IMAGES/'image_manifest.json').write_text(json.dumps(receipt, indent=2)+'\n')
    lines = ['# C2+C3 GDS snapshot atlas', '',
             'All 50 frozen GDS inputs, grouped by complexity level. Each A3 landscape page contains two cases.',
             'Each case has a full-layout view, a routing inspection window, and a target detail view.', '',
             '## PDFs', '']
    lines += [f'- [{p.name}](../../../{p.relative_to(ROOT)}) - {len(PdfReader(p).pages)} pages.' for p in outputs]
    lines += ['', '## View contract', ''] + [f'- {n}' for n in receipt['notes']]
    lines += ['- One DBU is 0.25 nm. Scale bars adapt to each physical camera window.',
              '- Full GDS inputs remain unchanged. No checker, repair, or model call was run.',
              '- The qualified scored profile and full public-deck audit have different scopes.', '',
              '## Case index', '', '| Case | Level | Kind | Full GDS | Snapshots |', '|---|---|---|---|---|']
    for r in records:
        images = ' / '.join(f'[{role}]({Path(r["images"][role]["image"]).name})' for role in ('full', 'context', 'detail'))
        lines.append(f'| {r["case_id"]} | L{r["level"]} | {r["kind"]} | [GDS](../../../{r["full_gds"]}) | {images} |')
    (IMAGES/'README.md').write_text('\n'.join(lines)+'\n')
    print(f'Created {len(outputs)} A3 PDFs, 50 cases, 150 snapshots. Sources unchanged.', flush=True)


if __name__ == '__main__':
    main()
