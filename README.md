# HA Multiscrape

[![GitHub Release][releases-shield]][releases]
[![License][license-shield]](LICENSE)

[![pre-commit][pre-commit-shield]][pre-commit]
[![Black][black-shield]][black]

[![hacs][hacsbadge]][hacs]
![hacs installs](https://img.shields.io/endpoint.svg?url=https%3A%2F%2Flauwbier.nl%2Fhacs%2Fmultiscrape&style=for-the-badge)

[![Project Maintenance][maintenance-shield]][user_profile]
[![BuyMeCoffee][buymecoffeebadge]][buymecoffee]

[![Discord][discord-shield]][discord]
[![Community Forum][forum-shield]][forum]

## Important note: troubleshooting

If you don't manage to scrape the value you are looking for, please [enable debug logging](#debug-logging) and `log_response`. This will provide you with a lot of information for continued investigation. `log_response` will write all responses to files. If the value you want to scrape is not in the files with the output from BeautifulSoup (\*-soup.txt), Multiscrape will not be able to scrape it. Most likely it is retrieved in the background by javascript. Your best chance in this case, is to investigate the network traffic in de developer tools of your browser, and try to find a json response containing the value you are looking for.

If all of this doesn't help, use the home assistant forum. I cannot give everyone personal assistance and please don't create github issues unless you are sure there is a bug.
Check the [wiki](https://github.com/danieldotnl/ha-multiscrape/wiki) for a scraping guide and other details on the functionality of this component.

## Important note: be a good citizen and be aware of your responsibility

You and you alone, are accountable for your scraping activities. Be a good (web) citizen. Set reasonable `scan_interval` timings, seek explicit permission before scraping, and adhere to local and international laws. Respect website policies, handle data ethically, mind resource usage, and regularly monitor your actions. Uphold these principles to ensure ethical and sustainable scraping practices.

# HA MultiScrape custom component

This Home Assistant custom component can scrape multiple fields (using CSS selectors) from a single HTTP request (the existing scrape sensor can scrape a single field only). The scraped data becomes available in separate sensors.

It is based on both the existing [Rest sensor](https://www.home-assistant.io/integrations/rest/) and the [Scrape sensor](https://www.home-assistant.io/integrations/scrape). Most properties of the Rest and Scrape sensor apply.

<a href="https://www.buymeacoffee.com/danieldotnl" target="_blank"><img src="https://cdn.buymeacoffee.com/buttons/default-blue.png" alt="Buy Me A Coffee" style="height: 51px !important;width: 217px !important;" ></a>

## Installation

[![hacs][hacsbadge]][hacs]
![hacs installs](https://img.shields.io/endpoint.svg?url=https%3A%2F%2Flauwbier.nl%2Fhacs%2Fmultiscrape&style=for-the-badge)

Install via HACS (default store) or install manually by copying the files in a new 'custom_components/multiscrape' directory.

## Example configuration (YAML)

```yaml
multiscrape:
  - name: HA scraper
    resource: https://www.home-assistant.io
    scan_interval: 3600
    sensor:
      - unique_id: ha_latest_version
        name: Latest version
        select: ".current-version > h1:nth-child(1)"
        value_template: '{{ (value.split(":")[1]) }}'
      - unique_id: ha_release_date
        icon: >-
          {% if is_state('binary_sensor.ha_version_check', 'on') %}
            mdi:alarm-light
          {% else %}
            mdi:bat
          {% endif %}
        name: Release date
        select: ".release-date"
    binary_sensor:
      - unique_id: ha_version_check
        name: Latest version == 2021.7.0
        select: ".current-version > h1:nth-child(1)"
        value_template: '{{ (value.split(":")[1]) | trim == "2021.7.0" }}'
        attributes:
          - name: Release notes link
            select: "div.links:nth-child(3) > a:nth-child(1)"
            attribute: href
```

## Options

Based on latest (pre) release.

| name              | description                                                                                                               | required | default | type            |
| ----------------- | ------------------------------------------------------------------------------------------------------------------------- | -------- | ------- | --------------- |
| name              | The name for the integration.                                                                                             | False    |         | string          |
| resource          | The url for retrieving the site or a template that will output an url. Not required when `resource_template` is provided. | True     |         | string          |
| resource_template | A template that will output an url after being rendered. Only required when `resource` is not provided.                   | True     |         | template        |
| authentication    | Configure HTTP authentication. `basic` or `digest`. Use this with username and password fields.                           | False    |         | string          |
| username          | The username for accessing the url.                                                                                       | False    |         | string          |
| password          | The password for accessing the url.                                                                                       | False    |         | string          |
| headers           | The headers for the requests.                                                                                             | False    |         | template - list |
| params            | The query params for the requests.                                                                                        | False    |         | template - list |
| method            | The method for the request. Either `POST` or `GET`.                                                                       | False    | GET     | string          |
| payload           | Optional payload to send with a POST request.                                                                             | False    |         | string          |
| verify_ssl        | Verify the SSL certificate of the endpoint.                                                                               | False    | True    | boolean         |
| log_response      | Log the HTTP responses and HTML parsed by BeautifulSoup in files. (Will be written to/config/multiscrape/name_of_config)  | False    | False   | boolean         |
| timeout           | Defines max time to wait data from the endpoint.                                                                          | False    | 10      | int             |
| scan_interval     | Determines how often the url will be requested.                                                                           | False    | 60      | int             |
| parser            | Determines the parser to be used with beautifulsoup. Either `lxml` or `html.parser`.                                      | False    | lxml    | string          |
| list_separator    | Separator to be used in combination with `select_list` features.                                                          | False    | ,       | string          |
| form_submit       | See [Form-submit](#form-submit)                                                                                           | False    |         |                 |
| sensor            | See [Sensor](#sensorbinary-sensor)                                                                                        | False    |         | list            |
| binary_sensor     | See [Binary sensor](#sensorbinary-sensor)                                                                                 | False    |         | list            |
| button            | See [Refresh button](#refresh-button)                                                                                     | False    |         | list            |

### Sensor/Binary Sensor

Configure the sensors that will scrape the data.

| name                | description                                                                                                                                                                                                      | required | default | type            |
| ------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------- | ------- | --------------- |
| unique_id           | Will be used as entity_id and enables editing the entity in the UI                                                                                                                                               | False    |         | string          |
| name                | Friendly name for the sensor                                                                                                                                                                                     | False    |         | string          |
|                     | Shared fields from the [Selector](#Selector).                                                                                                                                                                    | True     |         |                 |
| attributes          | See [Sensor attributes](#sensor-attributes)                                                                                                                                                                      | False    |         | list            |
| unit_of_measurement | Defines the units of measurement of the sensor                                                                                                                                                                   | False    |         | string          |
| device_class        | Sets the device_class for [sensors](https://www.home-assistant.io/integrations/sensor/) or [binary sensors](https://www.home-assistant.io/integrations/binary_sensor/)                                           | False    |         | string          |
| state_class         | Defines the state class of the sensor, if any. (measurement, total or total_increasing) (not for binary_sensor)                                                                                                  | False    | None    | string          |
| icon                | Defines the icon or a template for the icon of the sensor. The value of the selector (or value_template when given) is provided as input for the template. For binary sensors, the value is parsed in a boolean. | False    |         | string/template |
| picture             | Contains a path to a local image and will set it as entity picture                                                                                                                                               | False    |         | string          |
| force_update        | Sends update events even if the value hasn’t changed. Useful if you want to have meaningful value graphs in history.                                                                                             | False    | False   | boolean         |

### Refresh button

Configure a refresh button to manually trigger scraping.

| name      | description                                                        | required | default | type   |
| --------- | ------------------------------------------------------------------ | -------- | ------- | ------ |
| unique_id | Will be used as entity_id and enables editing the entity in the UI | False    |         | string |
| name      | Friendly name for the button                                       | False    |         | string |

### Sensor attributes

Configure the attributes on the sensor that can be set with additional scraping values.

| name           | description                                   | required | default | type            |
| -------------- | --------------------------------------------- | -------- | ------- | --------------- |
| name           | Name of the attribute (will be slugified)     | True     |         | string          |
|                | Shared fields from the [Selector](#Selector). | True     |         |                 |

### Form-submit

Configure the form-submit functionality which enables you to submit a (login) form before scraping a site. More details on how this works [can be found on the wiki](https://github.com/danieldotnl/ha-multiscrape/wiki/Form-submit-functionality).

| name              | description                                                                                               | required | default | type                |
| ----------------- | --------------------------------------------------------------------------------------------------------- | -------- | ------- | ------------------- |
| resource          | The url for the site with the form                                                                        | False    |         | string              |
| select            | CSS selector used for selecting the form in the html. When omitted, the input fields are directly posted. | False    |         | string              |
| input             | A dictionary with name/values which will be merged with the input fields on the form                      | False    |         | string - dictionary |
| input_filter      | A list of input fields that should not be submitted with the form                                         | False    |         | string - list       |
| submit_once       | Submit the form only once on startup instead of each scan interval                                        | False    | False   | boolean             |
| resubmit_on_error | Resubmit the form after a scraping error is encountered                                                   | False    | True    | boolean             |
| header_mappings   | See [Header Mappings](#Header-Mappings)                                                                   | False    |         | list                |

### Header Mappings

Configure the headers you want to be forwarded from scraping the [Form-submit](#form-submit) page to scraping the main page for sensor data. A common use case is to populate the `X-Login-Token` header which is the result of the login.

| name           | description                                   | required | default | type            |
| -------------- | --------------------------------------------- | -------- | ------- | --------------- |
| name           | Name of the header                            | True     |         | string          |
|                | Shared fields from the [Selector](#Selector). | True     |         |                 |


### Selector

Shared field used in multiple configs above. Used to define the scraping: how to extract a value from the page.

| name           | description                                                                                                                                           | required | default | type            |
| -------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------- | -------- | ------- | --------------- |
| select         | CSS selector used for retrieving the value of the attribute. Only required when `select_list` or `value_template` is not provided.                    | False    |         | string/template |
| select_list    | CSS selector for multiple values of multiple elements which will be returned as csv. Only required when `select` or `value_template` is not provided. | False    |         | string/template |
| attribute      | Attribute from the selected element to read as value.                                                                                                 | False    |         | string          |
| value_template | Defines a template applied to extract the value from the result of the selector (if provided) or raw page (if selector not provided)                  | False    |         | string/template |
| on_error       | See [On-error](#on-error)                                                                                                                             | False    |         |                 |

### On-error

Configure what should happen in case of a scraping error (the css selector does not return a value).

| name    | description                                                                                                                                                                                                                                                             | required | default | type   |
| ------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------- | ------- | ------ |
| log     | Determines if and how something should be logged in case of a scraping error. Value can be either 'false', 'info', 'warning' or 'error'.                                                                                                                                | False    | error   | string |
| value   | Determines what value the sensor/attribute should get in case of a scraping error. The value can be 'last' meaning that the value does not change, 'none' which results in HA showing 'Unkown' on the sensor, or 'default' which will show the specified default value. | False    | none    | string |
| default | The default value to be used when the on-error value is set to 'default'.                                                                                                                                                                                               | False    |         | string |

## Services

For each multiscrape instance, a service will be created to trigger a scrape run through an automation. (For manual triggering, the button entity can now be configured.)
The services are named `multiscrape.trigger_{name of integration}`.

## Debug logging

Debug logging can be enabled as follows:

```yaml
logger:
  default: info
  logs:
    custom_components.multiscrape: debug
```

Depending on your issue, also consider enabling `log_response`.

### Contributions are welcome!

If you want to contribute to this please read the [Contribution guidelines](CONTRIBUTING.md)

### Credits

This project was generated from [@oncleben31](https://github.com/oncleben31)'s [Home Assistant Custom Component Cookiecutter](https://github.com/oncleben31/cookiecutter-homeassistant-custom-component) template.

Code template was mainly taken from [@Ludeeus](https://github.com/ludeeus)'s [integration_blueprint][integration_blueprint] template

---

[integration_blueprint]: https://github.com/custom-components/integration_blueprint
[black]: https://github.com/psf/black
[black-shield]: https://img.shields.io/badge/code%20style-black-000000.svg?style=for-the-badge
[buymecoffee]: https://www.buymeacoffee.com/danieldotnl
[buymecoffeebadge]: https://img.shields.io/badge/buy%20me%20a%20coffee-donate-yellow.svg?style=for-the-badge
[commits-shield]: https://img.shields.io/github/commit-activity/y/danieldotnl/ha-multiscrape.svg?style=for-the-badge
[commits]: https://github.com/danieldotnl/ha-multiscrape/commits/main
[hacs]: https://hacs.xyz
[hacsbadge]: https://img.shields.io/badge/HACS-Default-orange.svg?style=for-the-badge
[discord]: https://discord.gg/Qa5fW2R
[discord-shield]: https://img.shields.io/discord/330944238910963714.svg?style=for-the-badge
[forum-shield]: https://img.shields.io/badge/community-forum-brightgreen.svg?style=for-the-badge
[forum]: https://community.home-assistant.io/t/scrape-sensor-improved-scraping-multiple-values/218350
[license-shield]: https://img.shields.io/github/license/danieldotnl/ha-multiscrape.svg?style=for-the-badge
[maintenance-shield]: https://img.shields.io/badge/maintainer-%40danieldotnl-blue.svg?style=for-the-badge
[pre-commit]: https://github.com/pre-commit/pre-commit
[pre-commit-shield]: https://img.shields.io/badge/pre--commit-enabled-brightgreen?style=for-the-badge
[releases-shield]: https://img.shields.io/github/release/danieldotnl/ha-multiscrape.svg?style=for-the-badge
[releases]: https://github.com/danieldotnl/multiscrape/releases
[user_profile]: https://github.com/danieldotnl
