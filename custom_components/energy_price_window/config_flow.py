from __future__ import annotations
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    CONF_CONTINUOUS,
    CONF_DURATION,
    CONF_END_TIME,
    CONF_FORECAST_SOURCE_ENTITY,
    CONF_NAME,
    CONF_SOURCE_ENTITY,
    CONF_START_TIME,
    DEFAULT_CONTINUOUS,
    DEFAULT_DURATION,
    DEFAULT_NAME,
    DOMAIN,
)

# start_time / end_time are OPTIONAL; leave empty to use runtime defaults.
DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_SOURCE_ENTITY): selector.EntitySelector(
            selector.EntitySelectorConfig(domain=["sensor"])
        ),
        vol.Optional(CONF_FORECAST_SOURCE_ENTITY, default=""): selector.EntitySelector(
            selector.EntitySelectorConfig(domain=["sensor"])
        ),
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): selector.TextSelector(),
        vol.Optional(
            CONF_START_TIME, default=""
        ): selector.TextSelector(),  # e.g. {{ today_at('16:00') }} or blank
        vol.Optional(
            CONF_END_TIME, default=""
        ): selector.TextSelector(),  # e.g. {{ today_at('22:00') }} or blank
        vol.Required(CONF_DURATION, default=DEFAULT_DURATION): selector.TextSelector(),
        vol.Optional(
            CONF_CONTINUOUS, default=DEFAULT_CONTINUOUS
        ): selector.BooleanSelector(),
    }
)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(
                title=user_input.get(CONF_NAME) or DEFAULT_NAME,
                data=user_input,
            )
        return self.async_show_form(step_id="user", data_schema=DATA_SCHEMA)

    async def async_step_import(self, user_input):
        return await self.async_step_user(user_input)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return OptionsFlowHandler(config_entry)


class OptionsFlowHandler(config_entries.OptionsFlow):
    def __init__(self, entry):
        self.entry = entry

    async def async_step_init(self, user_input=None):
        if user_input is not None:
            res = self.async_create_entry(title="", data=user_input)
            self.hass.async_create_task(
                self.hass.config_entries.async_reload(self.entry.entry_id)
            )
            return res

        data = {**self.entry.data, **(self.entry.options or {})}
        schema = vol.Schema(
            {
                vol.Required(
                    CONF_SOURCE_ENTITY, default=data.get(CONF_SOURCE_ENTITY, "")
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain=["sensor"])
                ),
                vol.Optional(
                    CONF_FORECAST_SOURCE_ENTITY,
                    default=data.get(CONF_FORECAST_SOURCE_ENTITY, ""),
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain=["sensor"])
                ),
                vol.Optional(
                    CONF_NAME, default=data.get(CONF_NAME, DEFAULT_NAME)
                ): selector.TextSelector(),
                vol.Optional(
                    CONF_START_TIME, default=str(data.get(CONF_START_TIME, "") or "")
                ): selector.TextSelector(),
                vol.Optional(
                    CONF_END_TIME, default=str(data.get(CONF_END_TIME, "") or "")
                ): selector.TextSelector(),
                vol.Required(
                    CONF_DURATION,
                    default=str(data.get(CONF_DURATION, DEFAULT_DURATION)),
                ): selector.TextSelector(),
                vol.Optional(
                    CONF_CONTINUOUS,
                    default=bool(data.get(CONF_CONTINUOUS, DEFAULT_CONTINUOUS)),
                ): selector.BooleanSelector(),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
