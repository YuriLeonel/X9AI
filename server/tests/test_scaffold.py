"""Import smoke for the scaffolded package (build-gate only)."""

import x9ai


def test_package_is_importable_and_versioned() -> None:
    assert x9ai.__version__ == "0.1.0"