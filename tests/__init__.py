"""Init tests for Multiscrape integration."""

class MockHttpWrapper:
    """Mock class for HttpWrapper."""

    def __init__(self, test_name):
        """Initialize the mock class."""
        self.test_name = test_name
        self.count = 0

    async def async_request(self, context, resource, method=None, request_data=None, variables: dict = {}):
        """Return mocked response."""

        self.count += 1
        if self.test_name == "simple_html":
            return MockHttpResponse(
                    "<div class='current-version material-card text'>"
                        "<h1>Current Version: 2024.8.3</h1>Released: <span class='release-date'>January 17, 2022</span>"
                        "<div class='links' style='links'><a href='/latest-release-notes/'>Release notes</a>"
                        "</div>"
                    "</div>"
                    "<template>Trying to get</template>"
                    "<div class='current-time'>"
                        "<h1>Current Time:</h1><span class='utc-time'>2022-12-22T13:15:30Z</span>"
                    "</div>"
            )
        elif self.test_name == "simple_json":
            return MockHttpResponse('{"name":"John", "age":30, "car":null}')






class MockHttpResponse:
    """Mock class for HttpResponse."""

    def __init__(self, text):
        """Initialize the mock class."""
        self.text = text


