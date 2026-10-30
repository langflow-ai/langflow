import pytest
from langflow.services.evaluations.csv_io import CsvFormatError, decode_upload, export_rows, plan_import, preview


class TestDecode:
    def test_should_strip_utf8_bom(self):
        assert decode_upload("﻿input,expected\n".encode()) == "input,expected\n"

    def test_should_reject_non_utf8_with_a_clear_message(self):
        with pytest.raises(CsvFormatError, match="UTF-8"):
            decode_upload("pergunta,ação\n".encode("latin-1"))


class TestPreview:
    def test_should_detect_semicolon_delimiter_and_count_rows(self):
        headers, rows, total = preview("question;answer\nWhat?;That\nWho?;Me\n")
        assert headers == ["question", "answer"]
        assert rows == [["What?", "That"], ["Who?", "Me"]]
        assert total == 2

    def test_should_skip_blank_lines_before_the_header(self):
        headers, _, total = preview("\n\nq,a\n1,2\n")
        assert headers == ["q", "a"]
        assert total == 1

    def test_should_keep_commas_in_a_single_column_file(self):
        headers, rows, total = preview("question\nWhat is 2, 3 and 4?\nName a, b\n")
        assert headers == ["question"]
        assert rows == [["What is 2, 3 and 4?"], ["Name a, b"]]
        assert total == 2

    def test_should_take_the_delimiter_from_the_header_only(self):
        headers, rows, _ = preview("question\tanswer\nOne, two\tThree; four\n")
        assert headers == ["question", "answer"]
        assert rows == [["One, two", "Three; four"]]

    def test_should_fail_on_an_empty_file(self):
        with pytest.raises(CsvFormatError, match="header"):
            preview("\n \n")


class TestPlanImport:
    def test_should_keep_quoted_multiline_cells(self):
        plan = plan_import('q,a\n"line one\nline two","x, y"\n', input_column="q", expected_column="a", max_rows=10)
        assert plan.rows[0].input == "line one\nline two"
        assert plan.rows[0].expected_output == "x, y"

    def test_should_skip_rows_with_empty_input_and_report_line_numbers(self):
        plan = plan_import("q,a\n,orphan\nkept,\n", input_column="q", expected_column="a", max_rows=10)
        assert [row.input for row in plan.rows] == ["kept"]
        assert plan.rows[0].expected_output is None
        assert plan.skipped == [(2, "Input is empty")]

    def test_should_allow_no_expected_column(self):
        plan = plan_import("q\nonly input\n", input_column="q", expected_column=None, max_rows=10)
        assert plan.rows[0].expected_output is None

    def test_should_reject_an_unknown_column(self):
        with pytest.raises(CsvFormatError, match="not in the file"):
            plan_import("q,a\n1,2\n", input_column="question", expected_column=None, max_rows=10)

    def test_should_stop_at_the_row_limit_and_report_the_rest(self):
        text = "q\n" + "".join(f"row {i}\n" for i in range(5))
        plan = plan_import(text, input_column="q", expected_column=None, max_rows=3)
        assert len(plan.rows) == 3
        assert plan.skipped == [(5, "Row limit of 3 reached: 2 more rows were not imported")]

    def test_should_tolerate_short_rows(self):
        plan = plan_import("q,a\nonly-q\n", input_column="q", expected_column="a", max_rows=10)
        assert plan.rows[0].expected_output is None


class TestExport:
    def test_should_neutralize_formulas_and_start_with_bom(self):
        chunks = list(export_rows([("=SUM(A1)", "+1"), ("plain", None)]))
        text = "".join(chunks)
        assert text.startswith("﻿input,expected_output\r\n")
        assert "'=SUM(A1),'+1\r\n" in text
        assert "plain,\r\n" in text

    def test_should_round_trip_plain_rows(self):
        rows = [("What is 2+2?", "4"), ('Say "hi", please', "hi\nthere")]
        text = "".join(export_rows(rows)).removeprefix("﻿")
        plan = plan_import(text, input_column="input", expected_column="expected_output", max_rows=10)
        assert [(row.input, row.expected_output) for row in plan.rows] == rows


class TestResultsExport:
    def test_should_neutralize_formula_scorer_names_in_the_header(self):
        from langflow.services.evaluations.results_export import export_results

        header = next(export_results([], ["-A1"]))
        assert ",-A1," not in header
        assert "'-A1" in header
