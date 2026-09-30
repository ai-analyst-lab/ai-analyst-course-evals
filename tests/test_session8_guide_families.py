"""Active service-recovery guide contracts; offline only, no model calls."""
from copy import deepcopy
from decimal import Decimal
import hashlib
import json
from pathlib import Path

import pytest
import yaml

from course_evals.grader import load_case
from course_evals.graders.deterministic.sql.compare_v2 import compare_results
from course_evals.graders.deterministic.sql.execute_v1 import QueryResult
from course_evals.graders.deterministic.sql.safety_v2 import inspect_sql

IDS = ['session8-guide-service-recovery-november', 'session8-guide-service-recovery-monthly']
ANALYST = Path(__file__).resolve().parents[2] / 'ai-analyst'


def table(rows, columns=('segment','value')):
    return QueryResult(columns=tuple({'name': c} for c in columns),
                       rows=tuple((r['segment'],r['value']) for r in rows),
                       query_id='offline-fixture', elapsed_ms=0, truncated=False)


@pytest.mark.parametrize('cid', IDS)
def test_reference_contract_and_frozen_sql(cid):
    root, reference, grading = load_case(cid, '1')
    assert reference['case_version']==grading['case_version']=='1'
    assert reference['evaluation_mode']==grading['evaluation_mode']=='sql_results'
    assert grading['model_graders']==[]
    assert 'engineering' in reference['review_status']
    sql=(root/'reference.sql').read_text()
    output=grading['query_outputs'][0]
    assert inspect_sql(sql,allowed_sources=output['allowed_sources']).passed
    assert hashlib.sha256(sql.encode()).hexdigest()==reference['provenance']['reference_sql_sha256']
    assert 'AS "segment"' in sql and 'AS "value"' in sql
    assert output['comparison_version']=='2'
    assert reference['source']['table_fingerprint']['value']=='c7e6b8580027b9c9f090eeb68c9bd476232553ebc9338199f301817121d51ea0'
    assert reference['provenance']['reference_query_id']
    expected=reference['expected']['results']
    assert compare_results(table(list(reversed(expected))),table(expected),output['comparison'])['pass']==1


@pytest.mark.parametrize('cid', IDS)
@pytest.mark.parametrize('mutation', ['missing','duplicate','wrong_key','wrong_value','null','nonfinite','precision'])
def test_standard_grader_rejects_mutations(cid,mutation):
    _,reference,grading=load_case(cid,'1')
    expected=reference['expected']['results']
    changed=deepcopy(expected)
    if mutation=='missing': changed=changed[:-1]
    elif mutation=='duplicate': changed+=deepcopy(changed[:1])
    elif mutation=='wrong_key': changed[0]['segment']='not-a-source-group'
    elif mutation=='wrong_value': changed[0]['value']=str(Decimal(str(changed[0]['value']))+1)
    elif mutation=='null': changed[0]['value']=None
    elif mutation=='nonfinite': changed[0]['value']='NaN'
    elif mutation=='precision': changed[0]['value']=str(Decimal(str(changed[0]['value']))+Decimal('.00001'))
    assert compare_results(table(changed),table(expected),grading['query_outputs'][0]['comparison'])['pass']==0


@pytest.mark.parametrize('cid', IDS)
def test_source_specific_wrong_definition_rejected(cid):
    root,reference,grading=load_case(cid,'1')
    for mutation in json.loads((root/'mutations.json').read_text()).values():
        assert compare_results(table(mutation['rows']),table(reference['expected']['results']),grading['query_outputs'][0]['comparison'])['pass']==0


@pytest.mark.parametrize('cid', IDS)
def test_public_contract_has_no_answer_or_implementation(cid):
    if not ANALYST.is_dir(): pytest.skip('Local analyst checkout absent')
    public=ANALYST/'evals/cases/public'/cid/'v1'
    case=yaml.safe_load((public/'case.yaml').read_text())
    _,reference,grading=load_case(cid,'1')
    assert case['case_id']==cid and case['case_version']=='1'
    assert case['slices']==reference['slices']
    assert case['data_scope']['snapshot_fingerprint']['sha256']==reference['source']['table_fingerprint']['value']
    assert set(case['required_outputs'])==set(grading['artifact_contract']['required_files'])
    schema=json.loads((public/'result.schema.json').read_text())
    assert schema['properties']['case_id']['const']==cid
    for forbidden in ['2345','2.2917','payment_issue','plus_trial','ENDED_AT','IS_PLUS_MEMBER_ORDER','reference_sql','/Users/']:
        assert forbidden not in (public/'case.yaml').read_text()
    assert reference['coverage']['guides'] in [['support-service-recovery'],['paid-plus-access-history']]


def test_column_casing_is_separate_from_standard_comparator():
    _,reference,grading=load_case(IDS[0],'1')
    expected=reference['expected']['results']
    assert compare_results(table(expected,('SEGMENT','VALUE')),table(expected),grading['query_outputs'][0]['comparison'])['pass']==1
    assert 'separately audited' in reference['provenance']['caveat']
