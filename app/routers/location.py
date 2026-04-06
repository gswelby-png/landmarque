from fastapi import APIRouter, Depends, HTTPException, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from datetime import date, datetime, timedelta, timezone
import stripe
import os

from ..database import get_db
from ..models import CarPark, Transaction, TransactionStatus
from ..pricing import get_active_rule, calculate_price, build_duration_options

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

# Walk data — keyed by estate slug then walk slug
WALKS = {
    "shere-manor-estate": [
        {
            "slug": "shere-village",
            "title": "Shere Village",
            "distance": "0.5 km",
            "duration": "15 min",
            "difficulty": "Easy",
            "summary": "A short walk around the village, taking in various interesting buildings, the church, stores, restaurants.",
            "image_url": "",
            "center": [51.2164, -0.4444],
            "zoom": 16,
            "waypoint_zoom": 17,
            "route": [
                [51.21696,-0.4448],[51.21697,-0.44463],[51.21696,-0.4448],[51.21667,-0.44476],[51.21636,-0.4447],[51.21632,-0.44466],[51.2163,-0.44465],[51.21628,-0.44462],[51.21624,-0.44454],[51.21619,-0.44443],[51.21615,-0.44431],[51.21602,-0.44372],[51.21593,-0.44334],[51.21569,-0.44233],[51.21568,-0.44227],[51.21559,-0.44171],[51.21551,-0.44156],[51.21542,-0.44146],[51.21536,-0.44144],[51.21521,-0.44143],[51.2152,-0.44135],[51.21517,-0.44111],[51.2152,-0.44135],[51.21521,-0.44143],[51.21536,-0.44144],[51.21542,-0.44146],[51.21551,-0.44156],[51.21559,-0.44171],[51.21568,-0.44227],[51.21569,-0.44233],[51.21593,-0.44334],[51.21602,-0.44372],[51.21615,-0.44431],[51.21619,-0.44443],[51.21624,-0.44454],[51.21628,-0.44462],[51.2163,-0.44465],[51.21632,-0.44466],[51.21636,-0.4447],[51.21667,-0.44476],[51.21696,-0.4448]
            ],
            "waypoint_coords": [
                [51.2167, -0.4451], [51.2170, -0.4443], [51.2163, -0.4434], [51.2158, -0.4440]
            ],
            "waypoints": [
                {
                    "title": "Shere Car Park",
                    "description": [
                        "Start at the village car park, one of only a handful of spaces available in this small but perpetually busy village. Shere is consistently voted one of the most beautiful villages in England, and it is easy to see why — the streets are lined with timber-framed houses, many dating from the 15th and 16th centuries, and there is not a chain shop or supermarket in sight.",
                        "From the car park, follow the path toward the village centre. You will cross a small bridge over the Tillingbourne, the chalk stream that has shaped life in Shere for centuries. Look down into the crystal-clear water and you may spot brown trout hovering in the current, barely moving in their effortless way against the flow.",
                    ],
                    "image_url": ""
                },
                {
                    "title": "St James' Church",
                    "description": [
                        "St James' Church is the undisputed heart of Shere and one of the finest Norman churches in Surrey. The main structure dates from around 1190, though there have been places of worship on this site for much longer. The square flint tower is a landmark for miles around, and the interior contains remarkable medieval features including a 13th-century font and fine stained glass.",
                        "Look for the small window set into the north wall of the chancel — this is the anchorite's cell, home to Christine Carpenter, who in 1329 had herself voluntarily enclosed within the cell to live a life of prayer and contemplation. She was given food through a small hatch and could see the altar through this little window. Christine's story has fascinated visitors for centuries and was the inspiration for a well-known novel.",
                        "The churchyard is well worth exploring. Several inscribed stones date from the 17th century, and the eastern end offers fine views back across the rooftops toward the wooded hills beyond.",
                    ],
                    "image_url": ""
                },
                {
                    "title": "Middle Street",
                    "description": [
                        "Middle Street is the main thoroughfare of Shere and one of the most photographed streets in England. The combination of timber-framed buildings, hanging flower baskets and the gentle sound of the Tillingbourne running alongside makes it particularly picturesque in spring and summer, though it has a quiet charm in every season.",
                        "The street is home to a good selection of independent shops and eating places. The William Bray tea rooms offer excellent homemade cakes and cream teas. The White Horse pub, which dates from the 14th century, is one of the oldest buildings in the village and a perennial favourite with walkers coming in off the hills. There is also a village stores, a pottery, and several small artisan businesses occupying the old farm buildings at the eastern end.",
                        "Look up as you walk — many of the upper storeys and roof lines predate the current shopfronts by several centuries, and the overall streetscape has changed remarkably little since the 18th century. Film crews have used it repeatedly as a stand-in for various periods of English history.",
                    ],
                    "image_url": ""
                },
                {
                    "title": "The Tillingbourne",
                    "description": [
                        "The Tillingbourne is a chalk stream rising on the southern slopes of the North Downs near Albury and flowing westward through the Surrey Hills to join the River Wey at Shalford. Chalk streams are among the rarest and most biodiverse freshwater habitats in the world — only around 200 exist globally, and the vast majority are in southern England.",
                        "The shallow ford in the centre of the village is enormously popular with families, particularly in summer, when children paddle in the clear, cold water and attempt the stepping stones alongside. The stream supports brown trout, water voles, kingfishers and a rich variety of aquatic insects, and the water quality is among the best in the county.",
                        "Follow the stream back toward the car park, passing the old mill building on your left. The mill was in operation from at least the 16th century and was last used commercially in the early 20th century. The millpond behind it is now a tranquil wildlife area and worth a few quiet minutes before returning to the car.",
                    ],
                    "image_url": ""
                },
            ],
        },
        {
            "slug": "william-iv",
            "title": "William IV",
            "distance": "4 km",
            "duration": "1 hr",
            "difficulty": "Moderate",
            "summary": "A lovely walk along the river and through parkland to the quaint and rather upmarket William IV pub.",
            "image_url": "",
            "center": [51.2165, -0.4530],
            "zoom": 14,
            "waypoint_zoom": 16,
            "route": [
                [51.21696,-0.4448],[51.21701,-0.4448],[51.21715,-0.44479],[51.21731,-0.44468],[51.21769,-0.44452],[51.2178,-0.44447],[51.2179,-0.44436],[51.218,-0.4442],[51.21807,-0.44409],[51.2182,-0.44392],[51.2183,-0.44381],[51.21834,-0.44377],[51.21846,-0.44366],[51.21851,-0.4436],[51.21856,-0.44368],[51.2186,-0.44372],[51.21876,-0.4439],[51.21883,-0.44398],[51.21888,-0.44407],[51.21891,-0.44426],[51.21891,-0.4445],[51.21889,-0.44478],[51.21889,-0.44492],[51.2189,-0.44509],[51.21892,-0.44532],[51.21896,-0.44557],[51.21902,-0.44586],[51.21907,-0.44605],[51.21917,-0.44642],[51.21936,-0.44676],[51.21942,-0.44686],[51.2197,-0.44729],[51.21965,-0.44737],[51.2196,-0.44745],[51.21952,-0.44753],[51.21942,-0.44756],[51.21928,-0.44755],[51.21909,-0.44762],[51.21884,-0.4478],[51.21863,-0.44798],[51.21842,-0.44805],[51.21821,-0.44806],[51.21809,-0.4481],[51.21792,-0.44818],[51.21753,-0.44837],[51.21734,-0.4485],[51.21737,-0.44855],[51.21744,-0.44868],[51.21747,-0.44884],[51.21746,-0.44895],[51.21743,-0.44909],[51.21728,-0.44858],[51.21708,-0.44889],[51.21702,-0.44901],[51.21701,-0.44914],[51.21704,-0.44943],[51.21711,-0.44976],[51.21716,-0.44997],[51.21718,-0.45007],[51.2172,-0.45017],[51.21726,-0.45047],[51.21731,-0.45072],[51.21738,-0.45109],[51.21744,-0.4514],[51.21747,-0.45165],[51.21746,-0.4518],[51.21742,-0.45191],[51.21744,-0.45202],[51.21746,-0.45215],[51.21756,-0.45217],[51.21774,-0.45217],[51.21811,-0.45208],[51.2183,-0.452],[51.21839,-0.45194],[51.21873,-0.45173],[51.21894,-0.45155],[51.21918,-0.45136],[51.21937,-0.4512],[51.21952,-0.45107],[51.21982,-0.45095],[51.21997,-0.4509],[51.22011,-0.45077],[51.22048,-0.45046],[51.22081,-0.45024],[51.22098,-0.45011],[51.22104,-0.45018],[51.22116,-0.45076],[51.22123,-0.4513],[51.22124,-0.45163],[51.22123,-0.45194],[51.22122,-0.45237],[51.22123,-0.45275],[51.22122,-0.45305],[51.2212,-0.45348],[51.22117,-0.45393],[51.22113,-0.45442],[51.22108,-0.45497],[51.22101,-0.45552],[51.2209,-0.45633],[51.22085,-0.45697],[51.22084,-0.45725],[51.22085,-0.45783],[51.22077,-0.45814],[51.22064,-0.45822],[51.2206,-0.45835],[51.22055,-0.45869],[51.22049,-0.45932],[51.22031,-0.46065],[51.22024,-0.46117],[51.22022,-0.46141],[51.22022,-0.46171],[51.22025,-0.46193],[51.2203,-0.46231],[51.22041,-0.46305],[51.22048,-0.4635],[51.22048,-0.46362],[51.22049,-0.46388],[51.22048,-0.46436],[51.22038,-0.46447],[51.22019,-0.46449],[51.21994,-0.46458],[51.21975,-0.46469],[51.21956,-0.46479],[51.21935,-0.4648],[51.219,-0.4648],[51.21876,-0.46485],[51.21861,-0.46497],[51.21838,-0.46536],[51.21821,-0.4656],[51.218,-0.46571],[51.21772,-0.46566],[51.21749,-0.46561],[51.21668,-0.46542],[51.21629,-0.46529],[51.21554,-0.46509]
            ],
            "waypoint_coords": [
                [51.2167, -0.4451], [51.2178, -0.4490], [51.2182, -0.4515], [51.2158, -0.4618]
            ],
            "waypoints": [
                {
                    "title": "Shere Village",
                    "description": [
                        "The walk begins at the village car park and heads west along the valley bottom. Cross the ford or stepping stones over the Tillingbourne and follow the signed footpath along the south bank of the stream. The path is well maintained and straightforward to follow, though it can be muddy after wet weather — stout shoes or walking boots are recommended.",
                        "As you leave the village behind, the path passes through a succession of classic Surrey countryside — ancient hedgerows, water meadows grazed by cattle in season, and veteran oak trees that would have been saplings when Elizabeth I was on the throne. The valley narrows gently and the sound of traffic fades within a few minutes of leaving the car park.",
                        "Keep an eye out for the old mill leat running parallel to the stream on your right. This man-made channel dates from at least the 13th century and was used to power a succession of mills along the Tillingbourne, which was once one of the most intensively industrialised river valleys in southern England — producing iron, gunpowder and paper at various points in its history.",
                    ],
                    "image_url": ""
                },
                {
                    "title": "Tillingbourne Valley",
                    "description": [
                        "The path follows the Tillingbourne west through open water meadows with fine views across the valley — the wooded escarpment of the North Downs to the north and the greensand ridge to the south create a gentle bowl of countryside that has remained largely unchanged for centuries. This stretch is particularly good for birds: kingfishers are regularly seen darting low along the stream, grey herons stand motionless in the shallows, and in summer the meadows ring with skylarks.",
                        "The river here is a textbook chalk stream — gin-clear, cold, and fast-flowing over a clean gravel bed. Chalk streams are among the rarest freshwater habitats in the world; only around 200 exist globally, and most are in southern England. This one is in unusually fine condition, largely because the valley has escaped the intensive drainage and fertiliser run-off that has degraded so many comparable rivers. Brown trout are visible most days, rising to take flies on summer evenings.",
                        "About halfway along this section you will pass the remains of an old watermill, its wheel pit and sluice gates still discernible in the undergrowth by the bank. The Tillingbourne drove dozens of mills from the medieval period onward, and the remnants of that industrial past are scattered all along the valley floor for those who look carefully.",
                    ],
                    "image_url": ""
                },
                {
                    "title": "Albury Park",
                    "description": [
                        "The path skirts the edge of Albury Park, a historic private estate at the centre of the valley. The park was laid out in the late 17th century by John Evelyn — diarist, polymath, and one of the founding fellows of the Royal Society — who was a close friend of the then owner. Evelyn's design incorporated a remarkable series of terraced gardens cut into the hillside to the north, some of which survive in altered form and can be glimpsed through the trees.",
                        "The estate passed through several hands before being acquired by Henry Drummond in the early 19th century, who commissioned Augustus Pugin — the architect responsible for the interiors of the Houses of Parliament — to carry out extensive work on the house and estate buildings. Pugin's Catholic chapel, with its elaborate Gothic interior, stands near the estate entrance and is occasionally open to visitors.",
                        "The old parish church of St Peter and St Paul stands within the park boundary and is worth a detour if it is open. It is notable for its Saxon chancel arch, an early Norman apse, and the extraordinary series of painted wooden grave covers in the churchyard. The church is no longer in regular use and is maintained by the Churches Conservation Trust.",
                    ],
                    "image_url": ""
                },
                {
                    "title": "William IV",
                    "description": [
                        "Your destination is the William IV pub, tucked away in the hamlet of Little London near Albury Heath. Despite its somewhat remote location — there are no road signs pointing to it and first-time visitors often overshoot — it has built a serious reputation over the past decade as one of the finest country pubs in Surrey. A booking is strongly recommended for weekend lunches and dinners. The building itself is a classic Surrey cottage, low-ceilinged, beamed and with an open fire that makes it especially welcoming on cold days.",
                        "The menu changes regularly to reflect seasonal and local produce, and the kitchen has close relationships with several nearby farms. The game dishes are outstanding in autumn and winter, and the puddings are the kind that make you glad you walked here rather than drove. The wine list is thoughtfully assembled and the beer selection includes several good ales from Surrey and Sussex breweries.",
                        "To return, retrace your steps east along the Tillingbourne valley — the walk back is, if anything, even better than the outward leg, since the light is different and the views open up from directions you did not see on the way out. Allow around 50 minutes for the return to Shere.",
                    ],
                    "image_url": ""
                },
            ],
        },
    ]
}


