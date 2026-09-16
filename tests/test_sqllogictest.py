from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SPEC = importlib.util.spec_from_file_location("picc_sqllogictest", ROOT / "studies" / "runtime" / "sql" / "sqllogictest.py")
assert SPEC is not None and SPEC.loader is not None
slt = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = slt
SPEC.loader.exec_module(slt)


class ParserTests(unittest.TestCase):
    def test_records_conditions_comments_and_halt(self) -> None:
        text = (
            "# comment\nhash-threshold 3\n\nstatement ok\nCREATE TABLE t(a)\n\n"
            "onlyif mysql # note\nquery I nosort\nSELECT 1 DIV 1\n----\n1\n\n"
            "skipif sqlite\nstatement ok\nBOGUS\n\n"
            "query II rowsort lbl\nSELECT a, b\n  FROM t\n----\n1\n2\n\n"
            "statement error\nSELECT nothing\n\nhalt\n\nquery I nosort\nSELECT 2\n----\n2\n"
        )
        records = slt.parse_script(text)
        self.assertEqual([r.kind for r in records], ["hash-threshold", "statement", "query", "statement", "query", "statement", "halt", "query"])
        self.assertEqual(records[0].threshold, 3)
        self.assertTrue(records[2].skipped)
        self.assertTrue(records[3].skipped)
        query = records[4]
        self.assertEqual((query.types, query.sort, query.label), ("II", "rowsort", "lbl"))
        self.assertEqual(query.sql, "SELECT a, b\n  FROM t")
        self.assertEqual(query.expected, ["1", "2"])
        self.assertEqual(records[5].expect, "error")
        executed = slt.statements_of(records)
        self.assertEqual([r.line for r in executed], [4, 17, 24])
        self.assertTrue(slt.script_input(executed).startswith("CREATE TABLE t(a);\n\nSELECT a, b\n  FROM t;\n\nSELECT nothing;\n"))

    def test_query_without_results_and_bad_records(self) -> None:
        records = slt.parse_script("query I nosort\nSELECT 1 WHERE 0\n----\n\nquery X nosort\nSELECT 1\n\nfrobnicate\n")
        self.assertEqual(records[0].expected, [])
        self.assertEqual(records[1].kind, "invalid")
        self.assertEqual(records[2].kind, "invalid")


class RenderingTests(unittest.TestCase):
    def test_typed_rendering_matches_reference_runner(self) -> None:
        self.assertEqual(slt.render_typed(None, "I"), "NULL")
        self.assertEqual(slt.render_typed(5000000000, "I"), "705032704")
        self.assertEqual(slt.render_typed(20.9, "I"), "20")
        self.assertEqual(slt.render_typed(1e20, "I"), "-1")
        self.assertEqual(slt.render_typed("12abc", "I"), "12")
        self.assertEqual(slt.render_typed("abc", "I"), "0")
        self.assertEqual(slt.render_typed(2, "R"), "2.000")
        self.assertEqual(slt.render_typed("", "T"), "(empty)")
        self.assertEqual(slt.render_typed("tab\there", "T"), "tab@here")
        self.assertEqual(slt.render_typed("café".encode(), "T"), "caf@@")
        self.assertEqual(slt.render_typed(3.0, "T"), "3.0")
        self.assertEqual(slt.render_typed(1e20, "T"), "1.0e+20")
        self.assertEqual(slt.render_typed(0.1 + 0.2, "T"), "0.3")

    def test_candidate_tokens_follow_the_same_rules(self) -> None:
        self.assertEqual(slt.render_candidate_token("NULL", "T"), "NULL")
        self.assertEqual(slt.render_candidate_token("48.6666666666667", "I"), "48")
        self.assertEqual(slt.render_candidate_token("-5000000000", "I"), "-705032704")
        self.assertEqual(slt.render_candidate_token("1.0e+20", "I"), "-1")
        self.assertEqual(slt.render_candidate_token("2.5", "R"), "2.500")
        self.assertEqual(slt.render_candidate_token("", "T"), "(empty)")
        self.assertEqual(slt.unescape_value("a\\tb\\\\c\\n"), "a\tb\\c\n")


class ComparisonTests(unittest.TestCase):
    def test_sorting_hashing_and_labels(self) -> None:
        record = slt.Record("query", 1, types="II", sort="rowsort", label="x")
        values = ["2", "b", "1", "a", "10", "c"]
        record.expected = ["1", "a", "10", "c", "2", "b"]
        labels = slt.LabelRegistry()
        self.assertEqual(slt.compare_query(record, values, 8, labels), (True, None))
        hashed = slt.Record("query", 2, types="I", sort="valuesort", label="x")
        hashed.expected = [slt.hash_line(sorted(["2", "b", "1", "a", "10", "c"]))]
        # Same label, different values: the second record fails the label check.
        ok, detail = slt.compare_query(hashed, ["c", "b", "a", "2", "10", "1"], 3, labels)
        self.assertFalse(ok)
        self.assertIn("labeled result", detail)
        self.assertEqual(slt.compare_query(record, None, 8, slt.LabelRegistry()), (False, "query failed"))
        short = slt.Record("query", 3, types="I", sort="nosort")
        short.expected = ["1", "2"]
        self.assertFalse(slt.compare_query(short, ["1"], 8, slt.LabelRegistry())[0])
        self.assertFalse(slt.compare_query(short, ["1", "3"], 8, slt.LabelRegistry())[0])

    def test_candidate_output_parsing(self) -> None:
        blocks, malformed = slt.parse_candidate_output("ok 2\n1\ta\n2\tb\nerror no such table\nok 0\n")
        self.assertIsNone(malformed)
        self.assertEqual([b.ok for b in blocks], [True, False, True])
        self.assertEqual(blocks[0].rows, [["1", "a"], ["2", "b"]])
        self.assertEqual(blocks[1].message, "no such table")
        blocks, malformed = slt.parse_candidate_output("ok 1\n1\nwhat\nok 0\n")
        self.assertEqual(len(blocks), 1)
        self.assertIn("malformed", malformed)
        blocks, malformed = slt.parse_candidate_output("ok 3\n1\n")
        self.assertEqual(blocks, [])
        self.assertIn("ends early", malformed)

    def test_sqlite_verification_of_smoke_scripts(self) -> None:
        for path in sorted((ROOT / "fixtures" / "smoke-sql" / "test").rglob("*.test")):
            records = slt.parse_script(path.read_text(encoding="utf-8"))
            report = slt.verify_with_sqlite(records)
            self.assertEqual(report["disagreements"], [], path.name)
            self.assertGreater(report["executed"], 0)


if __name__ == "__main__":
    unittest.main()
