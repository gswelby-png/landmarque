<!-- LANDMARQUE ESTATE GUIDE BUILDER — MASTER PROMPT v2.0 -->
<!-- Recovered from session 0d011a38 — saved 2026-04-17 -->

# LANDMARQUE ESTATE GUIDE BUILDER — MASTER PROMPT v2.0

## INPUT REQUIRED (one line only):
```
TARGET REGION: [region name]
```
That is all. Do not ask for anything else. Research and build everything yourself.

---

## PHASE 0 — DISCOVER TARGET ESTATES

Search for privately owned rural estates in the target region that have
public visitor access. Use the following search strategies in parallel:

**SEARCH QUERIES TO RUN:**
- "[region] estate open to public walking"
- "[region] country estate visitor guide"
- "[region] private estate parkland public footpath"
- "[region] estate parking car park countryside"
- "site:historichouses.org [region]"
- "site:visitengland.com [region] estate"
- "[region] estate heathland woodland public access"
- "[region] manor estate countryside open"

**SOURCES TO CHECK:**
- historichouses.org (privately owned estates — ideal targets)
- visitengland.com / visitsurrey.com / equivalent regional tourism board
- OS Maps / Ordnance Survey for public footpath networks
- Alltrails.com / Komoot for walking route clusters (high cluster = high footfall estate)
- Google Maps satellite view for large green private land near population centres
- The Ramblers (ramblers.org.uk) walk databases

BUILD A LONGLIST of 10-15 candidate estates. For each record:
- Estate name
- Location (county, nearest town)
- Management type (Private / NT / EH / Charity / Council / Unknown)
- Brief description (1-2 sentences)
- Source URL

---

## SCORE EACH ESTATE (0-20 points)

### OWNERSHIP
- +4 Privately owned family estate (not NT/EH/Council)
- +2 Charity/conservation trust (not NT/EH)
- +0 National Trust / English Heritage / Council (viable but lower revenue)

### PARKING OPPORTUNITY
- +4 Has existing free informal car parking (ideal — full revenue module)
- +2 Has managed free parking (some monetisation opportunity)
- +0 Already charges for parking (parking module excluded — other revenue still possible)
- -2 No accessible parking at all (skip)

### VISITOR FOOTFALL INDICATORS
- +3 Near large population centre (50k+ people within 20 miles)
- +2 Multiple walking routes already listed on AllTrails/Komoot/Ramblers
- +1 Mentioned in regional tourism board guides

### DIGITAL GAP
- +3 No existing digital visitor guide / poor estate website
- +1 Has website but it's static/outdated (opportunity to add value)
- -2 Already has a professional visitor app or guide (low opportunity)

### REVENUE DIVERSITY
- +1 each for: fishing / shooting / accommodation / events history /
  conservation charity / distinctive photography subject / farm shop

**SHORTLIST:** Select the top 3-5 estates by score.
Present the scored longlist before proceeding, so the operator can override.

Ask: "These are the top estates I've found. Type GO to build all of them,
or type the name(s) you want to prioritise."

Then proceed autonomously without further questions.

---

## PHASE 1 — CLASSIFY EACH ESTATE

Run this for each shortlisted estate.

### 1A. MANAGEMENT TYPE
Confirm management type from estate website, Companies House, Charity Commission,
and Land Registry (use-land-property-data.service.gov.uk).

- → NT / EH / Cadw / Historic England managed → set flag: MANAGED
- → Privately owned family → set flag: PRIVATE
- → Registered charity → set flag: CHARITY (look up number at register-of-charities.charitycommission.gov.uk)
- → Unknown → ⚠️ FLAG

### 1B. EXISTING COMMERCIAL FEATURES
Search estate website + Google for:
- "Pays for parking already" → flag: HAS_PAID_PARKING
- "Has ticketed events" → flag: HAS_EVENTS
- "Has online shop / gift shop" → flag: HAS_SHOP
- "Has holiday lets / cottages" → flag: HAS_ACCOMMODATION
- "Has existing donation / membership scheme" → flag: HAS_DONATIONS
- "Has active restaurant or café" → flag: HAS_CAFE
- "Has fishing rights" → flag: HAS_FISHING
- "Has game shoot" → flag: HAS_SHOOTING

### 1C. ESTATE CHARACTER
Classify as one or more of:
WOODLAND / HEATHLAND / PARKLAND / FORMAL_GARDENS / HISTORIC_HOUSE / WORKING_FARM / MIXED

---

## PHASE 2 — DETERMINE FEATURE SET