# Places to eat — keyed by estate slug
PLACES_TO_EAT = {
    "shere-manor-estate": [
        {
            "slug": "kinghams",
            "name": "Kinghams",
            "type": "restaurant",
            "rating": 4.8,
            "guide_price": "£55",
            "open_today": "12–14, 19–21",
            "distance": "3 min walk",
            "coords": [51.21645, -0.44438],
            "summary": "Widely regarded as the finest restaurant in the Surrey Hills, Kinghams occupies a 17th-century cottage on Gomshall Lane. The cooking is modern British with classical technique — expect beautifully sourced local game, fish from the south coast, and a wine list that has clearly been assembled with care. Booking essential, particularly at weekends.",
            "image_url": "https://picsum.photos/seed/kinghams/600/320?grayscale",
        },
        {
            "slug": "william-iv",
            "name": "The William IV",
            "type": "pub",
            "rating": 4.7,
            "guide_price": "£45",
            "open_today": "12–15, 18–22",
            "distance": "45 min walk",
            "coords": [51.21554, -0.46509],
            "summary": "A destination pub tucked away in the hamlet of Little London near Albury Heath, with a serious reputation for seasonal, locally sourced food. The game dishes in autumn and winter are outstanding, and the low-ceilinged, beamed interior with open fire makes it especially rewarding after a long walk. Book well ahead for weekends.",
            "image_url": "https://picsum.photos/seed/williamiv/600/320?grayscale",
        },
        {
            "slug": "white-horse",
            "name": "The White Horse",
            "type": "pub",
            "rating": 4.5,
            "guide_price": "£35",
            "open_today": "11–23",
            "distance": "2 min walk",
            "coords": [51.21680, -0.44402],
            "summary": "A 14th-century village pub at the heart of Shere, with a sun-trap garden overlooking the Tillingbourne, open fires in winter, and a menu that draws on Surrey producers. One of the oldest buildings in the village and a perennial favourite with walkers coming in off the hills.",
            "image_url": "https://picsum.photos/seed/whitehorse/600/320?grayscale",
        },
        {
            "slug": "hillys",
            "name": "Hillys",
            "type": "café",
            "rating": 4.5,
            "guide_price": "£15",
            "open_today": "8–17",
            "distance": "5 min walk",
            "coords": [51.21600, -0.44550],
            "summary": "A bright, friendly café a short stroll from the village centre, popular for brunch, homemade soups, and excellent flat whites. The outdoor terrace catches the afternoon sun well and is reliably busy on fine weekends. Good options for vegetarians.",
            "image_url": "https://picsum.photos/seed/hillys/600/320?grayscale",
        },
        {
            "slug": "dabbling-duck",
            "name": "The Dabbling Duck",
            "type": "pub",
            "rating": 4.4,
            "guide_price": "£30",
            "open_today": "11–22",
            "distance": "12 min walk",
            "coords": [51.21420, -0.44820],
            "summary": "A relaxed country pub on the southern edge of the village, popular with families and walkers. The garden is large and well kept, the food is straightforward and generously portioned, and the atmosphere is reliably convivial. Good selection of ales from Surrey and Sussex breweries.",
            "image_url": "https://picsum.photos/seed/dabblingduck/600/320?grayscale",
        },
        {
            "slug": "william-bray",
            "name": "William Bray Tea Rooms",
            "type": "café",
            "rating": 4.4,
            "guide_price": "£12",
            "open_today": "9–17",
            "distance": "3 min walk",
            "coords": [51.21650, -0.44470],
            "summary": "A much-loved tearoom on Middle Street, famous for homemade scones, cakes, and proper loose-leaf teas served in a cosy, beamed interior. The cream tea is exactly as it should be. Particularly popular on weekend afternoons — arrive early or expect to queue.",
            "image_url": "https://picsum.photos/seed/williambray/600/320?grayscale",
        },
        {
            "slug": "gomshall-mill",
            "name": "Gomshall Mill",
            "type": "restaurant",
            "rating": 4.2,
            "guide_price": "£30",
            "open_today": "12–21",
            "distance": "20 min walk",
            "coords": [51.21130, -0.42630],
            "summary": "A converted watermill with a riverside terrace, serving a broad, crowd-pleasing menu in a relaxed setting. The outdoor seating beside the millrace is especially good in summer. Well suited to families and larger groups.",
            "image_url": "https://picsum.photos/seed/gomshallmill/600/320?grayscale",
        },
        {
            "slug": "lucky-duck",
            "name": "The Lucky Duck",
            "type": "café",
            "rating": 4.1,
            "guide_price": "£10",
            "open_today": "8–16",
            "distance": "4 min walk",
            "coords": [51.21620, -0.44510],
            "summary": "A laid-back café beside the Tillingbourne stream, popular for brunch and light lunches. Dog-friendly with outdoor seating, and a short menu that changes regularly. Good coffee and a decent selection of sandwiches and wraps.",
            "image_url": "https://picsum.photos/seed/luckyduck/600/320?grayscale",
        },
    ]
}


