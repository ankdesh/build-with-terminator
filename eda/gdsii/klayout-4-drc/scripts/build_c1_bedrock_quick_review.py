#!/usr/bin/env python3
"""Build a 20-case review from saved Bedrock evidence. No models or repairs run.

Requires the project KLayout environment plus Pillow, reportlab, and pypdf.
Use the bundled PDF packages through PYTHONPATH if needed. Native KLayout
renders the actual GDS geometry and saved checker markers offscreen.
"""
from __future__ import annotations

from collections import Counter
import hashlib
import json
import os
from pathlib import Path
from klayout_drc.handoff.report_paths import ROOT, FONTS, resolve_record

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import klayout.db as db
import klayout.lay as lay
from PIL import Image, ImageDraw
from pypdf import PdfReader
from reportlab.lib.colors import HexColor, white
from reportlab.lib.pagesizes import A3, landscape
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

from capture_c1_examples import COLORS, FONTS, font, geometry, overlays, report_counts

BASE = ROOT/'test_data/benchmark_v1'
import os
CAMPAIGN = Path(os.environ.get('DRC_REPORT_CAMPAIGN', ROOT/'reports/runs/c1_bedrock_all100_strict_api_20261027'))
IMAGES = ROOT/'docs/reports/c1_bedrock_quick_review'
OUTPUT = ROOT/'output/pdf/c1_bedrock_quick_review.pdf'
ORIGINAL = ROOT/'output/pdf/c1_heuristic_quick_review.pdf'

