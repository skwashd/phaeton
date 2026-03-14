"""Tests for expression translation (Category A n8n to JSONata)."""

from __future__ import annotations

import pytest

from n8n_to_sfn.errors import ExpressionTranslationError
from n8n_to_sfn.translators.expressions import (
    translate_all_expressions,
    translate_n8n_expression,
)


class TestExpressionTranslation:
    """Test every row in the expression translation table."""

    def test_json_field(self) -> None:
        """Test simple JSON field access translation."""
        assert (
            translate_n8n_expression("{{ $json.field }}") == "{% $states.input.field %}"
        )

    def test_json_field_subfield(self) -> None:
        """Test nested JSON field access translation."""
        assert (
            translate_n8n_expression("{{ $json.field.subfield }}")
            == "{% $states.input.field.subfield %}"
        )

    def test_json_array_index(self) -> None:
        """Test JSON array index access translation."""
        assert (
            translate_n8n_expression("{{ $json.arr[0] }}")
            == "{% $states.input.arr[0] %}"
        )

    def test_to_upper_case(self) -> None:
        """Test toUpperCase translation to $uppercase."""
        assert (
            translate_n8n_expression("{{ $json.name.toUpperCase() }}")
            == "{% $uppercase($states.input.name) %}"
        )

    def test_to_lower_case(self) -> None:
        """Test toLowerCase translation to $lowercase."""
        assert (
            translate_n8n_expression("{{ $json.name.toLowerCase() }}")
            == "{% $lowercase($states.input.name) %}"
        )

    def test_trim(self) -> None:
        """Test trim translation to $trim."""
        assert (
            translate_n8n_expression("{{ $json.text.trim() }}")
            == "{% $trim($states.input.text) %}"
        )

    def test_split(self) -> None:
        """Test split translation to $split."""
        assert (
            translate_n8n_expression("{{ $json.text.split(',') }}")
            == "{% $split($states.input.text, ',') %}"
        )

    def test_replace(self) -> None:
        """Test replace translation to $replace."""
        assert (
            translate_n8n_expression("{{ $json.text.replace('a','b') }}")
            == "{% $replace($states.input.text, 'a', 'b') %}"
        )

    def test_includes(self) -> None:
        """Test includes translation to $contains."""
        assert (
            translate_n8n_expression("{{ $json.text.includes('x') }}")
            == "{% $contains($states.input.text, 'x') %}"
        )

    def test_text_length(self) -> None:
        """Test text length translation to $length."""
        assert (
            translate_n8n_expression("{{ $json.text.length }}")
            == "{% $length($states.input.text) %}"
        )

    def test_arr_length(self) -> None:
        """Test array length translation to $count."""
        assert (
            translate_n8n_expression("{{ $json.arr.length }}")
            == "{% $count($states.input.arr) %}"
        )

    def test_addition(self) -> None:
        """Test addition expression translation."""
        assert (
            translate_n8n_expression("{{ $json.a + $json.b }}")
            == "{% $states.input.a + $states.input.b %}"
        )

    def test_ternary(self) -> None:
        """Test ternary expression translation."""
        result = translate_n8n_expression("{{ $json.a > 10 ? 'high' : 'low' }}")
        assert result == "{% $states.input.a > 10 ? 'high' : 'low' %}"

    def test_math_round(self) -> None:
        """Test Math.round translation to $round."""
        assert (
            translate_n8n_expression("{{ Math.round($json.val) }}")
            == "{% $round($states.input.val) %}"
        )

    def test_math_floor(self) -> None:
        """Test Math.floor translation to $floor."""
        assert (
            translate_n8n_expression("{{ Math.floor($json.val) }}")
            == "{% $floor($states.input.val) %}"
        )

    def test_math_ceil(self) -> None:
        """Test Math.ceil translation to $ceil."""
        assert (
            translate_n8n_expression("{{ Math.ceil($json.val) }}")
            == "{% $ceil($states.input.val) %}"
        )

    def test_object_keys(self) -> None:
        """Test Object.keys translation to $keys."""
        assert (
            translate_n8n_expression("{{ Object.keys($json) }}")
            == "{% $keys($states.input) %}"
        )

    def test_json_stringify(self) -> None:
        """Test JSON.stringify translation to $string."""
        assert (
            translate_n8n_expression("{{ JSON.stringify($json) }}")
            == "{% $string($states.input) %}"
        )

    def test_parse_int(self) -> None:
        """Test parseInt translation to $number."""
        assert (
            translate_n8n_expression("{{ parseInt($json.str) }}")
            == "{% $number($states.input.str) %}"
        )

    def test_template_literal(self) -> None:
        """Test template literal translation to string concatenation."""
        result = translate_n8n_expression("{{ `Hello ${$json.name}` }}")
        assert result == '{% "Hello " & $states.input.name %}'

    def test_map(self) -> None:
        """Test map translation to property access."""
        assert (
            translate_n8n_expression("{{ $json.items.map(i => i.name) }}")
            == "{% $states.input.items.name %}"
        )

    def test_filter(self) -> None:
        """Test filter translation to predicate expression."""
        assert (
            translate_n8n_expression("{{ $json.items.filter(i => i.active) }}")
            == "{% $states.input.items[active = true] %}"
        )

    def test_new_date(self) -> None:
        """Test new Date translation to $now."""
        assert (
            translate_n8n_expression("{{ new Date().toISOString() }}") == "{% $now() %}"
        )

    def test_sort(self) -> None:
        """Test sort translation to $sort."""
        result = translate_n8n_expression("{{ $json.arr.sort((a,b) => a.n - b.n) }}")
        assert (
            result == "{% $sort($states.input.arr, function($a,$b){ $a.n > $b.n }) %}"
        )

    def test_reduce_sum(self) -> None:
        """Test reduce sum translation to $sum."""
        result = translate_n8n_expression("{{ $json.arr.reduce((s,i) => s+i.v, 0) }}")
        assert result == "{% $sum($states.input.arr.v) %}"

    def test_spread_array(self) -> None:
        """Test spread array translation to $append."""
        result = translate_n8n_expression("{{ [...$json.a, ...$json.b] }}")
        assert result == "{% $append($states.input.a, $states.input.b) %}"

    def test_spread_object(self) -> None:
        """Test spread object translation to $merge."""
        result = translate_n8n_expression("{{ {...$json.a, ...$json.b} }}")
        assert result == "{% $merge([$states.input.a, $states.input.b]) %}"


