"""Tests for the annotator-text sanitizer.

stdlib unittest only. Each test names the threat it covers.
"""

from __future__ import annotations

import unittest

from mcp_server.sanitize import (
    MAX_RESPONSE_LENGTH,
    _sanitize_value,
    sanitize_responses,
    sanitize_results,
    sanitize_text,
)


class HtmlTagStrippingTests(unittest.TestCase):
    def test_strips_simple_html_tags(self):
        self.assertEqual(sanitize_text("<b>bold</b>"), "bold")

    def test_strips_script_payload(self):
        out = sanitize_text("<script>alert(1)</script>safe")
        self.assertNotIn("<", out)
        self.assertNotIn("script", out)
        self.assertEqual(out, "alert(1)safe")

    def test_keeps_text_with_angle_brackets_in_words(self):
        out = sanitize_text("a < b > c")
        self.assertIn("a ", out)
        self.assertIn(" c", out)


class TruncationTests(unittest.TestCase):
    def test_long_string_truncated_with_ellipsis(self):
        text = "x" * (MAX_RESPONSE_LENGTH + 100)
        out = sanitize_text(text)
        self.assertEqual(len(out), MAX_RESPONSE_LENGTH + 3)
        self.assertTrue(out.endswith("..."))

    def test_short_string_unchanged(self):
        self.assertEqual(sanitize_text("short"), "short")


class InvisibleCharacterStrippingTests(unittest.TestCase):
    def test_strips_zero_width_space(self):
        out = sanitize_text("hello​world")
        self.assertEqual(out, "helloworld")

    def test_strips_zero_width_joiner_and_non_joiner(self):
        out = sanitize_text("a‌b‍c")
        self.assertEqual(out, "abc")

    def test_strips_byte_order_mark(self):
        out = sanitize_text("﻿text")
        self.assertEqual(out, "text")

    def test_strips_bidi_rtl_override(self):
        out = sanitize_text("safe‮txt.exe")
        self.assertNotIn("‮", out)
        self.assertIn("safe", out)
        self.assertIn("txt.exe", out)

    def test_strips_word_joiner_and_invisible_separators(self):
        out = sanitize_text("⁠hidden⁣text")
        self.assertEqual(out, "hiddentext")


class ControlCharacterStrippingTests(unittest.TestCase):
    def test_strips_null_and_other_c0(self):
        out = sanitize_text("a\x00b\x07c")
        self.assertEqual(out, "abc")

    def test_strips_c1_controls(self):
        out = sanitize_text("a\x80b\x9fc")
        self.assertEqual(out, "abc")

    def test_preserves_tab_and_newline(self):
        out = sanitize_text("line1\nline2\tcol")
        self.assertIn("\n", out)
        self.assertIn("\t", out)

    def test_strips_del_character(self):
        out = sanitize_text("a\x7fb")
        self.assertEqual(out, "ab")


class UnicodeNormalizationTests(unittest.TestCase):
    def test_fullwidth_digits_fold_to_ascii(self):
        # U+FF11 etc. — fullwidth versions of "1" "2" "3"
        out = sanitize_text("１２３")
        self.assertEqual(out, "123")

    def test_compatibility_ligature_decomposed(self):
        # U+FB01 ("fi") decomposes to "fi" under NFKC
        out = sanitize_text("ﬁnal")
        self.assertEqual(out, "final")


class MarkdownLinkDefangingTests(unittest.TestCase):
    def test_link_open_paren_escaped(self):
        out = sanitize_text("[click me](http://example.com)")
        self.assertNotIn("](http", out)
        self.assertIn(r"\(http", out)

    def test_image_open_paren_escaped(self):
        out = sanitize_text("![alt text](http://example.com/img.png)")
        self.assertIn(r"\(http", out)

    def test_plain_text_with_brackets_preserved(self):
        # A bracket without a following paren is harmless and unchanged
        out = sanitize_text("see [note] for context")
        self.assertEqual(out, "see [note] for context")

    def test_only_first_paren_after_bracket_is_escaped(self):
        out = sanitize_text("[a](url1) and [b](url2)")
        self.assertEqual(out.count(r"\("), 2)

    def test_nested_brackets_still_defanged(self):
        out = sanitize_text("[outer [inner]](http://evil.com)")
        self.assertNotIn("](http", out)
        self.assertIn(r"\(http", out)

    def test_double_bracket_still_defanged(self):
        out = sanitize_text("[[wikilink]](http://evil.com)")
        self.assertNotIn("](http", out)


class NonStringInputTests(unittest.TestCase):
    def test_int_coerced_via_str(self):
        self.assertEqual(sanitize_text(42), "42")

    def test_none_coerced_to_string(self):
        self.assertEqual(sanitize_text(None), "None")


class SanitizeValueRecursionTests(unittest.TestCase):
    def test_dict_values_sanitized_recursively(self):
        payload = {"answer": "<b>yes</b>", "rationale": "I prefer it​because"}
        out = _sanitize_value(payload)
        self.assertEqual(out["answer"], "yes")
        self.assertEqual(out["rationale"], "I prefer itbecause")

    def test_list_items_sanitized(self):
        out = _sanitize_value(["<i>a</i>", "b‮flip"])
        self.assertEqual(out[0], "a")
        self.assertNotIn("‮", out[1])

    def test_non_string_preserved(self):
        out = _sanitize_value({"score": 4, "flagged": True, "extras": None})
        self.assertEqual(out, {"score": 4, "flagged": True, "extras": None})

    def test_deep_nesting_terminates(self):
        # Build a 15-deep nested dict; the sanitizer caps recursion at 10.
        obj: object = "leaf"
        for _ in range(15):
            obj = {"k": obj}
        out = _sanitize_value(obj)
        self.assertIsInstance(out, dict)


class SanitizeListWrappersTests(unittest.TestCase):
    def test_sanitize_results_processes_each_dict(self):
        results = [
            {"datapoint_index": 0, "consensus": "<b>A</b>"},
            {"datapoint_index": 1, "consensus": "B​"},
        ]
        out = sanitize_results(results)
        self.assertEqual(out[0]["consensus"], "A")
        self.assertEqual(out[1]["consensus"], "B")

    def test_sanitize_responses_processes_each_dict(self):
        responses = [{"response": "<i>yes</i>", "annotator_id": "anon_1"}]
        out = sanitize_responses(responses)
        self.assertEqual(out[0]["response"], "yes")
        self.assertEqual(out[0]["annotator_id"], "anon_1")


if __name__ == "__main__":
    unittest.main()
