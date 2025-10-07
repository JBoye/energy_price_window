from __future__ import annotations
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import template
from homeassistant.helpers.event import async_track_state_change_event, async_track_time_interval
from homeassistant.util import dt as dt_util

from .const import (
	ATTR_CONTINUOUS, ATTR_DURATION, ATTR_END_TIME, ATTR_INTERVALS, ATTR_LAST_CALCULATED, ATTR_START_TIME,
	CONF_CONTINUOUS, CONF_DURATION, CONF_END_TIME, CONF_SOURCE_ENTITY, CONF_START_TIME, CONF_NAME,
	DEFAULT_NAME, DEFAULT_START_TIME, DEFAULT_END_TIME, DEFAULT_DURATION, DEFAULT_CONTINUOUS, CONF_FORECAST_SOURCE_ENTITY
)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities) -> None:
	async_add_entities([PriceWindowBinarySensor(hass, entry)])

class PriceWindowBinarySensor(BinarySensorEntity):
	_should_poll = False

	def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
		self.hass = hass
		self._entry = entry
		data = {**entry.data, **(entry.options or {})}

		name = data.get(CONF_NAME) or DEFAULT_NAME
		self._attr_name = name
		self._entity_id = data[CONF_SOURCE_ENTITY]
		self._forecast_entity_id = data.get(CONF_FORECAST_SOURCE_ENTITY)

		raw_start = data.get(CONF_START_TIME, DEFAULT_START_TIME)
		raw_end = data.get(CONF_END_TIME, DEFAULT_END_TIME)

		self._tmpl_start = template.Template(str(raw_start), hass) if raw_start else None
		self._tmpl_end = template.Template(str(raw_end), hass) if raw_end else None

		self._tmpl_duration = template.Template(str(data.get(CONF_DURATION, DEFAULT_DURATION)), hass)
		self._continuous_raw = data.get(CONF_CONTINUOUS, DEFAULT_CONTINUOUS)

		self._attr_unique_id = f"{entry.entry_id}"
		self._attr_is_on = False
		self._attr_extra_state_attributes: Dict[str, Any] = {}

	async def async_added_to_hass(self) -> None:
		watch = [self._entity_id]
		if self._forecast_entity_id:
			watch.append(self._forecast_entity_id)
		self.async_on_remove(async_track_state_change_event(self.hass, watch, self._handle_change))
		self.async_on_remove(async_track_time_interval(self.hass, self._handle_time_tick, timedelta(minutes=1)))
		await self._recalc()

	async def _handle_change(self, *_): await self._recalc()
	async def _handle_time_tick(self, *_): await self._recalc()

	def _render_native(self, tmpl: template.Template | None) -> Any:
		if tmpl is None:
			return None
		try:
			return tmpl.async_render(parse_result=True)
		except TypeError:
			return tmpl.async_render()

	def _parse_datetime(self, value: Any) -> Optional[datetime]:
		if isinstance(value, datetime): return value
		if isinstance(value, str):
			dt = dt_util.parse_datetime(value)
			if dt: return dt
			try:
				naive = datetime.fromisoformat(value)
				return dt_util.as_local(naive) if naive.tzinfo is None else naive
			except Exception:
				return None
		return None

	def _parse_today_time(self, value: Any, now_local: datetime) -> Optional[datetime]:
		if not isinstance(value, str): return None
		s = value.strip()
		if ":" not in s or "T" in s or "-" in s or "/" in s: return None
		try:
			parts = s.split(":")
			h = int(parts[0]); m = int(parts[1])
			sec = float(parts[2]) if len(parts) > 2 else 0.0
			sec_i = int(sec); micro = int(round((sec - sec_i) * 1_000_000))
			base = dt_util.as_local(now_local)
			return base.replace(hour=h, minute=m, second=sec_i, microsecond=micro)
		except Exception:
			return None

	def _parse_duration(self, value: Any) -> Optional[timedelta]:
		if isinstance(value, timedelta): return value
		if isinstance(value, (int, float)): return timedelta(hours=float(value))
		if isinstance(value, str):
			v = value.strip()
			if ":" in v:
				parts = v.split(":")
				if len(parts) >= 2:
					try:
						h = float(parts[0]); m = float(parts[1]); s = float(parts[2]) if len(parts) > 2 else 0.0
						return timedelta(hours=h, minutes=m, seconds=s)
					except Exception:
						return None
			try:
				return timedelta(hours=float(v))
			except Exception:
				return None
		return None

	def _parse_bool(self, value: Any) -> bool:
		if isinstance(value, bool): return value
		if isinstance(value, (int, float)): return bool(value)
		if isinstance(value, str):
			v = value.strip().lower()
			if v in ("true", "on", "1", "yes"): return True
			if v in ("false", "off", "0", "no"): return False
		return False

	def _coerce_dt(self, val: Any) -> Optional[datetime]:
		if isinstance(val, datetime): return dt_util.as_local(val)
		if isinstance(val, str): return self._parse_datetime(val)
		return None

	def _read_items_from_entity(self, entity_id: str) -> List[dict]:
		ent = self.hass.states.get(entity_id)
		if not ent: return []
		attrs = ent.attributes or {}
		raw_prices = attrs.get("prices") or []
		if raw_prices:
			out: List[dict] = []
			for p in raw_prices:
				if not isinstance(p, dict): continue
				st = self._coerce_dt(p.get("start")); ed = self._coerce_dt(p.get("end")); pr = p.get("price")
				if st is None or ed is None or pr is None: continue
				if ed <= st: continue
				out.append({"start": st, "end": ed, "price": float(pr)})
			out.sort(key=lambda x: x["start"])
			return out
		raw_today = attrs.get("raw_today") or []
		raw_tomorrow = attrs.get("raw_tomorrow") or []
		arr = list(raw_today) + list(raw_tomorrow)
		if len(arr) == 0: return []
		def _coerce_hour(x: Any) -> Optional[datetime]:
			h = x.get("hour") if isinstance(x, dict) else None
			if isinstance(h, datetime): return dt_util.as_local(h)
			if isinstance(h, str): return self._parse_datetime(h)
			return None
		items: List[dict] = []
		# infer slot if possible
		slot = None
		if len(arr) >= 2:
			h0 = _coerce_hour(arr[0]); h1 = _coerce_hour(arr[1])
			if h0 and h1 and h1 > h0:
				slot = h1 - h0
		for p in arr:
			if not isinstance(p, dict): continue
			h = _coerce_hour(p)
			pr = p.get("price")
			if h is None or pr is None: continue
			if slot is None:
				# default to 1 hour if cadence unknown
				slot = timedelta(hours=1)
			items.append({"start": h, "end": h + slot, "price": float(pr)})
		items.sort(key=lambda x: x["start"])
		return items

	def _merge_overlaps(self, intervals: List[Tuple[datetime, datetime]]) -> List[Tuple[datetime, datetime]]:
		if not intervals: return []
		ints = sorted(intervals, key=lambda x: x[0])
		out = []
		cs, ce = ints[0]
		for s, e in ints[1:]:
			if s <= ce:
				if e > ce: ce = e
			else:
				out.append((cs, ce))
				cs, ce = s, e
		out.append((cs, ce))
		return out

	def _subtract_blockers(self, segment: Tuple[datetime, datetime], blockers: List[Tuple[datetime, datetime]]) -> List[Tuple[datetime, datetime]]:
		s0, e0 = segment
		if not blockers: return [(s0, e0)]
		rem = [(s0, e0)]
		for bs, be in blockers:
			new_rem = []
			for rs, re in rem:
				if be <= rs or bs >= re:
					new_rem.append((rs, re)); continue
				if bs <= rs and be >= re:
					continue
				if bs <= rs < be < re:
					new_rem.append((be, re)); continue
				if rs < bs < re <= be:
					new_rem.append((rs, bs)); continue
				if rs < bs and be < re:
					new_rem.append((rs, bs)); new_rem.append((be, re)); continue
			rem = new_rem
			if not rem: break
		return rem

	def _clip_to_range(self, s: datetime, e: datetime, r0: datetime, r1: datetime) -> Optional[Tuple[datetime, datetime]]:
		if e <= r0 or s >= r1: return None
		return max(s, r0), min(e, r1)

	def _time_weighted_avg(self, segs: List[dict]) -> Optional[float]:
		total = 0.0
		w = 0.0
		for seg in segs:
			d = (seg["end"] - seg["start"]).total_seconds()
			if d <= 0: continue
			total += seg["price"] * d
			w += d
		if w <= 0: return None
		return total / w

	async def _recalc(self) -> None:
		now_local = dt_util.now()

		primary = self._read_items_from_entity(self._entity_id)
		if not primary:
			return

		# infer nominal primary slot (used for candidate stepping and grouping equality)
		if len(primary) >= 1:
			primary_slot = primary[0]["end"] - primary[0]["start"]
			if len(primary) >= 2:
				d = primary[1]["start"] - primary[0]["start"]
				if d.total_seconds() > 0:
					primary_slot = d
		else:
			return

		forecast: List[dict] = []
		if self._forecast_entity_id:
			rawf = self._read_items_from_entity(self._forecast_entity_id)
			if rawf:
				blockers = self._merge_overlaps([(p["start"], p["end"]) for p in primary])
				for f in rawf:
					parts = self._subtract_blockers((f["start"], f["end"]), blockers)
					for s, e in parts:
						if e > s:
							forecast.append({"start": s, "end": e, "price": f["price"]})

		items_all = sorted(primary + forecast, key=lambda x: x["start"])

		start_val = self._render_native(self._tmpl_start)
		end_val = self._render_native(self._tmpl_end)
		duration_val = self._render_native(self._tmpl_duration)

		start_dt = None
		if start_val is not None:
			start_dt = self._parse_today_time(start_val, now_local) or self._parse_datetime(start_val)
		if start_dt is None:
			start_dt = now_local

		end_dt = None
		if end_val is not None:
			end_dt = self._parse_today_time(end_val, now_local) or self._parse_datetime(end_val)
		if end_dt is None:
			end_dt = items_all[-1]["end"]
		if end_dt <= now_local:
			end_dt = end_dt + timedelta(days=1)

		duration_td = self._parse_duration(duration_val)
		if not duration_td:
			return

		continuous = self._continuous_raw if isinstance(self._continuous_raw, bool) else self._parse_bool(self._continuous_raw)

		# Filter to evaluation range
		segs = []
		for it in items_all:
			clipped = self._clip_to_range(it["start"], it["end"], start_dt, end_dt)
			if clipped:
				s, e = clipped
				segs.append({"start": s, "end": e, "price": it["price"]})
		if not segs:
			self._attr_is_on = False
			self._attr_extra_state_attributes = {
				ATTR_INTERVALS: [],
				ATTR_START_TIME: start_dt.isoformat(),
				ATTR_END_TIME: end_dt.isoformat(),
				ATTR_DURATION: duration_td.total_seconds() / 3600,
				ATTR_CONTINUOUS: bool(continuous),
				"next_start_time": None,
				"average": None,
				ATTR_LAST_CALCULATED: now_local.isoformat(),
			}
			self.async_write_ha_state()
			return
		segs.sort(key=lambda x: x["start"])

		# Build candidate start points at every price-change boundary within range
		candidates = [s["start"] for s in segs if s["start"] >= start_dt and s["start"] + duration_td <= end_dt]
		intervals: List[dict] = []

		if continuous:
			best_avg = None
			best_window = None
			for s0 in candidates:
				t_end = s0 + duration_td
				wparts: List[dict] = []
				covered = 0.0
				for seg in segs:
					if seg["end"] <= s0: continue
					if seg["start"] >= t_end: break
					ss = max(seg["start"], s0)
					ee = min(seg["end"], t_end)
					if ee > ss:
						wparts.append({"start": ss, "end": ee, "price": seg["price"]})
						covered += (ee - ss).total_seconds()
					if covered + 1e-6 >= duration_td.total_seconds():
						break
				if covered + 1e-6 < duration_td.total_seconds():
					continue
				avg = self._time_weighted_avg(wparts)
				if avg is None: continue
				if best_avg is None or avg < best_avg:
					best_avg = avg
					best_window = (s0, t_end, wparts)
			if best_window:
				s0, t_end, wparts = best_window
				intervals = [{"start": s0, "end": t_end, "average": self._time_weighted_avg(wparts)}]
		else:
			need = duration_td.total_seconds()
			# consider all segments by price (cheapest first)
			segs_sorted = sorted(segs, key=lambda x: (x["price"], x["start"]))
			picks: List[dict] = []
			for seg in segs_sorted:
				if need <= 0: break
				seg_len = (seg["end"] - seg["start"]).total_seconds()
				if seg_len <= 0: continue
				take = min(need, seg_len)
				picks.append({"start": seg["start"], "end": seg["start"] + timedelta(seconds=take), "price": seg["price"]})
				need -= take
			if picks:
				picks.sort(key=lambda x: x["start"])
				group: List[dict] = []
				for p in picks:
					if not group:
						group = [p]; continue
					prev = group[-1]
					if p["start"] == prev["end"] and p["price"] == prev["price"]:
						group[-1] = {"start": prev["start"], "end": p["end"], "price": prev["price"]}
					elif p["start"] == prev["end"]:
						group.append(p)
					else:
						avg = self._time_weighted_avg(group)
						intervals.append({"start": group[0]["start"], "end": group[-1]["end"], "average": avg})
						group = [p]
				if group:
					avg = self._time_weighted_avg(group)
					intervals.append({"start": group[0]["start"], "end": group[-1]["end"], "average": avg})

		active = any(i["start"] <= now_local < i["end"] for i in intervals)

		next_start = None
		future_starts = [i["start"] for i in intervals if i["start"] > now_local]
		if future_starts:
			next_start = min(future_starts)

		total_sec = sum((i["end"] - i["start"]).total_seconds() for i in intervals)
		weighted_avg = None
		if total_sec > 0:
			weighted_avg = sum(i["average"] * (i["end"] - i["start"]).total_seconds() for i in intervals) / total_sec

		self._attr_is_on = active
		self._attr_extra_state_attributes = {
			ATTR_INTERVALS: [{"start": dt_util.as_local(i["start"]).isoformat(),
			                  "end": dt_util.as_local(i["end"]).isoformat(),
			                  "average": i["average"]} for i in intervals],
			ATTR_START_TIME: start_dt.isoformat(),
			ATTR_END_TIME: end_dt.isoformat(),
			ATTR_DURATION: duration_td.total_seconds() / 3600,
			ATTR_CONTINUOUS: bool(continuous),
			"next_start_time": dt_util.as_local(next_start).isoformat() if next_start else None,
			"average": weighted_avg,
			ATTR_LAST_CALCULATED: now_local.isoformat(),
		}
		self.async_write_ha_state()
