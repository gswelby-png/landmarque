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
            "image_url": "/static/images/village-ford.jpg",
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
            "image_url": "https://s0.geograph.org.uk/photos/08/65/086595_f5aab469.jpg",
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
            "image_url": "https://assets.simpleviewinc.com/simpleview/image/upload/c_fill,f_jpg,h_563,q_65,w_1920/v1/clients/surrey/Kinghams_Shere_copyright_GBC_Image_captured_by_Chris_Lacey_December_24_e4c4238c-9c4d-4472-bad4-b1d790121b63.jpg",
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
            "image_url": "https://londontheinside.com/wp-content/uploads/2025/04/william-iv-1200x675.jpg",
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
            "image_url": "/static/images/white-horse.jpg",
        },
        {
            "slug": "hillys",
            "name": "Hilly's Tea Shop",
            "type": "café",
            "rating": 4.6,
            "guide_price": "£15",
            "open_today": "9–17",
            "distance": "2 min walk",
            "coords": [51.21655, -0.44492],
            "summary": "A much-loved independent teashop on The Square, serving freshly baked scones all day, homemade cakes, sandwiches, sausage rolls and light lunches. Pre-bookable afternoon tea at £40 per person. By evening it transforms into the Shere Kocktail Bar — craft cocktails, small plates and a speakeasy atmosphere.",
            "image_url": "/static/images/hillys.jpg",
        },
        {
            "slug": "dabbling-duck",
            "name": "The Dabbling Duck",
            "type": "café",
            "rating": 4.3,
            "guide_price": "£18",
            "open_today": "9–16",
            "distance": "3 min walk",
            "coords": [51.21640, -0.44460],
            "summary": "A petite café and restaurant beside the Tillingbourne stream, well placed for watching the river and the ducks go by. Relaxed and informal, serving brunch, light lunches and homemade cakes in a charming setting. Popular with families and visitors exploring the village.",
            "image_url": "/static/images/dabbling-duck.jpg",
        },
        {
            "slug": "william-bray",
            "name": "The William Bray",
            "type": "pub",
            "rating": 4.6,
            "guide_price": "£40",
            "open_today": "12–23",
            "distance": "3 min walk",
            "coords": [51.21650, -0.44470],
            "summary": "A smart, high-end pub and restaurant in an elegant Georgian building in the heart of the village. The William Bray has built a strong reputation for well-executed seasonal cooking, a thoughtful wine list, and a refined but unstuffy atmosphere. The terrace is one of the nicest spots to eat outdoors in the Surrey Hills.",
            "image_url": "/static/images/william-bray.jpg",
        },
        {
            "slug": "gomshall-mill",
            "name": "The Gomshall Mill",
            "type": "pub",
            "rating": 4.2,
            "guide_price": "£30",
            "open_today": "12–22",
            "distance": "20 min walk",
            "coords": [51.21130, -0.42630],
            "summary": "A character-filled pub and dining venue in a converted watermill on the A25 in Gomshall, with a river terrace and mill-race views. Serves a broad, hearty menu in a relaxed setting — well suited to families and larger groups. The outdoor riverside seating is especially good in summer.",
            "image_url": "https://gomshallmill.co.uk/wp-content/uploads/2023/01/Mill-View-1.jpg",
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
            "image_url": "/static/images/church.jpg",
        },
        {
            "slug": "the-holiday-film",
            "name": "The Holiday Film Location",
            "type": "Film Location",
            "distance": "2 min walk",
            "coords": [51.21640, -0.44490],
            "summary": "Shere village was the principal English location for the 2006 romantic comedy The Holiday, starring Cameron Diaz, Kate Winslet, Jude Law and Jack Black. The production built a purpose-designed cottage set in the village, and many scenes were filmed on and around Middle Street. The village is instantly recognisable to fans of the film, and it remains one of the most popular reasons people visit Shere for the first time.",
            "image_url": "",
        },
        {
            "slug": "shere-village-hall",
            "name": "Shere Village Hall",
            "type": "Community",
            "distance": "4 min walk",
            "coords": [51.21580, -0.44480],
            "summary": "The village hall is the beating heart of community life in Shere, hosting everything from farmers' markets and craft fairs to theatrical productions and fitness classes. Built in the 1930s, the building retains much of its original character. The programme of events is posted on the noticeboard outside — if there is something on during your visit, it is usually well worth attending.",
            "image_url": "",
        },
        {
            "slug": "tillingbourne-ford",
            "name": "The Tillingbourne Ford",
            "type": "Natural Feature",
            "distance": "3 min walk",
            "coords": [51.21640, -0.44460],
            "summary": "The shallow ford and stepping stones at the centre of the village are one of Shere's most iconic features and enormously popular with families in summer. The Tillingbourne is a chalk stream — one of only around 200 in the world, almost all of them in southern England — and the water running over the ford is gin-clear and cold year-round. Brown trout are visible on most days, and in fine weather the ford becomes an informal gathering point for the village.",
            "image_url": "/static/images/village-ford.jpg",
        },
        {
            "slug": "shere-museum",
            "name": "Shere Museum",
            "type": "Museum",
            "distance": "4 min walk",
            "coords": [51.21650, -0.44500],
            "summary": "A small but well-curated local museum telling the story of Shere and the surrounding villages from prehistoric times to the present day. Exhibits cover the industrial history of the Tillingbourne valley — which once powered gunpowder mills, iron foundries, and paper works — as well as the agricultural and domestic life of the community. Open on weekend afternoons and most Bank Holidays; admission is free.",
            "image_url": "https://s0.geograph.org.uk/photos/53/52/535233_3166a1a7.jpg",
        },
        {
            "slug": "middle-street",
            "name": "Middle Street",
            "type": "Historic Street",
            "distance": "2 min walk",
            "coords": [51.21655, -0.44470],
            "summary": "The main thoroughfare of Shere and one of the most photographed streets in England. The combination of timber-framed buildings — many dating from the 15th and 16th centuries — hanging baskets and the sound of the Tillingbourne running alongside makes it particularly picturesque. The overall streetscape has changed remarkably little since the 18th century and has been used repeatedly by film and television productions as a stand-in for various periods of English history.",
            "image_url": "/static/images/middle-street.jpg",
        },
    ]
}


