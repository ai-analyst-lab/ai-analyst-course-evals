"""Public policy conformance: evaluator never imports candidate repository code."""
import pytest
from course_evals.graders.deterministic.sql.safety_v2 import inspect_sql, qualify_table
@pytest.mark.parametrize("sql,passed", [
    ("SELECT * FROM DB.SCH.T", True),
    ("SELECT * FROM db.sch.t", True),
    ('SELECT * FROM "DB"."SCH"."T"', True),
    ('SELECT * FROM "db"."sch"."t"', False),
    ("SELECT * FROM T", False),
    ("SELECT * FROM SCH.T", False),
    ("SELECT * FROM OTHER.SCH.T", False),
    ("WITH t AS (SELECT 1) SELECT * FROM OTHER.SCH.T", False),
    ("WITH t AS (SELECT 1) SELECT * FROM t", True),
    ("WITH x AS (SELECT * FROM DB.SCH.T) SELECT * FROM x", True),
    ("SELECT * FROM DB.SCH.T WHERE EXISTS (WITH t AS (SELECT 1) SELECT * FROM t)", True),
    ("SELECT * FROM DB.SCH.T UNION ALL SELECT * FROM OTHER.SCH.T", False),
    ("SELECT * FROM DB.SCH.T WHERE id IN (SELECT id FROM OTHER.SCH.T)", False),
    ("SELECT 1", True),
    ("SELECT CURRENT_DATABASE(), CURRENT_SCHEMA()", True),
    ("SELECT 'FROM OTHER.SCH.T' AS text -- DELETE\n", True),
    ("SELECT 1; SELECT 2", False),
    ("DELETE FROM DB.SCH.T", False),
    ("CREATE TEMP TABLE X AS SELECT 1", False),
    ("SELECT * INTO X FROM DB.SCH.T", False),
    ("SELECT * FROM IDENTIFIER('DB.SCH.T')", False),
    ("SELECT SYSTEM$SEND_EMAIL('x')", False),
    ("SELECT DB.SCH.F(1)", False),
    ("SELECT * FROM TABLE(GENERATOR(ROWCOUNT => 2))", False),
    ("SELECT * FROM @stage", False),
])
def test_policy(sql, passed):
    result = inspect_sql(sql, allowed_sources=["DB.SCH.T"])
    assert result.passed is passed, result.as_dict()


def test_quoted_dots_and_no_suffix_matching():
    assert inspect_sql('SELECT * FROM "db.x".SCH.T', allowed_sources=['"db.x".SCH.T']).passed
    assert not inspect_sql('SELECT * FROM DB.SCH.T', allowed_sources=[]).passed
    with pytest.raises(ValueError):
        inspect_sql('SELECT * FROM DB.SCH.T', allowed_sources=['SCH.T'])


def test_reference_construction():
    assert qualify_table('orders', database='DB', schema='SCH') == 'DB.SCH.ORDERS'
    assert qualify_table('SCH.ORDERS', database='DB', schema='SCH') == 'DB.SCH.ORDERS'
    assert qualify_table('DB.SCH.ORDERS', database='DB', schema='SCH') == 'DB.SCH.ORDERS'
    assert qualify_table('"lower.dot"', database='DB', schema='SCH') == 'DB.SCH."lower.dot"'
    with pytest.raises(ValueError):
        qualify_table('orders; DELETE FROM x', database='DB', schema='SCH')
