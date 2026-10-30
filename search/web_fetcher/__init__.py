"""search.web_fetcher - публичный API."""
from .fetcher import WebFetcher
from .html_parser import extract_from_html, extract_magnets_from_html

__all__ = ["WebFetcher", "extract_from_html", "extract_magnets_from_html"]
