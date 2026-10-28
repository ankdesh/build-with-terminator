#!/usr/bin/env python3
"""Render accepted C1 evidence with KLayout and build a beginner PDF guide.

Run with the project environment (klayout) plus Pillow and reportlab installed:
  QT_QPA_PLATFORM=offscreen .venv/bin/python scripts/capture_c1_examples.py
No checker or repair is run. Input evidence is verified before any export.
"""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
from klayout_drc.handoff.report_paths import ROOT, FONTS, resolve_record
from xml.etree import ElementTree

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import klayout.db as db
import klayout.lay as lay
from PIL import Image, ImageDraw, ImageFont
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor, white
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from klayout_drc.parser import DRCParser
from klayout_drc.marker_geometry import EdgePairMarker, EdgeMarker, PolygonMarker, BoxMarker

BASE = ROOT / 'test_data/benchmark_v1'
OUT = ROOT / 'docs/reports/c1_visual_guide'
PDF = ROOT / 'output/pdf/c1_visual_guide.pdf'
COLORS = {18: ('V0', 0x777777, 3), 19: ('M1', 0x2476B3, 3),
          20: ('M2', 0xBB780D, 5), 21: ('V1', 0x8654AA, 7)}
EXAMPLES = [
 ('m1_w1_iso_01', 'A wire that is too narrow',
  'The M1 rectangle is 10 nm wide and 100 nm long. Look at the two long red edges.',
  'M1.W.1 requires a width of at least 18 nm. One marker identifies the narrow wire.',
  'The heuristic expands the rectangle to 32 nm in width. It passes the five scoped rules and preservation checks.',
  'A repair can pass yet add more metal than needed. This is geometry success, not proof of a good circuit.'),
 ('m1_w1_iso_08', 'A narrow section inside a wider wire',
  'The outside width is 24 nm. The middle section is only 12 nm wide. Look at the neck between y = 30 and 70 nm.',
  'M1.W.1 requires at least 18 nm at the narrow section. The outside bounding box cannot show this fault.',
  'The heuristic expands the polygon. The narrow section becomes 24 nm wide. The saved after-check has no scoped marker.',
  'Check local shape width. A wide overall outline can still contain a narrow section.'),
 ('m1_w1_bnd_01', 'One database step below the limit',
  'The wire is 17.75 nm wide. It is 71 database units wide. Look at the red side edges.',
  'M1.W.1 requires 18 nm, or 72 database units. The 0.25 nm shortfall produces one marker.',
  'The heuristic expands the wire to 39.75 nm in width. The saved output passes the scoped geometry checks.',
  'A small difference can change a checker result. Exact integer coordinates matter.'),
 ('m1_w1_bnd_04', 'At the limit: a clean control',
  'The wire is exactly 18 nm wide. It is 72 database units wide. It has no input marker.',
  'M1.W.1 accepts this width. The other four scoped checks also produce no marker.',
  'The heuristic still expands the wire to 30 nm in width. It remains checker-clean, but the recorded outcome is unnecessary_edit.',
  'A clean output alone does not prove useful repair. A clean input should stay unchanged.'),
 ('m2_w1_iso_06', 'The same type of check on M2',
  'The horizontal M2 wire is 100 nm long and 12 nm wide. M2 is the amber layer, 20/0.',
  'M2.W.1 requires at least 18 nm. The pair of horizontal red edges marks the narrow width.',
  'The heuristic expands the wire to 22 nm in width. The saved output has no scoped marker.',
  'Layer numbers select which rule applies. Screen colour is only a viewer setting.'),
 ('m1_a1_iso_01', 'Width passes, but area fails',
  'The M1 pad is 18 by 18 nm. Its area is 324 square nm. Look at the red polygon outline.',
  'M1.A.1 requires at least 504 square nm. The width is legal, but the pad area is too small.',
  'The heuristic makes a 30 by 30 nm pad. Its area is 900 square nm. The saved output has no scoped marker.',
  'Width measures a distance. Area measures a surface. Passing one does not imply passing the other.'),
 ('m1_s1_iso_01', 'A small gap and an invalid shortcut',
  'Two M1 wires are each 40 nm wide and 80 nm long. Their gap is 10 nm. Look between the wires.',
  'M1.S.1 flags this gap. The facing edges are longer than 36 nm, and the scoped minimum spacing is 18 nm.',
  'The heuristic expands the wires until they join. The component count changes from two to one. Validation rejects the patch before after-DRC.',
  'Joining separate wires is not an acceptable repair. Preservation checks must pass before success can be scored.'),
 ('m1_s1_neg_03', 'A narrow gap with no scoped marker',
  'Two M1 stubs are 40 nm wide and only 30 nm long. Their gap is 12 nm. The input has no marker.',
  'This deck filters spacing results using edges up to 36 nm long. These short stubs do not produce an M1.S.1 marker.',
  'The heuristic expands the stubs and joins them. Validation rejects the two-to-one component change. After-DRC is not run.',
  'No marker means no fault found by these checks. It does not prove compliance with every ASAP7 spacing rule.'),
 ('v1_w1_iso_01', 'One via shape, two width markers',
  'The V1 square is 10 by 10 nm. The checker marks the horizontal and vertical width directions.',
  'V1.W.1 requires at least 18 nm. One square produces two edge-pair markers. Marker count is not shape count.',
  'The heuristic expands V1 to 20 by 20 nm and adds M1 metal. The saved output has no scoped marker.',
  'This deck checks via width. It does not prove via enclosure, a square-cut rule, or electrical connection.'),
 ('m2_w1_int_02', 'Two layers cross in a flat view',
  'A 12 nm M1 wire runs vertically. A 12 nm M2 wire crosses it horizontally. Both layers appear in this flat view.',
  'M1.W.1 and M2.W.1 each produce one marker. Each wire fails its own width check.',
  'The heuristic widens both wires. The saved output passes the five scoped checks and component checks.',
  'An overlap in a two-dimensional drawing does not prove a connection between layers. A circuit needs more evidence.'),
]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def check_hash(path, expected):
    if not expected or sha(path) != expected:
        raise ValueError(f'Evidence hash mismatch: {path}')