# Places of interest — keyed by estate slug
PLACES_OF_INTEREST = {
    "shere-manor-estate": [
        {
            "slug": "st-james-church",
            "name": "St James' Church",
            "type": "Church",
            "distance": "2 min walk",
            "coords": [51.21668, -0.44418],
            "summary": "One of the finest Norman churches in Surrey, with origins dating to around 1190. The square flint tower is a local landmark and the interior contains a 13th-century font, remarkable medieval stained glass, and the anchorite's cell of Christine Carpenter — a woman who in 1329 had herself voluntarily enclosed within a small chamber in the north wall to live a life of prayer, able to see the altar only through a tiny window. Her story has fascinated visitors for centuries.",
            "image_url": "https://picsum.photos/seed/stjamesshere/600/320?grayscale",
        },
        {
            "slug": "the-holiday-barn",
            "name": "The Holiday Barn",
            "type": "Film Location",
            "distance": "5 min walk",
            "coords": [51.21580, -0.44560],
            "summary": "The barn now occupied by Steam Dreams was the location used for the interior scenes of the lead character's cottage in the 2006 film The Holiday, starring Cameron Diaz, Kate Winslet, Jude Law and Jack Black. The production team constructed the cottage set within the barn, and much of the film's English scenes were shot in and around Shere village. The exterior of the cottage used in the film can still be identified by locals, and the village remains a popular destination for fans of the film.",
            "image_url": "https://picsum.photos/seed/holidaybarn/600/320?grayscale",
        },
        {
            "slug": "tillingbourne-ford",
            "name": "The Tillingbourne Ford",
            "type": "Natural Feature",
            "distance": "3 min walk",
            "coords": [51.21640, -0.44460],
            "summary": "The shallow ford and stepping stones at the centre of the village are one of Shere's most iconic features and enormously popular with families in summer. The Tillingbourne is a chalk stream — one of only around 200 in the world, almost all of them in southern England — and the water running over the ford is gin-clear and cold year-round. Brown trout are visible on most days, and in fine weather the ford becomes an informal gathering point for the village.",
            "image_url": "https://picsum.photos/seed/tillingbourneford/600/320?grayscale",
        },
        {
            "slug": "shere-museum",
            "name": "Shere Museum",
            "type": "Museum",
            "distance": "4 min walk",
            "coords": [51.21650, -0.44500],
            "summary": "A small but well-curated local museum telling the story of Shere and the surrounding villages from prehistoric times to the present day. Exhibits cover the industrial history of the Tillingbourne valley — which once powered gunpowder mills, iron foundries, and paper works — as well as the agricultural and domestic life of the community. Open on weekend afternoons and most Bank Holidays; admission is free.",
            "image_url": "https://picsum.photos/seed/sheremuseum/600/320?grayscale",
        },
        {
            "slug": "middle-street",
            "name": "Middle Street",
            "type": "Historic Street",
            "distance": "2 min walk",
            "coords": [51.21655, -0.44470],
            "summary": "The main thoroughfare of Shere and one of the most photographed streets in England. The combination of timber-framed buildings — many dating from the 15th and 16th centuries — hanging baskets and the sound of the Tillingbourne running alongside makes it particularly picturesque. The overall streetscape has changed remarkably little since the 18th century and has been used repeatedly by film and television productions as a stand-in for various periods of English history.",
            "image_url": "https://picsum.photos/seed/middlestreetshere/600/320?grayscale",
        },
    ]
}


