"""Sample JSON data for testing scrapers."""

# Simple JSON object
SAMPLE_JSON_SIMPLE = '{"name":"John", "age":30, "car":null}'

# Complex nested JSON
SAMPLE_JSON_NESTED = """{
    "user": {
        "id": 123,
        "name": "John Doe",
        "email": "john@example.com",
        "preferences": {
            "theme": "dark",
            "notifications": true
        }
    },
    "data": [1, 2, 3, 4, 5]
}"""

# JSON array
SAMPLE_JSON_ARRAY = '[{"id": 1, "name": "Item 1"}, {"id": 2, "name": "Item 2"}]'

# Invalid JSON for error testing
SAMPLE_JSON_INVALID = '{"name": "John", "age": 30'  # Missing closing brace

# JSON with special characters
SAMPLE_JSON_SPECIAL_CHARS = '{"text": "Text with \\"quotes\\" and \\n newlines"}'
