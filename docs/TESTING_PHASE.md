# FASE 7 — TESTING

## 7.1 Tujuan Fase Testing

Fase testing bertujuan untuk memastikan framework scraping:
- Berfungsi sesuai spesifikasi
- Menangani edge cases dengan baik
- Memiliki coverage yang memadai (>80%)
- Mudah di-maintain dan di-extend
- Tahan terhadap perubahan kode (regression-resistant)

## 7.2 Strategi Testing

Kami mengadopsi **Testing Pyramid** dengan komposisi:
- **70% Unit Tests**: Test individual components secara isolasi
- **20% Integration Tests**: Test interaksi antar komponen
- **10% End-to-End Tests**: Test full pipeline dengan data nyata

## 7.3 Testing Tools

| Tool | Fungsi | Alasan Pemilihan |
|------|--------|------------------|
| `pytest` | Test runner | Ekosistem plugin kaya, syntax sederhana |
| `pytest-asyncio` | Async test support | Mendukung async/await dalam tests |
| `pytest-cov` | Coverage reporting | Terintegrasi dengan pytest |
| `pytest-mock` | Mocking utilities | Wrapper around unittest.mock |
| `httpx` | HTTP mocking | Async-compatible HTTP client |

## 7.4 Struktur Testing

```
tests/
├── __init__.py
├── conftest.py              # Shared fixtures & configuration
├── fixtures/
│   └── sample_html.py       # HTML samples untuk testing
├── unit/
│   ├── __init__.py
│   ├── test_core.py         # Tests untuk core module
│   ├── test_parser.py       # Tests untuk parser infrastructure
│   ├── test_http_client.py  # Tests untuk HTTP client
│   └── test_storage.py      # Tests untuk storage backends
├── integration/
│   ├── __init__.py
│   └── test_full_pipeline.py # End-to-end pipeline tests
└── e2e/
    └── test_real_scraping.py # Tests dengan website nyata (optional)
```

## 7.5 Test Coverage Saat Ini

### Unit Tests (✅ Selesai - 42 tests passing)

#### `test_core.py` (19 tests)
- ✅ Request validation
- ✅ Response handling
- ✅ Item creation
- ✅ Exception hierarchy
- ✅ Encoding handling

#### `test_parser.py` (23 tests)
- ✅ LxmlParser: CSS selectors, XPath, attribute extraction
- ✅ BeautifulSoupParser: CSS selectors, error handling
- ✅ HybridParser: Fallback mechanism, delegation

### Integration Tests (🔄 Dalam Pengembangan)

Akan mencakup:
- Full pipeline execution dengan mock HTTP
- Retry logic dengan simulated failures
- Circuit breaker behavior
- Storage pipeline integration

### Edge Cases yang Ditangani

1. **Invalid Input**:
   - Malformed HTML
   - Empty responses
   - Invalid selectors
   - Missing attributes

2. **Network Issues**:
   - Timeouts
   - Connection errors
   - HTTP errors (4xx, 5xx)
   - Redirects

3. **Parsing Edge Cases**:
   - Unicode characters
   - Whitespace variations
   - Nested structures
   - Missing elements

4. **Storage Edge Cases**:
   - Duplicate items
   - Large datasets
   - File permission issues
   - Database connection failures

## 7.6 Best Practices Testing

### 7.6.1 Fixture Management
```python
# ✅ GOOD: Reusable fixtures in conftest.py
@pytest.fixture
def sample_html() -> str:
    return "<html><body><h1>Test</h1></body></html>"

@pytest.fixture
def parser() -> HybridParser:
    return HybridParser()
```

### 7.6.2 Test Naming Convention
```python
# ✅ GOOD: Descriptive test names
def test_css_select_title_when_element_exists() -> None
def test_css_select_returns_none_when_element_not_found() -> None
def test_parser_handles_malformed_html_gracefully() -> None
```

### 7.6.3 Assertion Style
```python
# ✅ GOOD: Clear assertions with context
assert result is not None, "Expected element to be found"
assert len(results) == 3, f"Expected 3 items, got {len(results)}"
assert parser.extract_text(result) == "Hello World"
```

### 7.6.4 Async Testing
```python
# ✅ GOOD: Async tests with pytest-asyncio
@pytest.mark.asyncio
async def test_async_fetch_success() -> None:
    client = HttpxDownloader()
    response = await client.fetch(Request(url="https://example.com"))
    assert response.status_code == 200
```

## 7.7 Running Tests

```bash
# Run all tests
pytest

# Run with coverage report
pytest --cov=src --cov-report=term-missing

# Run specific test file
pytest tests/unit/test_parser.py -v

# Run specific test class
pytest tests/unit/test_parser.py::TestLxmlParser -v

# Run specific test function
pytest tests/unit/test_parser.py::TestLxmlParser::test_css_select_title -v

# Run tests matching pattern
pytest -k "css" -v

# Run with detailed output on failure
pytest -vvv --tb=long

# Run without coverage (faster)
pytest --no-cov
```

## 7.8 Coverage Requirements

Minimum coverage thresholds:
- **Overall**: 80%
- **Core module**: 90%
- **Infrastructure**: 85%
- **Middleware**: 80%

Coverage enforcement via `pyproject.toml`:
```toml
[tool.pytest.ini_options]
addopts = "--cov=src --cov-report=term-missing --cov-fail-under=80"
```

## 7.9 Continuous Integration

Tests akan dijalankan otomatis pada:
- Setiap push ke repository
- Setiap pull request
- Sebelum merge ke branch utama

CI Pipeline stages:
1. Lint & Format check (Ruff, Black)
2. Type checking (mypy)
3. Unit tests
4. Integration tests
5. Coverage report

## 7.10 Kesimpulan Fase 7

Testing framework telah dibangun dengan:
- ✅ 42 unit tests passing
- ✅ Comprehensive fixtures untuk reusable test data
- ✅ Coverage tracking dengan threshold 80%
- ✅ Support untuk async testing
- ✅ Edge case handling untuk robust error scenarios

Framework testing siap digunakan dan dapat di-extend seiring penambahan fitur baru.

**Status**: ✅ SELESAI

Fase selanjutnya: **FASE 8 — LOGGING**
