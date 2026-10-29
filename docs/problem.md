# Problem understanding

Given an origin, destination, departure time and load weight, generate 3 route options, sample weather every 10 / 25 / 50 miles at the truck's estimated arrival time at each checkpoint, classify risk with the provided risk and load rules, and recommend a route by: fewest Severe miles, fewest High miles, lowest average risk, shortest travel time. Show routes, checkpoints, risk levels, ETAs and summaries on a map, plus a corridor weather heatmap with a 0–48 hour slider.

## Open decisions

- Threshold boundaries: which band owns shared edges (e.g. rain 0.25 in/hr, wind between 34 and 35 mph).
- Combining conditions: worst of wind, rain and snow per checkpoint.
- How No Travel miles rank relative to Severe, or whether they disqualify a route.
- How checkpoint risk converts to miles (each checkpoint owns the stretch to the next).
- Numeric risk scale and weighting for "average risk".
- Sustained wind vs. gusts.
- Heatmap hour 0: now or departure time.
- Behaviour when the trip extends past the forecast horizon, or departure is in the past.
- Whether ETAs account for Hours of Service breaks.
- Fallback when the routing API returns fewer than 3 alternatives.

## Findings

- openrouteservice (v9.10.0, 2026-10-29) rejects `alternative_routes` when the route exceeds 100 km (error 2004), so it cannot produce 3 options for real truck trips. Working approach: request the direct route plus two routes forced through via points offset perpendicular from the midpoint (20% of the straight-line distance each side), with `radiuses: -1` so the via point snaps to the nearest road. Dallas → Denver gives 782 mi / 18.9 h, 885 mi / 21.8 h and 926 mi / 22.5 h.
- The URL api.openrouteservice.org is being deprecated in favour of api.heigit.org/openrouteservice.