# Known estate slugs — extend as new estates are onboarded
ESTATES = {
    "shere-manor-estate": {
        "name": "Shere Manor Estate",
        "tagline": "A private estate in the heart of the Surrey Hills.",
        "car_park_slug": "shere-manor",
    },
}


def _get_estate(slug: str):
    return ESTATES.get(slug)


# ── Estate information pages ──────────────────────────────────────────────────

@router.get("/{slug}", response_class=HTMLResponse)
def location_home(request: Request, slug: str):
    estate = _get_estate(slug)
    if not estate:
        return RedirectResponse(url="/", status_code=302)
    return templates.TemplateResponse("location/home.html", {"request": request, "slug": slug, "estate": estate})


@router.get("/{slug}/parking", response_class=HTMLResponse)
def location_parking(request: Request, slug: str):
    estate = _get_estate(slug)
    if not estate:
        return RedirectResponse(url="/", status_code=302)
    return templates.TemplateResponse("location/parking.html", {"request": request, "slug": slug, "estate": estate})


@router.get("/{slug}/walking-routes", response_class=HTMLResponse)
def location_walking(request: Request, slug: str):
    estate = _get_estate(slug)
    if not estate:
        return RedirectResponse(url="/", status_code=302)
    return templates.TemplateResponse("location/walking.html", {"request": request, "slug": slug, "estate": estate})


