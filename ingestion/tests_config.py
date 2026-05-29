"""
Pure-Python tests for ConfigurationLoader (no Django DB required).

Run with:
    pytest ingestion/tests_config.py -v

Requirements: 21.1, 21.2, 21.3, 21.4, 22.1, 22.2, 22.3, 22.4
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Locate the default config file so tests can reference it directly.
# ---------------------------------------------------------------------------
_HERE = Path(__file__).resolve().parent          # ingestion/
_PROJECT_ROOT = _HERE.parent                     # project root
_DEFAULT_CONFIG = _PROJECT_ROOT / "config" / "emission_config.json"


# ---------------------------------------------------------------------------
# Import the module under test (no Django settings needed).
# ---------------------------------------------------------------------------
from ingestion.config_loader import ConfigurationLoader, EmissionConfig


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_loader(config_path: str | None = None) -> ConfigurationLoader:
    """Return a ConfigurationLoader pointing at the default config (or a custom path)."""
    if config_path is None:
        return ConfigurationLoader(str(_DEFAULT_CONFIG))
    return ConfigurationLoader(config_path)


def _write_config(path: str, data: dict) -> None:
    """Write *data* as JSON to *path*."""
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestLoadConfig:
    """Tests for ConfigurationLoader.load_config()."""

    def test_load_config_returns_emission_config(self):
        """load_config() returns an EmissionConfig with all three sections populated."""
        loader = _make_loader()
        config = loader.load_config()

        assert isinstance(config, EmissionConfig), (
            "load_config() should return an EmissionConfig instance"
        )
        assert config.emission_factors, "emission_factors should not be empty"
        assert config.unit_conversions, "unit_conversions should not be empty"
        assert config.cabin_class_multipliers, "cabin_class_multipliers should not be empty"

    def test_emission_factors_contain_diesel(self):
        """emission_factors must include a 'diesel' key."""
        loader = _make_loader()
        config = loader.load_config()

        assert "diesel" in config.emission_factors, (
            "emission_factors should contain 'diesel'"
        )
        assert isinstance(config.emission_factors["diesel"], (int, float)), (
            "diesel emission factor should be a numeric value"
        )

    def test_cabin_class_multipliers_business_is_3(self):
        """cabin_class_multipliers['BUSINESS'] must equal 3.0."""
        loader = _make_loader()
        config = loader.load_config()

        assert "BUSINESS" in config.cabin_class_multipliers, (
            "cabin_class_multipliers should contain 'BUSINESS'"
        )
        assert config.cabin_class_multipliers["BUSINESS"] == 3.0, (
            "BUSINESS cabin class multiplier should be 3.0"
        )


class TestExportImport:
    """Tests for ConfigurationLoader.export_config() and import_config()."""

    def test_export_then_import_round_trip(self):
        """
        Export the default config to a temp file, import it back, and verify
        the resulting EmissionConfig is equivalent to the original.
        """
        loader = _make_loader()
        original = loader.load_config()

        with tempfile.NamedTemporaryFile(
            suffix=".json", delete=False, mode="w"
        ) as tmp:
            tmp_path = tmp.name

        try:
            # Export
            loader.export_config(tmp_path)

            # Import back using a fresh loader
            fresh_loader = ConfigurationLoader()
            imported = fresh_loader.import_config(tmp_path)

            # Verify equivalence
            assert imported.emission_factors == original.emission_factors, (
                "Imported emission_factors should match original"
            )
            assert imported.unit_conversions == original.unit_conversions, (
                "Imported unit_conversions should match original"
            )
            assert imported.cabin_class_multipliers == original.cabin_class_multipliers, (
                "Imported cabin_class_multipliers should match original"
            )
        finally:
            os.unlink(tmp_path)

    def test_export_produces_valid_json_file(self):
        """export_config() must write a valid JSON file that can be parsed."""
        loader = _make_loader()

        with tempfile.NamedTemporaryFile(
            suffix=".json", delete=False, mode="w"
        ) as tmp:
            tmp_path = tmp.name

        try:
            loader.export_config(tmp_path)

            with open(tmp_path, "r", encoding="utf-8") as fh:
                data = json.load(fh)

            assert "emission_factors" in data
            assert "unit_conversions" in data
            assert "cabin_class_multipliers" in data
        finally:
            os.unlink(tmp_path)


class TestHotReload:
    """Tests for hot-reload behaviour (Requirement 21.4)."""

    def test_hot_reload_picks_up_changes(self):
        """
        Modifying the config file and calling load_config() again should
        return the updated values without restarting the application.
        """
        initial_data = {
            "emission_factors": {"diesel": 2.68, "petrol": 2.31},
            "unit_conversions": {
                "L": {"target_unit": "litres", "factor": 1.0}
            },
            "cabin_class_multipliers": {"ECONOMY": 1.0, "BUSINESS": 3.0},
        }
        updated_data = {
            "emission_factors": {"diesel": 9.99, "petrol": 8.88},
            "unit_conversions": {
                "L": {"target_unit": "litres", "factor": 1.0}
            },
            "cabin_class_multipliers": {"ECONOMY": 1.0, "BUSINESS": 3.0},
        }

        with tempfile.NamedTemporaryFile(
            suffix=".json", delete=False, mode="w"
        ) as tmp:
            tmp_path = tmp.name

        try:
            # Write initial config and load it
            _write_config(tmp_path, initial_data)
            loader = ConfigurationLoader(tmp_path)
            first_load = loader.load_config()
            assert first_load.emission_factors["diesel"] == 2.68

            # Overwrite the file with updated values
            _write_config(tmp_path, updated_data)

            # load_config() should pick up the new values without restart
            second_load = loader.load_config()
            assert second_load.emission_factors["diesel"] == 9.99, (
                "Hot-reload: load_config() should return updated diesel factor after file change"
            )
            assert second_load.emission_factors["petrol"] == 8.88, (
                "Hot-reload: load_config() should return updated petrol factor after file change"
            )
        finally:
            os.unlink(tmp_path)
