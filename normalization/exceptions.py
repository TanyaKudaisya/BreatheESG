"""
Custom exceptions for the normalization app.
"""


class DateParseError(ValueError):
    """
    Raised when a date string cannot be parsed by any supported format.

    Supported formats:
    - YYYYMMDD
    - DD.MM.YYYY
    - DD/MM/YYYY
    - YYYY-MM-DD
    """

    def __init__(self, date_string: str):
        self.date_string = date_string
        super().__init__(
            f"Unable to parse date '{date_string}'. "
            "Supported formats: YYYYMMDD, DD.MM.YYYY, DD/MM/YYYY, YYYY-MM-DD."
        )


class UnknownUnitError(ValueError):
    """
    Raised when a unit code is not recognized by the normalization service.

    Recognized unit codes: L, LTR, M3, KG.
    """

    def __init__(self, unit_code: str):
        self.unit_code = unit_code
        super().__init__(
            f"Unknown unit code '{unit_code}'. "
            "Recognized unit codes: L, LTR, M3, KG."
        )
