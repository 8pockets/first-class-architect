"""Validate the separate official-exam learning-objective audit.

A related keyword or card link is not evidence of coverage. Only records with
an explicit semantic review note and verified cards enter the verified count.
"""
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
import re

from principle_catalog.catalog import CatalogError, _load_yaml, _question_audit_sha256
from principle_catalog.models import Catalog

EXAM_COVERAGE_PATH = Path('data/principles/steel/exam-coverage.yaml')
_SCOPES = {'steel', 'steel_cross_topic', 'prerequisite_reference', 'excluded'}
_STATES = {'gap', 'mapped_unverified', 'partial_modality', 'verified'}


@dataclass(frozen=True)
class ExamCoverageAudit:
    years: tuple[int, ...]
    questions: int
    steel_questions: int
    objectives: int
    verified: int
    open_objectives: int
    index_url: str


def load_exam_coverage(catalog: Catalog, path: Path = EXAM_COVERAGE_PATH) -> ExamCoverageAudit:
    data = _load_yaml(path)
    def require(condition: bool, message: str) -> None:
        if not condition:
            raise CatalogError(f'{path}: {message}')

    require(data.get('version') == 1, 'unsupported exam audit version')
    years = tuple(data['scope']['years'])
    require(years == tuple(range(2017, 2027)), 'audit must include 2017–2026')
    sources = data['sources']
    require(len(sources) == 10 and {s['year'] for s in sources} == set(years), 'one official source per year is required')
    for source in sources:
        require(source['url'].startswith('https://www.jaeic.or.jp/'), 'official source URL required')
        require(bool(re.fullmatch('[a-f0-9]{64}', source['sha256'])), 'source PDF digest required')
        require(source['availability'] == 'available', 'source PDF must have been obtained')
    questions = data['questions']
    expected = {(year, number) for year in years for number in range(1, 31)}
    require(len(questions) == 300 and {(q['year'], q['question']) for q in questions} == expected, 'all 300 questions must be screened exactly once')
    by_code = {item.code: item for item in catalog.principles}
    claims = []
    for question in questions:
        require(question['all_choices_text_screened'] == [1, 2, 3, 4], 'every choice must be screened')
        require(question['scope'] in _SCOPES, 'unknown scope')
        if question['scope'] not in {'steel', 'steel_cross_topic'}:
            continue
        records = question.get('claims', [])
        require(bool(records), 'steel question has no learning objectives')
        for claim in records:
            require(claim['coverage'] in _STATES, 'unknown coverage status')
            for code in claim.get('candidate_cards', []):
                require(code in by_code, f'unknown candidate card {code}')
            if claim['coverage'] == 'verified':
                cards = claim.get('verified_cards', [])
                require(bool(cards) and bool(claim.get('verification_note', '').strip()), 'verified coverage needs cards and a semantic review note')
                require(all(code in by_code and by_code[code].editorial_status == 'source_checked' for code in cards), 'verified coverage must map to published cards')
                if claim['modality'] in {'diagram', 'mixed'}:
                    require(question.get('diagram_review') == 'complete', 'diagram review is required')
                if 'hysteresis-diagram' in claim.get('required_objectives', []):
                    require(any(by_code[code].question.figure for code in cards), 'hysteresis coverage requires an actual original figure question')
                if claim['modality'] == 'calculation':
                    require(any(re.search(r'[0-9]', by_code[code].question.prompt) for code in cards), 'calculation coverage requires an actual numerical question')
            claims.append(claim)
    counts = Counter(claim['coverage'] for claim in claims)
    verified_codes = {code for claim in claims if claim['coverage'] == 'verified' for code in claim['verified_cards']}
    revisions = data.get('verified_card_revisions', {})
    require(set(revisions) == verified_codes, 'every verified card needs its audited content revision')
    for code in verified_codes:
        require(revisions[code] == _question_audit_sha256((by_code[code],)), f'verified card content changed; semantic re-review required: {code}')
    summary = data['summary']
    require(summary['questions_text_screened'] == len(questions), 'screened question count mismatch')
    require(summary['choices_text_screened'] == len(questions)*4, 'screened choice count mismatch')
    require(summary['learning_objective_records'] == len(claims), 'objective count mismatch')
    require(summary['fully_verified_learning_objectives'] == counts['verified'], 'verified objective count mismatch')
    require({k:v for k,v in summary['coverage_counts'].items() if v} == dict(counts), 'coverage status counts mismatch')
    scopes = Counter(q['scope'] for q in questions)
    require(dict(scopes) == summary['question_scope_counts'], 'scope counts mismatch')
    return ExamCoverageAudit(years, len(questions), scopes['steel']+scopes['steel_cross_topic'], len(claims), counts['verified'], len(claims)-counts['verified'], data['scope']['official_index'])