# Fun for kids — keyed by estate slug
FUN_FOR_KIDS = {
    "shere-manor-estate": [
        {
            "slug": "shere-delights",
            "name": "Shere Delights Ice Cream",
            "type": "Food & Drink",
            "distance": "2 min walk",
            "coords": [51.21655, -0.44470],
            "summary": "Widely regarded as the best ice cream in Surrey, Shere Delights serves up extraordinary homemade flavours in the heart of the village. Expect proper thick scoops in classic flavours alongside rotating specials — salted caramel, honeycomb, and seasonal fruit options. On a warm day the queue stretches down the street, but it moves quickly and it is always worth the wait.",
            "image_url": "/static/images/shere-delights.jpg",
        },
        {
            "slug": "feed-the-ducks",
            "name": "Feed the Ducks",
            "type": "Wildlife",
            "distance": "2 min walk",
            "coords": [51.21640, -0.44460],
            "summary": "The ducks on the Tillingbourne at the High Street bridge are a Shere institution and completely unafraid of people. Children can feed them from the bridge or from the bank alongside. Bread is not recommended — the village store sells proper duck food. Keep an eye out for moorhens nesting in the reeds, and if you are lucky you may spot a grey heron standing very still further downstream.",
            "image_url": "https://s0.geograph.org.uk/photos/08/65/086595_f5aab469.jpg",
        },
        {
            "slug": "river-paddling",
            "name": "River Paddling & Crayfish",
            "type": "Outdoor Activity",
            "distance": "5 min walk",
            "coords": [51.21620, -0.44380],
            "summary": "The park between the churchyard and the lido is the best spot in the village for paddling in the Tillingbourne. The water is crystal clear, cold and shallow — perfect for children to wade and explore. If you have a small hand net and patience, you stand a good chance of catching American signal crayfish under the stones. They are an invasive species, so there is no limit and no licence required. Just put them back when you are done.",
            "image_url": "/static/images/village-ford.jpg",
        },
        {
            "slug": "stepping-stones",
            "name": "The Stepping Stones",
            "type": "Outdoor Activity",
            "distance": "3 min walk",
            "coords": [51.21640, -0.44460],
            "summary": "The stepping stones across the Tillingbourne ford are one of the most fun features of the village for younger children. The ford is shallow and the stones are broad and stable, though they can be slippery — wellies or water shoes recommended. On busy summer weekends a small informal queue forms, and there is a good-natured atmosphere as families help each other across. The water is gin-clear and you can often spot brown trout hovering in the current.",
            "image_url": "https://s0.geograph.org.uk/geophotos/03/28/63/3286364_eda822d0.jpg",
        },
        {
            "slug": "shere-lido",
            "name": "Shere Lido",
            "type": "Swimming",
            "distance": "8 min walk",
            "coords": [51.21580, -0.44200],
            "summary": "Shere Lido is a beautiful private open-air pool set in a woodland clearing — one of the last surviving rural lidos in Surrey. Unfortunately the lido is not accessible to day visitors; it is available exclusively to members and residents of the estate. If you are staying locally it is worth enquiring about guest access. For visitors, the river paddling in the park nearby is a lovely alternative on a warm day.",
            "image_url": "https://www.bathsandwashhouses.co.uk/wp-content/uploads/2020/05/Shere-Swimming-Pool-Twitter-21-May-2020-1024x618.jpg",
        },
        {
            "slug": "village-cricket",
            "name": "Shere Cricket Ground",
            "type": "Sport",
            "distance": "10 min walk",
            "coords": [51.21500, -0.44300],
            "summary": "On summer Saturdays and Sundays, Shere Cricket Club plays on one of the most scenic grounds in the county. The pavilion is open to spectators and there is usually a tea tent. Watching village cricket on a sunny afternoon — with the church tower visible above the treeline and the sound of leather on willow — is one of those quintessentially English experiences that is hard to beat. Check the club noticeboard at the ground for the fixture list.",
            "image_url": "",
        },
        {
            "slug": "shere-museum",
            "name": "Shere Museum",
            "type": "Museum",
            "distance": "4 min walk",
            "coords": [51.21650, -0.44500],
            "summary": "A small, free museum telling the story of Shere from prehistoric times to the present. Children enjoy the exhibits on the old water mills that once lined the Tillingbourne, the Roman road that ran through the valley, and the various film productions that have used the village as a location. Open on weekend afternoons and most Bank Holidays. Admission is free.",
            "image_url": "/static/images/middle-street.jpg",
        },
    ]
}


