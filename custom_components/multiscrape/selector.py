from homeassistant.const import CONF_VALUE_TEMPLATE

from .const import CONF_ATTR
from .const import CONF_INDEX
from .const import CONF_SELECT
from .const import CONF_SELECT_LIST


class Selector:
    def __init__(self, hass, conf):
        self.select_template = conf.get(CONF_SELECT)
        self.select_list_template = conf.get(CONF_SELECT_LIST)
        self.attribute = conf.get(CONF_ATTR)
        self.index = conf.get(CONF_INDEX)
        self.value_template = conf.get(CONF_VALUE_TEMPLATE)

        if not self.select_template and not self.select_list_template:
            raise ValueError(
                "Selector error: either select or select_list should contain a selector."
            )

        if self.value_template is not None:
            self.value_template.hass = hass
        if self.select_template is not None:
            self.select_template.hass = hass
        if self.select_list_template is not None:
            self.select_list_template.hass = hass

    @property
    def is_list(self):
        return self.select_list_template is not None

    @property
    def element(self):
        return self.select_template.async_render(parse_result=True)

    @property
    def list(self):
        return self.select_list_template.async_render(parse_result=True)
