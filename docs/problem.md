# Problem understanding

Given an origin, destination, departure time and load weight, generate 3 route options, sample weather every 10 / 25 / 50 miles at the truck's estimated arrival time at each checkpoint, classify risk with the provided risk and load rules, and recommend a route by: fewest Severe miles, fewest High miles, lowest average risk, shortest travel time. Show routes, checkpoints, risk levels, ETAs and summaries on a map, plus a corridor weather heatmap with a 0–48 hour slider.

## Decisions

The spec leaves these points open. Each decision below states what we chose and why, so anyone with better information can change it deliberately. Where the spec is explicit, it wins and nothing here overrides it.

### Ranking: No Travel miles come first

Routes are ranked by fewest No Travel miles, then the spec's own order: fewest Severe miles, fewest High miles, lowest average risk, shortest travel time.

Why: the spec's list starts at Severe and never mentions No Travel, yet No Travel is the worst level. Extending the spec's own logic ("fewer miles of the worst conditions wins") one level up is the smallest addition that keeps the ranking sensible. Folding No Travel into Severe would let a route with 30 No Travel miles beat one with 60 Severe miles and none at No Travel. Routes with No Travel miles are still shown and ranked, never hidden, so the driver sees every option.

### Wind thresholds use sustained wind

The wind bands and the load rules are applied to the forecast's sustained wind speed (Open-Meteo `wind_speed_10m`). Gusts (`wind_gusts_10m`) are shown alongside in checkpoint details but do not change the level.

Why: the spec says "wind" without qualification, and sustained speed is the usual meaning of a wind forecast. Gusts typically run 1.3–1.6× sustained speed, so applying these bands to gusts would push most breezy plains days to Severe or No Travel for heavy loads and make the recommendation alarmist. The trade-off is real: gusts are what physically push a trailer over. To switch, change the one place the wind value is read in the risk classification; a middle path is to keep sustained wind for the level and add a warning when gusts cross the next band.

### ETAs are continuous driving, without Hours of Service breaks

Checkpoint ETAs come from the routing engine's drive time with no stops added.

Why: the spec asks for the truck's estimated arrival time and does not mention driver hours. Real US trips include mandatory breaks (roughly an 11-hour driving limit with a 10-hour rest, and a 30-minute break after 8 hours of driving), which on a trip longer than ~8 hours shifts later checkpoints to later forecast hours. Adding them raises further questions the spec does not answer, such as where the driver stops and whether weather while parked counts. This is a known limitation, stated in the README.

### Heatmap hour 0 is the departure time

The 0–48 hour slider runs from departure to 48 hours after departure.

Why: it lines up the heatmap with checkpoint ETAs and the truck's position on the map, so moving the slider shows the weather the truck will actually meet. A departure several days out uses forecasts further ahead, which are less accurate; Open-Meteo forecasts reach about 16 days.

### Times are local to the origin

The departure is entered as wall-clock time at the origin, and every time the app shows (departure, checkpoint ETAs, arrival, heatmap hours) is in the origin's time zone, labelled with its abbreviation.

Why: a driver leaving Dallas at 9 AM means 9 AM in Dallas, wherever the person planning the trip is sitting. One zone for the whole trip keeps times easy to compare along the route, and matches how US drivers keep their logs (in their home terminal's time). The origin's zone comes from Open-Meteo's `timezone=auto` lookup. The API still accepts an exact instant with a zone (`...Z`).

### Builder's calls

These follow directly from the spec's wording and were settled without needing a product decision:

- Band edges: each band includes its lower bound and excludes its upper bound (rain 0.25 in/hr is High, wind 35 mph is High). The No Travel cut-offs follow the spec's own symbols: wind ≥55 mph, rain >1.00 in/hr, snow >3.0 in/hr, so exactly 1.00 in/hr of rain is Severe.
- Combining conditions: a checkpoint's level is the worst of its wind, rain and snow levels; the load rules can then only raise it.
- Load rules: strictly "over" the stated weight, so exactly 40,000 lb in 35–44 mph wind stays High.
- Miles per level: each checkpoint stands for the stretch of road from it to the next checkpoint, so a route's miles at each level sum to its length.
- Average risk: levels are scored Low 0, Moderate 1, High 2, Severe 3, No Travel 4, and averaged weighted by miles.
- Forecast hour: wind is a reading at the top of each hour, so a checkpoint reads wind at the hour nearest its ETA (14:40 reads 15:00). Rain and snow are totals over the hour before each stamp, so a checkpoint reads the hour it is driving in (14:20 and 14:40 both read the 14:00–15:00 total, stamped 15:00). Heatmap frames use the same rule.
- Rank reasons: each route is explained against its neighbour (the recommended route against the runner-up, every other route against the one above it) by the first criterion that separates them, plus the drive-time difference, so the time a safer route costs is visible.
- Beyond the forecast: checkpoints past the forecast horizon get no level and the response carries a `beyond_forecast` warning instead of failing.
- Three routes: the direct route plus two forced through via points (see Findings), because the routing API's own alternatives stop at 100 km. A via route that drives more than 5 miles of road out and back (it snapped to a dead end) is retried with the via point at another distance, and a via route sharing over 85% of its road with a route already kept is dropped; the response then warns `fewer_routes`.
- Route names: alternatives are named after the numbered highway (interstate, US or state route) they drive most beyond what any other route drives of it, e.g. "Via US 183", needing a margin of at least 20 miles. Without one, the town nearest the route's midpoint is used, then "Alternative n".
- Weather retries: a rate-limited, failed or timed-out weather request is retried after 1 s and again after 3 s. Open-Meteo's limits are per minute, so if it is still rate-limited the API answers 503 `weather_busy` with `Retry-After: 60` rather than holding the request open for a minute; the web app retries the heatmap once after that wait.
- Departure window: from 1 hour ago to 14 days ahead, the useful reach of the forecast.
- Weather lookups are rounded to ~1 km (0.01°), finer than the forecast grid, and the heatmap grid holds at most about 250 points, to stay within Open-Meteo's per-minute request limit (each location counts as a request).

## Findings

- openrouteservice (v9.10.0, 2026-10-29) rejects `alternative_routes` when the route exceeds 100 km (error 2004), so it cannot produce 3 options for real truck trips. Working approach: request the direct route plus two routes forced through via points offset perpendicular from the midpoint (20% of the straight-line distance each side), with `radiuses: -1` so the via point snaps to the nearest road. Dallas → Denver gives 782 mi / 18.9 h, 885 mi / 21.8 h and 926 mi / 22.5 h.
- The URL api.openrouteservice.org is being deprecated in favour of api.heigit.org/openrouteservice. On the new host, geocoding lives at `/pelias/v1/search`, not `/openrouteservice/geocode/search` (404).
- ORS route responses split each route into steps, each with its own duration and the range of geometry points it covers, so ETAs can follow real road speeds rather than a constant average.
- Open-Meteo returns wind in mph and rain and snowfall in inches with `wind_speed_unit=mph&precipitation_unit=inch`. Hourly values are the amount over the preceding hour, which is in/hr. Total rain is `rain` + `showers`. One request can carry many locations.