@router.get("/{slug}/cycle-routes", response_class=HTMLResponse)
def location_cycling(request: Request, slug: str):
    estate = _get_estate(slug)
    if not estate:
        return RedirectResponse(url="/", status_code=302)
    return templates.TemplateResponse("location/cycling.html", {"request": request, "slug": slug, "estate": estate})


@router.get("/{slug}/places-of-interest", response_class=HTMLResponse)
def location_places(request: Request, slug: str):
    estate = _get_estate(slug)
    if not estate:
        return RedirectResponse(url="/", status_code=302)
    return templates.TemplateResponse("location/places.html", {"request": request, "slug": slug, "estate": estate})


@router.get("/{slug}/legacies", response_class=HTMLResponse)
def location_legacies(request: Request, slug: str):
    estate = _get_estate(slug)
    if not estate:
        return RedirectResponse(url="/", status_code=302)
    return templates.TemplateResponse("location/legacies.html", {"request": request, "slug": slug, "estate": estate})


@router.get("/{slug}/benches", response_class=HTMLResponse)
def location_benches(request: Request, slug: str):
    estate = _get_estate(slug)
    if not estate:
        return RedirectResponse(url="/", status_code=302)
    return templates.TemplateResponse("location/benches.html", {"request": request, "slug": slug, "estate": estate})