# Merch products — keyed by estate slug
MERCH_PRODUCTS = {
    "shere-manor-estate": [
        {
            "name": "Shere Village Cap",
            "category": "Clothing",
            "price": "£22",
            "description": "Dark green six-panel cap with embroidered Shere Manor Estate crest on the front. Spellout text around the rear strap. Adjustable. One size fits most.",
            "mockup_type": "cap",
        },
        {
            "name": "Shere Village T-Shirt",
            "category": "Clothing",
            "price": "£28",
            "description": "100% organic cotton tee in off-white with the Shere Manor Estate crest and spellout printed on the chest. Available in S, M, L, XL.",
            "mockup_type": "tshirt",
        },
        {
            "name": "Shere Tea Towel",
            "category": "Home",
            "price": "£12",
            "description": "Pure linen tea towel with dark green border stripes and the Shere Manor Estate logo in the corner. A timeless souvenir of the village.",
            "mockup_type": "teatowel",
        },
        {
            "name": "Shere Village Mug",
            "category": "Home",
            "price": "£14",
            "description": "Bone china mug in white with the full Shere Manor Estate logo in green on the face. Dishwasher safe. Made in Staffordshire.",
            "mockup_type": "mug",
        },
        {
            "name": "Tanhurst Estate Rosé 2023",
            "category": "Local Produce",
            "price": "£18",
            "description": "An elegant English rosé from Tanhurst Estate, just two miles from Shere in the Surrey Hills. Pale salmon in colour with notes of strawberry, white peach and a crisp mineral finish. Single bottle, 75cl.",
            "image_url": "https://tanhurstestate.co.uk/wp-content/uploads/2025/03/6-bottles-Rosiers-Rose.jpg",
        },
        {
            "name": "Silent Pool Gin",
            "category": "Local Produce",
            "price": "£38",
            "description": "The celebrated Surrey Hills gin, distilled at Silent Pool just outside Albury — a short walk from Shere. Floral and complex, with 24 botanicals including local elderflower and honey. 70cl, 43% ABV.",
            "image_url": "https://silentpooldistillers.com/cdn/shop/files/1x1_Packshot_white.jpg?crop=center&height=500&v=1743162805&width=500",
        },
    ]
}