def geometry(path):
    layout = db.Layout()
    layout.read(str(path))
    top = layout.top_cell()
    if top is None:
        raise ValueError(f'No top cell: {path}')
    regions, stats = {}, {}
    for li in layout.layer_indices():
        info = layout.get_info(li)
        region = db.Region(top.begin_shapes_rec(li)).merged()
        if region.is_empty():
            continue
        key = f'{info.layer}/{info.datatype}'
        regions[key] = region
        box = region.bbox()
        stats[key] = {'bbox_dbu': [box.left, box.bottom, box.right, box.top],
                      'bbox_nm': [round(x * layout.dbu * 1000, 8) for x in [box.left, box.bottom, box.right, box.top]],
                      'area_nm2': round(region.area() * (layout.dbu * 1000) ** 2, 8),
                      'components': region.count(), 'geometry_dbu': str(region)}
    box = top.bbox()
    return layout, regions, stats, [x * layout.dbu for x in [box.left, box.bottom, box.right, box.top]]


def report_counts(path):
    if path is None:
        return None
    return {k: n for k, n in DRCParser().parse(path).rule_summary.items() if n}


def overlays(view, report):
    markers = []
    if report is None:
        return markers
    for category in DRCParser().parse(report).categories:
        for item in category.violations:
            for geometry_item in item.geometries:
                g = geometry_item.marker
                edges = [g.edge1, g.edge2] if isinstance(g, EdgePairMarker) else [g] if isinstance(g, EdgeMarker) else []
                if edges:
                    shapes = [('edge', db.DEdge(e.p1.x, e.p1.y, e.p2.x, e.p2.y)) for e in edges]
                elif isinstance(g, PolygonMarker):
                    # Draw edges individually: no opaque marker fill can hide the metal.
                    pts = list(g.points)
                    shapes = [('edge', db.DEdge(a.x, a.y, b.x, b.y)) for a, b in zip(pts, pts[1:] + pts[:1])]
                elif isinstance(g, BoxMarker):
                    shapes = [('box', db.DBox(*g.bbox))]
                else:
                    raise ValueError(f'Unsupported marker geometry: {geometry_item}')
                for kind, shape in shapes:
                    marker = lay.Marker(view)
                    marker.color = marker.frame_color = 0xCF2535
                    marker.line_width = 3
                    getattr(marker, 'set_' + kind)(shape)
                    markers.append(marker)
    return markers


