import json
import pytest
import hashlib
from course_evals.compare_suites import compare_suites


def manifests(root):
    base = {'suite_id': 'test', 'suite_version': '1', 'model': 'test-model', 'evaluation_mode': 'sql_results',
            'runtime_and_cases_digest': 'same', 'requested_case_count': 1,
            'cases': [{'case_id': 'a', 'case_version': '1', 'status': 'error', 'run_id': None}]}
    a, b = root / 'a.json', root / 'b.json'
    a.write_text(json.dumps(base))
    b.write_text(json.dumps(base))
    return a, b, base


def test_execution_errors_remain_in_matched_denominator(tmp_path):
    a, b, _ = manifests(tmp_path)
    result = compare_suites(a, b)
    assert result['scheduled_cases'] == 1
    assert result['before_accuracy'] == result['after_accuracy'] == 0
    assert result['cases'][0]['change'] == 'still_not_passing'


@pytest.mark.parametrize('field,value', [('model', 'different'), ('runtime_and_cases_digest', 'changed'), ('suite_version', '2'), ('evaluation_mode', 'full_analysis')])
def test_incompatible_runs_do_not_claim_context_improvement(tmp_path, field, value):
    a, b, base = manifests(tmp_path)
    base[field] = value
    b.write_text(json.dumps(base))
    with pytest.raises(ValueError):
        compare_suites(a, b)


def test_unfinished_case_set_refused(tmp_path):
    a, b, base = manifests(tmp_path)
    base['requested_case_count'] = 2
    b.write_text(json.dumps(base))
    with pytest.raises(ValueError, match='unfinished'):
        compare_suites(a, b)


def test_declared_capability_requires_exact_verified_inventory_diff(tmp_path):
    a, b, base = manifests(tmp_path)
    records = [{'path': 'helpers/base.py', 'sha256': 'a'}]
    paths = []
    for name, rows in [('before', records), ('after', records + [{'path': 'helpers/course_calculations.py', 'sha256': 'b'}])]:
        folder = tmp_path / name
        folder.mkdir()
        (folder / 'system-inputs.json').write_text(json.dumps(rows))
        manifest = dict(base, runtime_and_cases_digest=hashlib.sha256(json.dumps(rows, sort_keys=True).encode()).hexdigest())
        path = folder / 'manifest.json'
        path.write_text(json.dumps(manifest))
        paths.append(path)
    result = compare_suites(*paths, allowed_runtime_changes=['helpers/course_calculations.py'])
    assert result['comparison_type'] == 'context plus declared capability'
    with pytest.raises(ValueError, match='declared intervention'):
        compare_suites(*paths, allowed_runtime_changes=['helpers/other.py'])
    (paths[1].parent / 'system-inputs.json').write_text(json.dumps(records))
    with pytest.raises(ValueError, match='digest'):
        compare_suites(*paths, allowed_runtime_changes=['helpers/course_calculations.py'])