class TestExpressionEdgeCases:
    """Tests for expression edge cases."""

    def test_nested_property_access(self) -> None:
        """Test deeply nested property access."""
        result = translate_n8n_expression("{{ $json.a.b.c.d }}")
        assert result == "{% $states.input.a.b.c.d %}"

    def test_unknown_pattern_with_cross_node_ref(self) -> None:
        """Test unknown pattern with cross-node reference raises error."""
        with pytest.raises(ExpressionTranslationError):
            translate_n8n_expression("{{ $('Other').first().json.id }}")

    def test_equals_prefix_expression(self) -> None:
        """Test equals prefix expression translation."""
        result = translate_n8n_expression("=$json.field")
        assert result == "{% $states.input.field %}"

    def test_translate_all_expressions_mixed(self) -> None:
        """Test translate_all_expressions with mixed parameters."""
        params = {
            "url": "https://api.example.com",
            "body": "{{ $json.data }}",
            "nested": {
                "value": "{{ $json.name.toUpperCase() }}",
                "literal": "hello",
            },
            "items": ["{{ $json.id }}", "static"],
        }
        result = translate_all_expressions(params)
        assert result["url"] == "https://api.example.com"
        assert result["body"] == "{% $states.input.data %}"
        assert result["nested"]["value"] == "{% $uppercase($states.input.name) %}"
        assert result["nested"]["literal"] == "hello"
        assert result["items"][0] == "{% $states.input.id %}"
        assert result["items"][1] == "static"

    def test_template_literal_multiple_substitutions(self) -> None:
        """Test template literal with multiple substitutions."""
        result = translate_n8n_expression("{{ `${$json.first} ${$json.last}` }}")
        assert result == '{% $states.input.first & " " & $states.input.last %}'