def font(size, bold=False):
    return ImageFont.truetype(str(FONTS / ('DejaVuSans-Bold.ttf' if bold else 'DejaVuSans.ttf')), size)


def render(path, report, window, target, title, subtitle, stats, ruler=None, detail=False):
    view = lay.LayoutView()
    for key, val in [('background-color', '#ffffff'), ('foreground-color', '#223247'),
                     ('grid-visible', 'false'), ('text-visible', 'false'), ('annotation-font-size', '20')]:
        view.set_config(key, val)
    view.commit_config()
    view.load_layout(str(path), False)
    view.max_hier()
    view.add_missing_layers()
    it = view.begin_layers()
    while not it.at_end():
        props = it.current()
        _, color, pattern = COLORS.get(props.source_layer, ('Other', 0x777777, 3))
        props.fill_color = props.frame_color = color
        props.dither_pattern = pattern
        props.width = 2
        view.set_layer_properties(it, props)
        it.next()
    markers = overlays(view, report)  # Keep objects alive until save_image completes.
    if ruler:
        x1, y1, x2, y2, label = ruler
        ann = lay.Annotation()
        ann.p1 = db.DPoint(x1, y1)
        ann.p2 = db.DPoint(x2, y2)
        ann.fmt = ''
        ann.style = lay.Annotation.StyleArrowBoth
        view.insert_annotation(ann)
    left, bottom, right, top = window
    cx, cy = (left+right)/2, (bottom+top)/2
    width = max(right-left, (top-bottom)*720/560)
    height = width*560/720
    actual = db.DBox(cx-width/2,cy-height/2,cx+width/2,cy+height/2)
    view.resize(720,560)
    view.zoom_box(actual)
    raw = target.with_name(target.stem + '.raw.png')
    view.save_image_with_options(str(raw),720,560,1,1,1,actual,False)
    image = Image.new('RGB', (720, 750), 'white')
    image.paste(Image.open(raw).convert('RGB'), (0, 90))
    raw.unlink()
    draw = ImageDraw.Draw(image)
    draw.text((20, 10), title, fill='#142e46', font=font(29, True))
    draw.text((20, 51), subtitle, fill='#8e2530' if report is None else '#36465a', font=font(22))
    draw.line((20, 87, 700, 87), fill='#cbd6df', width=2)
    legend_x = 22
    for layer in [19, 20, 21]:
        name, color, _ = COLORS[layer]
        draw.rectangle((legend_x, 661, legend_x + 18, 679), fill=f'#{color:06x}')
        draw.text((legend_x + 25, 655), name, fill='#223247', font=font(22))
        legend_x += 105
    draw.text((350, 655), 'Red = DRC marker', fill='#b22131', font=font(22))
    measure = []
    for layer, s in stats.items():
        b = s['bbox_nm']
        label = COLORS.get(int(layer.split('/')[0]), (layer,))[0]
        measure.append(f'{label}: {b[2]-b[0]:g} x {b[3]-b[1]:g} nm')
    draw.text((20, 694), ' | '.join(measure), fill='#223247', font=font(21))
    # Use the exact export box for scale bars and annotation positions.
    if ruler:
        x1, y1, x2, y2, label = ruler
        mx = ((x1+x2)/2-actual.left) / actual.width()*720
        my = 90+(actual.top-(y1+y2)/2) / actual.height()*560
        label_font = font(22, True)
        tw = draw.textlength(label, font=label_font)
        tx = mx-tw/2 if y1 == y2 else mx+12
        ty = my+12 if y1 == y2 else my-15
        tx = max(5, min(tx, 715-tw))
        draw.rectangle((tx-3,ty-1,tx+tw+3,ty+28), fill='white')
        draw.text((tx,ty),label,fill='#223247',font=label_font)
    scale_nm = 1 if detail else 20
    px = scale_nm / 1000 / actual.width() * 720
    draw.line((545, 619, 545 + px, 619), fill='#223247', width=4)
    for x in [545, 545 + px]:
        draw.line((x, 614, x, 624), fill='#223247', width=3)
    draw.text((535, 584), f'{scale_nm} nm', fill='#223247', font=font(21))
    image.save(target)
    view.destroy()
    return {'image': os.path.relpath(target, ROOT), 'sha256': sha(target),
            'gds': str(path.relative_to(ROOT)), 'gds_sha256': sha(path),
            'report': str(report.relative_to(ROOT)) if report else None,
            'report_sha256': sha(report) if report else None,
            'counts': report_counts(report), 'geometry': stats,
            'requested_window_um': window, 'actual_window_um': [actual.left, actual.bottom, actual.right, actual.top],
            'ruler_um': ruler, 'size_px': [720, 750]}


