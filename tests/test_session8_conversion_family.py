from copy import deepcopy
from decimal import Decimal
from pathlib import Path
import pytest
import yaml
from course_evals.grader import load_case
from course_evals.graders.deterministic.sql.compare_v2 import compare_results
from course_evals.graders.deterministic.sql.execute_v1 import QueryResult
from course_evals.graders.deterministic.sql.safety_v2 import inspect_sql

IDS = ['session8-semantic-purchase-conversion-november', 'session8-semantic-purchase-conversion-monthly']

def table(rows):
    return QueryResult(columns=({'name':'segment'}, {'name':'value'}), rows=tuple((r['segment'], r['value']) for r in rows), query_id='fixture', elapsed_ms=0, truncated=False)

@pytest.mark.parametrize('cid', IDS)
def test_contract_and_mutations(cid):
    root, reference, grade = load_case(cid, 'probe-1')
    output = grade['query_outputs'][0]
    assert inspect_sql((root/'reference.sql').read_text(), allowed_sources=output['allowed_sources']).passed
    rows = reference['expected']['results']
    config = output['comparison']
    assert compare_results(table(rows[::-1]), table(rows), config)['pass'] == 1
    wrong = deepcopy(rows)
    wrong[0]['value'] = str(Decimal(wrong[0]['value']) + Decimal('.01'))
    for mutation in [wrong, rows[:-1], rows+rows[:1], [dict(r, value=None) for r in rows]]:
        assert compare_results(table(mutation), table(rows), config)['pass'] == 0
    analyst = Path(__file__).resolve().parents[2]/'ai-analyst'
    public = yaml.safe_load((analyst/'evals/cases/public'/cid/'probe-1/case.yaml').read_text())
    assert public['slices'] == reference['slices']
    assert public['data_scope']['snapshot_fingerprint']['sha256'] == reference['source']['table_fingerprint']['value']
    assert grade['model_graders'] == []
    assert not any(word in public['task'] for word in ['purchase_complete', 'HAD_PURCHASE', 'EVENT_TYPE'])
