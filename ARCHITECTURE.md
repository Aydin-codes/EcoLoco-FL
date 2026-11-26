# EcoLoco-FL Architecture

## Part 1: How EcoLoco works (no coding needed)

You take or upload up to 5 photos of one plant and enter your school's Florida ZIP code. Pl@ntNet, a plant identification AI, guesses which plant it is. If Pl@ntNet's top matches are close, OpenAI looks at the photos and suggests one, and you still pick. If Pl@ntNet can't be reached, OpenAI names the plant instead. If that answer isn't sure either, you pick from OpenAI's list. If no match is strong enough, the app says it couldn't identify the plant. Then the app checks the plant against a few lists, in order, and stops at the first list that knows it. You see whether the plant is native, non-native or invasive, and which list the answer came from. If no list knows the plant, the app says so instead of guessing.

```mermaid
flowchart TD
  photo["Photo"] --> reach{"Pl@ntNet reachable?"}
  reach -->|Yes| plantnet["Pl@ntNet names it"]
  reach -->|No| openai["OpenAI names it"]
  plantnet --> sure{"Sure enough?"}
  openai --> sure
  sure -->|No| suggest["OpenAI suggests one<br>(Pl@ntNet path only)"]
  suggest --> pick["You pick"]
  sure -->|Yes| invasive["Florida invasive list"]
  pick --> invasive
  invasive --> native["Our native list"]
  native --> atlas["Our short not-native list"]
  atlas --> usda["USDA"]
  usda --> result["Result"]
```

### Where each answer comes from

| Question | Where the answer comes from |
|---|---|
| What plant is this? | Pl@ntNet. If Pl@ntNet can't be reached, OpenAI looks at the photos instead. |
| Is it invasive? | Florida Invasive Species Council (FISC) 2026 list, 179 plants |
| Is it native? | Our list of 21 South Florida natives, then the USDA PLANTS database |
| Is it non-native but not invasive? | USF Atlas of Florida Plants (one plant so far: tropical sage), then USDA |
| What should our school plant? | Our list of 30 native plants, each checked by our team. Only shown for Palm Beach County ZIP codes. |
| Which plants feed the most caterpillars? | National Wildlife Federation keystone plant list for South Florida |
| What grows near our school? | iNaturalist, within about 5 km |
| Where is our school? | OpenStreetMap, plus a ZIP-to-county table from the 2020 Census |

### What the AI does and doesn't do

- Pl@ntNet names the plant from your photos. If Pl@ntNet can't be reached, OpenAI names it instead, and that answer goes through the same picker and list checks.
- When Pl@ntNet's top matches are close, OpenAI looks at the photos and suggests one. You still pick.
- OpenAI rewords the first paragraph of the letter to your principal. If the new wording adds a plant or changes a number, the app throws it out and keeps the original.
- The AI never decides if a plant is native or invasive, and never picks which plants to recommend. Those answers come only from the lists above.

### How we know it works

- 1124 automated tests check the backend, the data files and the app's wording. They all pass.
- **Coontie bug:** the same coontie photo got four different answers. Pl@ntNet split its score between two names for the same plant, so a Mexican plant won. Now the app merges names for the same plant before ranking, and shows "Which one is it?" when it isn't sure.
- **Asparagus fern bug:** asparagus fern showed as "Non-native" even though it is on Florida's invasive list. Pl@ntNet calls it *Asparagus densiflorus*, and our list only had *Asparagus aethiopicus*. We added the other names Pl@ntNet, USDA and POWO use for each invasive plant.

## Part 2: Technical details

The app is an Expo (SDK 57) React Native app that also runs on the web. It talks to a Python Flask backend. The frontend reads the backend address from `EXPO_PUBLIC_API_URL` (`frontend/services/geminiService.js`). API keys stay in the backend's `.env`.

### Folder structure

