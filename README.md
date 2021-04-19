# HA Multiscrape

[![GitHub Release][releases-shield]][releases]
[![License][license-shield]](LICENSE)

[![pre-commit][pre-commit-shield]][pre-commit]
[![Black][black-shield]][black]

[![hacs][hacsbadge]][hacs]
[![Project Maintenance][maintenance-shield]][user_profile]
[![BuyMeCoffee][buymecoffeebadge]][buymecoffee]

[![Discord][discord-shield]][discord]
[![Community Forum][forum-shield]][forum]

# HA MultiScrape custom component

This Home Assistant custom component can scrape multiple fields (using CSS selectors) from a single HTTP request (the existing scrape sensor can scrape a single field only). The scraped data becomes available in separate sensors.

It is based on both the existing [Rest sensor](https://www.home-assistant.io/integrations/rest/) and the [Scrape sensor](https://www.home-assistant.io/integrations/scrape). Most properties of the Rest and Scrape sensor apply.

<a href="https://www.buymeacoffee.com/danieldotnl" target="_blank"><img src="https://cdn.buymeacoffee.com/buttons/default-blue.png" alt="Buy Me A Coffee" style="height: 51px !important;width: 217px !important;" ></a>

### Installation

[![hacs][hacsbadge]][hacs]

Install via HACS (default store) or install manually by copying the files in a new 'custom_components/multiscrape' directory.

### Example configuration (YAML)

```yaml
sensor:
  - platform: multiscrape
    name: home assistant scraper
    resource: https://www.home-assistant.io
    scan_interval: 30
    selectors:
      version:
        name: Current version
        select: ".current-version > h1:nth-child(1)"
        value_template: '{{ (value.split(":")[1]) }}'
      releasedate:
        name: Release date
        select: ".release-date"
```

## Contributions are welcome!

If you want to contribute to this please read the [Contribution guidelines](CONTRIBUTING.md)

## Credits

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
