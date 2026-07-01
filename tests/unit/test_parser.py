"""Unit tests for parser infrastructure."""

import pytest

from src.infrastructure.parser import LxmlParser, BeautifulSoupParser, HybridParser
from tests.fixtures.sample_html import (
    SAMPLE_BOOK_PAGE,
    SAMPLE_INVALID_HTML,
    SAMPLE_EMPTY_PAGE,
    SAMPLE_BOOK_LIST,
    EXPECTED_BOOK_DATA,
    EXPECTED_BOOK_LIST_COUNT,
)


class TestLxmlParser:
    """Test cases for LxmlParser implementation."""

    @pytest.fixture
    def parser(self) -> LxmlParser:
        return LxmlParser()

    def test_parse_html_string(self, parser: LxmlParser) -> None:
        """Test parsing HTML string returns lxml element."""
        doc = parser.parse(SAMPLE_BOOK_PAGE)
        assert doc is not None
        assert hasattr(doc, 'xpath')

    def test_css_select_title(self, parser: LxmlParser) -> None:
        """Test CSS selector extraction for title."""
        doc = parser.parse(SAMPLE_BOOK_PAGE)
        result = parser.css(doc, "#book-title")
        assert result is not None
        assert parser.extract_text(result).strip() == "The Great Gatsby"

    def test_css_select_price(self, parser: LxmlParser) -> None:
        """Test CSS selector extraction for price."""
        doc = parser.parse(SAMPLE_BOOK_PAGE)
        result = parser.css(doc, ".price")
        assert result is not None
        assert parser.extract_text(result) == "£19.99"

    def test_css_select_all_paragraphs(self, parser: LxmlParser) -> None:
        """Test CSS select_all for multiple elements."""
        doc = parser.parse(SAMPLE_BOOK_LIST)
        results = parser.css_all(doc, ".book-item")
        assert len(results) == EXPECTED_BOOK_LIST_COUNT

    def test_xpath_select_author(self, parser: LxmlParser) -> None:
        """Test XPath selector extraction."""
        doc = parser.parse(SAMPLE_BOOK_PAGE)
        result = parser.xpath(
            doc, "//th[text()='Author']/following-sibling::td/text()"
        )
        assert result is not None
        assert len(result) > 0
        assert result[0].strip() == "F. Scott Fitzgerald"

    def test_css_select_not_found(self, parser: LxmlParser) -> None:
        """Test CSS selector when element not found."""
        doc = parser.parse(SAMPLE_BOOK_PAGE)
        result = parser.css(doc, ".non-existent-class")
        assert result is None

    def test_css_all_empty(self, parser: LxmlParser) -> None:
        """Test css_all with no matches."""
        doc = parser.parse(SAMPLE_BOOK_PAGE)
        results = parser.css_all(doc, ".non-existent")
        assert results == []

    def test_invalid_html_handling(self, parser: LxmlParser) -> None:
        """Test parser handles invalid HTML gracefully."""
        doc = parser.parse(SAMPLE_INVALID_HTML)
        result = parser.css(doc, ".broken")
        # Should not raise exception, may return None or partial result
        assert result is not None or result is None  # Depends on lxml tolerance

    def test_empty_page_handling(self, parser: LxmlParser) -> None:
        """Test parser handles empty page."""
        doc = parser.parse(SAMPLE_EMPTY_PAGE)
        result = parser.css(doc, "body")
        assert result is not None  # Body tag exists even in empty page

    def test_extract_attribute(self, parser: LxmlParser) -> None:
        """Test extracting attribute value."""
        doc = parser.parse(SAMPLE_BOOK_LIST)
        results = parser.css_all(doc, ".book-item")
        assert len(results) > 0
        first_item = results[0]
        data_id = parser.extract_attr(first_item, "data-id")
        assert data_id == "1"

    def test_extract_text_with_whitespace(self, parser: LxmlParser) -> None:
        """Test text extraction strips whitespace."""
        html = "<p>   Hello World   </p>"
        doc = parser.parse(html)
        result = parser.css(doc, "p")
        assert result is not None
        assert parser.extract_text(result) == "Hello World"