| Path | What's there |
|---|---|
| `App.js`, `index.js`, `app.json` | App start, safe-area setup, and Expo settings |
| `frontend/screens/` | One file per screen: `HomeScreen.js`, `IdentificationScreen.js`, `AuditScreen.js` (EcoScan), `AuditResultsScreen.js`, `RecommendationScreen.js` |
| `frontend/navigation/AppNavigator.js` | The four bottom tabs, plus the results screen |
| `frontend/components/` | Pieces shared between screens (match picker, plan cards, leaf ring, location picker, photo strip and more) |
| `frontend/services/geminiService.js` | Sends every request to the backend. The name is left over from an early Gemini version. |
| `frontend/theme.js`, `frontend/motion.js` | Colors, fonts, text sizes, and animation timing (turned off when reduce motion is on) |
| `frontend/photoFiles.js`, `frontend/photoFiles.web.js` | Photo picking. The web version also turns iPhone HEIC photos into JPEGs. |
| `frontend/cameraAccess.js`, `frontend/lastPlace.js` | Camera permission, and the last location set (kept in memory only) |
| `backend/app.py` | The Flask server and all API routes |
| `backend/services/` | The backend logic (see below) |
| `backend/data/` | Data files that ship with the backend (see below) |
| `backend/scripts/` | Scripts that rebuild data files from their official sources |
| `backend/tests/` | The pytest tests |
| `docs/architecture.html` | Interactive code map. Its `graph-data` JSON is the source for the generated sections at the end of this file. |
| `render.yaml` | Render hosting config for the backend |

### Main backend files

| File | What it does |
|---|---|
| `backend/app.py` | Defines the routes. Checks input: Florida ZIP codes only (32004 to 34997), 1 to 5 photos, JPEG or PNG, at most 10 MB each. |
| `backend/services/identification_service.py` | Sends photos to Pl@ntNet, merges names for the same plant, and decides between "identified", "confirm" (Which one is it?) and "unidentified". Calls OpenAI for close calls, or for everything if Pl@ntNet fails. |
| `backend/services/ai_service.py` | Builds what Identify shows, handles "choose by name", and builds the letter. The letter is made from the plan, and OpenAI may only reword its opening. |
| `backend/services/fl_plants_service.py` | `get_status()` checks a plant in order: FISC, our natives, our Atlas non-natives, then USDA. |
| `backend/services/species_service.py` | `resolve()` turns any name (scientific name, synonym or common name) into one scientific name. |
| `backend/services/usda_service.py` | Asks the USDA PLANTS database if a plant is native to Florida. |
| `backend/services/plan_service.py` | Builds the plan: a Remove card for each invasive found, and Add cards from our 30 checked plants. |
| `backend/services/summary_service.py` | Counts plants by status and works out percent native, now and with the plan. |
| `backend/services/location_service.py` | Address and ZIP lookup (OpenStreetMap Nominatim), the Palm Beach County check, and "Seen near you" (iNaturalist). |
| `backend/services/name_search.py` | Search for "Choose by name" over 5322 plant names recorded in Florida. |
| `backend/services/name_guard.py` | Checks that the AI's letter wording adds no new plant or animal names. |
| `backend/services/photo_service.py` | Finds the stored photo and photo credit for a plant. |
| `backend/services/openai_client.py` | The one place that calls OpenAI (model `gpt-4o-mini`, temperature 0). |

Identification thresholds, from `identification_service.py`:
- Top Pl@ntNet score under 0.20: "Couldn't identify this".
- Matches under 0.05 are dropped.
- Top score under 0.80, or within 0.15 of the runner-up: "Which one is it?".

### API endpoints

All routes are `POST` and live in `backend/app.py`.

| Route | Takes | Gives back |
|---|---|---|
| `/identify` | `images` (1 to 5 photos), `location` (ZIP) | Ranked matches, each with Florida status and source |
| `/names` | `query` (up to 80 characters) | Up to 20 matching Florida plant names |
| `/choose` | `scientific_name`, `location` | The same result shape as `/identify`, for a plant picked by name |
| `/recommend` | `location`, optional `site` (light, moisture, space, care) | Native plants to add, and whether this ZIP is checked for planting advice |
| `/plan` | `plants`, `location`, optional `skip`, `site`, `show_all`, `letter_extras` | Remove cards, Add cards, and the percent native summary |
| `/locate` | `query` (address or ZIP), or `lat` and `lon` | Rounded coordinates and a Florida ZIP |
| `/nearby` | `lat`, `lon` | The 5 plants seen most within about 5 km, from iNaturalist |
| `/letter` | `plan`, `zip_code` | The letter text, and whether the AI was available |

### Data files

All are in `backend/data/` and ship with the backend.