# Shopping — keyed by estate slug
SHOPPING = {
    "shere-manor-estate": [
        {
            "slug": "welcome-shere",
            "name": "Welcome Shere",
            "type": "Convenience Store",
            "distance": "1 min walk",
            "coords": [51.21660, -0.44440],
            "hours": "Mon–Sat 7–18, Sun 8–13",
            "website": "",
            "description": "The village's everyday essentials — a well-stocked convenience store and post office right in the heart of Shere. Stocks a wide range of groceries, fresh bread, local produce, newspapers, snacks and drinks. The noticeboard inside is the best way to find out what is happening in the village.",
            "image_url": "",
        },
        {
            "slug": "shere-pottage",
            "name": "Shere Pottage",
            "type": "Garden & Home Wares",
            "distance": "3 min walk",
            "coords": [51.21648, -0.44470],
            "hours": "Daily 10:30–17:30",
            "website": "https://sherepottage.co.uk",
            "description": "A thoughtfully curated independent shop at The Forge on Middle Street, selling garden and homewares, sustainable cleaning products, and ethically sourced gifts. Everything is chosen with care — natural ingredients, minimal packaging, and a genuine commitment to responsible sourcing. A lovely place to browse and find something a little different.",
            "image_url": "/static/images/shere-pottage.jpg",
        },
        {
            "slug": "split-figs",
            "name": "Split Figs",
            "type": "Interiors & Lifestyle",
            "distance": "2 min walk",
            "coords": [51.21655, -0.44490],
            "hours": "",
            "website": "https://splitfigs.com",
            "description": "An eclectic and beautifully styled interiors boutique on The Square, stocking vintage furniture, timeless homewares, and unique accessories curated from local artists and makers. The range covers everything from mirrors and lighting to cashmere, candles and decorative art — and the stock is constantly refreshed. Split Figs also runs creative workshops and events throughout the year.",
            "image_url": "",
        },
        {
            "slug": "shere-antiques",
            "name": "Shere Antiques Centre",
            "type": "Antiques",
            "distance": "3 min walk",
            "coords": [51.21648, -0.44480],
            "hours": "Mon–Sat 10–17, Sun 11–17",
            "website": "",
            "description": "A long-established antiques centre on Middle Street with multiple dealers under one roof. Sells small furniture, decorative arts, silverware, ceramics, jewellery, and collectibles spanning several centuries. The kind of place where patience is rewarded — something different turns up every visit.",
            "image_url": "",
        },
        {
            "slug": "lavender-goose",
            "name": "Lavender Goose",
            "type": "Lifestyle Store & Café",
            "distance": "5 min drive · Gomshall",
            "coords": [51.2110, -0.4390],
            "hours": "",
            "website": "http://www.lavendergoose.co.uk",
            "description": "Set in the handsome former Black Horse pub in Gomshall — just minutes from Shere — Lavender Goose is one of the area's best lifestyle stores. Stocks jewellery, handbags, scarves, cashmere, candles, mirrors, throws, lighting and decorative accessories from around the world. There is also a café serving breakfast sandwiches, cakes and coffee. Highly recommended if you have a spare half-hour.",
            "image_url": "",
        },
        {
            "slug": "shere-museum-shop",
            "name": "Shere Museum",
            "type": "Museum & Gift Shop",
            "distance": "2 min walk",
            "coords": [51.21640, -0.44460],
            "hours": "",
            "website": "https://www.sheremuseum.co.uk",
            "description": "Shere's small but absorbing local museum on Gomshall Lane tells the story of the village from its earliest history to the present day. The gift shop sells books, prints, and locally produced items, with all proceeds going directly back to the museum. Well worth a visit — and completely free to enter.",
            "image_url": "",
        },
    ]
}