@router.get("/{slug}/trees", response_class=HTMLResponse)
def location_trees(request: Request, slug: str):
    estate = _get_estate(slug)
    if not estate:
        return RedirectResponse(url="/", status_code=302)
    return templates.TemplateResponse("location/trees.html", {"request": request, "slug": slug, "estate": estate})


@router.get("/{slug}/about", response_class=HTMLResponse)
def location_about(request: Request, slug: str):
    estate = _get_estate(slug)
    if not estate:
        return RedirectResponse(url="/", status_code=302)
    return templates.TemplateResponse("location/about.html", {"request": request, "slug": slug, "estate": estate})


@router.get("/{slug}/contact", response_class=HTMLResponse)
def location_contact(request: Request, slug: str, sent: bool = False):
    estate = _get_estate(slug)
    if not estate:
        return RedirectResponse(url="/", status_code=302)
    return templates.TemplateResponse("location/contact.html", {"request": request, "slug": slug, "estate": estate, "sent": sent})


# ── Visitor / on-site pages ───────────────────────────────────────────────────

@router.get("/{slug}/visitor/welcome", response_class=HTMLResponse)
def visitor_welcome(request: Request, slug: str, db: Session = Depends(get_db)):
    estate = _get_estate(slug)
    if not estate:
        return RedirectResponse(url="/", status_code=302)
    cp_slug = estate["car_park_slug"]
    car_park = db.query(CarPark).filter(CarPark.slug == cp_slug).first()
    brand = {
        "primary": (car_park.brand_primary or "#1e3a1e") if car_park else "#1e3a1e",
        "accent": (car_park.brand_accent or "#B89A5A") if car_park else "#B89A5A",
        "text": (car_park.brand_text or "#ffffff") if car_park else "#ffffff",
    }
    return templates.TemplateResponse("location/visitor/welcome.html", {
        "request": request,
        "slug": slug,
        "estate": estate,
        "estate_name": car_park.owner.name if car_park else estate["name"],
        "car_park_name": car_park.name if car_park else "",
        "logo_url": (getattr(car_park, "logo_url", None) or "") if car_park else "",
        "welcome_text": (getattr(car_park, "welcome_text", None) or "") if car_park else "",
        "car_park_tagline": (car_park.tagline or "") if car_park else estate["tagline"],
        "brand": brand,
    })


@router.get("/{slug}/visitor/parking-select", response_class=HTMLResponse)
def visitor_parking_select(request: Request, slug: str, db: Session = Depends(get_db)):
    estate = _get_estate(slug)
    if not estate:
        return RedirectResponse(url="/", status_code=302)
    cp_slug = estate["car_park_slug"]
    car_park = db.query(CarPark).filter(CarPark.slug == cp_slug).first()
    return templates.TemplateResponse("location/visitor/parking_select.html", {
        "request": request,
        "slug": slug,
        "estate_name": car_park.owner.name if car_park else estate["name"],
        "car_park_name": "Parking Locations",
        "logo_url": (getattr(car_park, "logo_url", None) or "") if car_park else "",
    })


def _parking_response(request, slug, car_park_name_override, db):
    estate = _get_estate(slug)
    if not estate:
        return RedirectResponse(url="/", status_code=302)
    cp_slug = estate["car_park_slug"]
    car_park = db.query(CarPark).filter(CarPark.slug == cp_slug, CarPark.is_active == True).first()
    if not car_park:
        raise HTTPException(status_code=503, detail="Car park not available")
    rule = get_active_rule(db, car_park.id, date.today())
    if not rule:
        raise HTTPException(status_code=503, detail="No pricing available for today")
    options = build_duration_options(rule)
    brand = {
        "primary": car_park.brand_primary or "#1e3a1e",
        "accent": car_park.brand_accent or "#b8963e",
        "text": car_park.brand_text or "#ffffff",
    }
    return templates.TemplateResponse("driver/park.html", {
        "request": request,
        "car_park_name": car_park_name_override,
        "car_park_slug": cp_slug,
        "car_park_tagline": car_park.tagline,
        "estate_name": car_park.owner.name,
        "logo_url": getattr(car_park, "logo_url", None) or "",
        "welcome_text": getattr(car_park, "welcome_text", None) or "",
        "brand": brand,
        "options": options,
        "slug": slug,
        "checkout_url": f"/location/{slug}/visitor/parking-start/checkout",
    })


@router.get("/{slug}/visitor/parking-farm-field-car-park", response_class=HTMLResponse)
def visitor_parking_farm_field(request: Request, slug: str, db: Session = Depends(get_db)):
    return _parking_response(request, slug, "Farm Field Car Park", db)