| File | What's in it |
|---|---|
| `fisc_list.json` | The FISC 2026 invasive list: 179 plants (85 Category I, 94 Category II), with other names for each. Built by `backend/scripts/build_fisc_list.py`. |
| `fl_natives.json` | 21 South Florida native plants |
| `fl_non_natives.json` | Plants the USF Atlas lists as not native (1 so far: tropical sage) |
| `fl_recommendations.json` | 30 native plants we recommend, each marked verified, with sources |
| `fl_plant_names.json` | 5322 plant names from the USDA Florida checklist, for "Choose by name" |
| `fl_zip_counties.json` | 1013 Florida ZIP codes and their county, from the 2020 Census |
| `nwf_keystone_fl.json` | NWF Ecoregion 15 caterpillar counts by plant group |
| `plant_photos.json` | 198 openly licensed iNaturalist photos with credits |
| `why_this_matters.json` | The sourced facts in "Why this matters" on the results screen |
| `nature_terms.json` | Plant and animal words the letter check watches for |

### Outside services

| Service | Used for | Called from |
|---|---|---|
| Pl@ntNet | Naming the plant from photos | `backend/services/identification_service.py` |
| OpenAI (`gpt-4o-mini`) | Breaking close calls, naming the plant if Pl@ntNet is down, rewording the letter opening | `backend/services/openai_client.py` |
| USDA PLANTS | Native or introduced, for plants not on our lists | `backend/services/usda_service.py` |
| OpenStreetMap Nominatim | Turning an address or GPS point into a ZIP code | `backend/services/location_service.py` |
| iNaturalist | "Seen near you" | `backend/services/location_service.py` |

## Full code map

The interactive version is at https://ecoloco.app/docs/architecture.html, or open [`docs/architecture.html`](docs/architecture.html) locally. It needs internet to load its layout library. Click any box to see what that file or function does, what it calls, and what calls it.

### Keeping this in sync

The `graph-data` JSON block in `docs/architecture.html` is the single source of truth. Everything between the `GENERATED` markers below is produced from it. After a significant change:

1. Edit the nodes and edges in `docs/architecture.html` (each node has a file, symbol, what, how, and an optional goal).
2. Run `node docs/sync-architecture.mjs`. It fails if a node points at code that no longer exists, or if a screen, API client function, route or service function has no node. It warns when a PLANNED node's code now exists. Then it rewrites the sections below.
3. `node docs/sync-architecture.mjs --check` only checks, without rewriting.

### Layers in the diagram

| Layer | What it means | Where |
|---|---|---|
| **Screen / UI** | What the user sees and taps | `frontend/screens/`, `frontend/components/`, `frontend/navigation/AppNavigator.js` |
| **Device** | Phone features the app uses: camera, photo library, clipboard | `expo-image-picker`, `expo-clipboard` |
| **API client** | Frontend functions that send requests to our backend | `frontend/services/geminiService.js` |
| **Flask route** | A backend URL that receives those requests | `backend/app.py` |
| **Service** | Backend functions that do the work | `backend/services/*.py` |
| **Bundled data** | Data files that ship with the backend | `backend/data/*.json` |
| **External API** | Outside services the backend calls | Pl@ntNet, OpenAI, USDA, Nominatim, iNaturalist |

| Marker | What it means |
|---|---|
| **Planned** | Doesn't exist yet but is decided. Drawn dashed, with its goal. |
| **Change planned** | Exists today, but a planned change will modify it. |
| **Dead code** | Exists but does nothing useful. Drawn dotted grey. |

### Planned and pending changes

<!-- GENERATED:planned -->
| Item | Status | Goal |
|---|---|---|
| `identifyPlant()`, `getPlantRecommendations()`, `generateLetter()`, `getPlan()`, `locate()`, `getNearby()` (frontend/services/geminiService.js) | change planned | File becomes apiClient.js, since it calls our Flask API, not Gemini. |
| `get_status()` (backend/services/fl_plants_service.py) | change planned | Add ZIP-specific regional lists behind the same get_status(). |
| `fisc_list.json` (backend/data/fisc_list.json) | change planned | Verify the 22 curated "why" lines against FISC / UF-IFAS, the way the 30 recommended plants were checked. |
| `fl_natives.json` (backend/data/fl_natives.json) | change planned | Verify every entry against UF/IFAS and the Atlas of Florida Plants, the way the 30 recommended plants were checked. |
<!-- /GENERATED:planned -->

### Diagram

One box per file, so it fits on a page. Screen-to-screen links and small UI pieces are left out. For every function and what passes between them, use the interactive map above.

