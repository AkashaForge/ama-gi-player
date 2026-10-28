"""Smoke tests: базовые проверки, что проект жив.

Не заменяют полноценные тесты, но гарантируют:
  - модули импортируются
  - базовые функции работают
  - CI зелёный, если нет регрессий
"""

import os
import sys

import pytest

# Корень проекта в sys.path
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def test_python_version():
    assert sys.version_info >= (3, 11)


def test_config_imports():
    import config
    assert config.BASE_DIR is not None
    assert config.DATA_DIR is not None
    assert isinstance(config.LEGAL_ONLY_MODE, bool)


def test_pyqt6_imports():
    from PyQt6.QtWidgets import QWidget, QLabel
    assert QWidget is not None
    assert QLabel is not None


def test_qmediaplayer_exists():
    try:
        from PyQt6.QtMultimedia import QMediaPlayer
        assert QMediaPlayer is not None
    except ImportError:
        pytest.skip("QtMultimedia not available")


def test_truncate_for_display():
    from ui.widgets.details_widget import _truncate_for_display
    assert _truncate_for_display("abc", 10) == "abc"
    long = "a " * 100
    result = _truncate_for_display(long, 20)
    assert len(result) <= 20
    assert result.endswith("...")


def test_clean_ia_description():
    from controllers.details_controller import _clean_ia_description
    assert _clean_ia_description("") == ""
    assert _clean_ia_description("<p>Hello</p>") == "Hello"
    assert _clean_ia_description(["a", "b"]) == "a b"
    # HTML с br
    result = _clean_ia_description("line1<br/>line2")
    assert "line1" in result and "line2" in result


def test_is_cyrillic_dominant():
    from controllers.details_controller import _is_cyrillic_dominant
    assert _is_cyrillic_dominant("Привет мир") is True
    assert _is_cyrillic_dominant("Hello world") is False
    assert _is_cyrillic_dominant("") is False


def test_make_slug():
    from controllers.feed_controller import _make_slug
    assert _make_slug("Hello World", "2020") == "hello_world_2020"
    assert _make_slug("", "") == ""
    assert _make_slug("a" * 200)[:3] == "aaa"
