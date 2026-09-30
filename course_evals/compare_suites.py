"""Matched SQL suite comparisons: preserve regressions and refuse incompatible runs."""
from collections import Counter
import json
import hashlib
from pathlib import Path
from .suite import grading_execution_errors


def _load(path):
    return json.loads(Path(path).read_text())


def compare_suites(before_path, after_path, *, allowed_runtime_changes=None):
    before, after = _load(before_path), _load(after_path)
    for key in ('suite_id', 'suite_version', 'model', 'evaluation_mode'):
        if not before.get(key) or before.get(key) != after.get(key):
            raise ValueError(f'Suite comparison differs or lacks {key}; start matched runs')
    runtime_changes = []
    if not before.get('runtime_and_cases_digest') or before.get('runtime_and_cases_digest') != after.get('runtime_and_cases_digest'):
        if not allowed_runtime_changes:
            raise ValueError('Suite comparison differs or lacks runtime_and_cases_digest; start matched runs')
        def inventory(path, manifest):
            rows = _load(Path(path).parent / 'system-inputs.json')
            digest = hashlib.sha256(json.dumps(rows, sort_keys=True).encode()).hexdigest()
            if digest != manifest.get('runtime_and_cases_digest'):
                raise ValueError('Runtime inventory does not match its recorded digest')
            result = {r['path']: r['sha256'] for r in rows}
            if len(result) != len(rows):
                raise ValueError('Duplicate runtime inventory paths')
            return result
        left, right = inventory(before_path, before), inventory(after_path, after)
        runtime_changes = sorted(p for p in left.keys() | right.keys() if left.get(p) != right.get(p))
        if set(runtime_changes) != set(allowed_runtime_changes):
            raise ValueError(f'Runtime changes differ from the declared intervention: {runtime_changes}')
    if before['evaluation_mode'] != 'sql_results':
        raise ValueError('This comparison measures SQL/result accuracy only')
    def records(manifest):
        rows = manifest.get('cases') or []
        if len(rows) != manifest.get('requested_case_count'):
            raise ValueError('A suite is unfinished; wait for every scheduled case')
        by_id = {row['case_id']: row for row in rows}
        if len(by_id) != len(rows):
            raise ValueError('Duplicate cases')
        return by_id
    a, b = records(before), records(after)
    if a.keys() != b.keys():
        raise ValueError('Suite case sets differ')
    def grade(row):
        if row['status'] != 'locked':
            return {'case_pass': 0, 'status': row['status']}, None
        root = Path(row['run_path'])
        paths = list(root.glob('trials/*/grades/summary.json'))
        if len(paths) != 1:
            raise ValueError(f"Case {row['case_id']} is not graded")
        return _load(paths[0]), _load(root / 'manifest.json')
    compared = []
    for case_id in sorted(a):
        if a[case_id]['case_version'] != b[case_id]['case_version']:
            raise ValueError(f'Case version changed: {case_id}')
        left, lm = grade(a[case_id])
        right, rm = grade(b[case_id])
        if lm and rm:
            lf, rf = lm.get('data_fingerprint', {}), rm.get('data_fingerprint', {})
            if lf.get('status') != 'verified' or rf.get('status') != 'verified' or lf.get('sha256') != rf.get('sha256'):
                raise ValueError(f'Data changed or was not verified: {case_id}')
            if left['grader_versions'] != right['grader_versions']:
                raise ValueError(f'Grader changed: {case_id}')
        passed_before, passed_after = int(left['case_pass']), int(right['case_pass'])
        state = ('kept_pass' if passed_before else 'improved') if passed_after else ('regressed' if passed_before else 'still_not_passing')
        compared.append({'case_id': case_id, 'before_run': a[case_id].get('run_id'), 'after_run': b[case_id].get('run_id'),
                         'before_pass': passed_before, 'after_pass': passed_after, 'change': state,
                         'before_execution_status': a[case_id]['status'], 'after_execution_status': b[case_id]['status'],
                         'before_grading_errors': grading_execution_errors(Path(a[case_id]['run_path'])) if a[case_id].get('run_path') else [],
                         'after_grading_errors': grading_execution_errors(Path(b[case_id]['run_path'])) if b[case_id].get('run_path') else []})
    n = len(compared)
    return {'metric': 'SQL/result accuracy', 'scheduled_cases': n,
            'declared_runtime_changes': runtime_changes,
            'comparison_type': 'context plus declared capability' if runtime_changes else 'context with fixed runtime',
            'before_accuracy': sum(r['before_pass'] for r in compared) / n,
            'after_accuracy': sum(r['after_pass'] for r in compared) / n,
            'changes': dict(Counter(r['change'] for r in compared)), 'cases': compared,
            'before_context': before.get('context_snapshot'), 'after_context': after.get('context_snapshot'),
            'limitations': ['Repeated development cases do not establish generalization.',
                           'A single before/after difference can reflect model variation; inspect regressions and repeat critical cases.',
                           'Delivery logs and query review diagnose a change; they are not substituted for result accuracy.']}
