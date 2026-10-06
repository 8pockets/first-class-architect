import pytest
import yaml
from dataclasses import replace

from principle_catalog.catalog import CatalogError, load_catalog
from principle_catalog.exam_coverage import EXAM_COVERAGE_PATH, load_exam_coverage
from principle_catalog.figures import FIGURE_IDS, question_figure


def altered_audit(tmp_path, edit):
    data = yaml.safe_load(EXAM_COVERAGE_PATH.read_text())
    edit(data)
    path = tmp_path / 'exam-coverage.yaml'
    path.write_text(yaml.safe_dump(data, allow_unicode=True))
    return path


def test_ten_year_audit_distinguishes_screening_and_semantic_verification():
    audit = load_exam_coverage(load_catalog())
    assert audit.years == tuple(range(2017, 2027))
    assert audit.questions == 300
    assert audit.steel_questions == 86
    assert audit.objectives == 265
    assert audit.verified == 265
    assert audit.open_objectives == 0


@pytest.mark.parametrize('edit,message', [
    (lambda d: d['questions'].pop(), 'all 300'),
    (lambda d: d['questions'][0].update(all_choices_text_screened=[1,2,3]), 'every choice'),
    (lambda d: d['summary'].update(questions_text_screened=299), 'count mismatch'),
    (lambda d: d['sources'][0].update(url='https://example.com/search'), 'official source'),
])
def test_incomplete_or_inconsistent_screening_is_rejected(tmp_path, edit, message):
    with pytest.raises(CatalogError, match=message):
        load_exam_coverage(load_catalog(), altered_audit(tmp_path,edit))


def test_a_keyword_link_alone_cannot_be_declared_verified(tmp_path):
    def edit(data):
        claim = next(q['claims'][0] for q in data['questions'] if q.get('claims'))
        claim['coverage'] = 'verified'
        claim.pop('verified_cards', None)
        claim.pop('verification_note', None)
    with pytest.raises(CatalogError, match='semantic review note'):
        load_exam_coverage(load_catalog(), altered_audit(tmp_path, edit))


def test_hysteresis_claim_requires_an_actual_figure_question(tmp_path):
    catalog = load_catalog()
    plain = next(item.code for item in catalog.principles if not item.question.figure)
    def edit(data):
        question = next(q for q in data['questions'] if q['year']==2023 and q['question']==18)
        question['claims'][0].update(coverage='verified', verified_cards=[plain], verification_note='test semantic review')
    with pytest.raises(CatalogError, match='actual original figure'):
        load_exam_coverage(catalog, altered_audit(tmp_path, edit))


def test_original_figures_are_versioned_accessible_and_allowlisted():
    assert FIGURE_IDS == {'hysteresis-loops-v1', 'brace-loops-v1'}
    assert question_figure(None) == ''
    for name in FIGURE_IDS:
        figure = question_figure(name)
        assert '<svg ' in figure and 'role="img"' in figure and 'aria-label=' in figure
        assert '自作模式図' in figure
        assert '<image' not in figure and '<script' not in figure
    with pytest.raises(ValueError):
        question_figure('<svg onload="alert(1)">')


def test_changed_teaching_content_requires_semantic_re_review():
    catalog = load_catalog()
    data = yaml.safe_load(EXAM_COVERAGE_PATH.read_text())
    code = next(iter(data['verified_card_revisions']))
    altered = replace(catalog, principles=tuple(
        replace(item, conclusion='changed teaching claim') if item.code == code else item
        for item in catalog.principles
    ))
    with pytest.raises(CatalogError, match='semantic re-review required'):
        load_exam_coverage(altered)
