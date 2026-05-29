"""
Property tests for configuration round-trip.

Property 10: Configuration round-trip

Requirements: 22.5
"""

import json
import os
import tempfile

from ingestion.config_loader import ConfigurationLoader


def test_config_round_trip():
    """Export → import → export produces equivalent JSON."""
    loader = ConfigurationLoader()
    original = loader.load_config()

    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f1:
        path1 = f1.name
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f2:
        path2 = f2.name

    try:
        # First export
        loader.export_config(path1)

        # Import from first export
        loader2 = ConfigurationLoader()
        imported = loader2.import_config(path1)

        # Second export
        loader2.export_config(path2)

        # Compare the two exported files
        with open(path1) as f:
            data1 = json.load(f)
        with open(path2) as f:
            data2 = json.load(f)

        assert data1 == data2, "Two exports of the same config should be identical"
        assert data1["emission_factors"] == original.emission_factors
        assert data1["unit_conversions"] == original.unit_conversions
        assert data1["cabin_class_multipliers"] == original.cabin_class_multipliers

    finally:
        os.unlink(path1)
        os.unlink(path2)


def test_config_import_export_preserves_values():
    """Imported config has same values as original."""
    loader = ConfigurationLoader()
    original = loader.load_config()

    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        path = f.name

    try:
        loader.export_config(path)
        loader2 = ConfigurationLoader()
        imported = loader2.import_config(path)

        assert imported.emission_factors == original.emission_factors
        assert imported.unit_conversions == original.unit_conversions
        assert imported.cabin_class_multipliers == original.cabin_class_multipliers
    finally:
        os.unlink(path)