def prepare():
    manifest_path = BASE / 'manifest.json'
    summary_path = ROOT / 'reports/runs/c1_corrected_heuristic/summary.json'
    manifest = json.loads(manifest_path.read_text())
    summary = json.loads(summary_path.read_text())
    cases = {c['case_id']: c for c in manifest['cases']}
    runs = {r['case_id']: r for r in summary['results']}
    deck = ROOT / 'test_data/rules/asap7_curated.lydrc'
    check_hash(deck, manifest['acceptance']['deck_sha256'])
    deck_text = ElementTree.parse(deck).getroot().findtext('text')
    assert all(f'output("{rule}"' in deck_text for rule in ['M1.W.1','M2.W.1','M1.A.1','M1.S.1','V1.W.1'])
    prepared = []
    verified = {manifest_path: sha(manifest_path), summary_path: sha(summary_path), deck: sha(deck), Path(__file__).resolve(): sha(Path(__file__).resolve())}
    for spec in EXAMPLES:
        cid = spec[0]
        case, run = cases[cid], runs[cid]
        a = case['acceptance']
        paths = {'reference': BASE / a['reference_gds'], 'input': BASE / case['gds_rel_path']}
        reports = {'reference': BASE / a['reference_report'], 'input': BASE / a['report']}
        for p, h in [(paths['reference'], a['reference_sha256']), (paths['input'], case['sha256']),
                     (reports['reference'], a['reference_report_sha256']), (reports['input'], a['report_sha256'])]:
            check_hash(p, h)
            verified[p] = h
        run_dir = resolve_record(run['run_dir'])
        rm_path = run_dir / 'run_manifest.json'
        rm = json.loads(rm_path.read_text())
        verified[rm_path] = sha(rm_path)
        for name in ['input.gds','patched.gds','before.lyrdb','deck.lydrc','benchmark_result.json'] + (['after.lyrdb'] if run['final_total'] is not None else []):
            p = run_dir / name
            check_hash(p, rm['artifact_hashes'].get(name))
            verified[p] = sha(p)
        if json.loads((run_dir / 'benchmark_result.json').read_text()) != run:
            raise ValueError(f'Summary differs from per-run result: {cid}')
        check_hash(run_dir / 'input.gds', case['sha256'])
        check_hash(run_dir / 'deck.lydrc', manifest['acceptance']['deck_sha256'])
        paths['output'] = run_dir / 'patched.gds'
        reports['output'] = run_dir / 'after.lyrdb' if run['final_total'] is not None else None
        if reports['output'] is None and (run_dir / 'after.lyrdb').exists():
            raise ValueError(f'Unexpected unmeasured after report: {cid}')
        if report_counts(reports['input']) != a['expected_counts'] or report_counts(reports['reference']) != {}:
            raise ValueError(f'Oracle counts mismatch: {cid}')
        if report_counts(reports['input']) != run['initial_violations']:
            raise ValueError(f'Initial counts mismatch: {cid}')
        if reports['output'] and report_counts(reports['output']) != run['final_violations']:
            raise ValueError(f'After counts mismatch: {cid}')
        prepared.append((spec, case, run, rm, paths, reports))
    return prepared, verified, manifest, summary


