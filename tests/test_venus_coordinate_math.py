"""Independent arithmetic checks for isolated, predeclared diagnostic candidates."""
from fractions import Fraction

import pytest

from scripts.diagnostics.venus_coordinate_math import (
    candidate_points, native_point, upstream_example_size,
)


def wrapped(expression):
    return f"<think>Frozen diagnostic output</think><action>{expression}</action>"


@pytest.mark.parametrize("expression,expected", [
    ("Click(box=(496,233))", (496, 233)),
    ("Click(box=[1100, -0.25])", (1100, -0.25)),
    ("Click(box=(1e4, 2.5))", (10000, 2.5)),
    ("Click(box=(0,1000))", (0, 1000)),
])
def test_extracts_native_click_without_imposing_normalized_bounds(expression, expected):
    assert native_point(wrapped(expression)) == expected


@pytest.mark.parametrize("raw", [
    "Click(box=(1,2))", wrapped("Hover(box=(1,2))"), wrapped("Click((1,2))"),
    wrapped("Click(box=(1,2), box=(3,4))"), wrapped("Click(box=(1,2), other=3)"),
    wrapped("Click(**{'box':(1,2)})"), wrapped("obj.Click(box=(1,2))"),
    wrapped("Click(box=(True,2))"), wrapped("Click(box=(1,False))"),
    wrapped("Click(box=(1e999,2))"), wrapped("Click(box=('1',2))"),
    wrapped("Click(box=(1,2,3,4))"), wrapped("Click(box=(1,))"),
    wrapped("Click(box=(1+2,3))"), wrapped("Click(box=__import__('os').getcwd())"),
    wrapped("Click(box=(1,2)); Wait()"), wrapped("Click(box=(1,2))") * 2,
    "</action><action>Click(box=(1,2))", wrapped("Type(content='Click(box=(1,2))')"),
])
def test_extraction_rejects_nonclick_or_unsafe_ambiguous_native_syntax(raw):
    with pytest.raises(ValueError):
        native_point(raw)


def test_legacy_496_233_has_four_fixed_distinct_interpretations():
    result = candidate_points((496, 233), (1280, 900), (1184, 832))
    assert result == {
        "normalized_1000": {"point": [634, 209], "valid": True, "source_size": [1000, 1000]},
        "prepared_image_pixels": {"point": [536, 252], "valid": True, "source_size": [1184, 832]},
        "original_image_pixels": {"point": [496, 233], "valid": True, "source_size": [1280, 900]},
        "upstream_example_factor28": {"point": [492, 234], "valid": True, "source_size": [1288, 896]},
    }


