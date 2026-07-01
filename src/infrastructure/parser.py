# Infrastructure HTML Parser
"""
HTML/XML parser implementation using lxml and BeautifulSoup.

This module provides a concrete implementation of the IParser interface
using lxml for high-performance parsing with BeautifulSoup fallback for
malformed HTML handling.
"""

from typing import Any

import structlog
from bs4 import BeautifulSoup, Tag
from lxml import etree, html

from src.core.exceptions import ContentError, ParseError, SelectorError
from src.core.interfaces import IParser

logger = structlog.get_logger(__name__)


class LxmlParser:
    """
    High-performance HTML/XML parser using lxml.

    Features:
    - Fast parsing with lxml
    - CSS selector support via cssselect
    - XPath selector support (native)
    - Robust handling of malformed HTML
    - Text and attribute extraction
    """

    def __init__(self, parser_type: str = "html") -> None:
        """
        Initialize parser.

        Args:
            parser_type: Type of parser ('html' or 'xml').
        """
        self.parser_type = parser_type
        if parser_type == "html":
            self._parser = html.HTMLParser(recover=True, encoding="utf-8")
        else:
            self._parser = etree.XMLParser(recover=True, encoding="utf-8")

    def parse(self, content: str | bytes, content_type: str = "text/html") -> Any:
        """
        Parse raw content into an lxml document.

        Args:
            content: Raw HTML or XML content as string or bytes.
            content_type: MIME type of content.

        Returns:
            Parsed lxml document object.

        Raises:
            ContentError: If content cannot be parsed.
        """
        try:
            if isinstance(content, str):
                content = content.encode("utf-8")

            if "xml" in content_type.lower():
                return etree.fromstring(content, parser=self._parser)
            else:
                return html.fromstring(content, parser=self._parser)

        except Exception as e:
            logger.error("Failed to parse content", error=str(e), content_type=content_type)
            raise ContentError(
                f"Failed to parse {content_type} content: {str(e)}",
                context={"content_type": content_type, "error_type": type(e).__name__},
            ) from e

    def css(self, doc: Any, selector: str) -> Any | None:
        """
        Select single element using CSS selector.

        Args:
            doc: Parsed lxml document.
            selector: CSS selector string.

        Returns:
            First matched lxml element or None if no matches.

        Raises:
            SelectorError: If selector is invalid.
        """
        try:
            # Use cssselect for CSS selector support
            from cssselect import GenericTranslator, SelectorError

            translator = GenericTranslator()
            xpath_expr = translator.css_to_xpath(selector)
            results = doc.xpath(xpath_expr)
            return results[0] if results else None

        except SelectorError as e:
            logger.warning("Invalid CSS selector", selector=selector, error=str(e))
            raise SelectorError(
                f"Invalid CSS selector: {selector}",
                context={"selector": selector},
            ) from e

        except Exception as e:
            logger.error("CSS selection failed", selector=selector, error=str(e))
            raise SelectorError(
                f"CSS selection failed: {str(e)}",
                context={"selector": selector},
            ) from e

    def css_all(self, doc: Any, selector: str) -> list[Any]:
        """
        Select all elements using CSS selector.

        Args:
            doc: Parsed lxml document.
            selector: CSS selector string.

        Returns:
            List of matched lxml elements (empty list if no matches).

        Raises:
            SelectorError: If selector is invalid.
        """
        try:
            # Use cssselect for CSS selector support
            from cssselect import GenericTranslator, SelectorError

            translator = GenericTranslator()
            xpath_expr = translator.css_to_xpath(selector)
            return doc.xpath(xpath_expr)

        except SelectorError as e:
            logger.warning("Invalid CSS selector", selector=selector, error=str(e))
            raise SelectorError(
                f"Invalid CSS selector: {selector}",
                context={"selector": selector},
            ) from e

        except Exception as e:
            logger.error("CSS selection failed", selector=selector, error=str(e))
            raise SelectorError(
                f"CSS selection failed: {str(e)}",
                context={"selector": selector},
            ) from e

    def xpath(self, doc: Any, selector: str) -> list[Any]:
        """
        Select elements using XPath expression.

        Args:
            doc: Parsed lxml document.
            selector: XPath expression string.

        Returns:
            List of matched elements/values.

        Raises:
            SelectorError: If XPath expression is invalid.
        """
        try:
            return doc.xpath(selector)
        except etree.XPathError as e:
            logger.warning("Invalid XPath expression", xpath=selector, error=str(e))
            raise SelectorError(
                f"Invalid XPath expression: {selector}",
                context={"xpath": selector},
            ) from e

        except Exception as e:
            logger.error("XPath selection failed", xpath=selector, error=str(e))
            raise SelectorError(
                f"XPath selection failed: {str(e)}",
                context={"xpath": selector},
            ) from e

    def extract_text(self, element: Any) -> str:
        """
        Extract text content from an element.

        Args:
            element: lxml element.

        Returns:
            Text content as cleaned string.
        """
        if element is None:
            return ""

        # Get text content
        text = element.text_content() if hasattr(element, "text_content") else str(element)

        # Clean whitespace
        text = " ".join(text.split())

        return text

    def extract_attr(self, element: Any, attr_name: str) -> str | None:
        """
        Extract attribute value from an element.

        Args:
            element: lxml element.
            attr_name: Name of attribute to extract.

        Returns:
            Attribute value or None if not found.
        """
        if element is None:
            return None

        if hasattr(element, "get"):
            return element.get(attr_name)
        elif isinstance(element, dict):
            return element.get(attr_name)

        return None