def input_ruler(cid, stats, regions, dbu_um):
    """Measure the annotated distance from integer region geometry."""
    key = '21/0' if cid.startswith('v1') else '20/0' if cid == 'm2_w1_iso_06' else '19/0'
    region = regions[key]
    box = region.bbox()
    if cid == 'm1_w1_iso_08':
        cy = (box.bottom+box.top)//2
        neck = (region & db.Region(db.Box(box.left,cy,box.right,cy+1))).bbox()
        distance = neck.width()*dbu_um*1000
        return (neck.left*dbu_um, cy*dbu_um, neck.right*dbu_um, cy*dbu_um, f'{distance:g} nm')
    if 's1_' in cid:
        boxes = sorted((poly.bbox() for poly in region.each()), key=lambda b:b.left)
        assert len(boxes) == 2
        x1,x2 = boxes[0].right*dbu_um,boxes[1].left*dbu_um
        return (x1,-.009,x2,-.009,f'{(x2-x1)*1000:g} nm gap')
    if cid == 'm2_w1_iso_06':
        cx = (box.left+box.right)/2*dbu_um
        return (cx,box.bottom*dbu_um,cx,box.top*dbu_um,f'{box.height()*dbu_um*1000:g} nm')
    return (box.left*dbu_um,-.008,box.right*dbu_um,-.008,f'{box.width()*dbu_um*1000:g} nm')


def capture(prepared):
    OUT.mkdir(parents=True, exist_ok=True)
    records = []
    for number, (spec, case, run, rm, paths, reports) in enumerate(prepared, 1):
        cid = spec[0]
        geom = {role: geometry(path) for role, path in paths.items()}
        boxes = [x[3] for x in geom.values()]
        left, bottom = min(b[0] for b in boxes), min(b[1] for b in boxes)
        right, top = max(b[2] for b in boxes), max(b[3] for b in boxes)
        span = max(right-left, top-bottom, .04)
        window = [left-span*.20, bottom-span*.22, right+span*.20, top+span*.15]
        images = {}
        for role in ['reference', 'input', 'output']:
            counts = report_counts(reports[role])
            subtitle = '0 scoped markers' if counts == {} else f'{sum(counts.values())} scoped marker(s)' if counts is not None else 'Rejected; after-DRC not run'
            ruler = input_ruler(cid, geom[role][2], geom[role][1], geom[role][0].dbu) if role == 'input' else None
            images[role] = render(paths[role], reports[role], window, OUT / f'{number:02}_{cid}_{role}.png',
                                  {'reference':'Synthetic legal reference','input':'Test input','output':'Saved heuristic output'}[role],
                                  subtitle, geom[role][2], ruler)
        records.append({'number': number, 'case_id': cid, 'tier': case['tier'], 'rule_id': case['rule_id'],
                        'verdict': run['verdict'], 'pipeline_verdict': run['pipeline_verdict'],
                        'validation': run['validation'], 'checker_version': rm['environment']['checker_cli_version'],
                        'duplicate_group': case['acceptance']['duplicate_group'], 'images': images})
        print(f'Captured {number:02} {cid}', flush=True)
    # The exact same window shows the right edge at 17.75 nm versus 18 nm.
    # These are cropped views of the real GDS, not a drawing of an imagined edge.
    for number in [3, 4]:
        spec, case, run, rm, paths, reports = prepared[number-1]
        target = OUT / f'{number:02}_{spec[0]}_edge_detail.png'
        record = render(paths['input'], reports['input'], [.015, .046, .021, .052], target,
                        'Right edge: ' + ('17.75 nm' if number == 3 else '18 nm'),
                        'Matched camera; one step = 0.25 nm', geometry(paths['input'])[2],
                        (.01775, .048, .018, .048, '0.25 nm'), True)
        records[number-1]['edge_detail'] = record
    return records


