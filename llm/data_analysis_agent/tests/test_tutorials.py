"""Check the shipped tutorial inputs, evidence and offline pack without model calls."""

from html.parser import HTMLParser
import json
from pathlib import Path
from urllib.parse import unquote, urlsplit
import zipfile

import pandas as pd
import pytest

from scripts.build_tutorials import embedded, filename
from scripts.tutorial_data import PACK, ROOT, sha
from scripts.tutorial_specs import LESSONS, expected
from scripts.tutorial_validate import prompt_hash


@pytest.mark.parametrize('key,rows,used', [
    ('penguins', 344, 342), ('retail', 99602, 97214),
    ('wine', 6497, 6497), ('bike', 731, 731),
])
def test_public_csv_provenance_and_practice(key, rows, used):
    metadata = json.loads((PACK / 'manifest.json').read_text())['datasets'][key]
    source = PACK / metadata['file']
    frame = pd.read_csv(source)
    assert len(frame) == rows == metadata['rows']
    assert source.stat().st_size < 100 * 1024**2
    assert sha(source) == metadata['sha256']
    assert set(frame.columns) == set(metadata['dictionary'])
    assert metadata['license'] and metadata['retrieved_at'] and metadata['source_sha256']
    count_name = {'penguins':'Records used', 'retail':'Invoice lines', 'wine':'Samples', 'bike':'Days'}[key]
    assert expected(key, frame)[count_name] == used
    practice = metadata['practice']
    replacement = pd.read_csv(PACK / practice['replacement'])
    invalid = pd.read_csv(PACK / practice['invalid'])
    assert list(replacement.columns) == list(frame.columns)
    assert len(replacement) == practice['rows']
    assert set(invalid.columns) == set(frame.columns) - {practice['removed_column']}
    for name in ['replacement', 'invalid']:
        assert sha(PACK / practice[name]) == practice[name + '_sha256']


def test_embedded_chart_data_cannot_close_its_script_element():
    value = {'label': '</script><script>alert(1)</script>\u2028\u2029'}
    encoded = embedded(value)
    assert '<' not in encoded and '\u2028' not in encoded and '\u2029' not in encoded
    assert json.loads(encoded) == value


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self.ids = set()
        self.csp = ''
    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if a.get('id'): self.ids.add(a['id'])
        for field in ('src', 'href'):
            if a.get(field): self.links.append((tag, field, a[field]))
        if a.get('http-equiv') == 'Content-Security-Policy': self.csp = a['content']


def test_all_offline_links_and_assets_resolve():
    pages = list(PACK.glob('*.html'))
    assert len(pages) == 6
    for page in pages:
        parsed = Links(); parsed.feed(page.read_text())
        assert "connect-src 'none'" in parsed.csp
        for tag, field, raw in parsed.links:
            url = urlsplit(raw)
            if url.scheme:
                # Only optional source hyperlinks may leave the extracted pack.
                assert tag == 'a' and field == 'href' and url.scheme == 'https'
                continue
            target = (page.parent / unquote(url.path)).resolve() if url.path else page
            assert target.is_relative_to(PACK.resolve()) and target.is_file(), (page, raw)
            if url.fragment:
                other = Links(); other.feed(target.read_text())
                assert unquote(url.fragment) in other.ids, (page, raw)


def test_published_pages_match_real_model_evidence_and_zip():
    manifest = json.loads((PACK / 'manifest.json').read_text())
    validation = json.loads((PACK / 'validation.json').read_text())
    for lesson in LESSONS:
        key = lesson['key']; evidence = validation['lessons'][key]
        assert evidence['status'] == 'passed'
        assert evidence['prompt_sha256'] == prompt_hash(lesson)
        assert evidence['input_sha256'] == manifest['datasets'][key]['sha256']
        assert [p['status'] for p in evidence['prompts']] == ['passed', 'passed']
        assert evidence['invalid_schema_retains_results'] and evidence['acceptance_passed']
        assert (PACK / filename(lesson)).is_file()
    with zipfile.ZipFile(ROOT / 'artifacts' / 'wps-ai-tutorial-pack.zip') as archive:
        for path in PACK.rglob('*'):
            if path.is_file():
                assert archive.read('wps-ai-tutorials/' + str(path.relative_to(PACK))) == path.read_bytes()


@pytest.mark.parametrize('lesson', LESSONS, ids=lambda item: item['key'])
def test_reference_chart_values_match_source(lesson):
    from pipeline_core.models import ProjectRevision, RunRecord
    from scripts.tutorial_validate import check_extra
    reference = json.loads((PACK / 'reference' / (lesson['key'] + '.json')).read_text())
    check_extra(lesson, pd.read_csv(PACK / 'data' / lesson['file']),
                ProjectRevision.model_validate(reference['revision']), RunRecord.model_validate(reference['run']))
