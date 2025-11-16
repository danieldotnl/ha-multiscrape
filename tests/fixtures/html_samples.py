"""Sample HTML data for testing scrapers."""

# Standard test HTML with various elements and structure
# Note: Whitespace is preserved as it affects extraction behavior
SAMPLE_HTML_FULL = """<div class='current-version material-card text'><h1>Current Version: 2024.8.3</h1>Released: <span class='release-date'>January 17, 2022</span><div class='links' style='links'><a href='/latest-release-notes/'>Release notes</a></div></div><template>Trying to get</template><div class='current-time'><h1>Current Time:</h1><span class='utc-time'>2022-12-22T13:15:30Z</span></div>"""

# Simple HTML for basic testing
SAMPLE_HTML_SIMPLE = """
<div class="test">
    <h1>Test Header</h1>
    <p class="content">Test content here</p>
    <a href="/test-link" class="link">Test Link</a>
</div>
"""

# HTML with special characters and encoding
SAMPLE_HTML_SPECIAL_CHARS = """
<div class="special">
    <p>Text with &amp; ampersand &lt; less than &gt; greater than</p>
    <p class="unicode">Unicode: café, naïve, 日本語</p>
</div>
"""

# Malformed HTML for error testing
SAMPLE_HTML_MALFORMED = """
<div class="unclosed">
    <p>This paragraph is not closed
    <div>Nested div
</div>
"""

# HTML with no content
SAMPLE_HTML_EMPTY = ""

# HTML for list selector testing
SAMPLE_HTML_LIST = """
<ul class="items">
    <li class="item">Item 1</li>
    <li class="item">Item 2</li>
    <li class="item">Item 3</li>
</ul>
"""

# HTML with script and style tags (special extraction)
SAMPLE_HTML_SPECIAL_TAGS = """
<html>
    <style>
        .test { color: red; }
    </style>
    <script>
        console.log("test");
    </script>
    <template>
        <div>Template content</div>
    </template>
</html>
"""
