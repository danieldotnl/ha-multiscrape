"""Init tests for Multiscrape integration."""

class MockHttpWrapper:
    """Mock class for HttpWrapper."""

    def __init__(self, test_name):
        """Initialize the mock class."""
        self.test_name = test_name
        self.count = 0

    async def async_request(self, context, resource, method=None, request_data=None, cookies=None, variables: dict = {}):
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
        elif self.test_name == "ecommerce_product":
            return MockHttpResponse(
                """<!DOCTYPE html>
                <html>
                <head><title>Product Page</title></head>
                <body>
                    <div class="product">
                        <h1 class="product-title">Smart Home Hub</h1>
                        <div class="price-container">
                            <span class="price" data-value="149.99">$149.99</span>
                            <span class="currency">USD</span>
                        </div>
                        <div class="rating" data-rating="4.5">
                            <span class="stars">★★★★½</span>
                            <span class="count">(327 reviews)</span>
                        </div>
                        <div class="availability in-stock" data-available="true">In Stock</div>
                        <div class="description">
                            <p>Advanced smart home hub with voice control</p>
                        </div>
                        <ul class="features">
                            <li>WiFi 6 support</li>
                            <li>Zigbee compatible</li>
                            <li>Voice assistant integration</li>
                        </ul>
                        <a href="/product/12345" class="buy-button">Add to Cart</a>
                    </div>
                </body>
                </html>"""
            )
        elif self.test_name == "blog_articles":
            return MockHttpResponse(
                """<!DOCTYPE html>
                <html>
                <head><title>Blog</title></head>
                <body>
                    <article class="post">
                        <h2 class="post-title">Getting Started with Home Automation</h2>
                        <div class="meta">
                            <span class="author" data-author-id="42">Jane Smith</span>
                            <time class="published" datetime="2024-01-15T10:30:00Z">January 15, 2024</time>
                            <span class="read-time">5 min read</span>
                        </div>
                        <div class="content">
                            <p>Home automation has revolutionized the way we live...</p>
                        </div>
                        <div class="tags">
                            <span class="tag">automation</span>
                            <span class="tag">smart-home</span>
                            <span class="tag">iot</span>
                        </div>
                    </article>
                    <article class="post">
                        <h2 class="post-title">Advanced Sensor Integration</h2>
                        <div class="meta">
                            <span class="author" data-author-id="23">John Doe</span>
                            <time class="published" datetime="2024-01-10T14:20:00Z">January 10, 2024</time>
                            <span class="read-time">8 min read</span>
                        </div>
                    </article>
                </body>
                </html>"""
            )
        elif self.test_name == "weather_data":
            return MockHttpResponse(
                """<!DOCTYPE html>
                <html>
                <body>
                    <div class="weather-widget">
                        <div class="current">
                            <span class="temperature" data-celsius="22" data-fahrenheit="72">72°F</span>
                            <span class="condition">Partly Cloudy</span>
                            <img src="/icons/partly-cloudy.png" alt="weather icon" class="icon">
                        </div>
                        <div class="details">
                            <div class="humidity">Humidity: <span>65%</span></div>
                            <div class="wind">Wind: <span data-speed="12">12 mph</span></div>
                            <div class="pressure">Pressure: <span>1013 hPa</span></div>
                        </div>
                        <div class="forecast">
                            <div class="day" data-day="monday">
                                <span class="day-name">Monday</span>
                                <span class="high">75°F</span>
                                <span class="low">58°F</span>
                            </div>
                            <div class="day" data-day="tuesday">
                                <span class="day-name">Tuesday</span>
                                <span class="high">78°F</span>
                                <span class="low">60°F</span>
                            </div>
                        </div>
                    </div>
                </body>
                </html>"""
            )
        elif self.test_name == "table_data":
            return MockHttpResponse(
                """<!DOCTYPE html>
                <html>
                <body>
                    <table class="data-table">
                        <thead>
                            <tr>
                                <th>Device</th>
                                <th>Status</th>
                                <th>Battery</th>
                                <th>Last Seen</th>
                            </tr>
                        </thead>
                        <tbody>
                            <tr class="device-row" data-id="sensor1">
                                <td class="name">Temperature Sensor</td>
                                <td class="status online">Online</td>
                                <td class="battery">85%</td>
                                <td class="timestamp">2024-01-20 14:30</td>
                            </tr>
                            <tr class="device-row" data-id="sensor2">
                                <td class="name">Motion Detector</td>
                                <td class="status online">Online</td>
                                <td class="battery">92%</td>
                                <td class="timestamp">2024-01-20 14:28</td>
                            </tr>
                            <tr class="device-row" data-id="sensor3">
                                <td class="name">Door Sensor</td>
                                <td class="status offline">Offline</td>
                                <td class="battery">12%</td>
                                <td class="timestamp">2024-01-19 08:15</td>
                            </tr>
                        </tbody>
                    </table>
                </body>
                </html>"""
            )
        elif self.test_name == "news_feed":
            return MockHttpResponse(
                """<!DOCTYPE html>
                <html>
                <body>
                    <div class="news-container">
                        <div class="headline featured" data-priority="high">
                            <h1 class="title">Major Technology Breakthrough</h1>
                            <a href="/news/article-1" class="link">Read more</a>
                            <span class="category">Technology</span>
                        </div>
                        <ul class="news-list">
                            <li class="news-item">
                                <a href="/news/article-2">Smart Home Market Growth</a>
                                <span class="date">2024-01-18</span>
                            </li>
                            <li class="news-item">
                                <a href="/news/article-3">New IoT Security Standards</a>
                                <span class="date">2024-01-17</span>
                            </li>
                            <li class="news-item">
                                <a href="/news/article-4">AI Integration Updates</a>
                                <span class="date">2024-01-16</span>
                            </li>
                        </ul>
                    </div>
                </body>
                </html>"""
            )
        elif self.test_name == "list_data":
            return MockHttpResponse(
                """<!DOCTYPE html>
                <html>
                <body>
                    <div class="categories">
                        <span class="category">Electronics</span>
                        <span class="category">Home & Garden</span>
                        <span class="category">Sports</span>
                        <span class="category">Books</span>
                    </div>
                    <div class="prices">
                        <span class="price">$29.99</span>
                        <span class="price">$49.99</span>
                        <span class="price">$15.50</span>
                    </div>
                </body>
                </html>"""
            )
        elif self.test_name == "complex_json":
            return MockHttpResponse(
                """{
                    "status": "success",
                    "data": {
                        "temperature": 22.5,
                        "humidity": 65,
                        "sensors": [
                            {"id": "sensor1", "value": 23.1, "unit": "celsius"},
                            {"id": "sensor2", "value": 68, "unit": "percent"}
                        ],
                        "metadata": {
                            "timestamp": "2024-01-20T14:30:00Z",
                            "location": "Living Room"
                        }
                    }
                }"""
            )
        elif self.test_name == "xml_feed":
            return MockHttpResponse(
                """<?xml version="1.0" encoding="UTF-8"?>
                <rss version="2.0">
                    <channel>
                        <title>Smart Home News</title>
                        <link>https://example.com</link>
                        <description>Latest smart home updates</description>
                        <item>
                            <title>New Device Release</title>
                            <link>https://example.com/article1</link>
                            <description>Exciting new smart home device launched</description>
                            <pubDate>Mon, 15 Jan 2024 10:00:00 GMT</pubDate>
                            <category>Products</category>
                        </item>
                        <item>
                            <title>Integration Update</title>
                            <link>https://example.com/article2</link>
                            <description>New integration available</description>
                            <pubDate>Fri, 12 Jan 2024 14:30:00 GMT</pubDate>
                            <category>Updates</category>
                        </item>
                    </channel>
                </rss>"""
            )
        elif self.test_name == "form_page":
            return MockHttpResponse(
                """<!DOCTYPE html>
                <html>
                <body>
                    <form id="login-form" action="/login" method="post">
                        <input type="text" name="username" placeholder="Username">
                        <input type="password" name="password" placeholder="Password">
                        <input type="hidden" name="csrf_token" value="abc123xyz">
                        <button type="submit">Login</button>
                    </form>
                    <div class="protected-content" style="display:none;">
                        <div class="user-info">
                            <span class="username">john_doe</span>
                            <span class="account-level">Premium</span>
                        </div>
                    </div>
                </body>
                </html>"""
            )
        elif self.test_name == "authenticated_content":
            return MockHttpResponse(
                """<!DOCTYPE html>
                <html>
                <body>
                    <div class="dashboard">
                        <h1>Welcome Back!</h1>
                        <div class="stats">
                            <div class="stat">
                                <span class="label">Total Devices</span>
                                <span class="value">24</span>
                            </div>
                            <div class="stat">
                                <span class="label">Active</span>
                                <span class="value">22</span>
                            </div>
                            <div class="stat">
                                <span class="label">Offline</span>
                                <span class="value">2</span>
                            </div>
                        </div>
                    </div>
                </body>
                </html>"""
            )
        elif self.test_name == "nested_structure":
            return MockHttpResponse(
                """<!DOCTYPE html>
                <html>
                <body>
                    <div class="container">
                        <section class="main">
                            <div class="wrapper">
                                <div class="inner">
                                    <article class="content">
                                        <header>
                                            <h1 class="deep-title">Deeply Nested Title</h1>
                                        </header>
                                        <div class="body">
                                            <p class="deep-paragraph">This is deeply nested content</p>
                                            <div class="meta">
                                                <span class="author">
                                                    <a href="/author/123" class="author-link">Author Name</a>
                                                </span>
                                            </div>
                                        </div>
                                    </article>
                                </div>
                            </div>
                        </section>
                    </div>
                </body>
                </html>"""
            )
        elif self.test_name == "empty_elements":
            return MockHttpResponse(
                """<!DOCTYPE html>
                <html>
                <body>
                    <div class="container">
                        <div class="missing"></div>
                        <div class="empty-text"></div>
                        <div class="whitespace">   </div>
                        <div class="valid">Valid Content</div>
                    </div>
                </body>
                </html>"""
            )






class MockHttpResponse:
    """Mock class for HttpResponse."""

    def __init__(self, text):
        """Initialize the mock class."""
        self.text = text


