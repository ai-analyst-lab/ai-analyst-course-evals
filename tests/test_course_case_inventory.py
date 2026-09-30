"""Student release inventory and all active SQL comparisons; no external calls."""
from copy import deepcopy
from decimal import Decimal
from pathlib import Path

import pytest
import yaml

from course_evals.grader import load_case
from course_evals.graders.deterministic.sql.compare_v2 import compare_results
from course_evals.graders.deterministic.sql.execute_v1 import QueryResult
from course_evals.graders.deterministic.sql.safety_v2 import inspect_sql

ROOT = Path(__file__).resolve().parents[1]
INDEX = yaml.safe_load((ROOT / 'course-cases.yaml').read_text())['suites']
CASES = [case for suite in INDEX.values() for case in suite['cases']]
SQL_CASES = INDEX['session-8-context-repair']['cases']


def test_only_current_course_cases_are_in_student_directory():
    assert len(INDEX['session-6-complete-analysis']['cases']) == 20
    assert len(SQL_CASES) == 16
    ids = {c['case_id'] for c in CASES}
    assert len(ids) == 36
    assert {p.name for p in (ROOT/'cases').iterdir() if p.is_dir()} == ids


@pytest.mark.parametrize('case', CASES, ids=lambda c: c['case_id'])
def test_every_reference_loads_at_its_pinned_version(case):
    directory, reference, grading = load_case(case['case_id'], str(case['case_version']))
    assert directory == ROOT / case['reference_path']
    assert reference['case_id'] == grading['case_id'] == case['case_id']
    for output in grading.get('query_outputs', []):
        assert output['allowed_sources']
    analyst = ROOT.parent / 'ai-analyst'
    if analyst.is_dir():
        public = yaml.safe_load((analyst/case['public_path']/'case.yaml').read_text())
        assert public['case_id'] == case['case_id']
        assert str(public['case_version']) == str(case['case_version'])


def table(rows):
    return QueryResult(columns=({'name':'segment'}, {'name':'value'}),
        rows=tuple((r['segment'], r['value']) for r in rows), query_id='offline',
        elapsed_ms=0, truncated=False)


@pytest.mark.parametrize('case', SQL_CASES, ids=lambda c: c['case_id'])
def test_active_sql_reference_configuration_and_safety(case):
    directory, reference, grading = load_case(case['case_id'], str(case['case_version']))
    assert reference['evaluation_mode'] == grading['evaluation_mode'] == 'sql_results'
    assert not grading.get('model_graders')
    spec = grading['query_outputs'][0]
    assert inspect_sql((directory/'reference.sql').read_text(), allowed_sources=spec['allowed_sources']).passed
    assert (directory/'reference.sql').stat().st_size > 0


SNAPSHOT_CASES = [c for c in SQL_CASES if 'expected' in load_case(c['case_id'], str(c['case_version']))[1]]


@pytest.mark.parametrize('case', SNAPSHOT_CASES, ids=lambda c: c['case_id'])
def test_wrong_answer_detection_for_stored_reference_tables(case):
    _, reference, grading = load_case(case['case_id'], str(case['case_version']))
    spec = grading['query_outputs'][0]
    expected = reference['expected']['results']
    assert compare_results(table(expected), table(expected), spec['comparison'])['pass'] == 1
    wrong = deepcopy(expected)
    wrong[0]['value'] = str(Decimal(str(wrong[0]['value'])) + 1)
    assert compare_results(table(wrong), table(expected), spec['comparison'])['pass'] == 0
    assert compare_results(table(expected[:-1]), table(expected), spec['comparison'])['pass'] == 0
    assert compare_results(table(expected + expected[:1]), table(expected), spec['comparison'])['pass'] == 0