<!-- GENERATED:mermaid -->
```mermaid
%%{init: {"flowchart": {"nodeSpacing": 18, "rankSpacing": 45}}}%%
flowchart LR
  subgraph L_ui["Screens & UI"]
    direction TB
    g0["HomeScreen.js"]
    g1["IdentificationScreen.js"]
    g2["RecommendationScreen.js"]
    g3["AuditScreen.js"]
    g4["AuditResultsScreen.js"]
    g5["SavedAuditsScreen.js"]
  end
  subgraph L_client["API client"]
    direction TB
    g6["geminiService.js"]
  end
  subgraph L_route["Flask routes"]
    direction TB
    g7["POST /identify"]
    g8["POST /recommend"]
    g9["POST /letter"]
    g25["POST /plan"]
    g31["POST /locate"]
    g32["POST /nearby"]
    g36["POST /names"]
    g37["POST /choose"]
    g43["POST /ask"]
  end
  subgraph L_svc["Services"]
    direction TB
    g10["ai_service.py"]
    g11["fl_plants_service.py"]
    g16["identification_service.py"]
    g18["usda_service.py"]
    g19["species_service.py"]
    g20["summary_service.py"]
    g24["plan_service.py"]
    g26["name_guard.py"]
    g30["location_service.py"]
    g38["name_search.py"]
    g40["photo_service.py"]
    g42["rate_limit.py"]
    g44["ask_service.py"]
  end
  subgraph L_data["Bundled data"]
    direction TB
    g13["fisc_list.json"]
    g14["fl_natives.json"]
    g21["fl_recommendations.json"]
    g22["nwf_keystone_fl.json"]
    g23["nature_terms.json"]
    g27["why_this_matters.json"]
    g34["fl_zip_counties.json"]
    g35["fl_non_natives.json"]
    g39["fl_plant_names.json"]
    g41["plant_photos.json"]
  end
  subgraph L_ext["External APIs"]
    direction TB
    g12["OpenAI (gpt-4o-mini)"]
    g15["USDA PLANTS"]
    g17["PlantNet API"]
    g28["Nominatim (OpenStreetMap)"]
    g29["iNaturalist API"]
    g33["USF Atlas of Florida Plants"]
  end
  g1 --> g6
  g1 --> g33
  g2 --> g6
  g2 --> g33
  g3 --> g6
  g4 --> g6
  g4 --> g33
  g6 --> g43
  g6 --> g37
  g6 --> g36
  g6 --> g32
  g6 --> g31
  g6 --> g25
  g6 --> g9
  g6 --> g8
  g6 --> g7
  g7 --> g10
  g8 --> g30
  g8 --> g24
  g9 --> g10
  g10 --> g11
  g10 --> g26
  g10 --> g12
  g10 --> g16
  g11 --> g40
  g11 --> g21
  g11 --> g19
  g11 --> g35
  g11 --> g18
  g11 --> g14
  g11 --> g13
  g16 --> g17
  g16 --> g19
  g16 --> g12
  g18 --> g15
  g19 --> g21
  g19 --> g14
  g19 --> g13
  g20 --> g11
  g24 --> g40
  g24 --> g20
  g24 --> g27
  g24 --> g22
  g24 --> g21
  g25 --> g30
  g25 --> g24
  g26 --> g23
  g30 --> g34
  g30 --> g28
  g30 --> g11
  g30 --> g29
  g31 --> g30
  g32 --> g30
  g36 --> g38
  g37 --> g10
  g37 --> g38
  g38 --> g39
  g40 --> g41
  g43 --> g44
  g44 --> g26
  g44 --> g22
  g44 --> g21
  g44 --> g13
  g44 --> g19
  g44 --> g11
  g44 --> g12
  classDef ui fill:#e3f2e1,stroke:#2e7d32,color:#12301a
  classDef device fill:#eceff1,stroke:#607d8b,color:#263238
  classDef client fill:#e1effa,stroke:#1e6fb8,color:#0d2d4d
  classDef route fill:#fff1d6,stroke:#c77800,color:#4a2c00
  classDef svc fill:#f1e4f7,stroke:#7b3fa0,color:#2e0f40
  classDef data fill:#e0f4f1,stroke:#00897b,color:#00332d
  classDef ext fill:#fde4e1,stroke:#c0392b,color:#4a0f08
  classDef planned stroke-dasharray:6 4,stroke-width:2px
  classDef dead fill:#f3f3f3,stroke:#9e9e9e,color:#616161,stroke-dasharray:3 3
  class g0,g1,g2,g3,g4,g5 ui
  class g6 client
  class g7,g8,g9,g25,g31,g32,g36,g37,g43 route
  class g10,g11,g16,g18,g19,g20,g24,g26,g30,g38,g40,g42,g44 svc
  class g13,g14,g21,g22,g23,g27,g34,g35,g39,g41 data
  class g12,g15,g17,g28,g29,g33 ext
```
<!-- /GENERATED:mermaid -->
