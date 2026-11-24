from dev_insights.signature import sql_signature


def test_literals_and_params_become_placeholders():
    a = 'SELECT * FROM "author" WHERE "author"."id" = 1 LIMIT 21'
    b = 'SELECT * FROM "author" WHERE "author"."id" = 42 LIMIT 21'
    c = 'SELECT * FROM "author" WHERE "author"."id" = %s LIMIT %s'
    assert sql_signature(a) == sql_signature(b) == sql_signature(c)
    assert sql_signature(a) == 'SELECT * FROM "author" WHERE "author"."id" = ? LIMIT ?'


def test_strings_with_escaped_quotes():
    sql = "SELECT 1 FROM t WHERE name = 'O''Brien' AND city = 'São Paulo'"
    assert sql_signature(sql) == "SELECT ? FROM t WHERE name = ? AND city = ?"


def test_in_lists_of_any_size_collapse():
    two = "SELECT * FROM t WHERE id IN (1, 2)"
    five = "SELECT * FROM t WHERE id IN (%s, %s, %s, %s, %s)"
    assert (
        sql_signature(two) == sql_signature(five) == "SELECT * FROM t WHERE id IN (...)"
    )


def test_bulk_values_collapse():
    one = "INSERT INTO t (a, b) VALUES (%s, %s)"
    three = "INSERT INTO t (a, b) VALUES (%s, %s), (%s, %s), (%s, %s)"
    assert sql_signature(one) == sql_signature(three)


def test_digits_inside_identifiers_are_kept():
    sql = 'SELECT "t1"."col2", t3.x FROM "t1" JOIN t3 ON t3.id = "t1".id2'
    assert sql_signature(sql) == sql


def test_named_placeholders_and_whitespace():
    sql = "SELECT *\n  FROM t\n WHERE a = %(a)s AND b = ?"
    assert sql_signature(sql) == "SELECT * FROM t WHERE a = ? AND b = ?"


def test_different_queries_keep_different_signatures():
    assert sql_signature("SELECT * FROM a WHERE id = 1") != sql_signature(
        "SELECT * FROM b WHERE id = 1"
    )
    assert sql_signature("SELECT * FROM a WHERE id = 1") != sql_signature(
        "SELECT * FROM a WHERE id IS NULL"
    )


def test_empty():
    assert sql_signature("") == "" and sql_signature(None) == ""
