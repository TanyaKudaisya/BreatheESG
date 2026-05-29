"""
Configuration Loader for the Breathe ESG Data Ingestion System.

Loads emission factors, unit conversion rates, and cabin class multipliers
from a JSON configuration file.  Supports hot-reload: every call to
``load_config()`` re-reads the file from disk so that updates take effect
without an application restart.

Requirements: 21.1, 21.2, 21.3, 21.4, 22.1, 22.2, 22.3, 22.4
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Default config path: <project_root>/config/emission_config.json
# ---------------------------------------------------------------------------
_BASE_DIR = Path(__file__).resolve().parent.parent  # project root
_DEFAULT_CONFIG_PATH = _BASE_DIR / "config" / "emission_config.json"


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class EmissionConfig:
    """
    Parsed representation of the emission configuration file.

    Attributes:
        emission_factors:        Mapping of fuel type → kg CO₂e per unit.
        unit_conversions:        Mapping of unit code → {target_unit, factor}.
        cabin_class_multipliers: Mapping of cabin class → emission multiplier.
    """

    emission_factors: dict = field(default_factory=dict)
    unit_conversions: dict = field(default_factory=dict)
    cabin_class_multipliers: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# ConfigurationLoader
# ---------------------------------------------------------------------------


class ConfigurationLoader:
    """
    Loads, exports, and imports the emission configuration file.

    Hot-reload behaviour
    --------------------
    ``load_config()`` reads the JSON file from disk on every call.  There is
    no in-process cache, so any change to the file is picked up immediately
    without restarting the application (Requirement 21.4).

    Args:
        config_path: Absolute or relative path to the JSON configuration file.
                     Defaults to ``<project_root>/config/emission_config.json``.
    """

    def __init__(self, config_path: Optional[str] = None) -> None:
        if config_path is None:
            self._config_path = Path(_DEFAULT_CONFIG_PATH)
        else:
            self._config_path = Path(config_path)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load_config(self) -> EmissionConfig:
        """
        Read the JSON configuration file and return an :class:`EmissionConfig`.

        The file is re-read on every call to support hot-reload without an
        application restart (Requirement 21.4).

        Returns:
            :class:`EmissionConfig` populated with emission factors, unit
            conversions, and cabin class multipliers.

        Raises:
            FileNotFoundError: If the configuration file does not exist.
            ValueError:        If the JSON is malformed or missing required keys.
        """
        if not self._config_path.exists():
            raise FileNotFoundError(
                f"Configuration file not found: {self._config_path}"
            )

        with open(self._config_path, "r", encoding="utf-8") as fh:
            try:
                raw = json.load(fh)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"Malformed JSON in configuration file '{self._config_path}': {exc}"
                ) from exc

        return self._parse_raw(raw)

    def export_config(self, output_path: str) -> None:
        """
        Write the current configuration to a JSON file at *output_path*.

        The current configuration is obtained by calling :meth:`load_config`,
        so the exported file always reflects the latest on-disk state.

        Args:
            output_path: Destination file path for the exported JSON.

        Raises:
            FileNotFoundError: If the source configuration file does not exist.
            ValueError:        If the source configuration is malformed.
        """
        config = self.load_config()
        data = {
            "emission_factors": config.emission_factors,
            "unit_conversions": config.unit_conversions,
            "cabin_class_multipliers": config.cabin_class_multipliers,
        }
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        with open(output, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2)

    def import_config(self, input_path: str) -> EmissionConfig:
        """
        Read a configuration from *input_path*, update the internal config
        path to point at the new file, and return the parsed
        :class:`EmissionConfig`.

        After calling this method, subsequent calls to :meth:`load_config`
        will read from *input_path*.

        Args:
            input_path: Source file path to import configuration from.

        Returns:
            :class:`EmissionConfig` parsed from the imported file.

        Raises:
            FileNotFoundError: If *input_path* does not exist.
            ValueError:        If the JSON is malformed or missing required keys.
        """
        self._config_path = Path(input_path)
        return self.load_config()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_raw(raw: dict) -> EmissionConfig:
        """
        Validate and convert a raw JSON dict into an :class:`EmissionConfig`.

        Args:
            raw: Parsed JSON dictionary.

        Returns:
            :class:`EmissionConfig` instance.

        Raises:
            ValueError: If any required top-level key is missing.
        """
        required_keys = {"emission_factors", "unit_conversions", "cabin_class_multipliers"}
        missing = required_keys - raw.keys()
        if missing:
            raise ValueError(
                f"Configuration file is missing required keys: {sorted(missing)}"
            )

        return EmissionConfig(
            emission_factors=dict(raw["emission_factors"]),
            unit_conversions=dict(raw["unit_conversions"]),
            cabin_class_multipliers=dict(raw["cabin_class_multipliers"]),
        )
