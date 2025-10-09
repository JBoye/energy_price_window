from __future__ import annotations

DOMAIN = "energy_price_window"

CONF_SOURCE_ENTITY = "sensor_name"
CONF_FORECAST_SOURCE_ENTITY = "forecast_source_entity"
CONF_NAME = "name"
CONF_START_TIME = "start_time"
CONF_END_TIME = "end_time"
CONF_DURATION = "duration"
CONF_CONTINUOUS = "continuous"

ATTR_INTERVALS = "intervals"
ATTR_START_TIME = "start_time"
ATTR_END_TIME = "end_time"
ATTR_DURATION = "duration"
ATTR_CONTINUOUS = "continuous"
ATTR_NEXT_START_TIME = "next_start_time"
ATTR_AVERAGE = "average"
ATTR_LAST_CALCULATED = "last_calculated"

DEFAULT_NAME = "Price Window"
DEFAULT_START_TIME: str | None = None  # -> defaults to now()
DEFAULT_END_TIME: str | None = None  # -> defaults to dataset end
DEFAULT_DURATION = "3:00"
DEFAULT_CONTINUOUS = True