def build_pdf(records, manifest):
    pdfmetrics.registerFont(TTFont('Guide', str(FONTS / 'DejaVuSans.ttf')))
    pdfmetrics.registerFont(TTFont('GuideBold', str(FONTS / 'DejaVuSans-Bold.ttf')))
    PDF.parent.mkdir(parents=True, exist_ok=True)
    w, h = landscape(A4)
    c = canvas.Canvas(str(PDF), pagesize=(w, h))
    c.setTitle('C1 visual guide: 10 GDS and DRC examples')
    c.setAuthor('KLayout DRC project')
    page = 0
    def text(txt, x, y, size=11, width=None, bold=False, color='#24384a'):
        c.setFillColor(HexColor(color)); c.setFont('GuideBold' if bold else 'Guide', size)
        if width is None:
            c.drawString(x, y, txt)
            return y-size*1.5
        lines = []
        for para in txt.split('\n'):
            line = ''
            for word in para.split():
                candidate = f'{line} {word}'.strip()
                if pdfmetrics.stringWidth(candidate, 'GuideBold' if bold else 'Guide', size) > width and line:
                    lines.append(line); line = word
                else: line = candidate
            lines.append(line)
        for line in lines:
            c.drawString(x, y, line); y -= size*1.48
        return y
    def new(title, subtitle='C1 / curated geometry checks / beginner guide'):
        nonlocal page
        if page: c.showPage()
        page += 1
        c.setFillColor(HexColor('#12354b')); c.rect(0,h-13,w,13,fill=1,stroke=0)
        text(title,34,h-49,21,bold=True)
        text(subtitle,34,h-70,10,color='#567084')
        c.setStrokeColor(HexColor('#d4dfe5')); c.line(34,31,w-34,31)
        text('Development benchmark | 23 October 2026 | geometry_only',34,18,8,color='#567084')
        text(str(page),w-47,18,8)
        return h-103
    def block(label, body, y, x=34, width=None):
        width = width or w-68
        y = text(label,x,y,11,bold=True,width=width)
        return text(body,x,y-1,10.5,width=width)-12
    y = new('Read a layout. Understand a DRC result.', '10 real C1 examples, shown with KLayout native image export')
    y = block('What this guide gives you', 'This guide shows simple test layouts, their checker markers, and saved heuristic outputs. Each example compares a synthetic legal reference, the test input, and one existing repair attempt. No new repair or model call was made for this guide.', y)
    y = block('GDS: the shapes', 'A GDS file stores two-dimensional shapes on numbered layers. A wire appears as a polygon. The file does not, by itself, explain the purpose of every shape. The screen shows a flat view of several physical layers.', y)
    y = block('DRC: the checks', 'Design rule checking compares geometry with rules. A rule can limit width, spacing, or area. The checker writes a report database (.lyrdb). Red highlights in this guide come from that report. They are not extra physical material.', y)
    y = block('Read the units', 'nm means nanometre. Area uses square nanometres (nm²). Here, one database unit (DBU) is 0.25 nm. Thus 18 nm = 72 DBU; 17.75 nm = 71 DBU. KLayout APIs use micrometres for these view coordinates: 1 µm = 1,000 nm.', y)
    y = block('Limits of the evidence', 'The dataset has 100 entries and 93 distinct layouts: 78 dirty inputs and 22 clean controls. This guide selects 10 teaching examples. It is not a statistical sample. A pass means no fault was found by the five scoped rules plus the recorded geometry preservation checks. It does not prove electrical correctness, enclosure, or full ASAP7 compliance.', y)
    new('The layers, rules, and case classes')
    y = h-106
    y = block('Layer/datatype notation', '19/0 means GDS layer 19, datatype 0. M1 is 19/0 (blue); M2 is 20/0 (amber); V1 is 21/0 (purple). V0 is 18/0 and is not checked by a rule in this subset. Colour and hatch are viewer settings. They do not show height, voltage, or an error state.', y)
    for label, body in [
        ('M1.W.1 and M2.W.1', 'Minimum metal width: 18 nm on M1 and M2. Measure across the wire, not along it.'),
        ('M1.A.1', 'Minimum M1 polygon area: 504 nm². A pad can pass width and still fail area.'),
        ('M1.S.1', 'Selected M1 spacing: 18 nm. The deck filters spacing polygons that interact with M1 edges up to 36 nm long. Read example 8 before treating this as a general spacing rule.'),
        ('V1.W.1', 'Minimum V1 width: 18 nm. It is a via-width check. Planned enclosure coverage was replaced by via width.'),
        ('Four case classes', 'Isolated: one main issue. Boundary: just below, at, or above a limit. Interaction: more than one shape, layer, or check. Negative control: intended to have no selected error. The labels do not guarantee that every file has a violation.')]:
        y = block(label, body, y)
    y = new('How to read the image panels')
    y = block('Left: synthetic legal reference', 'This is a checker-clean seed made for dataset acceptance. It keeps the layer set and component counts. It is not a recovered original design, and it is not a minimal repair. Its size and placement can differ a lot from the test input.',y)
    y = block('Centre: test input', 'This is the case given to the repair system. Red outlines show the actual saved checker markers. A width marker often contains two edges. A polygon marker may cover a gap or outline a small pad. Marker count does not equal the number of faulty shapes.',y)
    y = block('Right: saved heuristic output', 'This is the output from the existing corrected heuristic campaign. A successful output has an after-DRC report. A rejected output may have no after-report. Missing measurements stay unknown. They are never shown as zero.',y)
    y = block('Scale and dimensions', 'The three main panels use the same physical window for each example. A scale bar shows 20 nm. The footer gives the bounding-box size on each present layer; this is not always the local wire width. The input arrow marks the key width or gap. Separate edge details use a 1 nm scale bar.',y)
    y = block('What the result labels mean', 'clean_success: dirty input, accepted output, and no scoped after-markers. unnecessary_edit: clean input changed without a needed repair. invalid_patch: preservation or another validation check rejected the output. A clean checker report cannot override a preservation failure.',y)
    y = block('Version and evidence note', f'Dataset release {manifest["benchmark_version"]}. Python KLayout renderer: {db.__version__}. Saved campaign checker CLI: KLayout 0.28.16. Images use actual GDS geometry and report markers. View arrows, scale bars, legends, and titles are annotations. No source GDS was modified.',y)
    for spec, rec in zip(EXAMPLES, records):
        cid,title,see,rule,changed,lesson = spec
        new(f'{rec["number"]:02}  {title}', f'{cid}  |  class: {rec["tier"]}  |  recorded outcome: {rec["verdict"]}')
        image_width = (w-84)/3
        image_height = image_width*750/720
        top = h-88
        for i,role in enumerate(['reference','input','output']):
            c.drawImage(str(ROOT / rec['images'][role]['image']),34+i*(image_width+8),top-image_height,
                        width=image_width,height=image_height)
        y = top-image_height-18
        y = block('What you see and where to look',see,y)
        y = block('Rule and checker result',rule,y)
        # Two columns for the final explanations keep the page balanced.
        half = (w-88)/2
        block('What the heuristic changed',changed,y,x=34,width=half)
        block('Main lesson',lesson,y,x=54+half,width=half)
        if rec['images']['output']['counts'] is None:
            text('Patch rejected. After-DRC check was not run.',34,46,10,bold=True,color='#a12a34')
    new('Boundary detail: 17.75 nm versus 18 nm', 'Same crop and zoom in both panels. The view shows the right edge of each real input.')
    iw=330; ih=iw*750/720
    for index,rec in enumerate([records[2],records[3]]):
        c.drawImage(str(ROOT / rec['edge_detail']['image']), 66+index*380,h-92-ih,width=iw,height=ih)
    y=h-92-ih-21
    y=block('A small shift, a different result', 'The arrow spans x = 17.75 to 18 nm in both views. The left wire stops at 17.75 nm and has a red width marker. The right wire reaches 18 nm and has no marker. The rest of each wire is outside this crop. These are enlarged edge views, not full wire widths.',y)
    block('Keep the test precise', 'The difference is one DBU: 0.25 nm. Rounded labels or a full-layout view can hide it. The footer still gives the full layer bounding box, not the cropped size.',y)
    y=new('Open the files and check the evidence')
    y=block('Open a layout in KLayout', 'Use File > Open and select the case GDS. Select the TOP cell and fit the layout in the view. Show layer 19/0 for M1, 20/0 for M2, and 21/0 for V1. Use the ruler to measure a width or gap. The raw GDS does not contain this guide\'s titles or arrows.',y)
    y=block('Open its checker report', 'Open the Marker Database Browser (menu wording can vary by KLayout version), then load the matching .lyrdb file. Select a rule category and an item to zoom to its marker. Use the case report for the input and after.lyrdb only when the saved run has one.',y)
    y=block('Find the source files', 'Case GDS: test_data/benchmark_v1/cases/<case_id>.gds\nReference GDS: test_data/benchmark_v1/references/<case_id>.gds\nInput markers: test_data/benchmark_v1/oracle/<case_id>.lyrdb\nSaved outputs: reports/runs/c1_corrected_heuristic/runs/<run_id>/patched.gds\nUse the companion image_manifest.json for the exact run paths and file hashes.',y)
    y=block('Reproduce the guide', 'Run scripts/capture_c1_examples.py in the project Python environment with KLayout, Pillow, and reportlab available. Set QT_QPA_PLATFORM=offscreen for native image export without a desktop. The script checks hashes and report counts, exports the images, builds this PDF, and verifies that source files stayed unchanged.',y)
    y=block('Glossary', 'Bounding box: the smallest axis-aligned rectangle around a shape. Component: a connected piece of geometry on one layer. Heuristic: a fixed repair method. Polygon: a closed shape. Preservation: checks that required geometry was not erased or joined. Reference: an accepted comparison layout. Scoped: limited to the checks selected here.',y)
    y=block('Source records and documentation', 'Local evidence: benchmark manifest 1.1.0, curated deck, saved oracle reports, and corrected heuristic summary with per-run results. The companion image manifest stores hashes and measured integer geometry. KLayout native export API: https://www.klayout.de/doc-qt5/code/class_LayoutView.html',y)
    c.save()
    return page


