# Weather-Aware Truck Routing

A React + Django app that helps a truck driver choose the safest route. Given an origin, destination, departure time and load weight, it builds 3 route options, checks the forecast at each checkpoint for the hour the truck gets there, classifies the risk with the load rules, and recommends a route. A map shows every route with its checkpoints, risk levels and ETAs, and a weather heatmap along the trip corridor runs from departure to 48 hours later.

## How it works

1. **Places.** Origin and destination are typed (with suggestions as you type) or picked on the map, and geocoded through openrouteservice.
2. **Routes.** openrouteservice's truck (`driving-hgv`) profile gives the direct route. Its built-in alternatives stop at 100 km, so the other two routes are forced through via points on either side of the straight line; a via route that doubles back or mostly repeats another route is dropped, and the app says so when fewer than 3 remain. Alternatives are named after the highway that sets them apart, e.g. "Via US 287".
3. **Checkpoints.** Each route is sampled every 10, 25 or 50 miles (user's choice). A checkpoint's ETA follows the drive times openrouteservice gives for each stretch of road, so cities are slow and highways fast.
4. **Weather.** Open-Meteo gives hourly wind, rain and snow. Wind is read at the hour nearest the ETA; rain and snow are read for the hour the truck is driving in.
5. **Risk.** Each checkpoint takes the worst of its wind, rain and snow levels, then the load rules can raise it:

   | Condition | Low | Moderate | High | Severe | No Travel |
   |---|---|---|---|---|---|
   | Wind | <25 mph | 25–34 | 35–44 | 45–54 | ≥55 mph |
   | Rain | <0.10 in/hr | 0.10–0.25 | 0.25–0.50 | 0.50–1.00 | >1.00 |
   | Snow | <0.5 in/hr | 0.5–1.0 | 1.0–2.0 | 2.0–3.0 | >3.0 |

   Load rules: 45–54 mph with more than 30,000 lb is No Travel; 35–44 mph with more than 40,000 lb is Severe.
6. **Recommendation.** Each checkpoint stands for the road up to the next one, so every route gets its miles at each level. Routes are ranked by fewest No Travel miles, then the spec's order: fewest Severe miles, fewest High miles, lowest average risk, shortest travel time. Each route's card says why it sits where it does compared with its neighbour, including what that costs or saves in drive time.
7. **Heatmap.** A grid of up to 250 points within 25 miles of any route gets 49 hourly frames in one request. The map draws it as one smoothed image; the slider moves in quarter hours, blends between forecast hours, and can play the 48 hours with the truck moving along the selected route.

All times are entered and shown in the origin's local time zone.

Every judgement call the spec leaves open (band edges, why No Travel ranks first, sustained wind rather than gusts, and the rest) is written down with its reasoning in [docs/problem.md](docs/problem.md). The API between the frontend and backend is in [docs/api-contract.md](docs/api-contract.md).

## Known limitations

- **No Hours of Service breaks.** ETAs assume continuous driving. On a trip longer than about 8 hours, a real driver's mandatory breaks (30 minutes after 8 hours of driving, 10 hours of rest after 11) would put later checkpoints into later forecast hours.
- **Sustained wind, not gusts.** The risk bands apply to sustained wind speed. Gusts are shown in checkpoint details but don't change the level.
- **Forecast reach.** Departures can be up to 14 days ahead; checkpoints past the end of the forecast get no level, and the app warns about it. Forecasts further out are less accurate.
- **Free-tier APIs.** openrouteservice and Open-Meteo have per-minute and daily limits. If Open-Meteo is busy, the plan fails with a "try again in a minute" message, and the heatmap retries once on its own.

## Run locally

You need Python 3.14 with [uv](https://docs.astral.sh/uv/), Node with [pnpm](https://pnpm.io/), and a free [openrouteservice API key](https://openrouteservice.org/dev/#/signup). Open-Meteo needs no key.

Backend (http://127.0.0.1:8000):

```bash
cd backend
cp ../.env.example .env   # then set ORS_API_KEY
uv run python manage.py runserver
```

Frontend (http://localhost:5173, proxies `/api` to the backend):

```bash
cd frontend
pnpm install
pnpm dev
```

## Tests and checks

```bash
cd backend && uv run pytest
```

```bash
cd frontend && pnpm lint && pnpm build
```

The backend tests run without network access: routes come from a captured openrouteservice response for Dallas → Denver, and weather is synthetic.

## Project layout

```
backend/
  routing/
    planner.py           builds the /api/plan and /api/heatmap responses
    risk.py              risk bands and load rules
    ranking.py           route summaries, ranking and rank reasons
    corridor.py          the heatmap grid around the routes
    services/
      routes.py          openrouteservice routes and via-point alternatives
      checkpoints.py     checkpoints and ETAs along a route
      weather.py         Open-Meteo forecasts, retries and caching
      geocoding.py       place search and reverse lookup
frontend/src/
  App.tsx                page layout and state
  components/
    TripForm.tsx         trip inputs
    MapView.tsx          routes, checkpoints, markers and popups
    HeatGrid.tsx         the heatmap image
    TimeSlider.tsx       the 0–48 hour slider and playback
    RouteList.tsx        route cards and risk strips
docs/
  problem.md             decisions and findings
  api-contract.md        the frontend–backend API
```