# Local produce available to buy in the area — shown on the combined shopping page
LOCAL_PRODUCE = {
    "shere-manor-estate": [
        {
            "name": "Silent Pool Gin",
            "producer": "Silent Pool Distillers · Albury (10 min drive)",
            "price": "from £38",
            "description": "Handcrafted at Silent Pool just outside Albury, this celebrated Surrey Hills gin is made with 24 botanicals including local elderflower and honey. Floral, complex and distinctly of this landscape. Buy direct from the distillery shop — tastings and tours also available. 70cl, 43% ABV.",
            "image_url": "https://silentpooldistillers.com/cdn/shop/files/1x1_Packshot_white.jpg?crop=center&height=500&v=1743162805&width=500",
            "buy_url": "https://silentpooldistillers.com",
        },
        {
            "name": "Tanhurst Estate Rosé",
            "producer": "Tanhurst Estate Vineyard · Leith Hill (15 min drive)",
            "price": "from £18",
            "description": "An elegant English rosé from Tanhurst Estate on the lower slopes of Leith Hill, part of the Vineyards of the Surrey Hills wine route. Made from Chardonnay, Pinot Meunier, and Pinot Noir Précoce — pale salmon in colour with notes of strawberry and white peach. Visit the vineyard café at weekends. 75cl.",
            "image_url": "https://tanhurstestate.co.uk/wp-content/uploads/2025/03/6-bottles-Rosiers-Rose.jpg",
            "buy_url": "https://tanhurstestate.co.uk",
        },
    ]
}

# Bench types available for new bench orders
BENCH_TYPES = [
    {
        "slug": "natural-oak",
        "name": "Natural Oak",
        "description": "A classic FSC-certified oak bench in a natural finish, constructed using traditional mortice and tenon joinery. Will weather to a silver-grey over time and last for decades with minimal maintenance.",
        "image_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/8/8b/Bench_in_a_garden.jpg/640px-Bench_in_a_garden.jpg",
    },
    {
        "slug": "painted-hardwood",
        "name": "Painted Hardwood",
        "description": "Solid iroko hardwood bench finished in your choice of estate green, charcoal, or white. Robust and low-maintenance, well suited to exposed locations.",
        "image_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/8/8b/Bench_in_a_garden.jpg/640px-Bench_in_a_garden.jpg",
    },
    {
        "slug": "edwardian-cast-iron",
        "name": "Edwardian Cast Iron & Hardwood",
        "description": "A heritage-style bench with ornate cast iron ends and slatted hardwood seating, based on classic late Victorian and Edwardian public park designs. Elegant and distinctive — a real feature in any location.",
        "image_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/c/c5/Cast_iron_bench%2C_Victoria_Embankment.jpg/640px-Cast_iron_bench%2C_Victoria_Embankment.jpg",
    },
    {
        "slug": "memorial-stone",
        "name": "Memorial Stone Seat",
        "description": "A hand-cut local sandstone bench, unique to the estate. Heavy, permanent, and utterly in keeping with the Surrey Hills landscape. Each one is individually finished and takes approximately twelve weeks to complete.",
        "image_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/8/8b/Bench_in_a_garden.jpg/640px-Bench_in_a_garden.jpg",
    },
]

# Bench locations — existing benches to sponsor + sites for new ones
BENCH_LOCATIONS = {
    "shere-manor-estate": [
        {
            "slug": "tillingbourne-bank",
            "name": "Tillingbourne Bank",
            "status": "new",
            "description": "A south-facing position on the bank of the Tillingbourne, looking across the water meadows. Afternoon sun, sheltered by an ancient oak. One of the finest spots on the estate.",
            "image_url": "https://s0.geograph.org.uk/geophotos/03/18/72/3187296_9fd9fce6.jpg",
        },
        {
            "slug": "church-gate",
            "name": "St James' Church Gate",
            "status": "sponsor",
            "description": "A weathered oak bench set into the flint wall beside the churchyard gate. Well-used by walkers and visitors to the church. The existing dedication plaque has expired and the bench is available for re-dedication.",
            "image_url": "/static/images/church.jpg",
        },
        {
            "slug": "orchard-corner",
            "name": "The Orchard Corner",
            "status": "new",
            "description": "A peaceful spot at the eastern end of the estate orchard, where the footpath curves through old apple and pear trees. Beautiful in blossom season and tranquil year-round.",
            "image_url": "https://s0.geograph.org.uk/geophotos/08/23/42/8234276_17cf7dcb.jpg",
        },
        {
            "slug": "north-downs-view",
            "name": "North Downs Viewpoint",
            "status": "new",
            "description": "The highest bench position on the estate, on the ridge path with a clear view south across the Tillingbourne valley to the wooded hills beyond. Exposed but spectacular, especially at dawn and dusk.",
            "image_url": "https://s0.geograph.org.uk/geophotos/08/23/41/8234185_8802425b.jpg",
        },
        {
            "slug": "cricket-boundary",
            "name": "Cricket Ground Boundary",
            "status": "sponsor",
            "description": "A painted hardwood bench on the boundary of the cricket ground. Currently in need of restoration. The sponsorship includes full refurbishment, new slats, and a fresh plaque.",
            "image_url": "https://s0.geograph.org.uk/geophotos/08/23/42/8234276_17cf7dcb.jpg",
        },
    ]
}

