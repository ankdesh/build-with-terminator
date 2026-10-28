#!/usr/bin/env python3
"""Place all 32 saved C1 guide images in a separate two-page PDF.

Uses Pillow and reportlab. Does not run KLayout or modify source evidence.
"""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path
from klayout_drc.handoff.report_paths import ROOT, FONTS, resolve_record

from PIL import Image
from reportlab.lib.colors import HexColor, white
from reportlab.lib.pagesizes import A3, landscape
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

SOURCE = ROOT / 'docs/reports/c1_visual_guide/image_manifest.json'
OUTPUT = ROOT / 'output/pdf/c1_heuristic_quick_review.pdf'
INK = '#18364A'
MUTED = '#506779'
BORDER = '#D7E1E7'
STATUS = {
    'clean_success': ('ACCEPTED', '#176145', '#E8F3ED'),
    'unnecessary_edit': ('UNNEEDED EDIT', '#8B5811', '#FFF2D8'),
    'invalid_patch': ('REJECTED', '#A42C3D', '#FBECEF'),
}
NOTES = {
    'm1_w1_iso_01': (
        'M1 width: 10 -> 32 nm. Minimum: 18 nm.',
        'Scoped markers: 1 -> 0. The wire grows beyond the minimum width.'),
    'm1_w1_iso_08': (
        'M1 neck width: 12 -> 24 nm. Minimum: 18 nm.',
        'Scoped markers: 1 -> 0. The overall bounding box hides the narrow neck.'),
    'm1_w1_bnd_01': (
        'M1 width: 17.75 -> 39.75 nm. Minimum: 18 nm.',
        'Scoped markers: 1 -> 0. The input is one database step below the limit.'),
    'm1_w1_bnd_04': (
        'M1 width: 18 -> 30 nm. The input already passes.',
        'Scoped markers: 0 -> 0. The heuristic changes a clean control.'),
    'm2_w1_iso_06': (
        'M2 width: 12 -> 22 nm. Minimum: 18 nm.',
        'Scoped markers: 1 -> 0. The horizontal wire grows on M2.'),
    'm1_a1_iso_01': (
        'M1 pad: 18 x 18 -> 30 x 30 nm. Minimum area: 504 nm2.',
        'Scoped markers: 1 -> 0. The pad area grows from 324 to 900 nm2.'),
    'm1_s1_iso_01': (
        'M1 gap: 10 nm. The output joins two separate wires.',
        'Components: 2 -> 1. Patch rejected; after-DRC was not run.'),
    'm1_s1_neg_03': (
        'M1 gap: 12 nm. The clean input has short facing edges.',
        'Components: 2 -> 1. Patch rejected; after-DRC was not run.'),
    'v1_w1_iso_01': (
        'V1 cut: 10 x 10 -> 20 x 20 nm. The output also adds M1.',
        'Scoped markers: 2 -> 0. Via width passes; enclosure is not checked here.'),
    'm2_w1_int_02': (
        'Widths: M1 12 -> 34 nm; M2 12 -> 22 nm.',
        'Scoped markers: 2 -> 0. The output widens both crossing layers.'),
}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_sources(manifest: dict) -> list[dict]:
    """Fail before authoring if an image is missing, changed, or unlisted."""
    cases = manifest['cases']
    images = []
    assert len(cases) == 10
    assert [case['number'] for case in cases] == list(range(1, 11))
    assert set(NOTES) == {case['case_id'] for case in cases}
    for case in cases:
        panels = [case['images'][role] for role in ('reference', 'input', 'output')]
        assert len({tuple(panel['actual_window_um']) for panel in panels}) == 1
        if case['verdict'] == 'invalid_patch':
            assert panels[2]['counts'] is None
            assert panels[2]['report'] is None
        images.extend(panels)
        if 'edge_detail' in case:
            images.append(case['edge_detail'])
    assert len(images) == manifest['images_count'] == 32
    assert {ROOT / item['image'] for item in images} == set(SOURCE.parent.glob('*.png'))
    for item in images:
        path = ROOT / item['image']
        assert digest(path) == item['sha256'], f'Image hash mismatch: {path}'
        with Image.open(path) as picture:
            assert list(picture.size) == item['size_px']
    return images


