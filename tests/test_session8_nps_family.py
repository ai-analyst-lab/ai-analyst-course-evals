"""Offline NPS family contracts, exact result mutations and public leakage checks."""
from copy import deepcopy
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import re

import pytest
import yaml

from course_evals.grader import load_case
from course_evals.graders.deterministic.sql.compare_v2 import compare_results
from course_evals.graders.deterministic.sql.execute_v1 import QueryResult
from course_evals.graders.deterministic.sql.safety_v2 import inspect_sql

IDS = ['session8-semantic-paid-response-nps-q4', 'session8-semantic-paid-response-nps-monthly']
ANALYST = Path(__file__).resolve().parents[2]/'ai-analyst'
COURSE = ANALYST.parent/'ai-analytics-for-builders'


def table(rows):
    return QueryResult(columns=({'name':'segment'}, {'name':'value'}),
        rows=tuple((r['segment'],r['value']) for r in rows), query_id='offline-fixture',elapsed_ms=0,truncated=False)


@pytest.mark.parametrize('cid', IDS)
def test_reference_metadata_sql_and_output_gate(cid):
    root, reference, grade = load_case(cid, 'probe-1')
    assert reference['case_id']==grade['case_id']==cid
    assert reference['case_version']==grade['case_version']=='probe-1'
    assert reference['evaluation_mode']==grade['evaluation_mode']=='sql_results'
    assert grade['model_graders']==[]
    assert grade['headline']['required']==['artifact_contract','sql_result']
    output=grade['query_outputs'][0]
    assert output['comparison_version']=='2'
    assert output['comparison']['keys']==['segment']
    assert output['comparison']['columns']['value']['absolute_tolerance']==0
    sql=(root/'reference.sql').read_text()
    assert inspect_sql(sql,allowed_sources=output['allowed_sources']).passed
    # Original generator fingerprints executed SQL before adding its file newline.
    assert hashlib.sha256(sql.removesuffix('\n').encode()).hexdigest()==reference['provenance']['reference_sql_sha256']
    assert reference['provenance']['independent_query_id']
    assert reference['coverage']['intervention']=='guide_and_semantic_model'
    assert reference['coverage']['transfer']==cid.endswith('monthly')


@pytest.mark.parametrize('cid', IDS)
def test_reference_keys_and_four_decimal_nps(cid):
    _, ref, grade=load_case(cid,'probe-1')
    rows=ref['expected']['results']
    assert [r['segment'] for r in rows] == (['2024-Q4'] if cid.endswith('q4')
        else ['2024-10-01','2024-11-01','2024-12-01'])
    for row in rows:
        assert re.fullmatch(r'-?\d+\.\d{4}',row['value'])
        assert -100<=Decimal(row['value'])<=100
    assert compare_results(table(rows[::-1]),table(rows),grade['query_outputs'][0]['comparison'])['pass']==1


@pytest.mark.parametrize('cid', IDS)
@pytest.mark.parametrize('mutation',['missing','duplicate','key','value','precision','null','nonfinite'])
def test_standard_grader_rejects_wrong_results(cid, mutation):
    _,ref,grade=load_case(cid,'probe-1')
    rows=ref['expected']['results']; changed=deepcopy(rows)
    if mutation=='missing': changed=changed[:-1]
    elif mutation=='duplicate': changed+=changed[:1]
    elif mutation=='key': changed[0]['segment']='2024-10-02'
    elif mutation=='value': changed[0]['value']='7.6923'
    elif mutation=='precision': changed[0]['value']=str(Decimal(changed[0]['value'])+Decimal('.00001'))
    elif mutation=='null': changed[0]['value']=None
    elif mutation=='nonfinite': changed[0]['value']='NaN'
    assert compare_results(table(changed),table(rows),grade['query_outputs'][0]['comparison'])['pass']==0


@pytest.mark.parametrize('cid', IDS)
def test_public_private_metadata_match_without_answer_leak(cid):
    if not ANALYST.is_dir(): pytest.skip('Local analyst checkout absent')
    public=ANALYST/'evals/cases/public'/cid/'probe-1'
    case=yaml.safe_load((public/'case.yaml').read_text())
    _,ref,grade=load_case(cid,'probe-1')
    assert case['case_id']==cid and case['case_version']=='probe-1'
    assert case['evaluation_mode']=='sql_results'
    assert case['slices']==ref['slices']
    assert case['data_scope']['snapshot_fingerprint']['sha256']==ref['source']['table_fingerprint']['value']
    assert case['output_contract']['csv'][0]['max_rows']==len(ref['expected']['results'])
    assert case['output_contract']['sql']['columns']==['segment','value']
    assert set(case['required_outputs'])==set(grade['artifact_contract']['required_files'])
    schema=json.loads((public/'result.schema.json').read_text())
    assert schema['properties']['case_id']['const']==cid
    assert schema['additionalProperties'] is False
    assert set(p.name for p in public.iterdir())=={'case.yaml','result.schema.json'}
    content='\n'.join(p.read_text() for p in public.iterdir())
    for forbidden in ['49.0196','66.6667','64.2857','12.5000','7.6923','plus_trial','ENDED_AT',
                      'USER_SEGMENT','reference_sql','source-contract','/Users/']:
        assert forbidden not in content


def test_student_packet_has_source_contract_but_no_finished_answer():
    packet=COURSE/'bootcamp/flagship-restructure/bakeoff/2026-09-03-week0-session1/codex-v5/session-8/student-packets/paid-response-nps-model'
    if not packet.is_dir(): pytest.skip('Local course checkout absent')
    assert not list(packet.rglob('*.yaml'))
    content='\n'.join(p.read_text() for p in packet.rglob('*') if p.is_file() and p.suffix in {'.md','.py'})
    for forbidden in ['49.0196','66.6667','64.2857','12.5000','7.6923','expected_results','reference.json','ai-analyst-course-evals']:
        assert forbidden not in content
    assert 'source_time_policy' in content and 'date_start_of_day' in content
    assert 'warehouse_executed=False' in content