# Bench sponsorship tiers
BENCH_TIERS = [
    {
        "name": "New Bench",
        "price": "£1,200",
        "description": "Commission a brand new hardwood bench installed at a location of your choosing on the estate. Includes a brass commemorative plaque engraved with your chosen inscription (up to 40 characters). Benches are built to last a lifetime and maintained by the estate.",
        "includes": ["Hardwood bench (FSC certified oak)", "Brass engraved plaque", "Choice of location", "Estate maintenance in perpetuity", "Personalised certificate of dedication"],
    },
    {
        "name": "Sponsor an Existing Bench",
        "price": "£450",
        "description": "Dedicate one of the estate's existing benches to a loved one, a special occasion, or a cherished memory. A new brass plaque is fitted with your chosen inscription. The bench is cleaned and restored as part of the sponsorship.",
        "includes": ["Brass engraved plaque (up to 40 characters)", "Bench restoration", "5-year sponsorship term", "Personalised certificate of dedication"],
    },
    {
        "name": "Gift a Bench Experience",
        "price": "£85",
        "description": "Give someone special a framed print of a named bench on the estate, along with a handwritten dedication card and a year's access pass to the estate grounds. A thoughtful and lasting gift for a birthday, anniversary, or in memory of someone.",
        "includes": ["Framed bench photograph (A4)", "Handwritten dedication card", "One year estate access pass", "Gift box presentation"],
    },
]

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

@router.get("/{slug}/visitor/welcome-test", response_class=HTMLResponse)
def visitor_welcome_test(request: Request, slug: str, db: Session = Depends(get_db)):
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
    return templates.TemplateResponse("location/visitor/welcome_test.html", {
        "request": request,
        "slug": slug,
        "estate": estate,
        "estate_name": car_park.owner.name if car_park else estate["name"],
        "car_park_name": "Welcome",
        "logo_url": (getattr(car_park, "logo_url", None) or "") if car_park else "",
        "welcome_text": (getattr(car_park, "welcome_text", None) or "") if car_park else "",
        "car_park_tagline": (car_park.tagline or "") if car_park else estate["tagline"],
        "brand": brand,
    })


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
        "car_park_name": "Welcome",
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
    estate = _get_estate(slug)
    if not estate:
        return RedirectResponse(url="/", status_code=302)
    cp_slug = estate["car_park_slug"]
    car_park = db.query(CarPark).filter(CarPark.slug == cp_slug).first()
    return templates.TemplateResponse("location/visitor/parking_roadside.html", {
        "request": request,
        "slug": slug,
        "estate_name": car_park.owner.name if car_park else estate["name"],
        "car_park_name": "Roadside Parking",
        "logo_url": (getattr(car_park, "logo_url", None) or "") if car_park else "",
    })


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
        "slug": slug,
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
        "car_park_name": "Walking Routes",
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


@router.get("/{slug}/visitor/movies", response_class=HTMLResponse)
def visitor_movies(request: Request, slug: str, db: Session = Depends(get_db)):
    estate = _get_estate(slug)
    if not estate:
        return RedirectResponse(url="/", status_code=302)
    cp_slug = estate["car_park_slug"]
    car_park = db.query(CarPark).filter(CarPark.slug == cp_slug).first()
    return templates.TemplateResponse("location/visitor/movies.html", {
        "request": request,
        "slug": slug,
        "estate_name": car_park.owner.name if car_park else estate["name"],
        "car_park_name": "Movie Connections",
        "logo_url": (getattr(car_park, "logo_url", None) or "") if car_park else "",
    })