def main():
    prepared, verified, manifest, summary = prepare()
    records = capture(prepared)
    pages = build_pdf(records, manifest)
    for path, expected in verified.items():
        check_hash(path, expected)
    data = {'schema_version': 1, 'title': 'C1 visual guide', 'dataset_version': manifest['benchmark_version'],
            'renderer_version': db.__version__, 'checker_version': 'KLayout 0.28.16',
            'source_files_unchanged': True,
            'verified_sources': {str(p.relative_to(ROOT)): value for p,value in verified.items()},
            'images_count': 32, 'cases': records, 'pdf': {'path': str(PDF.relative_to(ROOT)), 'sha256': sha(PDF), 'pages':pages}}
    (OUT / 'image_manifest.json').write_text(json.dumps(data,indent=2)+'\n')
    # A short index keeps image links and source evidence easy to find in the repo.
    lines = ['# C1 visual guide', '', '[Read the PDF](../../output/pdf/c1_visual_guide.pdf)', '',
             'The PDF has ten examples. See the image manifest for verified hashes, exact source paths,',
             'integer geometry measurements, checker counts, and the saved verdicts.', '']
    for spec,rec in zip(EXAMPLES,records):
        lines.extend([f'## {rec["number"]:02} {spec[1]}', '', f'`{spec[0]}` | {rec["tier"]} | `{rec["verdict"]}`', '', *[p for body in spec[2:] for p in [body, '']]])
        for role,img in rec['images'].items():
            rel = 'c1_visual_guide/' + Path(img['image']).name
            lines.extend([f'[{role}: full image]({rel})', '', f'![{spec[0]} {role}]({rel})', ''])
    (ROOT / 'docs/reports/c1_visual_guide.md').write_text('\n'.join(lines))
    print(f'Created {PDF}: {pages} pages, 32 PNGs; verified {len(verified)} unchanged source files.')

if __name__ == '__main__':
    main()
