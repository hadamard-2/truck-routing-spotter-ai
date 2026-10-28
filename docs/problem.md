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
