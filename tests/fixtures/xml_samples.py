"""Sample XML data for testing XML scraping with lxml-xml parser."""

# Simple RSS feed
SAMPLE_XML_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Home Assistant Blog</title>
    <link>https://www.home-assistant.io/blog</link>
    <description>Home automation updates</description>
    <item>
      <title>Release 2024.8</title>
      <link>https://www.home-assistant.io/blog/2024/08/release</link>
      <pubDate>Wed, 07 Aug 2024 00:00:00 GMT</pubDate>
      <description>New features in 2024.8</description>
    </item>
    <item>
      <title>Release 2024.7</title>
      <link>https://www.home-assistant.io/blog/2024/07/release</link>
      <pubDate>Wed, 03 Jul 2024 00:00:00 GMT</pubDate>
      <description>New features in 2024.7</description>
    </item>
  </channel>
</rss>
"""

# Weather data in XML format
SAMPLE_XML_WEATHER = """<?xml version="1.0" encoding="UTF-8"?>
<weather>
  <location city="Amsterdam" country="NL" />
  <current>
    <temperature unit="celsius">21.5</temperature>
    <humidity unit="percent">65</humidity>
    <wind speed="12.3" direction="NW" unit="km/h" />
    <condition>Partly Cloudy</condition>
  </current>
  <forecast>
    <day date="2024-08-08">
      <high>24.0</high>
      <low>16.5</low>
      <condition>Sunny</condition>
    </day>
    <day date="2024-08-09">
      <high>22.0</high>
      <low>15.0</low>
      <condition>Rain</condition>
    </day>
  </forecast>
</weather>
"""

# SOAP-style XML response
SAMPLE_XML_SOAP = """<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"
               xmlns:ns="http://example.com/sensor">
  <soap:Body>
    <ns:GetSensorDataResponse>
      <ns:SensorReading id="sensor-001">
        <ns:Value>42.7</ns:Value>
        <ns:Unit>°C</ns:Unit>
        <ns:Timestamp>2024-08-07T14:30:00Z</ns:Timestamp>
        <ns:Status>active</ns:Status>
      </ns:SensorReading>
      <ns:SensorReading id="sensor-002">
        <ns:Value>1013.25</ns:Value>
        <ns:Unit>hPa</ns:Unit>
        <ns:Timestamp>2024-08-07T14:30:00Z</ns:Timestamp>
        <ns:Status>active</ns:Status>
      </ns:SensorReading>
    </ns:GetSensorDataResponse>
  </soap:Body>
</soap:Envelope>
"""

# Simple XML with attributes
SAMPLE_XML_ATTRIBUTES = """<?xml version="1.0" encoding="UTF-8"?>
<devices>
  <device id="light-1" type="light" room="living_room">
    <name>Living Room Light</name>
    <state>on</state>
    <brightness>80</brightness>
  </device>
  <device id="thermostat-1" type="climate" room="bedroom">
    <name>Bedroom Thermostat</name>
    <state>heating</state>
    <target_temp>21.0</target_temp>
    <current_temp>19.5</current_temp>
  </device>
  <device id="sensor-1" type="sensor" room="kitchen">
    <name>Kitchen Humidity</name>
    <state>62</state>
    <unit>%</unit>
  </device>
</devices>
"""

# XML with CDATA sections
SAMPLE_XML_CDATA = """<?xml version="1.0" encoding="UTF-8"?>
<notifications>
  <notification id="1" priority="high">
    <title>Security Alert</title>
    <message><![CDATA[Motion detected at <front door> at 02:30 AM]]></message>
    <timestamp>2024-08-07T02:30:00Z</timestamp>
  </notification>
  <notification id="2" priority="low">
    <title>Update Available</title>
    <message><![CDATA[Version 2024.8 is available for <Home Assistant>]]></message>
    <timestamp>2024-08-07T10:00:00Z</timestamp>
  </notification>
</notifications>
"""

# Empty XML document
SAMPLE_XML_EMPTY = """<?xml version="1.0" encoding="UTF-8"?>
<root/>
"""

# XML with mixed namespaces
SAMPLE_XML_NAMESPACES = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom" xmlns:custom="http://example.com/custom">
  <title>Smart Home Feed</title>
  <entry>
    <title>Door Opened</title>
    <custom:severity>warning</custom:severity>
    <custom:device>front_door</custom:device>
    <content type="text">Front door was opened</content>
  </entry>
  <entry>
    <title>Temperature High</title>
    <custom:severity>info</custom:severity>
    <custom:device>living_room_thermostat</custom:device>
    <content type="text">Temperature exceeded 25°C</content>
  </entry>
</feed>
"""

# XML with tag names that collide with HTML raw-text element names
# These are ordinary XML tags but share names with HTML's script/style/template
SAMPLE_XML_HTML_TAG_NAMES = """<?xml version="1.0" encoding="UTF-8"?>
<automation>
  <template>
    <trigger type="state">
      <entity>sensor.temperature</entity>
      <above>25</above>
    </trigger>
    <action type="service">
      <service>light.turn_on</service>
      <target>light.living_room</target>
    </action>
  </template>
  <script id="morning_routine">
    <step order="1">Open blinds</step>
    <step order="2">Turn on coffee maker</step>
  </script>
  <style name="dark_mode">
    <background>black</background>
    <foreground>white</foreground>
  </style>
</automation>
"""

# Malformed XML for error testing
SAMPLE_XML_MALFORMED = """<?xml version="1.0" encoding="UTF-8"?>
<root>
  <unclosed_tag>This is not properly closed
  <valid_tag>But this is</valid_tag>
</root>
"""