@pytest.mark.parametrize("original,prepared,upstream", [
    ((1280, 900), (1184, 832), (1288, 896)),
    ((1920, 480), (1920, 480), (1932, 476)),
    ((480, 1920), (480, 1920), (476, 1932)),
    ((390, 844), (384, 832), (392, 840)),
    ((101, 99), (256, 256), (112, 112)),
])
def test_candidates_match_independent_rational_arithmetic(original, prepared, upstream):
    assert upstream_example_size(original) == upstream
    point = (291, 651)
    result = candidate_points(point, original, prepared)
    frames = {"normalized_1000": (1000, 1000), "prepared_image_pixels": prepared,
              "original_image_pixels": original, "upstream_example_factor28": upstream}
    for name, source in frames.items():
        assert result[name]["source_size"] == list(source)
        if name == "upstream_example_factor28":
            exact = [min(d, max(0, Fraction(v) * d // s)) for v, d, s in zip(point, original, source)]
            assert result[name]["point"] == exact
            assert result[name]["valid"] == all(0 <= v < d for v, d in zip(exact, original))
        elif all(0 <= v < s for v, s in zip(point, source)):
            exact = list(point) if name == "original_image_pixels" else [Fraction(v) * d // s for v, d, s in zip(point, original, source)]
            assert result[name]["point"] == exact
            assert result[name]["valid"] is True
        else:
            assert result[name]["point"] is None and result[name]["valid"] is False


def test_normalized_endpoint_is_valid_but_pixel_frame_endpoints_are_invalid():
    result = candidate_points((1000, 1000), (1000, 1000), (1000, 1000))
    assert result["normalized_1000"]["point"] == [999, 999]
    assert result["normalized_1000"]["valid"] is True
    for name in ["original_image_pixels", "prepared_image_pixels"]:
        assert result[name]["point"] is None and result[name]["valid"] is False
    # Upstream rounds 1000 to a 1008 grid, so its edge policy must be checked
    # against that source frame rather than the original frame.
    edge = candidate_points((1008, 1008), (1000, 1000), (1000, 1000))["upstream_example_factor28"]
    assert edge == {"point": [1000, 1000], "valid": False, "source_size": [1008, 1008]}


@pytest.mark.parametrize("point", [(-0.01, 10), (10, -0.01), (1000.01, 10), (10, 1000.01)])
def test_normalized_rejection_does_not_suppress_other_candidate_results(point):
    result = candidate_points(point, (1920, 1080), (1600, 900))
    assert result["normalized_1000"]["point"] is None
    assert result["normalized_1000"]["valid"] is False
    assert set(result) == {"normalized_1000", "prepared_image_pixels", "original_image_pixels", "upstream_example_factor28"}
    if point[0] >= 0 and point[1] >= 0:
        assert result["original_image_pixels"]["valid"] is True
    else:
        # Explicitly preserve the upstream example's clipping behavior.
        assert result["upstream_example_factor28"]["valid"] is True


def test_fractional_pixels_floor_and_both_axis_bounds_apply():
    result = candidate_points((49.9, 50.1), (101, 99), (64, 96))
    assert result["normalized_1000"]["point"] == [5, 4]
    assert result["prepared_image_pixels"]["point"] == [78, 51]
    assert result["original_image_pixels"]["point"] == [49, 50]
    for point in [(64, 0), (0, 96), (-0.1, 5), (5, -0.1)]:
        item = candidate_points(point, (101, 99), (64, 96))["prepared_image_pixels"]
        assert item["point"] is None and item["valid"] is False


@pytest.mark.parametrize("original,expected", [
    ((1, 1), (56, 56)),  # runner minimum: 3136
    ((42, 70), (56, 56)),  # round-to-even at factor-28 half-grid positions
    ((8000, 8000), (3584, 3584)),  # runner maximum: 12845056
    ((14000, 3500), (7168, 1792)),
])
def test_upstream_resize_minimum_maximum_and_grid_rounding(original, expected):
    assert upstream_example_size(original) == expected


@pytest.mark.parametrize("bad", [(0, 900), (1280, -1), (True, 900), (1280.0, 900), (1280,), (1280, 900, 1)])
def test_invalid_dimensions_raise_before_candidate_evaluation(bad):
    with pytest.raises(ValueError):
        candidate_points((1, 2), bad, (256, 256))
    with pytest.raises(ValueError):
        candidate_points((1, 2), (1280, 900), bad)


@pytest.mark.parametrize("bad", [(True, 2), (float("nan"), 2), (1, float("inf")), (1,), (1, 2, 3)])
def test_nonfinite_boolean_and_malformed_points_rejected(bad):
    with pytest.raises(ValueError):
        candidate_points(bad, (1280, 900), (1184, 832))


def test_upstream_rejects_unsupported_aspect_ratio_instead_of_inventing_transform():
    with pytest.raises(ValueError, match="200"):
        candidate_points((1, 2), (201, 1), (256, 256))


def test_extreme_finite_raw_values_preserve_all_candidate_results_without_overflow():
    assert native_point(wrapped("Click(box=(1e308,-1e308))")) == (1e308, -1e308)
    result = candidate_points((1e308, -1e308), (1280, 900), (1184, 832))
    assert result["upstream_example_factor28"]["point"] == [1280, 0]
    assert result["upstream_example_factor28"]["valid"] is False
    for name in ["normalized_1000", "prepared_image_pixels", "original_image_pixels"]:
        assert result[name]["point"] is None and result[name]["valid"] is False
