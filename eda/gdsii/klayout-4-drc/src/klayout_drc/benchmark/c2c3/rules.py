"""Copy scored expressions from the immutable public deck and qualify boundaries."""
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET
import klayout.db as db
from ...config import DEFAULT_RULES_DIR
from ...profile import DRCProfileManager
from ..acceptance import run_checker

NEW_RULES = ('M2.S.1', 'M3.W.1', 'V2.W.1', 'V1.M2.EN.2', 'V2.M2.EN.1', 'V2.M3.EN.2')
CORE_RULES = ('M1.W.1', 'M2.W.1', 'M1.A.1', 'M1.S.1', 'V1.W.1')
PROFILE = 'asap7_c2c3_v1'


def write_deck():
    public = DEFAULT_RULES_DIR/'asap7.lydrc'
    source = ET.parse(public).getroot().findtext('text')
    lines = source.splitlines()
    core = ET.parse(DEFAULT_RULES_DIR/'asap7_curated.lydrc').getroot()
    text = core.findtext('text')
    # Preserve the full upstream copyright and license in the derived artifact.
    license_text = source[source.index('# BSD 2-Clause License'):source.index('#  Based on work')]
    selected, trace = [], {}
    for prefix in ('m2ovlp5v1 = ', 'm3ovlp5v2 = '):
        selected.append(next(line for line in lines if line.startswith(prefix)))
    for rule in NEW_RULES:
        matches = [(i+1, line) for i, line in enumerate(lines) if f'.output("{rule}"' in line]
        if len(matches) != 1:
            raise ValueError(f'Ambiguous or missing public checker expression: {rule}')
        number, expression = matches[0]
        copied = expression
        if rule == 'V2.M2.EN.1':
            expression = 'v2.enclosed(m2, 5.nm, projection, one_side_allowed, two_opposite_sides_allowed).output("V2.M2.EN.1", "C2+C3 corrected: V2 enclosure by M2 on two opposite sides: 5nm")'
        selected.append(expression)
        trace[rule] = {'source_line': number, 'public_expression': copied, 'scored_expression': expression,
                       'correction': 'Report edge-pair errors directly; permit errors only on one side or two opposite sides' if copied != expression else None}
    core.find('description').text = 'ASAP7 C2+C3 scored BEOL profile v1'
    core.find('text').text = license_text + '\n' + text.replace('\ndeep\n', '\nflat\n') + '\nm3 = input(30, 0)\nv2 = input(25, 0)\n' + '\n'.join(selected) + '\n'
    target = DEFAULT_RULES_DIR/'asap7_c2c3_v1.lydrc'
    ET.indent(core)
    target.write_bytes(ET.tostring(core, encoding='utf-8', xml_declaration=True))
    provenance = {'profile': PROFILE, 'upstream_commit': 'd3c27c104e9c4c492a853cb75ae2c03ecd151e45',
                  'source_sha256': hashlib.sha256(public.read_bytes()).hexdigest(),
                  'deck_sha256': hashlib.sha256(target.read_bytes()).hexdigest(),
                  'core_rules': CORE_RULES, 'new_rules': trace}
    target.with_suffix('.provenance.json').write_text(json.dumps(provenance, indent=2)+'\n')
    return target


def boundary_layout(rule, state):
    """Four physical-grid cases; expected labels are verified by the checker."""
    layout = db.Layout(); layout.dbu = .00025
    top = layout.create_cell('QUALIFICATION')
    def box(layer, values):
        top.shapes(layout.layer(layer, 0)).insert(db.Box(*values))
    width = {'legal': 96, 'legal_boundary': 72, 'illegal_boundary': 68, 'illegal': 48}[state]
    if rule in ('M3.W.1', 'V2.W.1'):
        box(30 if rule == 'M3.W.1' else 25, (200, 200, 200+width, 520))
        if rule == 'V2.W.1':
            for layer in (20, 30): box(layer, (172, 172, 228+width, 548))
    elif rule == 'M2.S.1':
        gap = width
        box(20, (200, 200, 520, 520))
        box(20, (520+gap, 200, 840+gap, 520))
    else:
        boundary = 24 if rule == 'V1.M2.EN.2' else 20
        cap = {'legal': 28, 'legal_boundary': boundary, 'illegal_boundary': boundary-4, 'illegal': 0}[state]
        box(21 if rule.startswith('V1') else 25, (200, 200, 272, 272))
        if rule == 'V1.M2.EN.2':
            box(20, (200, 200-cap, 272, 272+cap))
        elif rule == 'V2.M3.EN.2':
            box(20, (172, 172, 300, 300))
            box(30, (200, 200-cap, 272, 272+cap))
        else:
            box(20, (200-cap, 200-cap, 272+cap, 272+cap))
            box(30, (172, 172, 300, 300))
    return layout


def qualify_rules(output):
    output = Path(output); output.mkdir(parents=True, exist_ok=True)
    profile = DRCProfileManager().get_profile(PROFILE)
    rows = []
    for rule in NEW_RULES:
        for state in ('legal', 'legal_boundary', 'illegal_boundary', 'illegal'):
            stem = rule.replace('.', '_')+'_'+state
            gds, report = output/f'{stem}.gds', output/f'{stem}.lyrdb'
            layout = boundary_layout(rule, state)
            options = db.SaveLayoutOptions(); options.gds2_write_timestamps = False
            layout.write(str(gds), options)
            observed = run_checker(gds, profile, report)
            expected_dirty = state.startswith('illegal')
            actual_dirty = observed.rule_summary.get(rule, 0) > 0
            rows.append({'rule': rule, 'state': state, 'observed': observed.rule_summary,
                         'passed': actual_dirty == expected_dirty and (expected_dirty or not observed.total_violations),
                         'nominal_enclosure_um': .005 if '.EN.' in rule else None,
                         'boundary_basis': 'observed pinned-checker transition on the 1 nm manufacturing grid',
                         'manufacturing_grid_um': .001,
                         'gds_sha256': hashlib.sha256(gds.read_bytes()).hexdigest()})
    from .evaluator import checker_identity
    result = {'profile': PROFILE, 'checker': checker_identity(),
              'deck_sha256': hashlib.sha256(profile.deck_path.read_bytes()).hexdigest(),
              'passed': all(row['passed'] for row in rows), 'cases': rows}
    (output/'qualification.json').write_text(json.dumps(result, indent=2)+'\n')
    return result