@router.get("/{slug}/visitor/village-hall-car-park", response_class=HTMLResponse)
def visitor_parking_village_hall(request: Request, slug: str, db: Session = Depends(get_db)):
    estate = _get_estate(slug)
    if not estate:
        return RedirectResponse(url="/", status_code=302)
    cp_slug = estate["car_park_slug"]
    car_park = db.query(CarPark).filter(CarPark.slug == cp_slug).first()
    return templates.TemplateResponse("location/visitor/parking_village_hall.html", {
        "request": request,
        "slug": slug,
        "estate_name": car_park.owner.name if car_park else estate["name"],
        "car_park_name": "Village Hall Car Park",
        "logo_url": (getattr(car_park, "logo_url", None) or "") if car_park else "",
    })


@router.get("/{slug}/visitor/roadside-parking", response_class=HTMLResponse)
def visitor_parking_roadside(request: Request, slug: str, db: Session = Depends(get_db)):
    return _parking_response(request, slug, "Roadside Parking", db)


@router.get("/{slug}/visitor/parking-start", response_class=HTMLResponse)
def visitor_parking_start(request: Request, slug: str, db: Session = Depends(get_db)):
    return _parking_response(request, slug, "Farm Field Car Park", db)


@router.post("/{slug}/visitor/parking-start/checkout")
async def visitor_checkout(
    slug: str,
    request: Request,
    number_plate: str = Form(...),
    duration: str = Form(...),
    db: Session = Depends(get_db),
):
    estate = _get_estate(slug)
    if not estate:
        raise HTTPException(status_code=404)
    cp_slug = estate["car_park_slug"]
    car_park = db.query(CarPark).filter(CarPark.slug == cp_slug, CarPark.is_active == True).first()
    if not car_park:
        raise HTTPException(status_code=404)
    rule = get_active_rule(db, car_park.id, date.today())
    if not rule:
        raise HTTPException(status_code=503)

    is_all_day = duration == "all_day"
    duration_hours = None if is_all_day else int(duration)
    amount_pence = calculate_price(rule, duration_hours, is_all_day)
    duration_label = "All day" if is_all_day else f"{duration_hours} hour{'s' if duration_hours > 1 else ''}"

    brand = {
        "primary": car_park.brand_primary or "#1e3a1e",
        "accent": car_park.brand_accent or "#8B3A2A",
        "text": car_park.brand_text or "#ffffff",
    }
    context = {
        "request": request,
        "estate_name": car_park.owner.name,
        "car_park_name": car_park.name,
        "car_park_slug": cp_slug,
        "number_plate": number_plate.upper().replace(" ", ""),
        "duration_label": duration_label,
        "amount": f"£{amount_pence / 100:.2f}",
        "logo_url": getattr(car_park, "logo_url", None) or "",
        "welcome_text": getattr(car_park, "welcome_text", None) or "",
        "brand": brand,
    }
    return templates.TemplateResponse("driver/payment_mockup.html", context)

    # -- Stripe (live -- replace mockup block above when keys are ready) --
    commission_pence = int(amount_pence * car_park.owner.commission_pct / 100)
    owner_amount_pence = amount_pence - commission_pence

    txn = Transaction(
        car_park_id=car_park.id,
        number_plate=number_plate.upper().replace(" ", ""),
        duration_hours=duration_hours,
        is_all_day=is_all_day,
        amount_pence=amount_pence,
        commission_pence=commission_pence,
        owner_amount_pence=owner_amount_pence,
        status=TransactionStatus.pending,
    )
    db.add(txn)
    db.commit()
    db.refresh(txn)

    base_url = os.getenv("BASE_URL", "http://localhost:8000")
    stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

    session = stripe.checkout.Session.create(
        payment_method_types=["card"],
        line_items=[{
            "price_data": {
                "currency": "gbp",
                "product_data": {
                    "name": f"Parking — {car_park.name}",
                    "description": f"{duration_label} | {number_plate.upper()}",
                },
                "unit_amount": amount_pence,
            },
            "quantity": 1,
        }],
        mode="payment",
        success_url=f"{base_url}/location/{slug}/visitor/parking-receipt?txn={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{base_url}/location/{slug}/visitor/parking-start",
        metadata={"txn_id": str(txn.id)},
    )

    txn.stripe_payment_intent_id = session.payment_intent
    db.commit()

    return RedirectResponse(session.url, status_code=303)


@router.get("/{slug}/visitor/parking-payment", response_class=HTMLResponse)
def visitor_parking_payment(request: Request, slug: str, db: Session = Depends(get_db)):
    estate = _get_estate(slug)
    if not estate:
        return RedirectResponse(url="/", status_code=302)
    cp_slug = estate["car_park_slug"]
    car_park = db.query(CarPark).filter(CarPark.slug == cp_slug).first()
    accent = (car_park.brand_accent or "#8B3A2A") if car_park else "#8B3A2A"
    return templates.TemplateResponse("driver/payment_mockup.html", {
        "request": request,
        "slug": cp_slug,
        "estate_name": car_park.owner.name if car_park else "",
        "car_park_name": car_park.name if car_park else "",
        "logo_url": (getattr(car_park, "logo_url", None) or "") if car_park else "",
        "brand": {"accent": accent},
    })


