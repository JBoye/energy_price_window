from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
	DOMAIN,
	CONF_SOURCE_ENTITY,
	CONF_FORECAST_SOURCE_ENTITY,
	CONF_NAME,
	CONF_START_TIME,
	CONF_END_TIME,
	CONF_DURATION,
	CONF_CONTINUOUS,
	DEFAULT_NAME,
	DEFAULT_START_TIME,
	DEFAULT_END_TIME,
	DEFAULT_DURATION,
	DEFAULT_CONTINUOUS,
)

# Create flow schema:
# - sensor_name: required EntitySelector
# - forecast_source_entity: OPTIONAL EntitySelector (no default) – can be left blank
# - other fields: text/boolean selectors as before
DATA_SCHEMA = vol.Schema(
	{
		vol.Required(CONF_SOURCE_ENTITY): selector.EntitySelector(
			selector.EntitySelectorConfig(domain=["sensor"])
		),
		# Optional forecast entity using EntitySelector. No default so users can leave it empty.
		vol.Optional(CONF_FORECAST_SOURCE_ENTITY): selector.EntitySelector(
			selector.EntitySelectorConfig(domain=["sensor"])
		),
		vol.Optional(CONF_NAME, default=DEFAULT_NAME): selector.TextSelector(),
		vol.Optional(CONF_START_TIME, default=""): selector.TextSelector(),
		vol.Optional(CONF_END_TIME, default=""): selector.TextSelector(),
		vol.Required(CONF_DURATION, default=DEFAULT_DURATION): selector.TextSelector(),
		vol.Optional(CONF_CONTINUOUS, default=DEFAULT_CONTINUOUS): selector.BooleanSelector(),
	}
)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
	VERSION = 1

	async def async_step_user(self, user_input=None):
		if user_input is not None:
			# If forecast is empty, drop the key so it remains truly optional
			forecast_val = user_input.get(CONF_FORECAST_SOURCE_ENTITY)
			if not forecast_val:
				user_input.pop(CONF_FORECAST_SOURCE_ENTITY, None)

			return self.async_create_entry(
				title=user_input.get(CONF_NAME) or DEFAULT_NAME,
				data=user_input,
			)
		return self.async_show_form(step_id="user", data_schema=DATA_SCHEMA)

	async def async_step_import(self, user_input):
		# Support YAML imports; apply the same empty-forecast normalization
		if user_input is not None:
			forecast_val = user_input.get(CONF_FORECAST_SOURCE_ENTITY)
			if not forecast_val:
				user_input.pop(CONF_FORECAST_SOURCE_ENTITY, None)
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
			# Normalize empty forecast to "unset"
			forecast_val = user_input.get(CONF_FORECAST_SOURCE_ENTITY)
			if not forecast_val:
				user_input.pop(CONF_FORECAST_SOURCE_ENTITY, None)

			res = self.async_create_entry(title="", data=user_input)
			# Ensure platforms re-read the updated options
			self.hass.async_create_task(
				self.hass.config_entries.async_reload(self.entry.entry_id)
			)
			return res

		# Merge existing data + options for defaults
		data = {**self.entry.data, **(self.entry.options or {})}

		# If there is no saved forecast, use vol.UNDEFINED so HA doesn't inject a blank string;
		# that keeps the field truly optional in the form.
		forecast_default = (
			data.get(CONF_FORECAST_SOURCE_ENTITY)
			if data.get(CONF_FORECAST_SOURCE_ENTITY)
			else vol.UNDEFINED
		)

		schema = vol.Schema(
			{
				vol.Required(
					CONF_SOURCE_ENTITY,
					default=data.get(CONF_SOURCE_ENTITY, ""),
				): selector.EntitySelector(
					selector.EntitySelectorConfig(domain=["sensor"])
				),
				vol.Optional(
					CONF_FORECAST_SOURCE_ENTITY,
					default=forecast_default,
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
					CONF_DURATION, default=str(data.get(CONF_DURATION, DEFAULT_DURATION))
				): selector.TextSelector(),
				vol.Optional(
					CONF_CONTINUOUS,
					default=bool(data.get(CONF_CONTINUOUS, DEFAULT_CONTINUOUS)),
				): selector.BooleanSelector(),
			}
		)
		return self.async_show_form(step_id="init", data_schema=schema)