def build_pdf(manifest: dict) -> None:
    images = verify_sources(manifest)
    originals = {ROOT / item['image']: item['sha256'] for item in images}
    originals[SOURCE] = digest(SOURCE)
    old_pdf = ROOT / manifest['pdf']['path']
    originals[old_pdf] = digest(old_pdf)
    for name, file in [('Review', 'DejaVuSans.ttf'), ('ReviewBold', 'DejaVuSans-Bold.ttf')]:
        pdfmetrics.registerFont(TTFont(name, str(FONTS / file)))

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    width, height = landscape(A3)
    pdf = canvas.Canvas(str(OUTPUT), pagesize=(width, height), pageCompression=1)
    pdf.setTitle('C1 heuristic changes - two-page quick review')
    pdf.setAuthor('KLayout DRC project')
    pdf.setSubject('All 32 saved images: 10 example cases and 2 boundary close-ups')
    margin, gutter, row_gap = 24, 14, 10
    card_width = (width - 2 * margin - gutter) / 2
    card_height = (height - 85 - 28 - 2 * row_gap) / 3
    image_width = (card_width - 20 - 12) / 3
    image_height = image_width * 750 / 720
    drawn = []

    def text(value, x, y, size=9, bold=False, color=INK):
        pdf.setFont('ReviewBold' if bold else 'Review', size)
        pdf.setFillColor(HexColor(color))
        pdf.drawString(x, y, value)

    def right(value, x, y, size=9, color=MUTED):
        pdf.setFont('Review', size)
        pdf.setFillColor(HexColor(color))
        pdf.drawRightString(x, y, value)

    def fit(value, size, available, bold=False):
        font = 'ReviewBold' if bold else 'Review'
        assert pdfmetrics.stringWidth(value, font, size) <= available, value

    def shell(x, y):
        pdf.setFillColor(white)
        pdf.setStrokeColor(HexColor(BORDER))
        pdf.setLineWidth(0.6)
        pdf.roundRect(x, y, card_width, card_height, 6, stroke=1, fill=1)

    def slot(index):
        row, col = divmod(index, 2)
        return (margin + col * (card_width + gutter),
                height - 85 - (row + 1) * card_height - row * row_gap)

    def draw_image(record, x, y):
        pdf.drawImage(str(ROOT / record['image']), x, y,
                      width=image_width, height=image_height)
        drawn.append(record['image'])

    def header(page):
        pdf.setFillColor(HexColor('#F3F6F8'))
        pdf.rect(0, 0, width, height, stroke=0, fill=1)
        pdf.setFillColor(HexColor('#167E81'))
        pdf.rect(0, height - 5, width, 5, stroke=0, fill=1)
        text('C1 heuristic changes', margin, height - 33, 22, True)
        right(f'QUICK REVIEW  |  {page} / 2', width - margin, height - 30, 10)
        text('32 existing images / 10 selected cases / reference, input and output in each row',
             margin, height - 51, 10, color=MUTED)
        x = margin
        for label, color in [('M1', '#2476B3'), ('M2', '#BB780D'), ('V1', '#8654AA'), ('DRC marker', '#CF2535')]:
            pdf.setFillColor(HexColor(color))
            pdf.rect(x, height - 71, 7, 7, stroke=0, fill=1)
            text(label, x + 12, height - 71, 8.5, color=MUTED)
            x += 57 if label != 'DRC marker' else 112
        text('Matched scale within each case. Main scale bars: 20 nm. Edge close-ups: 1 nm.',
             x + 16, height - 71, 8.5, color=MUTED)
        text('C1 corrected heuristic / dataset 1.1.0 / geometry checks only', margin, 13, 8, color=MUTED)
        right('27 October 2026  |  A3 landscape', width - margin, 13, 8)

    def case_card(case, index):
        x, y = slot(index)
        shell(x, y)
        top = y + card_height
        title = f'{case["number"]:02d}  {case["case_id"]}'
        text(title, x + 10, top - 16, 10, True)
        status, color, fill = STATUS[case['verdict']]
        status_width = pdfmetrics.stringWidth(status, 'ReviewBold', 8) + 16
        pdf.setFillColor(HexColor(fill))
        pdf.roundRect(x + card_width - status_width - 9, top - 22, status_width, 16, 4, fill=1, stroke=0)
        text(status, x + card_width - status_width - 1, top - 17, 8, True, color)
        note, conclusion = NOTES[case['case_id']]
        fit(note, 8.4, card_width - 20)
        fit(conclusion, 8.2, card_width - 20)
        text(note, x + 10, top - 30, 8.4, color=MUTED)
        for col, role in enumerate(('reference', 'input', 'output')):
            draw_image(case['images'][role], x + 10 + col * (image_width + 6), y + 20)
        text(conclusion, x + 10, y + 8, 8.2, color=color if case['verdict'] != 'clean_success' else MUTED)
        pdf.bookmarkHorizontalAbsolute(case['case_id'], top)
        pdf.addOutlineEntry(f'{case["number"]:02d} {case["case_id"]} - {status}', case['case_id'])

    def details_card():
        x, y = slot(5)
        shell(x, y)
        top = y + card_height
        text('Boundary close-ups: one database step', x + 10, top - 16, 10, True)
        text('Exact input edges from cases 03 and 04. Same camera and zoom.', x + 10, top - 30, 8.4, color=MUTED)
        for col, case in enumerate(manifest['cases'][2:4]):
            draw_image(case['edge_detail'], x + 10 + col * (image_width + 6), y + 20)
        tx = x + 10 + 2 * (image_width + 6)
        for dy, value, size, bold, color in [
            (175, '17.75 nm = 71 DBU', 10, True, INK),
            (158, '1 width marker', 9, False, '#A42C3D'),
            (125, '18 nm = 72 DBU', 10, True, INK),
            (108, '0 width markers', 9, False, '#176145'),
            (73, 'Difference: 0.25 nm', 10, True, INK),
            (55, 'Full wire views can hide', 9, False, MUTED),
            (41, 'this small difference.', 9, False, MUTED),
        ]:
            fit(value, size, image_width, bold)
            text(value, tx, y + dy, size, bold, color)
        text('The extra images show the actual right edge of each input wire.', x + 10, y + 8, 8.2, color=MUTED)

    def notes_card():
        x, y = slot(5)
        shell(x, y)
        top = y + card_height
        text('Read the results', x + 12, top - 19, 12, True)
        counts = Counter(case['verdict'] for case in manifest['cases'])
        for col, verdict in enumerate(STATUS):
            label, color, fill = STATUS[verdict]
            bx = x + 12 + col * (card_width - 24) / 3
            bw = (card_width - 36) / 3
            pdf.setFillColor(HexColor(fill))
            pdf.roundRect(bx, top - 77, bw, 44, 4, fill=1, stroke=0)
            text(str(counts[verdict]), bx + 10, top - 55, 19, True, color)
            text(label, bx + 35, top - 53, 8.1, True, color)
        lines = [
            ('Reference', 'Synthetic legal comparison; it is not a minimum repair.'),
            ('Input', 'Red lines show saved DRC markers on the test geometry.'),
            ('Output', 'Saved heuristic attempt. Rejected outputs are shown too.'),
            ('Rejected', 'Both outputs join two components. After-DRC was not run.'),
            ('Scope', 'Five selected rules plus recorded preservation checks.'),
        ]
        baseline = top - 98
        for label, body in lines:
            text(label, x + 12, baseline, 8.5, True)
            fit(body, 8.4, card_width - 90)
            text(body, x + 83, baseline, 8.4, color=MUTED)
            baseline -= 18
        text('A pass does not establish electrical correctness or full-deck compliance.',
             x + 12, y + 22, 8.5, True)
        text('Source: saved C1 image manifest. All 32 source image hashes verified.',
             x + 12, y + 8, 8, color=MUTED)

    for page, cases in enumerate((manifest['cases'][:5], manifest['cases'][5:]), start=1):
        header(page)
        for index, case in enumerate(cases):
            case_card(case, index)
        details_card() if page == 1 else notes_card()
        pdf.showPage()
    assert Counter(drawn) == Counter(item['image'] for item in images)
    pdf.save()
    for path, expected in originals.items():
        assert digest(path) == expected, f'Source changed: {path}'
    print(f'Created {OUTPUT}: 2 A3 landscape pages; all 32 images included once.')


if __name__ == '__main__':
    build_pdf(json.loads(SOURCE.read_text()))
