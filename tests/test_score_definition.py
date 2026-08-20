import pytest

from vat.models.score_definition import ScoreDefinition


class TestScoreDefinitionValidation:
    def test_defaults(self):
        defn = ScoreDefinition(name="Technique")
        assert defn.minimum == 0.0
        assert defn.maximum == 100.0
        assert defn.dtype == "float"

    def test_rejects_empty_name(self):
        with pytest.raises(ValueError):
            ScoreDefinition(name="   ")

    def test_rejects_invalid_dtype(self):
        with pytest.raises(ValueError):
            ScoreDefinition(name="x", dtype="string")

    def test_rejects_min_not_less_than_max(self):
        with pytest.raises(ValueError):
            ScoreDefinition(name="x", minimum=10, maximum=10)
        with pytest.raises(ValueError):
            ScoreDefinition(name="x", minimum=10, maximum=5)

    def test_int_dtype_requires_whole_number_bounds(self):
        with pytest.raises(ValueError):
            ScoreDefinition(name="x", minimum=0.5, maximum=5, dtype="int")
        ScoreDefinition(name="x", minimum=1, maximum=5, dtype="int")  # ok

    def test_round_trip(self):
        defn = ScoreDefinition(name="Confidence", minimum=1, maximum=5, dtype="int")
        restored = ScoreDefinition.from_dict(defn.to_dict())
        assert restored == defn


class TestScoreDefinitionCoerce:
    def test_valid_float_in_range(self):
        defn = ScoreDefinition(name="Technique", minimum=0, maximum=100, dtype="float")
        assert defn.coerce("87.5") == 87.5

    def test_valid_int_in_range(self):
        defn = ScoreDefinition(name="Confidence", minimum=1, maximum=5, dtype="int")
        assert defn.coerce("3") == 3
        assert isinstance(defn.coerce("3"), int)

    def test_rejects_empty(self):
        defn = ScoreDefinition(name="x")
        with pytest.raises(ValueError):
            defn.coerce("")
        with pytest.raises(ValueError):
            defn.coerce("   ")

    def test_rejects_non_numeric(self):
        defn = ScoreDefinition(name="x")
        with pytest.raises(ValueError):
            defn.coerce("abc")

    def test_rejects_out_of_range_low(self):
        defn = ScoreDefinition(name="x", minimum=0, maximum=100)
        with pytest.raises(ValueError):
            defn.coerce("-1")

    def test_rejects_out_of_range_high(self):
        defn = ScoreDefinition(name="x", minimum=0, maximum=100)
        with pytest.raises(ValueError):
            defn.coerce("100.01")

    def test_boundary_values_accepted(self):
        defn = ScoreDefinition(name="x", minimum=0, maximum=100)
        assert defn.coerce("0") == 0.0
        assert defn.coerce("100") == 100.0

    def test_rejects_fractional_value_for_int_dtype(self):
        defn = ScoreDefinition(name="x", minimum=0, maximum=10, dtype="int")
        with pytest.raises(ValueError):
            defn.coerce("3.5")