@router.get("/{slug}/visitor/walking", response_class=HTMLResponse)
def visitor_walking_list(request: Request, slug: str, db: Session = Depends(get_db)):
    estate = _get_estate(slug)
    if not estate:
        return RedirectResponse(url="/", status_code=302)
    cp_slug = estate["car_park_slug"]
    car_park = db.query(CarPark).filter(CarPark.slug == cp_slug).first()
    walks = WALKS.get(slug, [])
    return templates.TemplateResponse("location/visitor/walking_list.html", {
        "request": request,
        "slug": slug,
        "estate_name": car_park.owner.name if car_park else estate["name"],
        "car_park_name": car_park.name if car_park else "",
        "logo_url": (getattr(car_park, "logo_url", None) or "") if car_park else "",
        "walks": walks,
    })


@router.get("/{slug}/visitor/walking/{walk_slug}", response_class=HTMLResponse)
def visitor_walking_detail(request: Request, slug: str, walk_slug: str, db: Session = Depends(get_db)):
    estate = _get_estate(slug)
    if not estate:
        return RedirectResponse(url="/", status_code=302)
    cp_slug = estate["car_park_slug"]
    car_park = db.query(CarPark).filter(CarPark.slug == cp_slug).first()
    walks = WALKS.get(slug, [])
    walk = next((w for w in walks if w["slug"] == walk_slug), None)
    if not walk:
        raise HTTPException(status_code=404)
    return templates.TemplateResponse("location/visitor/walking_detail.html", {
        "request": request,
        "slug": slug,
        "estate_name": car_park.owner.name if car_park else estate["name"],
        "car_park_name": car_park.name if car_park else "",
        "logo_url": (getattr(car_park, "logo_url", None) or "") if car_park else "",
        "walk": walk,
    })


@router.get("/{slug}/visitor/history", response_class=HTMLResponse)
def visitor_history(request: Request, slug: str, db: Session = Depends(get_db)):
    estate = _get_estate(slug)
    if not estate:
        return RedirectResponse(url="/", status_code=302)
    cp_slug = estate["car_park_slug"]
    car_park = db.query(CarPark).filter(CarPark.slug == cp_slug).first()
    return templates.TemplateResponse("location/visitor/history.html", {
        "request": request,
        "slug": slug,
        "estate_name": car_park.owner.name if car_park else estate["name"],
        "car_park_name": "Our History",
        "logo_url": (getattr(car_park, "logo_url", None) or "") if car_park else "",
    })


@router.get("/{slug}/visitor/places-of-interest", response_class=HTMLResponse)
def visitor_places_of_interest(request: Request, slug: str, db: Session = Depends(get_db)):
    estate = _get_estate(slug)
    if not estate:
        return RedirectResponse(url="/", status_code=302)
    cp_slug = estate["car_park_slug"]
    car_park = db.query(CarPark).filter(CarPark.slug == cp_slug).first()
    places = PLACES_OF_INTEREST.get(slug, [])
    return templates.TemplateResponse("location/visitor/places_of_interest.html", {
        "request": request,
        "slug": slug,
        "estate_name": car_park.owner.name if car_park else estate["name"],
        "car_park_name": "Places of Interest",
        "logo_url": (getattr(car_park, "logo_url", None) or "") if car_park else "",
        "places": places,
    })


@router.get("/{slug}/visitor/places-to-eat", response_class=HTMLResponse)
def visitor_places_to_eat(request: Request, slug: str, db: Session = Depends(get_db)):
    estate = _get_estate(slug)
    if not estate:
        return RedirectResponse(url="/", status_code=302)
    cp_slug = estate["car_park_slug"]
    car_park = db.query(CarPark).filter(CarPark.slug == cp_slug).first()
    places = PLACES_TO_EAT.get(slug, [])
    return templates.TemplateResponse("location/visitor/places_to_eat.html", {
        "request": request,
        "slug": slug,
        "estate_name": car_park.owner.name if car_park else estate["name"],
        "car_park_name": "Places to Eat",
        "logo_url": (getattr(car_park, "logo_url", None) or "") if car_park else "",
        "places": places,
    })


@router.get("/{slug}/visitor/parking-receipt", response_class=HTMLResponse)
def visitor_parking_receipt(request: Request, slug: str, db: Session = Depends(get_db)):
    estate = _get_estate(slug)
    if not estate:
        return RedirectResponse(url="/", status_code=302)
    cp_slug = estate["car_park_slug"]
    car_park = db.query(CarPark).filter(CarPark.slug == cp_slug).first()
    accent = (car_park.brand_accent or "#8B3A2A") if car_park else "#8B3A2A"
    return templates.TemplateResponse("driver/receipt_placeholder.html", {
        "request": request,
        "slug": cp_slug,
        "estate_name": car_park.owner.name if car_park else "",
        "car_park_name": car_park.name if car_park else "",
        "logo_url": (getattr(car_park, "logo_url", None) or "") if car_park else "",
        "brand": {"accent": accent},
    })
