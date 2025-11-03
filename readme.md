# Energy Price Window 

**Energy Price Window** calculates the cheapest time window based on electricity price data from **Energidataservice** or **Stromligning**.  
It creates a **binary sensor** that turns **on** when the current time is within the optimal (lowest-price) window and exposes detailed attributes for automations and dashboards — ideal for scheduling energy-intensive tasks like EV charging or heating during the cheapest hours.


## Installation

1. In Home Assistant, open **HACS → Integrations**  
2. Click the **⋮ (menu)** in the top-right → **Custom repositories**  
3. In the dialog:  
   - **Repository:** `https://github.com/JBoye/energy_price_window`  
   - **Type:** `Integration`  
4. Click **Add**, then **Close**  
5. The repository will now appear in HACS — search for **Energy Price Window** and click **Download**  
6. **Restart Home Assistant** to load the integration


## Setup

1. Go to **Settings → Devices & Services → Integrations**  
2. Click **Add Integration** and search for **Energy Price Window**  
3. Fill out the fields in the setup dialog:
   - **sensor_name** — Select a energy **price sensor**. Currently tested with the **Energidataservice** and **Stromligning** integration  
   - **forecast_source_entity** — (Optional) Select an entity that provides forecast data  
   - **name** — Enter a friendly name for this price window (e.g. *Cheapest 3h Window*)  
   - **start_time** — (Optional) Restrict calculation to start after this time  
     - Defaults to `{{ now() }}`  
     - Accepts both **time strings** (e.g. `07:00`) and **templates**  
   - **end_time** — (Optional) Restrict calculation to end before this time  
     - Defaults to the **available data range** in the selected price or forecast sensor  
     - Accepts both **time strings** and **templates**  
   - **duration** — Set the length of the window (e.g. `3:00` for 3 hours)  
     - Accepts both **time strings** and **templates**  
   - **continuous** — Toggle ON to only allow continuous time windows (default: ON)

4. Click **Submit**  
5. A new **binary_sensor** will be created. It turns **on** when the current time falls within the cheapest calculated price window.

## Sensor Attributes

The binary sensor provides detailed information about the current and next cheapest price window:

| Attribute | Description | Example |
|------------|--------------|----------|
| **intervals** | List of one or more optimal intervals. If **continuous = true**, there will always be **exactly one** interval. | `start: '2025-11-04T01:45:00+01:00'`, `end: '2025-11-04T04:25:00+01:00'`, `average: 1.2171875` |
| **start_time** | Start of the price data range considered | `November 3, 2025 at 14:14:00` |
| **end_time** | End of the price data range considered | `November 4, 2025 at 07:00:00` |
| **duration** | Duration of the target window (in hours) | `2.67` |
| **continuous** | Whether the window must be a single, continuous period | `true` |
| **next_start_time** | Start of the next cheapest period | `November 4, 2025 at 01:45:00` |
| **average** | Average price within the current cheapest window | `1.22` |
| **last_calculated** | Timestamp of the latest calculation | `November 3, 2025 at 14:14:00` |