# Ten accepted dirty-input repairs, then ten representative unsuccessful runs.
# These are teaching examples, not a random or proportionate sample.
CASES = [
    ('m1_w1_iso_04', 'clean_success', 'FIXED',
     'M1 width: 15 -> 18 nm. Minimum: 18 nm.',
     'Markers: 1 -> 0. The output widens the wire to the required width.'),
    ('m1_w1_bnd_01', 'clean_success', 'FIXED',
     'M1 input: 17.75 nm, one DBU below the 18 nm limit.',
     'Markers: 1 -> 0. A small sizing step clears the boundary violation.'),
    ('m2_w1_iso_01', 'clean_success', 'FIXED',
     'M2 width: 10 -> 18 nm. Minimum: 18 nm.',
     'Markers: 1 -> 0. The output changes M2 and keeps one component.'),
    ('m2_w1_int_02', 'clean_success', 'FIXED',
     'Crossing M1 and M2: both widths grow from 12 to 18 nm.',
     'Markers: 2 -> 0. Both metal width checks pass after the repair.'),
    ('m1_a1_iso_02', 'clean_success', 'FIXED',
     'M1 pad area: 360 -> 675 nm2. Minimum: 504 nm2.',
     'Markers: 1 -> 0. Legal width alone did not give enough input area.'),
    ('m1_a1_int_02', 'clean_success', 'FIXED',
     'Two M1 pads: each area grows from 360 to 505.25 nm2.',
     'Markers: 2 -> 0. The output keeps two separate components.'),
    ('m1_s1_iso_06', 'clean_success', 'FIXED',
     'M1 horizontal-wire gap: 12 -> 18 nm. Minimum: 18 nm.',
     'Markers: 1 -> 0. One wire moves; the two wires remain separate.'),
    ('m1_s1_iso_07', 'clean_success', 'FIXED',
     'M1 horizontal-wire gap: 14 -> 18 nm. Minimum: 18 nm.',
     'Markers: 1 -> 0. The output increases spacing without adding metal.'),
    ('v1_w1_iso_02', 'clean_success', 'FIXED',
     'V1 square: 12 x 12 -> 18 x 18 nm. Minimum width: 18 nm.',
     'Markers: 2 -> 0. Both width directions pass the scoped checker.'),
    ('v1_w1_int_02', 'clean_success', 'FIXED',
     'V1: 18 x 12 -> 36 x 30 nm. M2 width: 14 -> 32 nm.',
     'Markers: 2 -> 0. Both layers grow; this repair adds extra material.'),
    ('m1_w1_iso_02', 'failed_unchanged', 'NOT FIXED',
     'M1 width stays at 12 nm. Minimum: 18 nm.',
     'Markers: 1 -> 1. The output geometry is unchanged.'),
    ('m1_s1_iso_01', 'failed_unchanged', 'NOT FIXED',
     'M1 wire gap stays at 10 nm. Minimum scoped spacing: 18 nm.',
     'Markers: 1 -> 1. The script runs but does not repair the gap.'),
    ('v1_w1_iso_03', 'regression', 'REGRESSION',
     'V1 square: 14 x 14 -> 18 x 14 nm. One direction still fails.',
     'Markers: 2 -> 1. Saved marker comparison flags one introduced marker.'),
    ('m2_w1_int_01', 'partial_success', 'PARTIAL',
     'M2 width: 14 -> 18 nm. V1 stays at 18 x 12 nm.',
     'Markers: 2 -> 1. M2 is fixed; the V1 width fault remains.'),
    ('m1_s1_iso_05', 'invalid_patch', 'REJECTED',
     'M1 gap: 16 nm. The attempted expansion joins both wires.',
     'Components: 2 -> 1. Preservation rejects the output; no after-DRC.'),
    ('m1_w1_iso_10', 'invalid_patch', 'API ERROR',
     'The M1 branch is 12 nm thick. The script fails before output.',
     'API failure: Box.left_bottom does not exist. No after-DRC result.'),
    ('v1_w1_iso_01', 'invalid_patch', 'API ERROR',
     'V1 input: 10 x 10 nm. It has two width markers.',
     'API failure: Region.interacting receives EdgePairs. No output layout.'),
    ('m1_w1_neg_01', 'invalid_patch', 'CLEAN / ERROR',
     'The 18 nm M1 input already passes. The attempted script crashes.',
     'API failure: PolygonWithProperties.polygon. This is a clean control.'),
    ('m1_w1_iso_08', 'invalid_patch', 'SYNTAX ERROR',
     'M1 has a 12 nm neck inside a 24 nm outside width.',
     'IndentationError at line 60. The repair script cannot start.'),
    ('m1_a1_iso_01', 'model_error', 'JSON ERROR',
     'M1 pad: 18 x 18 nm; area 324 nm2. Minimum area: 504 nm2.',
     'The response omits rationale. Validation stops before script execution.'),
]
INK, MUTED, BORDER = '#18364A', '#506779', '#D7E1E7'
STYLES = {'FIXED': ('#176145', '#E8F3ED'), 'NOT FIXED': ('#8B5811', '#FFF2D8'),
          'PARTIAL': ('#8B5811', '#FFF2D8'), 'REGRESSION': ('#A42C3D', '#FBECEF'),
          'REJECTED': ('#A42C3D', '#FBECEF'), 'API ERROR': ('#A42C3D', '#FBECEF'),
          'CLEAN / ERROR': ('#A42C3D', '#FBECEF'), 'SYNTAX ERROR': ('#A42C3D', '#FBECEF'),
          'JSON ERROR': ('#A42C3D', '#FBECEF')}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def prepare():
    """Verify saved evidence, counts, and the exact intended 10/10 selection."""
    summary_path = CAMPAIGN/'summary.json'
    summary = json.loads(summary_path.read_text())
    manifest_path = BASE/'manifest.json'
    manifest = json.loads(manifest_path.read_text())
    runs = {r['case_id']: r for r in summary['results']}
    cases = {c['case_id']: c for c in manifest['cases']}
    assert len(CASES) == len({c[0] for c in CASES}) == 20
    assert sum(c[1] == 'clean_success' for c in CASES) == 10
    verified = {p: sha(p) for p in [summary_path, manifest_path, ORIGINAL,
                 CAMPAIGN/'campaign.json', CAMPAIGN/'analysis.json',
                 CAMPAIGN/'verification.json', Path(__file__),
                 Path(__file__).with_name('capture_c1_examples.py')]}
    prepared = []
    for spec in CASES:
        cid, verdict, label, note, conclusion = spec
        case, result = cases[cid], runs[cid]
        assert result['verdict'] == verdict, cid
        directory = resolve_record(result['run_dir'])
        audit_path = directory/'run_manifest.json'
        audit = json.loads(audit_path.read_text())
        verified[audit_path] = sha(audit_path)
        for name, expected in audit['artifact_hashes'].items():
            path = directory/name
            assert sha(path) == expected, f'Changed artifact: {path}'
            verified[path] = expected
        assert json.loads((directory/'benchmark_result.json').read_text()) == result
        assert sha(directory/'input.gds') == case['sha256']
        assert sha(directory/'deck.lydrc') == case['acceptance']['deck_sha256']
        a = case['acceptance']
        reference, reference_report = BASE/a['reference_gds'], BASE/a['reference_report']
        for p, expected in [(reference, a['reference_sha256']), (reference_report, a['reference_report_sha256'])]:
            assert sha(p) == expected
            verified[p] = expected
        paths = {'reference': reference, 'input': directory/'input.gds',
                 'output': directory/'patched.gds' if (directory/'patched.gds').exists() else None}
        reports = {'reference': reference_report, 'input': directory/'before.lyrdb',
                   'output': directory/'after.lyrdb' if result['final_total'] is not None else None}
        assert report_counts(reports['reference']) == {}
        assert report_counts(reports['input']) == result['initial_violations']
        if reports['output']:
            assert paths['output'] is not None
            assert report_counts(reports['output']) == result['final_violations']
        else:
            assert not (directory/'after.lyrdb').exists()
        prepared.append((spec, case, result, paths, reports))
    assert sum(p[3]['output'] is None for p in prepared) == 5
    return prepared, verified, summary