Apply these rules. Rules are non-negotiable. Do not override.

### RULE A — MANAGEMENT RESTRICTIONS
If MANAGED (NT / EH / Council):
- ✅ INCLUDE: Walking routes, Places of interest, Fun for kids, Nearby food
- ❌ EXCLUDE: Parking revenue, Bench sponsorship, Legacy/donations, Parking module
- ⚠️ NOTE: Position as "free visitor navigation guide" — approach their local office
  not head office; local rangers often have autonomy over digital tools

If PRIVATE or CHARITY:
- ✅ All modules included unless excluded by rules below

### RULE B — PARKING
If HAS_PAID_PARKING:
- ❌ EXCLUDE: Parking revenue module
- ✅ INCLUDE: Directions + parking info page (link to their existing payment system)
- ✅ Still include all other revenue modules

If free or unmanaged parking exists:
- ✅ INCLUDE: Full parking revenue module
- This is the primary revenue opportunity — treat it as the anchor module

### RULE C — EXISTING FEATURES
- If HAS_EVENTS: ✅ Include events page but link to their existing calendar, don't duplicate it
- If HAS_SHOP: ✅ Include shopping page but focus on estate produce, smaller/artisan vendors
- If HAS_DONATIONS and management is CHARITY: ⚠️ Check if Landmarque legacy module conflicts
- If HAS_CAFE: ✅ Feature their café prominently in Places to Eat — it's an asset not a conflict

---

## PHASE 3 — DEEP RESEARCH

For each shortlisted estate, find the following. Record source URL and confidence
(HIGH / MED / LOW) for every data point. LOW = ⚠️ flag for manual check.

### 3A. ESTATE OVERVIEW
- Full official name and any alternative names used locally
- Total size in acres and hectares
- Brief history: founding date, notable owners, architectural or ecological significance, any designations (SSSI, AONB, Listed Building grade)
- Current owner name (from Land Registry or estate website)
- Main entrance postcode
- what3words address for main entrance gate
- Opening season and hours (or open year-round)
- Admission charge (if any — most rural estates are free to walk)
- Official website URL
- Social media accounts (Instagram/Facebook — look for visitor photo volume)

### 3B. WALKING ROUTES
Sources to check in order: AllTrails, Komoot, Ramblers, OS Maps, estate website, local council walking guides, Visit[County] tourism site.

For each route:
- Route name
- Distance (miles and km) ⚠️ if estimated not measured
- Duration (walking pace, not running)
- Difficulty: Easy / Moderate / Challenging
- Circular or linear?
- Key highlights (max 3 bullet points — what makes it worth doing)
- Terrain: tarmac / gravel path / grass / woodland trail / open hillside / mixed
- Gradient: flat / gently undulating / hilly
- Dog friendly: Yes / On leads only / No dogs
- Accessible (pushchair/wheelchair): Yes / Partially / No
- Start point: parking area name + postcode + what3words
- Muddy in winter?

Target: minimum 4 routes, ideally 6-8 covering range of difficulties.

### 3C. PLACES TO EAT (within 5 miles)
Sources: Google Maps, TripAdvisor, estate website, local village websites.
Prioritise: estate café/tearoom first, then village pub, local restaurant, farm shop.

For each:
- Name, Type, Village/address
- Approx drive or walk from estate entrance
- Current opening days and hours ⚠️ (verify — these change seasonally)
- Dog friendly / Price range / Signature dish
- Any connection to the estate?
- Phone number + Website

Target: minimum 6, ideally 8-10.

### 3D. PLACES OF INTEREST
Sources: estate website, Wikipedia, Historic England list, local history society, Geograph.org.uk.

For each:
- Name, Type, Description (3-4 sentences)
- Location (compass direction from car park, or trail name)
- Any seasonal relevance
- Photo: Geograph.org.uk or Wikimedia Commons URL with CC licence

Target: minimum 6, ideally 10-12.

### 3E. FUN FOR KIDS
Sources: estate website, local family blogs, TripAdvisor family reviews, Mumsnet local boards, Days Out With the Kids website.

For each activity:
- Activity name, Recommended age range, Description
- Location on estate, Cost, Seasonal availability
- Any equipment needed

Also find: nearest playground, paddling area/stream, adventure play, organised kids activities.

Target: minimum 6 items.

### 3F. CAR PARKS (if parking module included)
For each car park:
- Name, Approximate capacity, Surface
- Entrance postcode, what3words for entrance
- Disabled spaces, Height restriction
- Current charge (if free: "currently free — monetisation opportunity")
- Which walks start here, Busiest season/times, Any management issues

