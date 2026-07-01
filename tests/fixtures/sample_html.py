"""Sample HTML fixture for testing parsers."""

SAMPLE_BOOK_PAGE = """
<!DOCTYPE html>
<html>
<head>
    <title>Book Page</title>
</head>
<body>
    <div class="product-page">
        <h1 id="book-title">The Great Gatsby</h1>
        <p class="price">£19.99</p>
        <p class="availability">In stock (20 available)</p>
        <div class="description">
            <p>A classic novel by F. Scott Fitzgerald.</p>
        </div>
        <ul class="breadcrumb">
            <li><a href="/">Home</a></li>
            <li><a href="/books">Books</a></li>
            <li>Fiction</li>
        </ul>
        <table class="info-table">
            <tr><th>Author</th><td>F. Scott Fitzgerald</td></tr>
            <tr><th>Publisher</th><td>Scribner</td></tr>
            <tr><th>ISBN</th><td>978-0-7432-7356-5</td></tr>
        </table>
    </div>
</body>
</html>
"""

SAMPLE_INVALID_HTML = """
<html>
<body>
    <div class="broken">
        <p>Unclosed tag
        <span>Nested wrong</div>
    </div>
</body>
</html>
"""

SAMPLE_EMPTY_PAGE = """
<!DOCTYPE html>
<html>
<head><title>Empty</title></head>
<body>
</body>
</html>
"""

SAMPLE_BOOK_LIST = """
<!DOCTYPE html>
<html>
<body>
    <div class="book-list">
        <article class="book-item" data-id="1">
            <h2 class="title">Book One</h2>
            <p class="price">£10.00</p>
            <a href="/books/book-one">Details</a>
        </article>
        <article class="book-item" data-id="2">
            <h2 class="title">Book Two</h2>
            <p class="price">£15.50</p>
            <a href="/books/book-two">Details</a>
        </article>
        <article class="book-item" data-id="3">
            <h2 class="title">Book Three</h2>
            <p class="price">£22.00</p>
            <a href="/books/book-three">Details</a>
        </article>
    </div>
</body>
</html>
"""

EXPECTED_BOOK_DATA = {
    "title": "The Great Gatsby",
    "price": "£19.99",
    "availability": "In stock (20 available)",
    "description": "A classic novel by F. Scott Fitzgerald.",
    "author": "F. Scott Fitzgerald",
    "publisher": "Scribner",
    "isbn": "978-0-7432-7356-5"
}

EXPECTED_BOOK_LIST_COUNT = 3