def ruler(cid, regions, dbu):
    key = '21/0' if cid.startswith('v1') else '20/0' if cid.startswith('m2') else '19/0'
    region = regions[key]
    box = region.bbox()
    if '_s1_' in cid:
        boxes = sorted([p.bbox() for p in region.each_merged()], key=lambda b:(b.bottom,b.left))
        if len(boxes) != 2:
            return None
        a, b = boxes
        if b.left >= a.right:
            value = (a.right, a.bottom-32, b.left, a.bottom-32)
            length = b.left-a.right
        elif b.bottom >= a.top:
            value = (a.left-32, a.top, a.left-32, b.bottom)
            length = b.bottom-a.top
        else:
            return None
        return (*[x*dbu for x in value], f'{length*dbu*1000:g} nm gap')
    if cid == 'm1_w1_iso_08':
        cy = (box.bottom+box.top)//2
        neck = (region & db.Region(db.Box(box.left,cy,box.right,cy+1))).bbox()
        return (neck.left*dbu, cy*dbu, neck.right*dbu, cy*dbu, f'{neck.width()*dbu*1000:g} nm')
    if cid == 'm1_w1_iso_10':
        return (.05,.03,.05,.042,'12 nm')
    poly = next(region.each_merged())
    if not poly.is_box():
        return None
    b = poly.bbox()
    if b.width() <= b.height():
        value = (b.left, b.bottom-32, b.right, b.bottom-32)
        length = b.width()
    else:
        value = ((b.left+b.right)//2, b.bottom, (b.left+b.right)//2, b.top)
        length = b.height()
    return (*[x*dbu for x in value],f'{length*dbu*1000:g} nm')


def wrap_pixels(draw, value, size, width, bold=False):
    result, line = [], ''
    for word in value.split():
        candidate = f'{line} {word}'.strip()
        if draw.textlength(candidate, font=font(size,bold)) > width and line:
            result.append(line)
            line = word
        else:
            line = candidate
    return result+[line]


def render_panel(path, report, window, target, title, subtitle, stats, measure=None):
    view = lay.LayoutView()
    for key, value in [('background-color','#ffffff'),('foreground-color',INK),
                       ('grid-visible','false'),('text-visible','false')]:
        view.set_config(key,value)
    view.commit_config()
    view.load_layout(str(path), False)
    view.max_hier()
    view.add_missing_layers()
    iterator = view.begin_layers()
    while not iterator.at_end():
        props = iterator.current()
        _, color, pattern = COLORS.get(props.source_layer,('Other',0x777777,3))
        props.fill_color = props.frame_color = color
        props.dither_pattern = pattern
        props.width = 2
        view.set_layer_properties(iterator,props)
        iterator.next()
    markers = overlays(view,report)
    if measure:
        x1,y1,x2,y2,_ = measure
        annotation = lay.Annotation()
        annotation.p1,annotation.p2 = db.DPoint(x1,y1),db.DPoint(x2,y2)
        annotation.fmt = ''
        annotation.style = lay.Annotation.StyleArrowBoth
        view.insert_annotation(annotation)
    actual = db.DBox(*window)
    raw = target.with_suffix('.raw.png')
    view.resize(720,540)
    view.zoom_box(actual)
    view.save_image_with_options(str(raw),720,540,1,1,1,actual,False)
    picture = Image.new('RGB',(720,750),'white')
    with Image.open(raw) as source:
        picture.paste(source.convert('RGB'),(0,90))
    raw.unlink()
    draw = ImageDraw.Draw(picture)
    draw.text((18,10),title,fill=INK,font=font(29,True))
    draw.text((18,51),subtitle,fill=MUTED if report else '#A42C3D',font=font(22))
    draw.line((18,87,702,87),fill=BORDER,width=2)
    if measure:
        x1,y1,x2,y2,label = measure
        x = ((x1+x2)/2-actual.left)/actual.width()*720
        y = 90+(actual.top-(y1+y2)/2)/actual.height()*540
        tw = draw.textlength(label,font=font(22,True))
        x = max(8,min(704-tw,x-tw/2 if y1==y2 else x+12))
        y += 10 if y1==y2 else -14
        draw.rectangle((x-3,y-1,x+tw+3,y+28),fill='white')
        draw.text((x,y),label,fill=INK,font=font(22,True))
    max_nm = actual.width()*1000*132/720
    scale = max(n for n in [1,2,5,10,20,50,100,200] if n<=max_nm)
    length = scale/1000/actual.width()*720
    draw.rectangle((547,582,712,629),fill='white')
    draw.text((550,581),f'{scale:g} nm',fill=INK,font=font(21))
    draw.line((555,618,555+length,618),fill=INK,width=4)
    for x in [555,555+length]:
        draw.line((x,613,x,623),fill=INK,width=3)
    legend_x = 18
    for layer in [19,20,21]:
        name,color,_ = COLORS[layer]
        draw.rectangle((legend_x,653,legend_x+16,669),fill=f'#{color:06x}')
        draw.text((legend_x+22,647),name,fill=INK,font=font(21))
        legend_x += 98
    draw.text((323,647),'Red = saved DRC marker',fill='#B22131',font=font(21))
    sizes = []
    for key, stat in stats.items():
        b=stat['bbox_nm']
        name=COLORS.get(int(key.split('/')[0]),(key,))[0]
        sizes.append(f'{name} bbox: {b[2]-b[0]:g} x {b[3]-b[1]:g} nm')
    for y, line in enumerate(wrap_pixels(draw,' | '.join(sizes),20,684)):
        draw.text((18,685+y*25),line,fill=INK,font=font(20))
    picture.save(target)
    view.destroy()
    return {'image':str(target.relative_to(ROOT)),'sha256':sha(target),
            'gds':str(path.relative_to(ROOT)),'gds_sha256':sha(path),
            'report':str(report.relative_to(ROOT)) if report else None,
            'report_sha256':sha(report) if report else None,'counts':report_counts(report),
            'geometry':stats,'actual_window_um':window,'ruler_um':measure,
            'scale_bar_nm':scale,'size_px':[720,750]}


def no_output(target,label,conclusion,window):
    picture=Image.new('RGB',(720,750),'#F6F8FA')
    draw=ImageDraw.Draw(picture)
    draw.text((18,10),'No output layout',fill=INK,font=font(29,True))
    draw.text((18,51),'After-DRC: not available',fill='#A42C3D',font=font(22))
    draw.line((18,87,702,87),fill=BORDER,width=2)
    draw.rounded_rectangle((32,145,688,603),radius=14,outline='#D4DDE4',width=3,fill='white')
    draw.text((62,185),label,fill='#A42C3D',font=font(30,True))
    y=248
    for line in wrap_pixels(draw,conclusion,27,580):
        draw.text((62,y),line,fill=INK,font=font(27))
        y+=42
    draw.text((62,514),'The original input is shown at left.',fill=MUTED,font=font(23))
    draw.text((62,552),'No replacement geometry is inferred.',fill=MUTED,font=font(23))
    draw.text((18,658),'No output GDS was saved by this attempt.',fill=MUTED,font=font(22))
    draw.text((18,697),'Missing measurements are not zero.',fill='#A42C3D',font=font(23,True))
    picture.save(target)
    return {'image':str(target.relative_to(ROOT)),'sha256':sha(target),'gds':None,
            'report':None,'counts':None,'geometry':None,'actual_window_um':window,
            'size_px':[720,750],'placeholder':True,'reason':conclusion}


def capture(prepared):
    IMAGES.mkdir(parents=True,exist_ok=True)
    records=[]
    for number,(spec,case,result,paths,reports) in enumerate(prepared,1):
        cid,verdict,label,note,conclusion=spec
        geom={role:geometry(path) for role,path in paths.items() if path}
        boxes=[g[3] for g in geom.values()]
        left,bottom=min(b[0] for b in boxes),min(b[1] for b in boxes)
        right,top=max(b[2] for b in boxes),max(b[3] for b in boxes)
        span=max(right-left,top-bottom,.04)
        cx,cy=(left+right)/2,(bottom+top)/2
        width=max((right-left)+.5*span,((top-bottom)+.5*span)*720/540)
        height=width*540/720
        window=[cx-width/2,cy-height/2,cx+width/2,cy+height/2]
        images={}
        for role in ['reference','input','output']:
            target=IMAGES/f'{number:02}_{cid}_{role}.png'
            if paths[role] is None:
                images[role]=no_output(target,label,conclusion,window)
                continue
            counts=report_counts(reports[role])
            subtitle=f'{sum(counts.values())} scoped marker(s)' if counts is not None else 'Rejected; after-DRC not run'
            title={'reference':'Synthetic legal reference','input':'Test input',
                   'output':'Saved rejected attempt' if reports[role] is None else 'Saved Bedrock output'}[role]
            measure=ruler(cid,geom[role][1],geom[role][0].dbu) if role=='input' else None
            images[role]=render_panel(paths[role],reports[role],window,target,title,subtitle,geom[role][2],measure)
            images[role]['component_areas_nm2']={key:[p.area()*(geom[role][0].dbu*1000)**2
                for p in region.each_merged()] for key,region in geom[role][1].items()}
        records.append({'number':number,'case_id':cid,'verdict':verdict,'label':label,
                        'tier':case['tier'],'rule_id':case['rule_id'],'initially_clean':result['initially_clean'],
                        'initial_total':result['initial_total'],'final_total':result['final_total'],
                        'run_dir':str(resolve_record(result['run_dir']).relative_to(ROOT)),
                        'note':note,'conclusion':conclusion,'validation':result['validation'],
                        'marker_comparison':result['marker_comparison'],'images':images})
        print(f'Captured {number:02} {cid}: {label}',flush=True)
    return records


def build_pdf(records,summary):
    for name,file in [('Review','DejaVuSans.ttf'),('ReviewBold','DejaVuSans-Bold.ttf')]:
        pdfmetrics.registerFont(TTFont(name,str(FONTS/file)))
    OUTPUT.parent.mkdir(parents=True,exist_ok=True)
    width,height=landscape(A3)
    pdf=canvas.Canvas(str(OUTPUT),pagesize=(width,height),pageCompression=1)
    pdf.setTitle('C1 Bedrock changes - 20-case quick review')
    pdf.setAuthor('KLayout DRC project')
    pdf.setSubject('10 fixed cases and 10 unsuccessful attempts from the strict-API 100-case run')
    margin,gutter,gap=24,14,10
    cw=(width-2*margin-gutter)/2
    ch=(height-85-28-2*gap)/3
    iw=(cw-32)/3
    ih=iw*750/720
    drawn=[]

    def text(value,x,y,size=9,bold=False,color=INK):
        pdf.setFont('ReviewBold' if bold else 'Review',size)
        pdf.setFillColor(HexColor(color))
        pdf.drawString(x,y,value)

    def fit(value,size,available,bold=False):
        assert pdfmetrics.stringWidth(value,'ReviewBold' if bold else 'Review',size)<=available,value

    def right(value,x,y,size=9):
        pdf.setFont('Review',size)
        pdf.setFillColor(HexColor(MUTED))
        pdf.drawRightString(x,y,value)

    def shell(index):
        row,col=divmod(index,2)
        x=margin+col*(cw+gutter)
        y=height-85-(row+1)*ch-row*gap
        pdf.setFillColor(white)
        pdf.setStrokeColor(HexColor(BORDER))
        pdf.setLineWidth(.6)
        pdf.roundRect(x,y,cw,ch,6,stroke=1,fill=1)
        return x,y

    def paragraph(value,x,y,max_width,size=9,leading=14):
        words=value.split()
        line=''
        for word in words:
            candidate=f'{line} {word}'.strip()
            if pdfmetrics.stringWidth(candidate,'Review',size)>max_width and line:
                text(line,x,y,size,color=MUTED)
                y-=leading
                line=word
            else:
                line=candidate
        if line:
            text(line,x,y,size,color=MUTED)
            y-=leading
        return y

    def header(page):
        pdf.setFillColor(HexColor('#F3F6F8'))
        pdf.rect(0,0,width,height,stroke=0,fill=1)
        pdf.setFillColor(HexColor('#167E81'))
        pdf.rect(0,height-5,width,5,stroke=0,fill=1)
        text('C1 Bedrock changes',margin,height-33,22,True)
        right(f'20-CASE QUICK REVIEW  |  {page} / 4',width-margin,height-30,10)
        section='Successful repairs' if page<=2 else 'Geometry failures' if page==3 else 'Execution and response failures'
        text(f'{section} / qwen.qwen3-coder-next / strict API instructions / one attempt per case',
             margin,height-51,10,color=MUTED)
        x=margin
        for label,color in [('M1','#2476B3'),('M2','#BB780D'),('V1','#8654AA'),('DRC marker','#CF2535')]:
            pdf.setFillColor(HexColor(color))
            pdf.rect(x,height-71,7,7,stroke=0,fill=1)
            text(label,x+12,height-71,8.5,color=MUTED)
            x+=57 if label!='DRC marker' else 110
        text('Matched camera within each case. Scale bars adapt to the window. Bbox is not local width.',
             x+16,height-71,8.5,color=MUTED)
        text('Saved C1 evidence / dataset 1.1.0 / geometry checks only / no new model calls',margin,13,8,color=MUTED)
        right('27 October 2026  |  A3 landscape',width-margin,13,8)

    def card(record,index):
        x,y=shell(index)
        top=y+ch
        text(f'{record["number"]:02}  {record["case_id"]}',x+10,top-16,10,True)
        label=record['label']
        color,fill=STYLES[label]
        sw=pdfmetrics.stringWidth(label,'ReviewBold',8)+16
        pdf.setFillColor(HexColor(fill))
        pdf.roundRect(x+cw-sw-9,top-22,sw,16,4,fill=1,stroke=0)
        text(label,x+cw-sw-1,top-17,8,True,color)
        fit(record['note'],8.4,cw-20)
        fit(record['conclusion'],8.1,cw-20)
        text(record['note'],x+10,top-30,8.4,color=MUTED)
        for col,role in enumerate(['reference','input','output']):
            item=record['images'][role]
            pdf.drawImage(str(ROOT/item['image']),x+10+col*(iw+6),y+20,width=iw,height=ih)
            drawn.append(item['image'])
        text(record['conclusion'],x+10,y+8,8.1,color=MUTED if label=='FIXED' else color)
        pdf.bookmarkHorizontalAbsolute(record['case_id'],top)
        pdf.addOutlineEntry(f'{record["number"]:02} {record["case_id"]} - {label}',record['case_id'])

    def note_card(page):
        x,y=shell(5)
        top=y+ch
        title,items={
            1:('Read the three panels',[
                ('Reference','A synthetic legal seed. It is not the required or smallest repair.'),
                ('Input','The actual test layout. Red lines are saved checker markers.'),
                ('Output','The saved model attempt. All three use the same physical window.'),
                ('Units','One DBU is 0.25 nm. A bbox measures the whole layer extent.'),
                ('Selection','10 fixed and 10 unsuccessful cases, chosen for review diversity.')]),
            2:('Full campaign: 100 cases',[
                ('Dirty inputs',f'{summary["clean_success_count"]}/78 repaired. This selected review has 10 of those repairs.'),
                ('Clean controls','19/22 passed unchanged. Three attempts stopped before output.'),
                ('API / types','15 KLayout binding errors and 2 Python value-type errors.'),
                ('Contract','5 responses omitted rationale and were rejected before execution.'),
                ('Compare','Cases 10 and 14 share input geometry but have different outcomes.')]),
            3:('A lower marker count can still fail',[
                ('Not fixed','The script runs, but the original violation remains.'),
                ('Partial','Case 14 fixes M2 but leaves the via fault.'),
                ('Regression','Case 13 has fewer markers, but the saved matcher flags a new one.'),
                ('Rejected','Case 15 joins wires. Preservation rejects it before after-DRC.'),
                ('Scope','Results cover five curated rules. Electrical correctness is unverified.')]),
            4:('Missing output stays unknown',[
                ('No output','The gray panel is a placeholder, not an imagined repaired layout.'),
                ('API errors','Cases 16-18 stop before a GDS is written. Case 18 starts clean.'),
                ('Syntax','Case 19 cannot start because of an indentation error.'),
                ('JSON','Case 20 returns a script but no rationale, so it is not executed.'),
                ('Evidence','Source hashes, exact run paths, and panel metadata are in image_manifest.json.')])
        }[page]
        text(title,x+12,top-20,12,True)
        by=top-44
        for label,body in items:
            text(label,x+12,by,8.8,True)
            bottom=paragraph(body,x+91,by,cw-107,8.6,12)
            by=min(by-30,bottom-11)
        text('Review examples are not a random or proportionate performance sample.',
             x+12,y+15,8.2,True)

    for page in range(1,5):
        header(page)
        for index,record in enumerate(records[(page-1)*5:page*5]):
            card(record,index)
        note_card(page)
        pdf.showPage()
    assert len(drawn)==len(set(drawn))==60
    pdf.save()
    reader=PdfReader(OUTPUT)
    assert len(reader.pages)==4
    content='\n'.join(p.extract_text() or '' for p in reader.pages)
    for record in records:
        assert record['case_id'] in content
    return 4


def main():
    prepared,verified,summary=prepare()
    records=capture(prepared)
    pages=build_pdf(records,summary)
    for path,expected in verified.items():
        assert sha(path)==expected,f'Source changed: {path}'
    manifest={'schema_version':1,'title':'C1 Bedrock 20-case quick review',
        'campaign':str(CAMPAIGN),'selection':'10 dirty repairs and 10 unsuccessful attempts; non-random',
        'renderer_version':db.__version__,'source_files_unchanged':True,
        'verified_sources':{str(p.relative_to(ROOT)):h for p,h in verified.items()},
        'images_count':60,'geometry_panels':55,'missing_output_panels':5,'cases':records,
        'pdf':{'path':str(OUTPUT.relative_to(ROOT)),'sha256':sha(OUTPUT),'pages':pages}}
    (IMAGES/'image_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    lines=['# C1 Bedrock quick review', '', '[Open the 20-case PDF](../../output/pdf/c1_bedrock_quick_review.pdf)', '',
           'Ten successful repairs and ten unsuccessful attempts from the strict-API 100-case Bedrock campaign.',
           'The selection shows different outcomes. It is not a statistical sample.', '',
           'All geometry and red markers come from saved evidence. Five missing output panels are explicit placeholders.',
           'The original heuristic review and all campaign evidence are unchanged.', '']
    for record in records:
        lines += [f'## {record["number"]:02} {record["case_id"]} - {record["label"]}', '',
                  f'Recorded verdict: `{record["verdict"]}`.', '', record['note'], '', record['conclusion'], '']
        for role in ['reference','input','output']:
            lines += [f'[{role} panel](c1_bedrock_quick_review/{Path(record["images"][role]["image"]).name})', '']
    (ROOT/'docs/reports/c1_bedrock_quick_review.md').write_text('\n'.join(lines))
    print(f'Created {OUTPUT}: {pages} A3 pages, 20 cases, 60 panels; {len(verified)} source hashes verified.')


if __name__=='__main__':
    main()