@router.get("/{slug}/visitor/history-test", response_class=HTMLResponse)
def visitor_history_test(request: Request, slug: str, db: Session = Depends(get_db)):
    estate = _get_estate(slug)
    if not estate:
        return RedirectResponse(url="/", status_code=302)
    cp_slug = estate["car_park_slug"]
    car_park = db.query(CarPark).filter(CarPark.slug == cp_slug).first()
    return templates.TemplateResponse("location/visitor/history_test.html", {
        "request": request,
        "slug": slug,
        "estate_name": car_park.owner.name if car_park else estate["name"],
        "car_park_name": "Our History",
        "logo_url": (getattr(car_park, "logo_url", None) or "") if car_park else "",
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


@router.get("/{slug}/visitor/fun-for-kids", response_class=HTMLResponse)
def visitor_fun_for_kids(request: Request, slug: str, db: Session = Depends(get_db)):
    estate = _get_estate(slug)
    if not estate:
        return RedirectResponse(url="/", status_code=302)
    cp_slug = estate["car_park_slug"]
    car_park = db.query(CarPark).filter(CarPark.slug == cp_slug).first()
    places = FUN_FOR_KIDS.get(slug, [])
    return templates.TemplateResponse("location/visitor/fun_for_kids.html", {
        "request": request,
        "slug": slug,
        "estate_name": car_park.owner.name if car_park else estate["name"],
        "car_park_name": "Fun for Kids",
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


@router.get("/{slug}/visitor/merch", response_class=HTMLResponse)
def visitor_merch(request: Request, slug: str):
    return RedirectResponse(url=f"/location/{slug}/visitor/shopping", status_code=301)


@router.get("/{slug}/visitor/shopping", response_class=HTMLResponse)
def visitor_shopping(request: Request, slug: str, db: Session = Depends(get_db)):
    estate = _get_estate(slug)
    if not estate:
        return RedirectResponse(url="/", status_code=302)
    cp_slug = estate["car_park_slug"]
    car_park = db.query(CarPark).filter(CarPark.slug == cp_slug).first()
    return templates.TemplateResponse("location/visitor/shopping.html", {
        "request": request,
        "slug": slug,
        "estate_name": car_park.owner.name if car_park else estate["name"],
        "car_park_name": "Shopping",
        "logo_url": (getattr(car_park, "logo_url", None) or "") if car_park else "",
        "shops": SHOPPING.get(slug, []),
        "local_produce": LOCAL_PRODUCE.get(slug, []),
    })


@router.get("/{slug}/visitor/sponsor-a-bench", response_class=HTMLResponse)
def visitor_bench(request: Request, slug: str, db: Session = Depends(get_db)):
    estate = _get_estate(slug)
    if not estate:
        return RedirectResponse(url="/", status_code=302)
    cp_slug = estate["car_park_slug"]
    car_park = db.query(CarPark).filter(CarPark.slug == cp_slug).first()
    return templates.TemplateResponse("location/visitor/bench.html", {
        "request": request,
        "slug": slug,
        "estate_name": car_park.owner.name if car_park else estate["name"],
        "car_park_name": "Sponsor a Bench",
        "logo_url": (getattr(car_park, "logo_url", None) or "") if car_park else "",
        "tiers": BENCH_TIERS,
        "bench_types": BENCH_TYPES,
        "bench_locations": BENCH_LOCATIONS.get(slug, []),
    })


@router.get("/{slug}/visitor/legacy", response_class=HTMLResponse)
def visitor_legacy(request: Request, slug: str, db: Session = Depends(get_db)):
    estate = _get_estate(slug)
    if not estate:
        return RedirectResponse(url="/", status_code=302)
    cp_slug = estate["car_park_slug"]
    car_park = db.query(CarPark).filter(CarPark.slug == cp_slug).first()
    return templates.TemplateResponse("location/visitor/legacy.html", {
        "request": request,
        "slug": slug,
        "estate_name": car_park.owner.name if car_park else estate["name"],
        "car_park_name": "Legacy",
        "logo_url": (getattr(car_park, "logo_url", None) or "") if car_park else "",
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
        "slug": slug,
        "estate_name": car_park.owner.name if car_park else "",
        "car_park_name": car_park.name if car_park else "",
        "logo_url": (getattr(car_park, "logo_url", None) or "") if car_park else "",
        "brand": {"accent": accent},
    })