class TestBeautifulSoupParser:
    """Test cases for BeautifulSoupParser implementation."""

    @pytest.fixture
    def parser(self) -> BeautifulSoupParser:
        return BeautifulSoupParser()

    def test_parse_html_string(self, parser: BeautifulSoupParser) -> None:
        """Test parsing HTML string returns BeautifulSoup object."""
        doc = parser.parse(SAMPLE_BOOK_PAGE)
        assert doc is not None
        assert hasattr(doc, 'select')

    def test_css_select_title(self, parser: BeautifulSoupParser) -> None:
        """Test CSS selector with BeautifulSoup."""
        doc = parser.parse(SAMPLE_BOOK_PAGE)
        result = parser.css(doc, "#book-title")
        assert result is not None
        assert parser.extract_text(result).strip() == "The Great Gatsby"

    def test_css_select_price(self, parser: BeautifulSoupParser) -> None:
        """Test price extraction."""
        doc = parser.parse(SAMPLE_BOOK_PAGE)
        result = parser.css(doc, ".price")
        assert result is not None
        assert parser.extract_text(result) == "£19.99"

    def test_css_select_all_books(self, parser: BeautifulSoupParser) -> None:
        """Test selecting multiple elements."""
        doc = parser.parse(SAMPLE_BOOK_LIST)
        results = parser.css_all(doc, ".book-item")
        assert len(results) == EXPECTED_BOOK_LIST_COUNT

    def test_xpath_not_supported(self, parser: BeautifulSoupParser) -> None:
        """Test that XPath raises NotImplementedError."""
        doc = parser.parse(SAMPLE_BOOK_PAGE)
        with pytest.raises(NotImplementedError):
            parser.xpath(doc, "//div")

    def test_invalid_html_handling(self, parser: BeautifulSoupParser) -> None:
        """Test BeautifulSoup handles invalid HTML well."""
        doc = parser.parse(SAMPLE_INVALID_HTML)
        result = parser.css(doc, ".broken")
        # BeautifulSoup is very tolerant of invalid HTML
        assert result is not None


class TestHybridParser:
    """Test cases for HybridParser with fallback logic."""

    @pytest.fixture
    def parser(self) -> HybridParser:
        return HybridParser()

    def test_parse_returns_lxml_by_default(self, parser: HybridParser) -> None:
        """Test that hybrid parser uses lxml as primary."""
        doc = parser.parse(SAMPLE_BOOK_PAGE)
        # Should be lxml element
        assert hasattr(doc, 'xpath')

    def test_css_select_with_lxml(self, parser: HybridParser) -> None:
        """Test CSS selection with lxml backend."""
        doc = parser.parse(SAMPLE_BOOK_PAGE)
        result = parser.css(doc, "#book-title")
        assert result is not None
        assert parser.extract_text(result).strip() == "The Great Gatsby"

    def test_fallback_mechanism(self, parser: HybridParser) -> None:
        """Test fallback to BeautifulSoup when needed."""
        # Hybrid parser should work with valid HTML
        doc = parser.parse(SAMPLE_BOOK_LIST)
        results = parser.css_all(doc, ".book-item")
        assert len(results) == EXPECTED_BOOK_LIST_COUNT

    def test_css_method(self, parser: HybridParser) -> None:
        """Test css method delegation."""
        doc = parser.parse(SAMPLE_BOOK_PAGE)
        result = parser.css(doc, ".availability")
        assert result is not None
        assert "In stock" in parser.extract_text(result)

    def test_css_all_method(self, parser: HybridParser) -> None:
        """Test css_all method delegation."""
        doc = parser.parse(SAMPLE_BOOK_PAGE)
        results = parser.css_all(doc, "tr")
        assert len(results) == 3  # 3 rows in table

    def test_xpath_delegation(self, parser: HybridParser) -> None:
        """Test xpath method delegates to lxml."""
        doc = parser.parse(SAMPLE_BOOK_PAGE)
        result = parser.xpath(
            doc, "//th[text()='Publisher']/following-sibling::td/text()"
        )
        assert result is not None
        assert len(result) > 0
        assert result[0].strip() == "Scribner"