### 3G. BENCH SPONSORSHIP (if PRIVATE or CHARITY)
- Estimate number of existing public benches
- Identify 5-10 prime scenic spots that don't yet have benches
- Note any memorial benches already in place
- Comparable pricing from other estates: range £500-£2,500
- Is there an existing estate memorial bench scheme? ⚠️ flag if so

### 3H. EVENTS (if applicable)
- What events has the estate historically hosted?
- Are any regular (annual)?
- Approximate capacity for outdoor events
- Work with third-party organisers or run directly?
- Seasonal highlights
⚠️ Do not list specific future dates unless confirmed on official source.

### 3I. LEGACY / COMMUNITY GIVING (if PRIVATE or CHARITY)
- Registered conservation charity? → search Charity Commission
- What conservation or restoration work is active or planned?
- Is there a Friends/supporters group?
- Comparable: Friends of the Hurtwood (charity 200053) = £100k-264k/year Surrey benchmark

### 3J. EXTENDED REVENUE FEATURES
Research all; include if applicable:
- FISHING PERMITS (if river/lake on estate)
- PHOTOGRAPHY & FILMING PERMITS
- GUIDED EXPERIENCES
- CONSERVATION SPONSORSHIP
- ACCOMMODATION (if HAS_ACCOMMODATION)
- SHOOTING / GAME DAYS (if HAS_SHOOTING — handle carefully)
- ESTATE PRODUCE / FARM SHOP

---

## PHASE 4 — REVENUE PROJECTIONS

### BENCHMARKS (use these — do not invent numbers):

**PARKING:** (daily cars) × (charge) × (operating days)
- Daily cars: AllTrails/Komoot monthly downloads ÷ 30, or comparable site data
- Conservative: 30-80 cars/day off-peak, 150-400 peak days
- Charge range: £2-5/car typical rural England
- 60% collection rate Year 1 (improves with signage)

**BENCH SPONSORSHIP:** (spots) × (avg price £800) × (40% Year 1 uptake)

**LEGACY / DONATIONS:** Year 1: 15% of nearest comparable charity's annual income; Year 2: 25%; Year 3: 40%

**EVENTS:** (Ticket price) × (capacity) × (events/year) × (65% fill Year 1, 80% Year 3)

**FISHING PERMITS:** (Rods) × (days fished per season) × (day ticket price)

**PHOTOGRAPHY PERMITS:** LOW: 20-40 personal day permits/year × £35 / HIGH: 80-150/year + 5-15 commercial × £500 avg

**GUIDED EXPERIENCES:** (Walks/month) × (avg group 8) × (price £25) × (10 months). Conservative Year 1: 2/month = ~£4,800/year

---

## PHASE 5 — BUILD GUIDE CONTENT

Write production-ready content for each section.
Write as if it will go live today — no placeholders, no "[insert photo here]".

### 5A. WELCOME PAGE
- Estate name (official full name)
- Tagline (one punchy sentence — captures the spirit of the place)
- Welcome text (3-4 sentences): lead with the most distinctive thing. Tone: warm, knowledgeable, slightly elevated — like a well-written guidebook
- Hero image: Geograph.org.uk URL — Photographer — Licence

### 5B-5J: All sections as per research in Phase 3

---

## PHASE 6 — PITCH SUMMARY (one per estate)

Write a single-page pitch to the estate owner. Tone: confident, factual, peer-to-peer. No overselling. Never use the word "solution".

Structure:
1. **WHAT WE'VE BUILT** — X walking routes, Y places of interest, Z places to eat, etc.
2. **THE OPPORTUNITY** — 2-3 bullet points with Year 1 revenue estimates
3. **WHAT IT TAKES TO GO LIVE** — minimal action list
4. **WHAT WE BUILD NEXT** — after they sign
5. **NEARBY ESTATES ALREADY ONBOARD** — network effect is the strongest pitch element

---

## PHASE 7 — VERIFICATION FLAGS SUMMARY

⚠️ NEEDS MANUAL VERIFICATION — numbered list of every flagged data point

✅ CONFIDENCE SUMMARY
- High confidence (sourced and verifiable): [count]
- Medium confidence (sourced but may be outdated): [count]
- Low confidence (estimated / inferred): [count]
- Excluded features (with reason): [list]

ESTIMATED TIME TO GO LIVE (after manual verification)

---

## END OF MASTER PROMPT v2.0