class BeautifulSoupParser:
    """
    Alternative parser using BeautifulSoup for robustness.

    This parser is more tolerant of malformed HTML but slower than lxml.
    Can be used as fallback when lxml fails.
    """

    def __init__(self, parser_backend: str = "lxml") -> None:
        """
        Initialize BeautifulSoup parser.

        Args:
            parser_backend: Backend parser ('lxml', 'html.parser', 'html5lib').
        """
        self.parser_backend = parser_backend

    def parse(self, content: str | bytes, content_type: str = "text/html") -> Any:
        """
        Parse content using BeautifulSoup.

        Args:
            content: Raw HTML content.
            content_type: MIME type (only text/html supported).

        Returns:
            BeautifulSoup document object.
        """
        if isinstance(content, bytes):
            content = content.decode("utf-8", errors="replace")

        return BeautifulSoup(content, self.parser_backend)

    def css(self, doc: Any, selector: str) -> Any | None:
        """Select single element using CSS selector with BeautifulSoup."""
        try:
            results = doc.select(selector)
            return results[0] if results else None
        except Exception as e:
            logger.error("CSS selection failed", selector=selector, error=str(e))
            raise SelectorError(
                f"CSS selection failed: {str(e)}",
                context={"selector": selector},
            ) from e

    def css_all(self, doc: Any, selector: str) -> list[Any]:
        """Select all elements using CSS selector with BeautifulSoup."""
        try:
            return doc.select(selector)
        except Exception as e:
            logger.error("CSS selection failed", selector=selector, error=str(e))
            raise SelectorError(
                f"CSS selection failed: {str(e)}",
                context={"selector": selector},
            ) from e

    def xpath(self, doc: Any, selector: str) -> list[Any]:
        """
        Select elements using XPath (limited support in BeautifulSoup).

        Note: BeautifulSoup has limited XPath support. For complex XPath,
        use LxmlParser instead.

        Args:
            doc: BeautifulSoup document.
            selector: XPath expression (not directly supported).

        Returns:
            Empty list (XPath not supported).

        Raises:
            NotImplementedError: XPath is not supported in BeautifulSoup.
        """
        raise NotImplementedError(
            "XPath is not supported in BeautifulSoupParser. Use LxmlParser instead."
        )

    def extract_text(self, element: Any) -> str:
        """
        Extract text content from a BeautifulSoup element.

        Args:
            element: BeautifulSoup Tag.

        Returns:
            Text content as cleaned string.
        """
        if element is None:
            return ""

        if isinstance(element, Tag):
            text = element.get_text(separator=" ", strip=True)
        else:
            text = str(element)

        return " ".join(text.split())

    def extract_attr(self, element: Any, attr_name: str) -> str | None:
        """
        Extract attribute value from a BeautifulSoup element.

        Args:
            element: BeautifulSoup Tag.
            attr_name: Attribute name.

        Returns:
            Attribute value or None.
        """
        if element is None or not isinstance(element, Tag):
            return None

        return element.get(attr_name)


class HybridParser:
    """
    Hybrid parser that combines lxml speed with BeautifulSoup robustness.

    Uses lxml as primary parser and falls back to BeautifulSoup for
    severely malformed HTML.
    """

    def __init__(self) -> None:
        self.lxml_parser = LxmlParser()
        self.bs4_parser = BeautifulSoupParser()
        self._use_bs4 = False

    def parse(self, content: str | bytes, content_type: str = "text/html") -> Any:
        """
        Parse content with automatic fallback.

        Args:
            content: Raw HTML/XML content.
            content_type: MIME type.

        Returns:
            Parsed document (lxml or BeautifulSoup).
        """
        if not self._use_bs4:
            try:
                return self.lxml_parser.parse(content, content_type)
            except ContentError as e:
                logger.warning("Lxml parsing failed, falling back to BeautifulSoup", error=str(e))
                self._use_bs4 = True

        return self.bs4_parser.parse(content, content_type)

    def css(self, doc: Any, selector: str) -> Any | None:
        """Select single element using CSS selector with automatic backend detection."""
        if isinstance(doc, BeautifulSoup):
            return self.bs4_parser.css(doc, selector)
        return self.lxml_parser.css(doc, selector)

    def css_all(self, doc: Any, selector: str) -> list[Any]:
        """Select all elements using CSS selector with automatic backend detection."""
        if isinstance(doc, BeautifulSoup):
            return self.bs4_parser.css_all(doc, selector)
        return self.lxml_parser.css_all(doc, selector)

    def xpath(self, doc: Any, selector: str) -> list[Any]:
        """Select elements using XPath."""
        if isinstance(doc, BeautifulSoup):
            raise NotImplementedError("XPath not supported with BeautifulSoup backend")
        return self.lxml_parser.xpath(doc, selector)

    def extract_text(self, element: Any) -> str:
        """Extract text from element."""
        if isinstance(element, Tag) or (hasattr(element, "find_all") and hasattr(element, "get_text")):
            return self.bs4_parser.extract_text(element)
        return self.lxml_parser.extract_text(element)

    def extract_attr(self, element: Any, attr_name: str) -> str | None:
        """Extract attribute from element."""
        if isinstance(element, Tag) or (hasattr(element, "find_all") and hasattr(element, "get")):
            return self.bs4_parser.extract_attr(element, attr_name)
        return self.lxml_parser.extract_attr(element, attr_name)


# Default parser instance
default_parser = HybridParser()


__all__ = [
    "LxmlParser",
    "BeautifulSoupParser",
    "HybridParser",
    "default_parser",
]
