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
from ..data.estates import ESTATES

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

# Walk data — keyed by estate slug then walk slug
WALKS = {
    "hever-castle": [
        {
            "slug": "lake-walk",
            "title": "Lake Walk",
            "distance": "3.5 km",
            "duration": "1 hr",
            "difficulty": "Easy",
            "summary": "A peaceful circuit of the castle's magnificent 38-acre lake, with views of the Japanese Tea House, the Italian Loggia, and the castle itself reflected across still water.",
            "image_url": "",
            "center": [51.1925, 0.1117],
            "zoom": 14,
            "waypoint_zoom": 16,
            "route": [
                [51.1934, 0.1108], [51.1938, 0.1122], [51.1937, 0.1140],
                [51.1932, 0.1158], [51.1924, 0.1168], [51.1915, 0.1165],
                [51.1908, 0.1152], [51.1906, 0.1135], [51.1910, 0.1118],
                [51.1917, 0.1107], [51.1925, 0.1103], [51.1934, 0.1108]
            ],
            "waypoint_coords": [
                [51.1934, 0.1108], [51.1937, 0.1148], [51.1908, 0.1150], [51.1916, 0.1107]
            ],
            "waypoints": [
                {
                    "title": "Castle Forecourt",
                    "description": [
                        "The walk begins at the castle forecourt, where the moat and drawbridge make for one of the most photographed scenes in Kent. The stone gatehouse dates from the 13th century and was already old when Anne Boleyn played here as a child. Take a moment to absorb the view before setting off — the castle reflected in the moat water is particularly striking in early morning light.",
                        "Follow the signed Lake Walk path heading south-east through the formal gardens. You will pass the Yew Maze on your left — planted in 1904 using more than a thousand yew trees imported from the Netherlands — and the Water Maze on Sixteen Acre Island, where stepping stones conceal hidden jets ready to drench the unwary.",
                    ],
                    "image_url": ""
                },
                {
                    "title": "The Italian Loggia",
                    "description": [
                        "At the northern end of the lake, the Italian Loggia announces itself with a sweep of colonnaded stonework descending to the water's edge. William Waldorf Astor — the American millionaire who rescued Hever from near-ruin in 1903 — had the loggia and the entire Italian Garden constructed to display his extraordinary collection of ancient Greek and Roman sculpture, amassed during his time as US Ambassador to Italy.",
                        "The statuary lining the Pompeiian Wall nearby includes pieces of genuine antiquity sitting alongside high-quality Edwardian reproductions. Some figures are two millennia old. The scale of the project was remarkable: over eight hundred men spent two years excavating the lake alone. The result is one of the finest Edwardian gardens in England, and virtually unchanged from when Astor first laid eyes on it.",
                    ],
                    "image_url": ""
                },
                {
                    "title": "Japanese Tea House",
                    "description": [
                        "About halfway round the lake you will spot the Japanese Tea House Folly perched on the edge of Sixteen Acre Island, its reflected silhouette shimmering on the water. This charming lakeside pavilion was originally built in the Edwardian period and was faithfully reconstructed in 2013 to mark the 30th anniversary of the Guthrie family's ownership of Hever. It is best viewed from a distance — the reflection and the surrounding pines give it a distinctly Japanese woodblock print quality.",
                        "This stretch of the lake walk offers the best birdwatching on the estate. Kingfishers are regularly seen darting low across the surface, and grey herons stand motionless in the shallows on the far bank. In summer, great crested grebes perform their elaborate courtship dances here, and mute swans nest in the reeds at the southern end.",
                    ],
                    "image_url": ""
                },
                {
                    "title": "Anne Boleyn's Walk",
                    "description": [
                        "The return leg passes through Anne Boleyn's Walk, a broad avenue of mature trees planted over a century ago. The scale of the trees — some now reaching thirty metres — gives this section a cathedral-like quality, especially in autumn when the canopy turns gold and amber. It is easy to understand why this was designated as a separate named walk: on a calm day it is one of the most tranquil spots on the entire estate.",
                        "The path loops back toward the castle through the formal rose gardens and the Italian Garden's outer terraces. Look back toward the lake as you rise — there are fine views of the water and the loggia behind you. The full circuit brings you back to the forecourt with a fresh appreciation of just how much Astor achieved in reshaping this landscape, and how seamlessly it has aged into something that feels entirely natural.",
                    ],
                    "image_url": ""
                },
            ],
        },
        {
            "slug": "italian-garden-stroll",
            "title": "Italian Garden Stroll",
            "distance": "1.5 km",
            "duration": "45 min",
            "difficulty": "Easy",
            "summary": "A leisurely wander through the award-winning Italian Garden, past ancient statuary, grottoes, fountains and the Pompeiian Wall — the finest Edwardian garden in the South East.",
            "image_url": "",
            "center": [51.1920, 0.1095],
            "zoom": 16,
            "waypoint_zoom": 17,
            "route": [
                [51.1928, 0.1108], [51.1925, 0.1098], [51.1920, 0.1088],
                [51.1914, 0.1082], [51.1910, 0.1090], [51.1912, 0.1102],
                [51.1917, 0.1108], [51.1922, 0.1110], [51.1928, 0.1108]
            ],
            "waypoint_coords": [
                [51.1925, 0.1098], [51.1914, 0.1082], [51.1912, 0.1098], [51.1920, 0.1108]
            ],
            "waypoints": [
                {
                    "title": "The Pompeiian Wall",
                    "description": [
                        "The Pompeiian Wall is the defining feature of the Italian Garden — a 160-metre-long colonnaded walk lined with ancient and Edwardian statuary, enclosed by climbing roses and wisteria. The niches between the columns contain pieces of genuine Roman and Greek antiquity, including funerary urns, marble torsos, and inscribed tablets, sitting alongside high-quality reproductions commissioned by William Waldorf Astor in the early 1900s.",
                        "Walking the length of the wall is an extraordinary experience — part museum, part garden, entirely unlike anything else in England. The effect Astor was seeking was unambiguous: he wanted visitors to feel they had stepped into a patrician Italian garden of the Renaissance period. He very largely succeeded.",
                    ],
                    "image_url": ""
                },
                {
                    "title": "Grottoes and Fountains",
                    "description": [
                        "Set into the hillside at the garden's southern end are a series of shaded grottoes — moss-covered stone alcoves with dripping water features and statuary within. They were designed to provide cool relief from summer heat and to evoke the garden follies of 18th-century Italy. Even on a warm day they retain a refreshing chill, and the sound of running water makes them a peaceful place to pause.",
                        "The central fountain of the Italian Garden is modelled on Florentine renaissance precedents. In summer, the plume of water and the surrounding beds of lavender and agapanthus make this the most photographed spot in the garden. The whole area rewards slow exploration — there is almost always some detail, inscription or carving that first-time visitors miss entirely.",
                    ],
                    "image_url": ""
                },
                {
                    "title": "The Anne Boleyn Statue",
                    "description": [
                        "In the heart of the Italian Garden stands a graceful marble statue of Anne Boleyn, placed here as a tribute to the woman most closely associated with Hever. Anne was born around 1501 and spent her early childhood at the castle before being sent abroad for her education. She returned to Hever in the late 1520s, and it was here that Henry VIII sent his famous love letters — seven of which survive in the Vatican Library, though historians remain uncertain how they arrived there.",
                        "The statue captures something of the intelligence and composure that contemporaries attributed to Anne. She was highly educated by the standards of her time, spoke French fluently, and was an accomplished musician and dancer. The garden setting seems appropriate: there is good evidence that Anne found pleasure in the grounds of Hever during the anxious months of Henry's pursuit, walking here while her fate was decided at court.",
                    ],
                    "image_url": ""
                },
                {
                    "title": "The Rose and Herb Gardens",
                    "description": [
                        "The walk concludes through Hever's rose gardens, which contain hundreds of varieties and are at their most spectacular in late June. The beds are arranged in formal geometric patterns with topiary hedging — a style faithful to the Tudor gardens that would have existed here in Anne Boleyn's time, though the planting itself is largely Victorian and Edwardian. The herb garden alongside follows a medieval pattern and is planted with species in use during the Tudor period.",
                        "The overall effect of the Italian Garden — statuary, water, fragrance, enclosure — is one of the most complete sensory experiences in any English garden. Allow more time than you think you need: it repays unhurried attention, and the combination of ancient Rome and Edwardian England is an improbable but entirely successful one.",
                    ],
                    "image_url": ""
                },
            ],
        },
        {
            "slug": "hever-chiddingstone-circular",
            "title": "Hever & Chiddingstone Circular",
            "distance": "10 km",
            "duration": "2.5 hrs",
            "difficulty": "Moderate",
            "summary": "A classic High Weald circuit linking Hever Castle with the picture-perfect Tudor village of Chiddingstone — two of the finest heritage sites in the Kentish Weald, connected by ancient footpaths and Eden Valley countryside.",
            "image_url": "",
            "center": [51.1960, 0.1220],
            "zoom": 13,
            "waypoint_zoom": 15,
            "route": [
                [51.1934, 0.1108], [51.1942, 0.1138], [51.1955, 0.1162],
                [51.1968, 0.1175], [51.1980, 0.1195], [51.1990, 0.1230],
                [51.1985, 0.1268], [51.1972, 0.1290], [51.1958, 0.1285],
                [51.1943, 0.1260], [51.1930, 0.1230], [51.1920, 0.1200],
                [51.1918, 0.1170], [51.1925, 0.1140], [51.1934, 0.1108]
            ],
            "waypoint_coords": [
                [51.1934, 0.1108], [51.1985, 0.1270], [51.1958, 0.1285], [51.1920, 0.1200]
            ],
            "waypoints": [
                {
                    "title": "Hever Castle Entrance",
                    "description": [
                        "The walk begins at Hever Castle and heads north-east on the Eden Valley Walk, a long-distance trail that follows the course of the River Eden through some of the finest countryside in the Kentish Weald. The path crosses open farmland with views back toward the castle — on a clear day you can see the keep from over a kilometre away — before entering a stretch of mixed woodland managed for conservation.",
                        "The High Weald landscape through which this walk travels is one of the best-preserved medieval countryside patterns in England. The irregular field boundaries, sunken lanes and ancient hedgerows you pass here follow boundaries established before the Norman Conquest and have survived largely intact for a thousand years. This is remarkable countryside, and it rewards a slow pace.",
                    ],
                    "image_url": ""
                },
                {
                    "title": "Bough Beech Reservoir",
                    "description": [
                        "The route passes close to Bough Beech Reservoir, a large artificial lake created in the 1960s to supply water to the Sevenoaks and Tonbridge area. Despite its utilitarian origins it has become one of the most important wildlife sites in Kent, managed as a nature reserve by the Kent Wildlife Trust. The surrounding scrub and wetland edge holds nationally important populations of breeding birds including nightingales, turtle doves, and several warbler species.",
                        "You can hear nightingales singing from this spot in May and early June — one of the most thrilling sounds in the English countryside. The reservoir itself supports significant numbers of wintering wildfowl and waders, including occasional rarities that attract birdwatchers from across the south-east. A short detour to the information centre is worthwhile if you have time.",
                    ],
                    "image_url": ""
                },
                {
                    "title": "Chiddingstone Village",
                    "description": [
                        "Chiddingstone is widely regarded as one of the most complete Tudor villages in England. The long, single street is lined with timber-framed buildings that have changed almost nothing externally since the 16th and 17th centuries, and the National Trust manages the entire street to preserve its character. There is not a chain shop or plastic fascia in sight — the effect is genuinely transporting.",
                        "The Castle Inn at the eastern end of the street has been serving travellers since 1420 and remains a proper country pub with real ales and good food. Chiddingstone Castle — a slightly misleading name for a country house with castle-style battlements — stands just beyond and is open to visitors at weekends in season. The medieval church of St Mary the Virgin sits at the western end and contains some fine monuments to the Streatfeild family, who built much of what you see around you.",
                    ],
                    "image_url": ""
                },
                {
                    "title": "Return via Eden Valley",
                    "description": [
                        "The return leg follows the Eden Valley Walk south-west through a succession of meadows and hop gardens, crossing the River Eden at a footbridge before climbing gently back toward Hever through ancient woodland. In early spring, bluebells carpet the woodland floor here in drifts of extraordinary intensity. In autumn the same path is richly coloured with fungi and turning leaves.",
                        "The final approach brings you back past St Peter's Church, Hever — a small medieval church in the village that contains the magnificent brass memorial to Sir Thomas Boleyn, Anne's father, who died in 1539. The brass is one of the finest Tudor brasses in England and shows Sir Thomas in his robes as a Knight of the Garter. It is open to visitors and well worth a few minutes of your time before returning to the castle.",
                    ],
                    "image_url": ""
                },
            ],
        },
        {
            "slug": "eden-valley-walk-hever-leigh",
            "title": "Eden Valley Walk: Hever to Leigh",
            "distance": "8 km",
            "duration": "2 hrs",
            "difficulty": "Moderate",
            "summary": "A linear walk along the Eden Valley Walk linking Hever Castle with the handsome village of Leigh, following the River Eden through the peaceful Weald countryside.",
            "image_url": "",
            "center": [51.2000, 0.1300],
            "zoom": 13,
            "waypoint_zoom": 15,
            "route": [
                [51.1934, 0.1108], [51.1948, 0.1120], [51.1962, 0.1145],
                [51.1978, 0.1168], [51.1992, 0.1195], [51.2005, 0.1225],
                [51.2018, 0.1258], [51.2030, 0.1290], [51.2045, 0.1320],
                [51.2058, 0.1350], [51.2068, 0.1380]
            ],
            "waypoint_coords": [
                [51.1934, 0.1108], [51.1978, 0.1168], [51.2030, 0.1290], [51.2068, 0.1380]
            ],
            "waypoints": [
                {
                    "title": "Hever Castle",
                    "description": [
                        "The Eden Valley Walk is one of Kent's best long-distance paths, tracing the course of the River Eden from Edenbridge to its confluence with the Medway at Penshurst. This section — from Hever to Leigh — is among the finest: a gentle, mostly flat route through classic Kentish countryside of orchards, hop gardens, water meadows and ancient woodland.",
                        "Leave Hever via the village lane and pick up the Eden Valley Walk waymarkers heading north-east. The path is well signed throughout, but a good map is advisable — the High Weald has a complex network of paths and the Eden Valley Walk occasionally shares routes with other trails before separating again. The going underfoot can be muddy after rain; boots are recommended from October to April.",
                    ],
                    "image_url": ""
                },
                {
                    "title": "River Eden Meadows",
                    "description": [
                        "The path soon joins the River Eden itself and follows its northern bank through a series of water meadows that have the feel of a much earlier England — unhurried, unimproved, and populated by little more than cattle, lapwings and the occasional heron. The river here is clean and slow-moving, bordered by crack willows and alder carr, and it is not unusual to spot otters, though they are shy and most often seen at dawn.",
                        "Look across the river toward the soft ridgeline to the south — this is the High Weald AONB, one of the most biodiverse landscapes in southern England. The patchwork of small fields, ancient hedgerows and copses you see from here follows a pattern established in the medieval period and largely unchanged since. The relative absence of modern agricultural intensification has allowed plant and animal diversity to survive here that has been lost from much of lowland England.",
                    ],
                    "image_url": ""
                },
                {
                    "title": "Penshurst View",
                    "description": [
                        "As the path approaches Penshurst the tower of the church of St John the Baptist becomes visible above the treeline, and shortly after, the roofline of Penshurst Place itself. The view of the medieval manor from the meadows to the west is one of the finest in Kent — the building appears to have grown organically from the landscape rather than been imposed on it, which is essentially what happened over its 680-year history.",
                        "You can detour into Penshurst village for refreshment — the Leicester Arms is an outstanding gastropub — and return to the Eden Valley Walk afterward. Alternatively, continue directly to Leigh following the waymarkers through the estate parkland. Both villages have good bus connections if you would prefer not to retrace your steps to Hever.",
                    ],
                    "image_url": ""
                },
                {
                    "title": "Leigh Village Green",
                    "description": [
                        "The walk ends at Leigh — pronounced 'Lie' by locals, a source of gentle confusion to visitors — a village of extraordinary prettiness centred on a large triangular green. The cricket ground on the green is in use on summer weekends and watching a match with a pint from the Fleur de Lis pub is one of the most classically English afternoons imaginable. The church of St Mary is worth visiting for its medieval interior and Norman south doorway.",
                        "Leigh station, on the Redhill to Tonbridge line, is a short walk from the green and allows an easy return to Hever or onward to London. Alternatively, taxis are available from Tonbridge. If you are walking back, allow two hours and be aware that the path is significantly more exposed to afternoon sun than the outward leg — carry water.",
                    ],
                    "image_url": ""
                },
            ],
        },
    ],
    "penshurst-place": [
        {
            "slug": "parkland-walk",
            "title": "Parkland Walk",
            "distance": "5 km",
            "duration": "1.5 hrs",
            "difficulty": "Easy",
            "summary": "A beautiful circuit through the ancient parkland of Penshurst Place, following the estate's own signed trail past the trout lakes, the arboretum and sweeping views of the medieval manor.",
            "image_url": "",
            "center": [51.1759, 0.1739],
            "zoom": 14,
            "waypoint_zoom": 16,
            "route": [
                [51.1765, 0.1730], [51.1772, 0.1750], [51.1778, 0.1772],
                [51.1780, 0.1795], [51.1775, 0.1815], [51.1765, 0.1825],
                [51.1752, 0.1820], [51.1742, 0.1808], [51.1738, 0.1790],
                [51.1740, 0.1768], [51.1748, 0.1748], [51.1758, 0.1735],
                [51.1765, 0.1730]
            ],
            "waypoint_coords": [
                [51.1765, 0.1730], [51.1778, 0.1795], [51.1752, 0.1820], [51.1748, 0.1748]
            ],
            "waypoints": [
                {
                    "title": "The Visitor Entrance",
                    "description": [
                        "The Parkland Walk begins at the visitor entrance to Penshurst Place and immediately enters the ancient parkland that has surrounded the manor for seven centuries. The estate covers around 2,500 acres in total, though the managed parkland open to walkers is a more intimate area of rolling grassland, mature oak and chestnut, and the trout lakes that shimmer in the valley below the house.",
                        "Penshurst Place has been the home of the Sidney family since 1552, when King Edward VI gave the estate to Sir William Sidney, a close courtier. The family has been here continuously for over 470 years — one of the longest unbroken aristocratic occupations in England. The current Viscount De L'Isle, whose family title derives from the Sidney line, still lives in part of the house, which gives Penshurst a lived-in quality missing from many heritage properties.",
                    ],
                    "image_url": ""
                },
                {
                    "title": "The Trout Lakes",
                    "description": [
                        "The path descends gently to the trout lakes — a series of linked ponds in the valley below the house, surrounded by mature willows and alders. The lakes were established for the estate's game fishing and are still privately managed, but the footpaths run along the banks and the reflections of the house and surrounding woodland in the still water on a calm morning make this one of the most beautiful spots on the estate.",
                        "Grey herons fish here year-round, and in summer the lake margins are busy with damselflies and dragonflies. The woodland edge around the lakes is particularly good for birds: nuthatches, treecreepers, great spotted woodpeckers and all three native woodpecker species have been recorded regularly. The arboretum above the lakes contains specimen trees planted in the Victorian period, some of which have now grown to considerable size.",
                    ],
                    "image_url": ""
                },
                {
                    "title": "The Arboretum",
                    "description": [
                        "The arboretum on the western slope above the lakes is one of the less-visited corners of the Penshurst estate and all the more rewarding for it. The Victorian plantings include some fine specimen conifers, a collection of rare oaks, and a mature mulberry grove that the estate records suggest may predate the current planting scheme by several centuries. In autumn the colour here is outstanding.",
                        "The Woodland Trail runs through the arboretum and includes a series of natural play features for younger visitors — fallen log tunnels, stepping posts, and quiet clearings with den-building materials. It is an excellent combination of adult interest and child-friendly exploration, and the paths are wide enough for pushchairs in dry conditions. The trail connects back to the main parkland walk at the eastern end.",
                    ],
                    "image_url": ""
                },
                {
                    "title": "View of the Manor",
                    "description": [
                        "The finest view of Penshurst Place is from the footpath that runs along the northern ridge of the parkland, where the full south-facing facade of the medieval manor is laid out before you. The building's extraordinary complexity — the result of additions and alterations spanning six centuries — is best appreciated from this distance, where you can read the different phases of construction in the changing rooflines and materials.",
                        "The oldest visible section is the Baron's Hall of 1341, its great chestnut-roofed ridge rising above everything around it. To the left is the Buckingham Building of the 1390s, and to the right the Sidney additions of the 16th and 17th centuries. The whole is held together by an ancient yew hedge — over a mile of it — that divides the formal walled garden from the parkland. From up here, it looks exactly as it would have to a horseman returning from a day's hunting in the 1580s.",
                    ],
                    "image_url": ""
                },
            ],
        },
        {
            "slug": "riverside-walk",
            "title": "Riverside Walk",
            "distance": "4 km",
            "duration": "1 hr",
            "difficulty": "Easy",
            "summary": "A tranquil walk following the River Medway through the lower estate, part of the Eden Valley Walk long-distance trail — flat, scenic and accessible throughout the year.",
            "image_url": "",
            "center": [51.1745, 0.1760],
            "zoom": 14,
            "waypoint_zoom": 16,
            "route": [
                [51.1758, 0.1735], [51.1750, 0.1720], [51.1740, 0.1710],
                [51.1728, 0.1705], [51.1718, 0.1712], [51.1710, 0.1725],
                [51.1708, 0.1740], [51.1712, 0.1758], [51.1720, 0.1772],
                [51.1730, 0.1778], [51.1742, 0.1775], [51.1752, 0.1760],
                [51.1758, 0.1745]
            ],
            "waypoint_coords": [
                [51.1758, 0.1735], [51.1718, 0.1712], [51.1708, 0.1740], [51.1742, 0.1775]
            ],
            "waypoints": [
                {
                    "title": "Penshurst Village",
                    "description": [
                        "The Riverside Walk begins in Penshurst village, a settlement that was already old when the Baron's Hall was constructed in 1341. The church of St John the Baptist at the village centre contains a remarkable collection of Sidney family monuments spanning four centuries, and is worth visiting before or after the walk. The village also has the Leicester Arms pub, which has been named in the Good Food Guide and is excellent for lunch.",
                        "From the church, follow the footpath south-west toward the River Medway. The path is signed as part of the Eden Valley Walk, which follows the River Eden from Edenbridge to its confluence with the Medway here at Penshurst. The Medway — one of the principal rivers of Kent — rises on the High Weald and flows north-east eventually to Rochester and the Thames estuary.",
                    ],
                    "image_url": ""
                },
                {
                    "title": "River Medway",
                    "description": [
                        "The path joins the river bank and follows the Medway through a landscape of riverside meadows, crack willows, and occasional riverside marshland. In winter and spring these meadows are often flooded, bringing with them large numbers of wildfowl — teal, wigeon, shoveler and pintail are all regular. In summer the water is clear enough to see the fish holding in the deeper pools, and the kingfisher is a reliable sight on this stretch.",
                        "The Medway here is neither fast nor dramatic — it is a quiet, reflective river, and the walk along its banks has a quality of peacefulness that the busier estate paths lack. There are no crowds, few other walkers, and the views are of nothing more demanding than willows, water and sky. It is exactly the kind of walk that rewards being in no hurry at all.",
                    ],
                    "image_url": ""
                },
                {
                    "title": "Lancup Well",
                    "description": [
                        "A short distance from the river is Lancup Well, a medieval spring that supplied water to the estate for centuries and is marked on Ordnance Survey maps as a place of historic interest. The well is set in a shaded hollow and has a pleasing atmosphere of antiquity — the stonework dates from the Tudor period, though the spring itself is certainly older.",
                        "The surrounding woodland in this area contains ancient ash and field maple, and the ground flora in spring is exceptional: primroses, wood anemones and early purple orchids are all present, followed by a flush of bluebells in late April. The combination of historic fabric, clean water and undisturbed flora makes this one of those tucked-away spots that long-term visitors to Penshurst tend to keep quietly to themselves.",
                    ],
                    "image_url": ""
                },
                {
                    "title": "Return via Estate Boundary",
                    "description": [
                        "The return leg follows the estate boundary wall — an ancient structure of Kentish ragstone that dates in parts from the medieval period. The wall is overhung with ferns, ivy and occasional garden escapes, and the path alongside it passes through the kind of dappled, enclosed woodland that feels genuinely old. The estate's deer are often seen grazing on the parkland slopes visible above the wall.",
                        "The path emerges at the lower entrance to the walled gardens, where you have the option of entering the formal garden enclosure before returning to the visitor entrance, or heading directly back via the parkland path. If the gardens are open, the lower entrance gives access to the rose garden and the Long Border — both at their best in June and July.",
                    ],
                    "image_url": ""
                },
            ],
        },
        {
            "slug": "chiddingstone-penshurst-circular",
            "title": "Chiddingstone & Penshurst Circular",
            "distance": "7.2 km",
            "duration": "2 hrs",
            "difficulty": "Moderate",
            "summary": "A wonderful circuit linking Penshurst Place with the Tudor village of Chiddingstone, crossing classic High Weald countryside of ancient lanes, farmland and orchard.",
            "image_url": "",
            "center": [51.1860, 0.1500],
            "zoom": 13,
            "waypoint_zoom": 15,
            "route": [
                [51.1758, 0.1735], [51.1768, 0.1712], [51.1782, 0.1688],
                [51.1800, 0.1660], [51.1820, 0.1635], [51.1845, 0.1612],
                [51.1868, 0.1600], [51.1888, 0.1588], [51.1905, 0.1582],
                [51.1895, 0.1610], [51.1875, 0.1642], [51.1852, 0.1668],
                [51.1825, 0.1695], [51.1800, 0.1710], [51.1778, 0.1720],
                [51.1758, 0.1735]
            ],
            "waypoint_coords": [
                [51.1758, 0.1735], [51.1845, 0.1612], [51.1905, 0.1582], [51.1825, 0.1695]
            ],
            "waypoints": [
                {
                    "title": "Penshurst Place",
                    "description": [
                        "Set out from the Penshurst Place visitor entrance and follow the footpath north-west through the parkland, passing below the house with its magnificent medieval roofline. The path climbs gently through the parkland before reaching open farmland at the estate boundary — a handgate in the ragstone wall marks the transition from private parkland to public footpath.",
                        "The High Weald countryside between Penshurst and Chiddingstone is among the best-preserved medieval landscape in England. The sunken lanes — some worn a metre or more below field level over centuries of use — the irregular field boundaries, and the ancient hedgerows give this stretch of countryside a timeless quality that is increasingly rare in south-east England.",
                    ],
                    "image_url": ""
                },
                {
                    "title": "High Weald Farmland",
                    "description": [
                        "The path crosses a series of pastoral fields — typically grazed by sheep or cattle — with wide views north toward the greensand ridge and south toward the wooded Weald beyond Groombridge and Withyham. On clear days, the radio masts on the North Downs are visible to the north, and the High Weald's characteristic ridgeline creates a horizon that feels much further away than it actually is.",
                        "Several of the fields on this stretch contain ancient field boundary trees — veteran oaks and ash with girths suggesting ages of 400 years or more. These veterans are ecologically irreplaceable: a single ancient oak supports more species of invertebrate than any other tree in the British Isles, and the lichens and fungi that colonise very old bark are found nowhere else. Look for woodpeckers excavating nest cavities in the softer dead wood of the largest specimens.",
                    ],
                    "image_url": ""
                },
                {
                    "title": "Chiddingstone Village",
                    "description": [
                        "Chiddingstone is one of the most perfectly preserved Tudor villages in England. The single village street, owned and maintained by the National Trust, is lined entirely with timber-framed buildings dating from the 15th to 17th centuries. There are no shop signs in modern fonts, no intrusive signage — just old buildings, old stone and a pub with origins in 1420.",
                        "The Castle Inn at the end of the street is an excellent stopping point — good real ales, reliable food and an atmosphere of comfortable antiquity. Chiddingstone Castle (actually an 18th-century country house in Gothic style) is open to visitors and contains a fascinating private collection of Japanese lacquerwork, Egyptian antiquities and Stuart memorabilia assembled by the eccentric Denys Bower, who left the house and its contents to the nation on his death in 1977.",
                    ],
                    "image_url": ""
                },
                {
                    "title": "Return via Wat Stock",
                    "description": [
                        "The return leg follows the Eden Valley Walk south-east from Chiddingstone through the hamlet of Wat Stock and back across the rolling farmland to Penshurst. The path descends through a fine section of ancient woodland before crossing the River Eden at a traditional footbridge — one of several that have stood at roughly this point for centuries.",
                        "The final kilometre runs through the southern edge of the Penshurst Place parkland, with good views of the house and the walled garden wall. If you time the walk to arrive back in the late afternoon, the light on the south face of the manor can be extraordinary — the pale Kentish ragstone glows warm gold in summer evenings, and the tower of the Baron's Hall, visible above everything else, gives the whole scene a quality that visitors sometimes describe, with complete sincerity, as magical.",
                    ],
                    "image_url": ""
                },
            ],
        },
        {
            "slug": "leigh-penshurst-circular",
            "title": "Leigh & Penshurst Circular",
            "distance": "8.5 km",
            "duration": "2.5 hrs",
            "difficulty": "Moderate",
            "summary": "A rewarding loop between two handsome Kentish villages — Leigh and Penshurst — through the flat water meadows and historic parkland of the Eden Valley.",
            "image_url": "",
            "center": [51.1900, 0.1540],
            "zoom": 13,
            "waypoint_zoom": 15,
            "route": [
                [51.2062, 0.1422], [51.2045, 0.1430], [51.2020, 0.1445],
                [51.1995, 0.1462], [51.1970, 0.1488], [51.1945, 0.1512],
                [51.1920, 0.1545], [51.1898, 0.1572], [51.1878, 0.1595],
                [51.1858, 0.1620], [51.1868, 0.1650], [51.1882, 0.1672],
                [51.1900, 0.1688], [51.1920, 0.1695], [51.1940, 0.1680],
                [51.1962, 0.1658], [51.1985, 0.1632], [51.2008, 0.1598],
                [51.2028, 0.1568], [51.2045, 0.1528], [51.2058, 0.1490],
                [51.2062, 0.1450], [51.2062, 0.1422]
            ],
            "waypoint_coords": [
                [51.2062, 0.1422], [51.1878, 0.1595], [51.1900, 0.1688], [51.2045, 0.1528]
            ],
            "waypoints": [
                {
                    "title": "Leigh Village Green",
                    "description": [
                        "Leigh — pronounced 'Lie' by everyone who lives there — is a village of considerable charm centred on a handsome triangular green. The cricket club plays here on summer weekends, and the combination of thatched cottages, the Fleur de Lis pub and a Norman church makes it one of the most satisfying village greens in the county. Start the walk from the green and follow the Eden Valley Walk south toward Penshurst.",
                        "The walk is largely flat — the Eden Valley is a broad, gently graded vale — and the going is straightforward except after sustained rain, when the riverside meadows can be very muddy. Boots are recommended from October to April. The route is signed throughout with Eden Valley Walk waymarkers, though a map is advisable on the Penshurst estate section where several paths converge.",
                    ],
                    "image_url": ""
                },
                {
                    "title": "Eden Valley Meadows",
                    "description": [
                        "The Eden Valley Walk crosses a series of traditionally managed meadows along the River Eden, a small and beautiful river that rises on the High Weald above Edenbridge and joins the Medway at Penshurst. The meadows here are unimproved — never ploughed or re-seeded — and contain plant species that have been present continuously for centuries. In June, the combination of grasses, sedges and wildflowers is remarkable by modern standards.",
                        "Lapwings breed in the meadows in good years, and the river margins support good populations of water voles — shy, round and entirely charming animals that have vanished from much of England due to habitat loss and mink predation. Listen for the characteristic 'plop' as they enter the water from their bankside runs. Otter spraints are found regularly on the bridge parapets, though the animals themselves are rarely seen in daylight.",
                    ],
                    "image_url": ""
                },
                {
                    "title": "Penshurst Place Parkland",
                    "description": [
                        "The path enters the Penshurst Place estate through a kissing gate and crosses the lower parkland with the house visible on the ridge above. The parkland here has been grazed by cattle and deer continuously for many centuries, and the combination of ancient trees — including several veteran oaks of great age — and close-cropped turf gives it the quality of a medieval deer park, which is essentially what it is.",
                        "The path passes below the formal walled garden wall and through the churchyard of the estate church, St John the Baptist, which contains an exceptional collection of Sidney family monuments. If the church is open, the tomb of Sir William Sidney and several fine Elizabethan brasses are worth seeking out. The churchyard itself, with its ancient yew trees and view up to the manor, is a place of considerable beauty.",
                    ],
                    "image_url": ""
                },
                {
                    "title": "Return via Wat Stock",
                    "description": [
                        "From Penshurst village, the return route heads north via Wat Stock — a quiet hamlet on the edge of the estate — before cutting across farmland back to Leigh. This section is less-walked than the outward leg and has a pleasingly deserted quality on weekdays. The field paths are well signed and the gentle rise and fall of the ground gives occasional views north toward the greensand hills.",
                        "The walk finishes back on Leigh Green, where the Fleur de Lis is an excellent choice for refreshment. The pub serves a good selection of ales and a solid menu of pub classics — the Sunday roast is particularly well regarded locally. Leigh station, a short walk from the green, gives direct train access to Tonbridge (15 minutes) and from there to London Bridge.",
                    ],
                    "image_url": ""
                },
            ],
        },
    ],
    "shere-manor-estate": [
        {
            "slug": "shere-village",
            "title": "Shere Village",
            "distance": "0.5 km",
            "duration": "15 min",
            "difficulty": "Easy",
            "summary": "A short walk around the village, taking in various interesting buildings, the church, stores, restaurants.",
            "image_url": "/static/images/memorial.jpg",
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
            "image_url": "https://s0.geograph.org.uk/geophotos/01/43/38/1433808_cc025f77.jpg",
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
    "hever-castle": [
        {
            "slug": "moat-restaurant",
            "name": "The Moat Restaurant",
            "type": "restaurant",
            "rating": 4.3,
            "guide_price": "£20",
            "open_today": "10:00–17:00 (hot food 12:00–15:00)",
            "distance": "on estate",
            "coords": [51.1930, 0.1112],
            "summary": "Hever Castle's main on-site restaurant sits at the heart of the grounds, combining a relaxed grab-and-go section with a proper table-service dining area. The menu draws on local Kent produce — expect seasonal soups, salads, fish cakes, burgers and daily specials — all backed by the estate's maximum food hygiene rating. A flexible choice whether you want a quick bite between attractions or a proper sit-down meal.",
            "image_url": "",
        },
        {
            "slug": "waterside-bar",
            "name": "The Waterside Bar, Restaurant & Terrace",
            "type": "restaurant",
            "rating": 4.2,
            "guide_price": "£30",
            "open_today": "9:00–21:00",
            "distance": "10 min walk",
            "coords": [51.1910, 0.1075],
            "summary": "A mile from the castle at Hever Castle Golf & Wellbeing, the Waterside offers a full day's dining from breakfast through to dinner, with a terrace overlooking the golf course. Afternoon tea at £29.50 is the standout — entirely homemade, served in civilised surroundings, with views that make the whole experience feel like a proper occasion. Castle ticket holders receive 10% off food and drink on the day of their visit.",
            "image_url": "",
        },
        {
            "slug": "king-henry-viii",
            "name": "The King Henry VIII Inn",
            "type": "pub",
            "rating": 4.4,
            "guide_price": "£28",
            "open_today": "12:00–23:30 (food 12:00–15:00 & 18:00–21:00)",
            "distance": "5 min walk",
            "coords": [51.1938, 0.1103],
            "summary": "Directly opposite Hever Castle's entrance, this half-timbered and peg-tiled pub has been welcoming visitors since 1597 — though the current building dates from 1647. A winner of Shepherd Neame's Pub Food of the Year award, it serves honest British pub cooking alongside well-kept ales in a low-beamed, genuinely historic interior. The obvious choice for lunch before or after exploring the castle, and consistently one of the best pubs in the Sevenoaks district.",
            "image_url": "",
        },
        {
            "slug": "greyhound-hever",
            "name": "The Greyhound",
            "type": "restaurant",
            "rating": 4.5,
            "guide_price": "£38",
            "open_today": "Mon–Thu 16:00–21:30, Fri–Sun 12:30–21:30",
            "distance": "10 min drive",
            "coords": [51.1885, 0.1048],
            "summary": "Tucked down a quiet country lane between Hever and Markbeech, The Greyhound is a licensed restaurant with five rooms for bed and breakfast, three of which have balcony views. The cooking is precise and serious — this is not a pub offering a standard menu, but a proper restaurant that happens to occupy a historic country building. Booking is essential and strongly recommended; the atmosphere on a Friday or Saturday evening is hard to match in the area.",
            "image_url": "",
        },
        {
            "slug": "wheatsheaf-bough-beech",
            "name": "The Wheatsheaf at Bough Beech",
            "type": "pub",
            "rating": 4.3,
            "guide_price": "£25",
            "open_today": "Mon–Sat 12:00–21:00, Sun 12:00–20:00",
            "distance": "8 min drive",
            "coords": [51.1968, 0.0920],
            "summary": "A fine Tudor-era pub at Bough Beech, just a few minutes' drive from Hever, with a kitchen garden that supplies seasonal ingredients for a menu built around the finest local produce. Freshly made by a dedicated kitchen team, the cooking ranges from elevated pub classics to seasonal specials. The beer garden is particularly pleasant in summer, and the pub's proximity to Bough Beech Reservoir makes it a natural stopping point for birdwatchers and walkers alike.",
            "image_url": "",
        },
        {
            "slug": "little-brown-jug",
            "name": "The Little Brown Jug",
            "type": "pub",
            "rating": 4.4,
            "guide_price": "£30",
            "open_today": "12:00–21:00 (Fri–Sat until 21:30)",
            "distance": "12 min drive",
            "coords": [51.1890, 0.1555],
            "summary": "A well-regarded country pub at Chiddingstone Causeway, with multiple comfortable dining rooms, a large garden, and a menu of quality seasonal food served all day. The Monday carvery with freshly carved roasted meats is a local institution, and the weekend brunch draws visitors from across the Weald. Dog-friendly throughout, with an outdoor fire pit for cool evenings and a genuinely welcoming atmosphere that makes it worth the short drive.",
            "image_url": "",
        },
    ],
    "penshurst-place": [
        {
            "slug": "porcupine-pantry",
            "name": "Porcupine Pantry",
            "type": "cafe",
            "rating": 4.3,
            "guide_price": "£12",
            "open_today": "9:00–17:00 (hot food until 15:30)",
            "distance": "on estate",
            "coords": [51.1765, 0.1728],
            "summary": "Penshurst Place's own café, open daily year-round just inside the visitor entrance, serves freshly baked cakes from local producers, warming soups, sandwiches, baguettes and hot lunch options. The allergy-aware menu includes gluten-free and dairy-free choices throughout. Afternoon tea, pre-booked Monday to Friday, is excellent value at £19.95 per person and makes a lovely pause midway through a day on the estate.",
            "image_url": "",
        },
        {
            "slug": "leicester-arms",
            "name": "The Leicester Arms",
            "type": "pub",
            "rating": 4.5,
            "guide_price": "£40",
            "open_today": "12:00–23:00 (food 12:00–15:00 & 18:00–21:00)",
            "distance": "5 min walk",
            "coords": [51.1760, 0.1702],
            "summary": "Nestled at the heart of Penshurst village, the Leicester Arms is one of the finest gastropubs in Kent — named in the Good Food Guide's inaugural 100 Best Pubs. With origins in the 16th century, the inn champions seasonal British produce with an emphasis on locally sourced ingredients, from elevated pub classics to contemporary plates. The 11 beautifully styled en-suite rooms make it an equally excellent base for a longer stay.",
            "image_url": "",
        },
        {
            "slug": "bottle-house-inn",
            "name": "The Bottle House Inn",
            "type": "pub",
            "rating": 4.4,
            "guide_price": "£32",
            "open_today": "12:00–21:00",
            "distance": "12 min drive",
            "coords": [51.1648, 0.1478],
            "summary": "A 15th-century free house in the Kent countryside outside Penshurst, awarded a TripAdvisor Travellers Choice for 2025 and ranked number one restaurant in the area. The seasonal menu relies on the highest-quality local produce, with a deep commitment to sustainability that begins with ingredients sourced as close to the kitchen as possible. Superb Sunday roasts, a welcoming atmosphere for families and dogs, and cooking that gives the short drive genuine purpose.",
            "image_url": "",
        },
        {
            "slug": "chaser-inn",
            "name": "The Chaser Inn",
            "type": "pub",
            "rating": 3.9,
            "guide_price": "£28",
            "open_today": "9:00–23:00",
            "distance": "15 min drive",
            "coords": [51.2090, 0.2258],
            "summary": "An award-winning gastropub set in a beautifully converted Victorian chapel in the village of Shipbourne, combining historic character with a food-led menu that caters to diverse tastes, including strong vegetarian options. Open fires in winter, a terrace for summer, and a welcoming unstuffy atmosphere. Well worth the short drive north from Penshurst for an evening meal or a weekend lunch.",
            "image_url": "",
        },
        {
            "slug": "forge-stores-cafe",
            "name": "Forge Stores, Penshurst",
            "type": "cafe",
            "rating": 4.1,
            "guide_price": "£8",
            "open_today": "8:00–17:00",
            "distance": "5 min walk",
            "coords": [51.1758, 0.1698],
            "summary": "The village shop and stores in Penshurst, a short walk from the estate entrance, provides everything from fresh bread and local produce to light snacks and hot drinks. It is a genuine community shop rather than a visitor-facing operation, which gives it a refreshingly unfussy quality. Perfect for assembling a picnic before entering the estate grounds — the designated picnic areas off the Lime Walk are among the most pleasant spots on the estate.",
            "image_url": "",
        },
        {
            "slug": "spotted-dog-fordcombe",
            "name": "The Spotted Dog",
            "type": "pub",
            "rating": 4.3,
            "guide_price": "£30",
            "open_today": "12:00–22:00",
            "distance": "15 min drive",
            "coords": [51.1512, 0.1298],
            "summary": "A lovely country pub in the small village of Fordcombe, between Penshurst and Royal Tunbridge Wells, serving award-winning food using locally sourced produce. The building is a classic Kent pub of considerable age, with a garden that is one of the nicest outdoor dining spots in the Weald on a summer evening. An excellent choice if you want something a little further from the estate crowds.",
            "image_url": "",
        },
    ],
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
            "image_url": "/static/images/kinghams.jpg",
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
            "image_url": "https://www.london-unattached.com/wp-content/uploads/2025/02/William-IV-Exterior.jpg",
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
            "image_url": "https://www.beautifulenglandphotos.uk/wp-content/uploads/2015/09/background-gomshall-mill-gomshall-4.jpg",
        },
    ]
}


# Places of interest — keyed by estate slug
PLACES_OF_INTEREST = {
    "hever-castle": [
        {
            "slug": "castle-interior",
            "name": "Hever Castle Interior",
            "type": "Historic Castle",
            "summary": "The heart of any visit to Hever, the castle interior is a sequence of panelled rooms whose walls tell six centuries of English history. The Long Gallery is lined with Tudor portraits — regarded by many as the finest collection outside the National Portrait Gallery — and Anne Boleyn's own prayer books, bearing her handwritten inscriptions and signatures, are displayed under glass in her former bedroom. The wood-panelled Great Hall, the tapestried state rooms and the roaring inglenook fireplaces create an atmosphere of genuine antiquity. Audio guides in six languages are included with the castle ticket.",
            "image_url": "",
        },
        {
            "slug": "italian-garden",
            "name": "The Italian Garden",
            "type": "Historic Garden",
            "summary": "One of the finest Edwardian gardens in Britain, created between 1904 and 1908 by American millionaire William Waldorf Astor to display his extraordinary collection of ancient Greek and Roman statuary. The Pompeiian Wall — 160 metres of colonnaded stonework flanked by ancient marble — is the centrepiece, but the grottoes, cascades, fountains, and geometric bedding extending to the loggia at the lake's edge are equally remarkable. Over eight hundred men worked for two years on the project; the result has mellowed beautifully in the century since.",
            "image_url": "",
        },
        {
            "slug": "hever-yew-maze",
            "name": "The Yew Maze",
            "type": "Historic Garden Feature",
            "summary": "Planted in 1904 using more than a thousand yew trees imported from the Netherlands, the Yew Maze at Hever covers 6,400 square feet with hedges standing eight feet tall. It was created by William Waldorf Astor as a garden ornament and entertainment feature, and remains one of the finest traditional yew mazes in England. Finding the central platform from which you can see over the whole maze is the challenge — and rather more difficult than it looks. Open from April to October, weather permitting.",
            "image_url": "",
        },
        {
            "slug": "ksy-military-museum",
            "name": "KSY Military Museum",
            "type": "Museum",
            "summary": "Housed in a purpose-built space designed to resemble a military operations tent, the Kent and Sharpshooters Yeomanry Museum traces the regiment from 1794 to the present day through imaginative, interactive displays. Highlights include a reconstructed World War One trench with sound effects and a World War Two Cromwell tank turret visitors can climb into. A Saladin armoured car and 25-pounder field gun stand outside. Four touch screens tell the personal stories of individual soldiers through video clips and first-hand accounts. Allow 30 minutes.",
            "image_url": "",
        },
        {
            "slug": "miniature-model-houses",
            "name": "Miniature Model Houses",
            "type": "Exhibition",
            "summary": "A unique permanent exhibition of 1/12 scale model houses commissioned from master miniaturist John J. Hodgson, illustrating the development of English country houses from Domesday England through Tudor, Stuart, Georgian and Victorian periods. The craftsmanship is extraordinary — tiny figures carry out period-appropriate daily tasks, furniture is accurately reproduced to the nearest millimetre, and the sequence of houses charts changing architectural fashions with scholarly precision. Accessed via the Hever Shop; allow half an hour.",
            "image_url": "",
        },
        {
            "slug": "st-peter-hever",
            "name": "St Peter's Church, Hever",
            "type": "Medieval Church",
            "summary": "The small medieval church beside the castle contains one of the great treasures of Kentish heritage: the magnificent brass memorial to Sir Thomas Boleyn, Earl of Wiltshire, Anne's father, who died in 1539. The brass shows Sir Thomas in his robes as a Knight of the Garter and is one of the finest Tudor brasses in England. The church itself dates from the 13th century and has a pleasing simplicity — dark, cool and quiet, with good stained glass and an atmosphere of genuine age. Free to enter.",
            "image_url": "",
        },
    ],
    "penshurst-place": [
        {
            "slug": "barons-hall",
            "name": "The Baron's Hall",
            "type": "Medieval Architecture",
            "summary": "Completed in 1341 for Sir John de Pulteney, four-time Lord Mayor of London, the Baron's Hall is one of the most complete surviving examples of 14th-century domestic architecture in England. Its magnificent chestnut roof, arcaded Gothic windows, unique octagonal central hearth and original Minstrel's Gallery have remained largely unchanged for nearly 700 years. Extraordinarily, the family portraits and antique furniture within have been accumulating here continuously since the Sidney family took ownership in 1552. Standing in this space on a winter afternoon, with the light coming through the lancet windows, is an experience that puts centuries into perspective.",
            "image_url": "",
        },
        {
            "slug": "state-rooms",
            "name": "State Rooms",
            "type": "Historic Interior",
            "summary": "Beyond the Baron's Hall, a sequence of State Rooms spans four centuries of addition and refinement: the intimate West Solar with its porcelain and family portraits; the Queen Elizabeth Room, named for the monarch who visited regularly; the Tapestry Room with its woven wall hangings; and the Long Gallery of 1599 — a magnificent Elizabethan corridor hung with royal portraits and displaying replica Tudor costumes. The recently opened Victorian Kitchen gives an insight into 19th-century domestic life below stairs. The Nether Gallery contains historic arms and armour, including Sir Philip Sidney's funeral helm, carried at his state funeral in 1587.",
            "image_url": "",
        },
        {
            "slug": "walled-gardens",
            "name": "The Walled Gardens",
            "type": "Historic Garden",
            "summary": "Eleven acres of formal walled garden, divided into distinct 'rooms' by over a mile of ancient yew hedging, make Penshurst's gardens one of the most celebrated in England. Each enclosure has its own character: the formal rose garden with over 5,000 roses including rare climbers and ramblers; the peony border in May; the magnificent spring tulip display; the magnolia garden; ponds and topiary throughout. The RHS has recognised the gardens as one of the finest in the country, and the National Gardens Scheme features them annually. The combination of medieval layout and Victorian and Edwardian planting creates an experience without close parallel.",
            "image_url": "",
        },
        {
            "slug": "toy-museum",
            "name": "The Toy Museum",
            "type": "Museum",
            "summary": "Housed in a handsome Gothic-style stable wing of 1836, the Penshurst Toy Museum contains around 2,000 artefacts spanning from the Georgian period to the 1980s, including dolls' houses and their furniture, Pollock's toy theatres, mechanical toys, rocking horses, storybooks and games. A £100,000 National Lottery Heritage Fund grant funded a stunning 2025 refurbishment with four themed zones, enhanced accessibility and new interactive areas for younger visitors. The collection traces several generations of the Sidney family's childhood — making it a personal as well as a historical exhibit.",
            "image_url": "",
        },
        {
            "slug": "penshurst-village",
            "name": "Penshurst Village",
            "type": "Historic Village",
            "summary": "The village surrounding Penshurst Place is itself a place of considerable historic interest. The church of St John the Baptist contains an exceptional collection of Sidney family monuments spanning four centuries, including fine Elizabethan brasses and the large marble tomb of Sir William Sidney. The Leicester Arms dates from the 16th century and remains one of the finest pubs in Kent. The village's stone and timber-framed buildings have changed little in two centuries, and the view from the churchyard up to the manor is one of the most evocative in the Weald.",
            "image_url": "",
        },
        {
            "slug": "film-locations",
            "name": "Film & TV Locations",
            "type": "Cultural Heritage",
            "summary": "Penshurst Place's medieval authenticity has made it a first-choice filming location for decades. Productions shot here include the 1969 film Anne of the Thousand Days; the BBC's 1971 Elizabeth R series; The Princess Bride (1987); The Other Boleyn Girl (2008); the BBC's long-running Merlin series; The Hollow Crown (2012); and Wolf Hall (2015). The Baron's Hall, in particular, has doubled for every conceivable period setting. Visiting with this context in mind adds a pleasing extra dimension — the hall you are standing in is the hall where Natalie Portman and Scarlett Johansson shot key scenes, and it looked exactly the same.",
            "image_url": "",
        },
    ],
    "shere-manor-estate": [
        {
            "slug": "st-james-church",
            "name": "St James' Church",
            "type": "Church",
            "distance": "2 min walk",
            "coords": [51.21668, -0.44418],
            "summary": "One of the finest Norman churches in Surrey, with origins dating to around 1190. The square flint tower is a local landmark and the interior contains a 13th-century font, remarkable medieval stained glass, and the anchorite's cell of Christine Carpenter — a woman who in 1329 had herself voluntarily enclosed within a small chamber in the north wall to live a life of prayer, able to see the altar only through a tiny window. Her story has fascinated visitors for centuries.",
            "image_url": "/static/images/lychgate.jpg",
        },
        {
            "slug": "the-holiday-film",
            "name": "The Holiday Film Location",
            "type": "Film Location",
            "distance": "2 min walk",
            "coords": [51.21640, -0.44490],
            "summary": "Shere village was the principal English location for the 2006 romantic comedy The Holiday, starring Cameron Diaz, Kate Winslet, Jude Law and Jack Black. The production built a purpose-designed cottage set in the village, and many scenes were filmed on and around Middle Street. The village is instantly recognisable to fans of the film, and it remains one of the most popular reasons people visit Shere for the first time.",
            "image_url": "/static/images/village-overview.jpg",
        },
        {
            "slug": "shere-village-hall",
            "name": "Shere Village Hall",
            "type": "Community",
            "distance": "4 min walk",
            "coords": [51.21580, -0.44480],
            "summary": "The village hall is the beating heart of community life in Shere, hosting everything from farmers' markets and craft fairs to theatrical productions and fitness classes. Built in the 1930s, the building retains much of its original character. The programme of events is posted on the noticeboard outside — if there is something on during your visit, it is usually well worth attending.",
            "image_url": "/static/images/shere-hall.jpg",
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
            "image_url": "https://media-cdn.tripadvisor.com/media/photo-p/14/c4/88/b6/the-exterior.jpg",
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
    "hever-castle": [
        {
            "slug": "tudor-towers",
            "name": "Tudor Towers Adventure Playground",
            "type": "Outdoor Play",
            "distance": "on estate",
            "coords": [51.1918, 0.1128],
            "summary": "The centrepiece of Hever's family offer — a magnificent nine-metre-tall wooden play castle bigger than a four-bedroom house, complete with its own moat, drawbridge, two slides, an underground tunnel and three turrets to climb. Children up to the age of 14 can run free across the enclosed wooden playground with climbing frames, swings and an aerial runway. It is genuinely impressive in scale and design, and most children consider it the highlight of the day.",
            "image_url": "",
        },
        {
            "slug": "acorn-dell",
            "name": "Acorn Dell Natural Play Area",
            "type": "Natural Play",
            "distance": "on estate",
            "coords": [51.1920, 0.1133],
            "summary": "Designed specifically for toddlers and children up to seven years old, Acorn Dell is a natural play area where younger children can explore freely and use their imagination in a safe, enclosed environment. Features include a two-metre-high willow structure — one of the most popular things in the grounds for small children — alongside a giant sandpit, log tunnels, and gentle climbing features. The materials are all natural and the setting is shaded and pleasant even in summer.",
            "image_url": "",
        },
        {
            "slug": "water-maze",
            "name": "The Water Maze",
            "type": "Interactive Activity",
            "distance": "on estate",
            "coords": [51.1922, 0.1145],
            "summary": "One of Hever's most beloved and unpredictable attractions. The Water Maze on Sixteen Acre Island is a series of concentric stepping stone walkways over water, and the object is to reach the centre without getting wet. This sounds straightforward until the stepping stones tilt underfoot and hidden jets spring into action to drench anyone who triggers them. Spare clothes are not just advisable — they are practically mandatory. Immensely good fun, and children will want to go round multiple times.",
            "image_url": "",
        },
        {
            "slug": "yew-maze",
            "name": "The Yew Maze",
            "type": "Outdoor Activity",
            "distance": "on estate",
            "coords": [51.1927, 0.1105],
            "summary": "More sedate than the Water Maze but no less satisfying, Hever's Yew Maze was planted in 1904 using over a thousand yew trees from the Netherlands. The hedges stand eight feet tall, meaning even adults cannot easily navigate by sight — and for children, the sense of genuine disorientation as familiar landmarks disappear behind green walls is absolutely delightful. The central platform from which you can look out over the whole maze is the goal; reaching it typically takes longer than expected. Open April to October.",
            "image_url": "",
        },
        {
            "slug": "boating-lake",
            "name": "Boating on the Lake",
            "type": "Water Activity",
            "distance": "on estate",
            "coords": [51.1920, 0.1148],
            "summary": "During school holidays, rowing boats and pedal boats are available for hire on Hever's magnificent 38-acre lake. Exploring the lake by water gives a completely different perspective on the castle, the Italian Garden and the Japanese Tea House — views that are simply not available from land. Kingfishers, herons and great crested grebes are regularly spotted from the boats. Available daily during school holidays from 11am to 4pm; additional charge applies.",
            "image_url": "",
        },
        {
            "slug": "archery",
            "name": "Try Archery",
            "type": "Active Experience",
            "distance": "on estate",
            "coords": [51.1928, 0.1118],
            "summary": "Available during school holidays as a separate-charge activity, Hever's archery experience gives visitors of all ages the chance to try the ancient sport under qualified supervision. Children take to it particularly well — the combination of focus, physical effort and immediate visual feedback makes it enormously satisfying. Minimum height and age restrictions apply; check with the Hever team on the day for current session times.",
            "image_url": "",
        },
        {
            "slug": "castle-trail",
            "name": "Children's Castle Trail",
            "type": "Educational Activity",
            "distance": "on estate",
            "coords": [51.1931, 0.1108],
            "summary": "The children's interactive audio guide — included with a Castle & Gardens ticket — takes younger visitors on a specially designed trail through the castle interior, with puzzles, questions and stories that bring Tudor history to life in an engaging way. Downloadable activity trails are also available before your visit: a Tudor History Trail for the castle, a Roman Trail for the Italian Garden, a Lake Walk Nature Trail, and both KS1 and KS2 Maths Trails for the grounds. Excellent for school-age children.",
            "image_url": "",
        },
    ],
    "penshurst-place": [
        {
            "slug": "adventure-playground",
            "name": "Adventure Playground",
            "type": "Outdoor Play",
            "distance": "on estate",
            "coords": [51.1772, 0.1758],
            "summary": "Penshurst's adventure playground is one of the best in Kent — a proper, ambitious outdoor play space featuring a commando trail, a wooden high top, enormous slide, swings, a dedicated toddler area, and a 30-metre zipline that children queue to go on repeatedly. The adjacent medieval-style fort adds an atmospheric element, and the rolling grassed slopes around the playground provide plenty of room to run between apparatus. Season ticket holders have exclusive winter weekend access when weather allows.",
            "image_url": "",
        },
        {
            "slug": "toy-museum-kids",
            "name": "Toy Museum",
            "type": "Museum",
            "distance": "on estate",
            "coords": [51.1768, 0.1742],
            "summary": "Following its stunning 2025 refurbishment — funded by a £100,000 National Lottery Heritage Fund grant — the Penshurst Toy Museum is better than ever. Four themed zones take children and adults through nearly three centuries of British toy-making, from Georgian wooden toys and Victorian mechanical curiosities to mid-20th-century favourites. The interactive activities area, dedicated children's trail and special exhibition space make this far more engaging than a conventional display. An automated 1920s Drinking Bear from a Parisian maker is the conversation-starter.",
            "image_url": "",
        },
        {
            "slug": "woodland-trail",
            "name": "Woodland Trail",
            "type": "Outdoor Activity",
            "distance": "on estate",
            "coords": [51.1780, 0.1795],
            "summary": "The Woodland Trail winds through the estate's managed arboretum and ancient woodland, incorporating natural play features created by the gardening team — log tunnels, stepping posts, den-making areas and quiet clearings. A wildlife-spotting trail runs throughout, and the paths are wide enough for pushchairs in dry conditions. New pathways were added in recent winters, expanding the route options and revealing corners of the woodland that most visitors never find. Perfect for children who prefer exploring to sitting still.",
            "image_url": "",
        },
        {
            "slug": "maize-maze",
            "name": "The Maize Maze",
            "type": "Outdoor Activity",
            "distance": "on estate",
            "coords": [51.1752, 0.1748],
            "summary": "Available through the summer school holidays, the Penshurst Maize Maze is cut fresh each year into a new design, typically incorporating a theme related to the estate's history or the season's events. The scale is genuinely impressive — the paths run through mature maize standing well above adult head height, and finding your way through requires proper navigation rather than just following the crowd. Great fun for families with children of primary-school age upward.",
            "image_url": "",
        },
        {
            "slug": "falconry-displays",
            "name": "Falconry Displays",
            "type": "Live Experience",
            "distance": "on estate",
            "coords": [51.1760, 0.1735],
            "summary": "On selected summer weekends, professional falconers bring birds of prey to Penshurst for flying demonstrations that are among the most popular events on the estate calendar. Watching a harris hawk or peregrine falcon respond to the falconer's signals, flying free across the parkland before returning to the glove, is genuinely extraordinary — and for children who have never seen it before, an experience they tend to talk about for some time. Check the estate's event calendar for 2026 flying dates.",
            "image_url": "",
        },
        {
            "slug": "craft-workshops",
            "name": "Craft Workshops",
            "type": "Educational Activity",
            "distance": "on estate",
            "coords": [51.1763, 0.1730],
            "summary": "During school holiday periods, the Old Coach House opens for drop-in children's craft workshops on Tuesday and Thursday afternoons. Children can try a range of heritage-inspired activities — from making Tudor-style shields to seasonal crafts related to the estate's gardens and history — and take their creations home. Storytelling events, including popular Alice in Wonderland performances on summer Sundays, add further variety to what Penshurst offers the younger visitor. Included within general admission pricing.",
            "image_url": "",
        },
    ],
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
            "image_url": "/static/images/feed-ducks.jpg",
        },
        {
            "slug": "river-paddling",
            "name": "River Paddling & Crayfish",
            "type": "Outdoor Activity",
            "distance": "5 min walk",
            "coords": [51.21620, -0.44380],
            "summary": "The park between the churchyard and the lido is the best spot in the village for paddling in the Tillingbourne. The water is crystal clear, cold and shallow — perfect for children to wade and explore. If you have a small hand net and patience, you stand a good chance of catching American signal crayfish under the stones. They are an invasive species, so there is no limit and no licence required. Just put them back when you are done.",
            "image_url": "/static/images/tillingbourne-bridge.jpg",
        },
        {
            "slug": "stepping-stones",
            "name": "The Stepping Stones",
            "type": "Outdoor Activity",
            "distance": "3 min walk",
            "coords": [51.21640, -0.44460],
            "summary": "The stepping stones across the Tillingbourne ford are one of the most fun features of the village for younger children. The ford is shallow and the stones are broad and stable, though they can be slippery — wellies or water shoes recommended. On busy summer weekends a small informal queue forms, and there is a good-natured atmosphere as families help each other across. The water is gin-clear and you can often spot brown trout hovering in the current.",
            "image_url": "https://upload.wikimedia.org/wikipedia/commons/9/96/Ford_at_Rectory_Lane%2C_Shere_%28March_2014%29_%281%29.jpg",
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
            "image_url": "https://shererec.org/wp-content/uploads/2024/10/shere-rec-pavilion-e1729580779341.jpg",
        },
        {
            "slug": "shere-museum",
            "name": "Shere Museum",
            "type": "Museum",
            "distance": "4 min walk",
            "coords": [51.21650, -0.44500],
            "summary": "A small, free museum telling the story of Shere from prehistoric times to the present. Children enjoy the exhibits on the old water mills that once lined the Tillingbourne, the Roman road that ran through the valley, and the various film productions that have used the village as a location. Open on weekend afternoons and most Bank Holidays. Admission is free.",
            "image_url": "https://media-cdn.tripadvisor.com/media/photo-p/14/c4/88/b6/the-exterior.jpg",
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
    "hever-castle": [
        {
            "slug": "hever-castle-shop",
            "name": "Hever Castle Shop",
            "type": "Heritage Gift Shop",
            "distance": "on estate",
            "coords": [51.1931, 0.1112],
            "hours": "Open daily with grounds (last exit 15 min before closing)",
            "website": "https://shop.hevercastle.co.uk",
            "description": "The main estate shop stocks a carefully chosen range of gifts, homeware and local produce inspired by the castle and its gardens. The Anne Boleyn collection — based on the illustrated borders of her prayer book on display in the castle — includes china cups and saucers, mugs, jugs, dinner plates and teapots. The Book of Hours range, the castle bauble collection and the B Necklace are unique to Hever and consistently popular. Local Kent produce lines the shelves alongside — preserves, chutneys, chocolates and seasonal specialities. The online shop carries a good selection for those who cannot visit in person.",
            "image_url": "",
        },
        {
            "slug": "hever-courtyard-shop",
            "name": "Courtyard Shop",
            "type": "Garden & Seasonal Shop",
            "distance": "on estate",
            "coords": [51.1929, 0.1115],
            "hours": "Seasonal — ask at Information Centre",
            "website": "https://www.hevercastle.co.uk/shop/",
            "description": "Located near the Guthrie Pavilion, the Courtyard Shop focuses on seasonal gardening products, kitchenware, and plants grown or selected to reflect the estate's own gardens. In spring the planted selections mirror the bulbs and perennials coming into flower in the Italian Garden; in autumn it carries a range of preserving equipment and seasonal produce. A good choice for gardeners looking for something connected to the landscape around them.",
            "image_url": "",
        },
        {
            "slug": "hever-golf-shop",
            "name": "Hever Golf Shop",
            "type": "Golf & Sport",
            "distance": "10 min walk",
            "coords": [51.1908, 0.1072],
            "hours": "Daily, standard retail hours (call 01732 701008)",
            "website": "https://www.hevercastle.co.uk/golf/",
            "description": "The professional shop at Hever Castle Golf & Wellbeing stocks an extensive range of equipment, clothing and accessories from the leading golf brands, alongside Hever-branded items not available in the main castle shop. Equipment hire and tuition booking are also handled here. The 27-hole course is open to non-members and green fees are available to book online — an excellent option if you are combining a golf trip with a castle visit.",
            "image_url": "",
        },
        {
            "slug": "king-henry-inn-shop",
            "name": "The King Henry VIII Inn",
            "type": "Pub & Local Goods",
            "distance": "5 min walk",
            "coords": [51.1938, 0.1103],
            "hours": "Mon–Sat 12:00–23:30, Sun 12:00–22:00",
            "website": "https://thehenryhever.co.uk",
            "description": "The 17th-century inn opposite the castle entrance carries a small but well-chosen range of local ales and spirits that make excellent souvenirs of a day at Hever. Shepherd Neame beers — brewed in Faversham, Kent's oldest brewery — are a house speciality, and the inn frequently stocks limited seasonal bottles and seasonal merchandise. It is less a gift shop than an opportunity to take a piece of the local brewing tradition home.",
            "image_url": "",
        },
    ],
    "penshurst-place": [
        {
            "slug": "penshurst-gift-shop",
            "name": "Penshurst Place Gift Shop",
            "type": "Heritage Gift Shop",
            "distance": "on estate",
            "coords": [51.1763, 0.1726],
            "hours": "Daily 9:00–17:00 (year-round)",
            "website": "https://www.penshurstplace.com/explore/eatshop/gift-shop",
            "description": "Housed in a beautifully converted 19th-century barn beside the visitor entrance, the Penshurst Gift Shop operates year-round as a genuine boutique rather than a souvenir stand. The range spans Jellycat plush toys (one of the finest selections in the county), Wrendale Designs homeware, artisan candles and skincare, local Kentish specialities, clothing accessories including printed scarves and blankets, and a thoughtfully curated selection of books — Kent walking guides, heritage titles and children's literature. In November and December the shop transforms entirely into a Christmas wonderland, with locally produced food hampers, handmade wreaths and estate-grown mistletoe.",
            "image_url": "",
        },
        {
            "slug": "penshurst-plant-centre",
            "name": "Plant Centre",
            "type": "Garden Centre",
            "distance": "on estate",
            "coords": [51.1762, 0.1724],
            "hours": "Daily 9:00–17:00 (year-round)",
            "website": "https://www.penshurstplace.com/explore/eatshop",
            "description": "Directly outside the Gift Shop, the Penshurst Plant Centre carries a seasonal range of flowering plants, bulbs, herbs and perennials selected to reflect what is growing in the walled gardens at any given time. Planters, pots, garden accessories and gifts complement the plant stock. In autumn the centre stocks an excellent range of spring-flowering bulbs — a good way to take a piece of Penshurst's celebrated garden home with you. All stock is personally selected by the estate's gardening team.",
            "image_url": "",
        },
        {
            "slug": "forge-stores-penshurst",
            "name": "Forge Stores",
            "type": "Village Shop",
            "distance": "5 min walk",
            "coords": [51.1756, 0.1698],
            "hours": "Mon–Sat 8:00–18:00, Sun 9:00–13:00",
            "website": "",
            "description": "The village shop in Penshurst, a genuine community store rather than a visitor-facing operation, stocks household goods, groceries, seasonal produce and a small but well-chosen selection of local Kentish goods. Local cheeses, honeys, preserves and cold meats make ideal picnic provisions, and the shop is the best place to assemble a picnic basket before entering the estate. The staff know the village and estate intimately and are a useful source of local knowledge.",
            "image_url": "",
        },
        {
            "slug": "adventure-playground-kiosk",
            "name": "Adventure Playground Kiosk",
            "type": "Refreshment Kiosk",
            "distance": "on estate",
            "coords": [51.1772, 0.1758],
            "hours": "School holidays & weekends only",
            "website": "https://www.penshurstplace.com/explore/play/adventure-playground",
            "description": "The small seasonal kiosk adjacent to the Adventure Playground offers takeaway hot and cold drinks, ice creams and light snacks during school holidays and weekend peak periods. It occupies a prime position for parents watching children on the playground and zipline. In summer it also carries a small range of branded Penshurst souvenirs and children's activity books. Opening is weather-dependent — the kiosk closes if the playground closes.",
            "image_url": "",
        },
    ],
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
            "image_url": "https://s0.geograph.org.uk/geophotos/08/23/41/8234185_8802425b.jpg",
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
            "image_url": "/static/images/split-figs.jpg",
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
            "slug": "shere-museum-shop",
            "name": "Shere Museum",
            "type": "Museum & Gift Shop",
            "distance": "2 min walk",
            "coords": [51.21640, -0.44460],
            "hours": "",
            "website": "https://www.sheremuseum.co.uk",
            "description": "Shere's small but absorbing local museum on Gomshall Lane tells the story of the village from its earliest history to the present day. The gift shop sells books, prints, and locally produced items, with all proceeds going directly back to the museum. Well worth a visit — and completely free to enter.",
            "image_url": "https://media-cdn.tripadvisor.com/media/photo-p/14/c4/88/b6/the-exterior.jpg",
        },
    ]
}


# ── Arundel Castle & Denbies Wine Estate ─────────────────────────────────────
# Walk data appended after initial dict definition

WALKS["arundel-castle"] = [
    {
        "slug": "river-arun-town-loop",
        "title": "River Arun Town Loop",
        "distance": "4.5 km",
        "duration": "1 hr 15 min",
        "difficulty": "Easy",
        "summary": "A gentle circuit from the castle gates along the western bank of the River Arun, returning through the historic town centre past the Cathedral.",
        "image_url": "",
        "center": [50.8550, -0.5510],
        "zoom": 14,
        "waypoint_zoom": 16,
        "route": [
            [50.8561, -0.5510], [50.8548, -0.5520], [50.8535, -0.5530],
            [50.8520, -0.5525], [50.8508, -0.5512], [50.8500, -0.5495],
            [50.8498, -0.5475], [50.8505, -0.5460], [50.8515, -0.5450],
            [50.8528, -0.5448], [50.8540, -0.5458], [50.8548, -0.5478],
            [50.8556, -0.5492], [50.8561, -0.5510],
        ],
        "waypoint_coords": [
            [50.8561, -0.5510], [50.8510, -0.5520], [50.8500, -0.5470], [50.8540, -0.5460],
        ],
        "waypoints": [
            {
                "title": "Arundel Castle Gates",
                "description": [
                    "Begin at the main castle gates on High Street, where the towering flint walls of Arundel Castle rise above you. The castle has occupied this strategic position above the River Arun since William the Conqueror's time, and the view from the gate — west across the rooftops and the water meadows beyond — has changed little in centuries. The gatehouse ahead dates from the 18th century, though its foundations are considerably older.",
                    "Head downhill on Mill Road and follow the signed riverside path as it bears left onto the western bank of the Arun. The river here is tidal, and the quality of light on the water changes dramatically between high and low tide — arrive at high tide and the water laps against the reedy margins; at low tide a wide swathe of gleaming mud is revealed, beloved by curlews and redshanks.",
                ],
                "image_url": "",
            },
            {
                "title": "The Black Rabbit Riverside",
                "description": [
                    "The path follows the riverbank south, passing through the water meadows that form the floodplain of the Arun. This stretch is one of the finest bird-watching spots in West Sussex — look for little egrets hunting in the shallows, flocks of lapwing in winter, and the occasional flash of blue that signals a kingfisher. The flat, open landscape makes sightings easy once you know what to look for.",
                    "After roughly 1.5 km the path reaches the hamlet of South Stoke, where The Black Rabbit pub sits directly on the riverbank with one of the most photographed views in the county — Arundel Castle reflected in the water. The pub takes its name from the white rabbits once bred on the nearby chalk downs. It is a perfect halfway stop for a drink and that view.",
                ],
                "image_url": "",
            },
            {
                "title": "WWT Wetland Edge",
                "description": [
                    "Crossing back north via the footbridge, the path skirts the southern edge of the WWT Arundel Wetland Centre — 65 acres of managed reedbed, open water, and fen. Even from outside the habitat is extraordinary: reed warblers churr in the summer, marsh harriers quarter the reedbeds in slow, buoyant flight, and in winter bitterns lurk invisibly among the stems. If you have time, a detour into the centre itself is strongly recommended.",
                    "The path continues north alongside the reed margin before climbing gently back into the town. Watch your footing on the boardwalk sections after wet weather — they can be slippery but are generally well maintained.",
                ],
                "image_url": "",
            },
            {
                "title": "Arundel Cathedral",
                "description": [
                    "The return route brings you through the upper town past the Cathedral Church of Our Lady and St Philip Howard, whose Gothic spire is visible for miles across the Arun valley. Built between 1869 and 1873 by the 15th Duke of Norfolk to designs by Joseph Hansom — the man who invented the hansom cab — it is one of the finest Victorian Gothic churches in England.",
                    "Step inside if the doors are open: the vaulted nave is magnificent and the stained glass spectacular, particularly in morning light. The shrine of St Philip Howard, a Catholic martyr executed in 1595, is in the south transept. From the cathedral, it is a three-minute walk back down High Street to the castle gates to complete the circuit.",
                ],
                "image_url": "",
            },
        ],
    },
    {
        "slug": "arundel-park-hiorne-tower",
        "title": "Arundel Park & Hiorne Tower",
        "distance": "7 km",
        "duration": "2 hrs",
        "difficulty": "Moderate",
        "summary": "A rewarding circuit through the castle's private parkland to Hiorne Tower — a Georgian folly on the ridge with sweeping views across the South Downs.",
        "image_url": "",
        "center": [50.8590, -0.5450],
        "zoom": 13,
        "waypoint_zoom": 15,
        "route": [
            [50.8561, -0.5510], [50.8570, -0.5490], [50.8580, -0.5470],
            [50.8595, -0.5450], [50.8610, -0.5430], [50.8625, -0.5410],
            [50.8640, -0.5395], [50.8648, -0.5390], [50.8640, -0.5370],
            [50.8620, -0.5360], [50.8600, -0.5375], [50.8580, -0.5400],
            [50.8565, -0.5450], [50.8561, -0.5510],
        ],
        "waypoint_coords": [
            [50.8561, -0.5510], [50.8610, -0.5435], [50.8648, -0.5390], [50.8580, -0.5400],
        ],
        "waypoints": [
            {
                "title": "Castle Grounds Entry",
                "description": [
                    "The walk enters Arundel Park through the Norfolk Gates at the northern end of the castle complex. This 1,100-acre swath of chalk downland, ancient woodland and parkland has been in the possession of the Dukes of Norfolk since the 16th century and is open to the public on foot throughout the year — a remarkable privilege given its scale and beauty.",
                    "The path climbs steadily north through open grassland managed for wildflowers. In summer the chalk turf is thick with orchids, marbled white butterflies and the hum of bees working through knapweed and scabious. The gradient is moderate but sustained — take your time and turn back regularly for increasingly impressive views over the town and the castle roofline.",
                ],
                "image_url": "",
            },
            {
                "title": "Open Downland Ridge",
                "description": [
                    "The ridge offers a panoramic view across the coastal plain to the sea on a clear day, with the Arun valley laid out below and the dark mass of the South Downs stretching east and west. The park here is grazed by a herd of fallow deer — one of the oldest managed herds in England — and encounters are common if you walk quietly.",
                    "The chalk grassland on the ridge is a Site of Special Scientific Interest and among the most species-rich habitats in West Sussex. Look down into the turf and you will find at least 30 different plant species per square metre in the best areas. The estate's conservation team manages it through light grazing to prevent the scrub encroachment that would otherwise overtake it within a decade.",
                ],
                "image_url": "",
            },
            {
                "title": "Hiorne Tower",
                "description": [
                    "Hiorne Tower stands on a high point of the park ridge and is visible from much of the Arun valley. Built in 1787 by Francis Hiorne as a Gothic Revival folly, it was erected in the hope of gaining favour with the 11th Duke of Norfolk, who was remodelling the castle at the time. The duke was reportedly unimpressed, but the tower has stood for over 230 years and its silhouette is one of the defining landmarks of the Arundel skyline.",
                    "The tower itself is not open to the public, but the views from the surrounding ground are excellent in all directions. Sit here for a few minutes and you will likely see red kites circling overhead — they were reintroduced to West Sussex in 2005 and have thrived in the Arun valley.",
                ],
                "image_url": "",
            },
            {
                "title": "Swanbourne Lake",
                "description": [
                    "The descent from the ridge brings you to the shore of Swanbourne Lake, a tranquil millpond enclosed by wooded hillsides that has been a focal point of the park since the 18th century. Rowing boats and pedalos are available for hire in the summer months, and the café on the eastern shore serves hot drinks and light snacks.",
                    "The lake is home to a large colony of swans alongside grebes, coots, tufted duck and a resident heron. Ducks come very close to the path — seed purchased from the kiosk is welcome but please avoid bread. The woodland path back to the castle gates runs along the western shore and is shaded even in the height of summer.",
                ],
                "image_url": "",
            },
        ],
    },
    {
        "slug": "arundel-to-amberley",
        "title": "Arundel to Amberley",
        "distance": "11 km",
        "duration": "3 hrs",
        "difficulty": "Moderate",
        "summary": "A linear walk following the River Arun north through the South Downs National Park to the ancient village of Amberley — best done one way with a train back.",
        "image_url": "",
        "center": [50.8680, -0.5470],
        "zoom": 12,
        "waypoint_zoom": 14,
        "route": [
            [50.8561, -0.5510], [50.8560, -0.5530], [50.8545, -0.5538],
            [50.8530, -0.5540], [50.8600, -0.5520], [50.8640, -0.5510],
            [50.8680, -0.5490], [50.8720, -0.5470], [50.8760, -0.5455],
            [50.8800, -0.5440], [50.8840, -0.5430], [50.8878, -0.5415],
        ],
        "waypoint_coords": [
            [50.8561, -0.5510], [50.8600, -0.5525], [50.8760, -0.5455], [50.8878, -0.5415],
        ],
        "waypoints": [
            {
                "title": "Arundel Town Quay",
                "description": [
                    "The walk begins at Arundel's old town quay, where the River Arun is wide and tidal. The quay was once one of the busiest ports on the Sussex coast, trading coal, timber and Caen stone — the limestone brought from Normandy to build the castle. Mooring rings set into the old stone walls are the last remnants of this seafaring past.",
                    "Head north along the river's western bank, following the South Downs Way signs. The path is flat and well-maintained for the first two kilometres as it passes through the water meadows below the castle. The castle towers above on the right; to the left, the broad water meadows stretch away to the reed-fringed margins of the WWT reserve.",
                ],
                "image_url": "",
            },
            {
                "title": "The South Downs National Park",
                "description": [
                    "Beyond the WWT reserve the path enters the South Downs National Park proper, where the landscape changes character. The valley narrows and the flanking chalk ridges press closer, with the river looping through an increasingly wild corridor of alder carr, willow and reed. The birdsong can be remarkable in spring — sedge warblers, reed buntings and the booming call of a bittern have all been recorded here.",
                    "Keep the river on your right throughout this section. At Houghton, roughly halfway, there is a small car park and a track up to the village if you need to cut the walk short. The village has a 17th-century pub — The George and Dragon — that does good food.",
                ],
                "image_url": "",
            },
            {
                "title": "Amberley Wild Brooks",
                "description": [
                    "Amberley Wild Brooks is a 350-hectare wetland complex and one of the most important inland wetlands in southern England. In winter it floods to form a vast shallow lake that attracts thousands of wildfowl: wigeon, teal, lapwing and golden plover in numbers rarely seen elsewhere in Sussex. In summer the damp meadows fill with ragged robin, yellow flag iris, and marsh orchids.",
                    "The final approach to Amberley follows a raised causeway across the brooks, with wide views in every direction. The white chalk face of the quarry above the village comes into view as you approach, and the church tower appears above the roofline of this remarkable, almost medieval village.",
                ],
                "image_url": "",
            },
            {
                "title": "Amberley Village & Station",
                "description": [
                    "Amberley village is one of the most beautiful in Sussex — chalk cottages, a Norman church, a ruined medieval castle, and lanes that have barely changed since the 18th century. Take time to explore before heading to the station: the Church of St Michael has extraordinary Norman carvings and a genuine sense of ancient calm.",
                    "Amberley Station is a 10-minute walk from the village centre on the Arun Valley Line, with regular services back to Arundel (approximately 10 minutes by train). Check times before you set out — services are roughly hourly. The train gives an excellent view of the valley route you have just walked.",
                ],
                "image_url": "",
            },
        ],
    },
    {
        "slug": "swanbourne-lake-circuit",
        "title": "Swanbourne Lake & Woodland",
        "distance": "3 km",
        "duration": "50 min",
        "difficulty": "Easy",
        "summary": "A short, family-friendly loop around Swanbourne Lake through castle woodland, with boat hire, café and spectacular castle views throughout.",
        "image_url": "",
        "center": [50.8590, -0.5480],
        "zoom": 15,
        "waypoint_zoom": 16,
        "route": [
            [50.8561, -0.5510], [50.8565, -0.5500], [50.8575, -0.5490],
            [50.8585, -0.5485], [50.8595, -0.5480], [50.8600, -0.5470],
            [50.8595, -0.5460], [50.8580, -0.5458], [50.8570, -0.5465],
            [50.8560, -0.5475], [50.8555, -0.5490], [50.8561, -0.5510],
        ],
        "waypoint_coords": [
            [50.8561, -0.5510], [50.8595, -0.5483], [50.8600, -0.5467], [50.8560, -0.5475],
        ],
        "waypoints": [
            {
                "title": "Mill Road Start",
                "description": [
                    "Begin at the foot of Mill Road where the path enters the park via a wooden kissing gate. This is one of Arundel's most popular family walks and is suitable for pushchairs on the main lake path, though the woodland loop on the return is more uneven. The route is signed throughout and almost impossible to get lost.",
                    "The path drops down through mixed woodland before the lake appears through the trees. The first glimpse of Swanbourne — its still water framed by the hanging beech woods above — is genuinely beautiful. The castle towers are visible above the treeline to the south, providing a perfect backdrop that photographers have captured since the earliest days of Victorian tourism.",
                ],
                "image_url": "",
            },
            {
                "title": "Swanbourne Lake & Café",
                "description": [
                    "Swanbourne Lake was created as a millpond in the 12th century to power the castle's grain mill. Today it is a tranquil wildlife lake, home to a large mute swan colony alongside great crested grebes, tufted duck, and a resident grey heron with the patience of a saint.",
                    "The lakeside café serves hot drinks, homemade cakes, sandwiches and ice creams in season, open most weekends and daily during school holidays. Rowing boats and pedalos are available for hire at the jetty — £4 per adult, £3 per child for 30 minutes — and life jackets are provided. Arrive early on warm days to avoid disappointment.",
                ],
                "image_url": "",
            },
            {
                "title": "Boat Hire Jetty",
                "description": [
                    "The jetty is the best spot from which to appreciate the scale of the lake and its extraordinary wooded setting. Looking back toward the castle from the water, you have the same view that Victorian artists including J.M.W. Turner came to paint — the castle rising above its wooded hillside, reflected in still water below.",
                    "Children will enjoy feeding the swans and ducks from the jetty — seed is available from the kiosk. Swans can be surprisingly assertive when food is on offer, so small children should be supervised closely.",
                ],
                "image_url": "",
            },
            {
                "title": "Woodland Return Path",
                "description": [
                    "The return route takes the higher woodland path above the western shore, winding through mature beech and oak before descending back to the Mill Road entrance. The path climbs modestly and offers a different perspective — looking down through the branches at the glittering water and across to the wooded ridge of Arundel Park beyond.",
                    "In bluebells season — typically mid-April to mid-May — this woodland path is spectacular, the floor carpeted in blue as far as you can see. The combination of bluebells, fresh beech leaves and castle glimpses through the canopy is genuinely memorable. The path rejoins the main track just above the kissing gate at the start.",
                ],
                "image_url": "",
            },
        ],
    },
]

WALKS["denbies-wine-estate"] = [
    {
        "slug": "vineyard-valley-loop",
        "title": "Vineyard Valley Loop",
        "distance": "4.5 km",
        "duration": "1 hr 15 min",
        "difficulty": "Easy",
        "summary": "A gently undulating circuit through the heart of the Denbies vineyard, with North Downs chalk grassland, vine-row views and the Conservatory Restaurant as a natural start and finish.",
        "image_url": "",
        "center": [51.2337, -0.3357],
        "zoom": 14,
        "waypoint_zoom": 16,
        "route": [
            [51.2337, -0.3357], [51.2350, -0.3340], [51.2365, -0.3325],
            [51.2375, -0.3310], [51.2370, -0.3290], [51.2355, -0.3285],
            [51.2340, -0.3295], [51.2325, -0.3310], [51.2318, -0.3330],
            [51.2325, -0.3348], [51.2337, -0.3357],
        ],
        "waypoint_coords": [
            [51.2337, -0.3357], [51.2370, -0.3315], [51.2360, -0.3288], [51.2322, -0.3335],
        ],
        "waypoints": [
            {
                "title": "Denbies Visitor Centre",
                "description": [
                    "Begin at the Denbies Visitor Centre — the handsome flint-clad building that houses the winery, restaurants, shop and gallery. The estate covers 265 acres of south-facing chalk slopes on the North Downs above Dorking, making it England's largest single-estate vineyard. From the car park you can already see vine rows climbing the hillside above in orderly lines stretching to the ridge.",
                    "Follow the vineyard track east from the visitor centre, passing through the first blocks of Chardonnay and Pinot Noir. The vines here were established in the late 1980s and are now well into their productive maturity — the oldest blocks have complex root systems reaching deep into the chalk, which is thought to contribute the mineral character for which Denbies wines are known.",
                ],
                "image_url": "",
            },
            {
                "title": "North Downs Ridge View",
                "description": [
                    "As the path climbs to the upper vineyard, the views open dramatically across the Mole Valley to Box Hill on the opposite side of the gap. On a clear day the horizon extends south across the Weald toward the South Downs, with Leith Hill — the highest point in South East England — visible to the southwest.",
                    "The chalk grassland on the upper slope, where vines give way to unimproved downland, is managed for biodiversity and supports a rich flora in summer — round-headed rampion, common spotted orchid, yellow rattle and numerous chalk-specialist butterflies including Adonis blue and chalkhill blue.",
                ],
                "image_url": "",
            },
            {
                "title": "Upper Vineyard Block",
                "description": [
                    "The upper vineyard blocks on the south-facing slope produce some of Denbies' most distinctive wines — the position maximises sun hours and the drainage through the chalk is excellent. The vineyard train runs past this point on its summer circuit, offering an alternative way to explore for those who prefer not to walk.",
                    "In late summer and early autumn the grapes ripen visibly on the vine. Denbies grows Chardonnay, Pinot Noir, Pinot Meunier, Bacchus and several other varieties, harvested by hand from mid-September. In harvest season the air smells sweetly of fermenting grape juice and you may see the picking teams at work.",
                ],
                "image_url": "",
            },
            {
                "title": "Return via Lower Vineyard",
                "description": [
                    "The lower vineyard path winds back to the visitor centre through the flatter ground of the valley floor, passing the estate's small lake and willow-fringed pond, which attracts dragonflies in summer and wildfowl in winter. The path is wide and well-surfaced through this section and suitable for pushchairs.",
                    "Back at the visitor centre, the Conservatory Restaurant is open from 9:30am to 4pm daily for light lunches, cakes and afternoon tea — all with excellent views across the vineyard. The wine and gift shop is immediately adjacent and the full Denbies range is available to taste and buy.",
                ],
                "image_url": "",
            },
        ],
    },
    {
        "slug": "denbies-norbury-park-river-mole",
        "title": "Denbies, Norbury Park & River Mole",
        "distance": "12.5 km",
        "duration": "3 hrs 30 min",
        "difficulty": "Moderate",
        "summary": "A varied circuit taking in the vineyard, the ancient yew woodland of Norbury Park, the River Mole valley, and the chalk escarpment — one of the finest day walks in Surrey.",
        "image_url": "",
        "center": [51.2420, -0.3300],
        "zoom": 13,
        "waypoint_zoom": 15,
        "route": [
            [51.2337, -0.3357], [51.2360, -0.3330], [51.2385, -0.3300],
            [51.2410, -0.3275], [51.2435, -0.3255], [51.2455, -0.3270],
            [51.2465, -0.3295], [51.2460, -0.3320], [51.2445, -0.3345],
            [51.2425, -0.3355], [51.2405, -0.3360], [51.2385, -0.3358],
            [51.2362, -0.3355], [51.2337, -0.3357],
        ],
        "waypoint_coords": [
            [51.2337, -0.3357], [51.2435, -0.3255], [51.2465, -0.3298], [51.2385, -0.3358],
        ],
        "waypoints": [
            {
                "title": "Denbies Wine Estate",
                "description": [
                    "The walk sets off from the Denbies Visitor Centre and climbs north through the vineyard to the chalk ridge of the North Downs. This opening section offers the best views of the estate as a whole — the vine-covered slopes laid out below you, the flint Visitor Centre at the valley floor, and the wooded Surrey Hills horizon in every direction.",
                    "At the top of the vineyard the path crosses open chalk downland before entering woodland on the descent toward Norbury Park. Follow the North Downs Way signs carefully through this transition — well waymarked but the junction onto the Norbury Park estate is easy to miss in poor visibility.",
                ],
                "image_url": "",
            },
            {
                "title": "Norbury Park Ancient Woodland",
                "description": [
                    "Norbury Park is a 1,300-acre Surrey County Council estate with a history stretching from Bronze Age settlement to Druid yew groves to the elegant Georgian manor built in 1774. The woodland here — ancient oak, beech, field maple and massive veteran yews — is some of the most atmospheric in the county. Walking under the spreading canopy of 400-year-old yew trees is an experience quite unlike anything else in Surrey.",
                    "The parkland holds a herd of fallow deer, most often seen in the early morning and late afternoon. The estate also supports treecreepers, nuthatches, spotted flycatchers in summer, and in the darker corners of the yew wood a resident colony of pipistrelle bats that emerge at dusk.",
                ],
                "image_url": "",
            },
            {
                "title": "River Mole & Stepping Stones",
                "description": [
                    "The path descends from Norbury Park to the floor of the Mole Gap, where the River Mole runs through one of the finest stretches of river valley in Surrey. The Stepping Stones at Westhumble are an iconic landmark on the North Downs Way and enormously popular with walkers and families. They were constructed in 1946 but the crossing itself is ancient.",
                    "Note that the Stepping Stones are impassable in flood conditions and can be slippery in frost or after heavy rain. If the river is high, a footbridge 400 metres downstream provides a safe alternative. The meadows alongside the river are excellent for wildflowers in summer, and the river itself supports otters, most often seen at dawn.",
                ],
                "image_url": "",
            },
            {
                "title": "North Downs Way Return",
                "description": [
                    "The return route climbs back to the North Downs chalk ridge via the North Downs Way, following the escarpment before dropping back to the vineyard. This final ridge section offers the finest views of the walk — south across the Weald to the South Downs on the horizon, north across the London Basin toward the city skyline on a clear day.",
                    "The descent back through the upper vineyard to the Visitor Centre is a fitting finale. The Gallery Restaurant opens for lunch Wednesday to Sunday, and the Conservatory is open daily — cold Denbies sparkling wine is particularly well earned after this distance.",
                ],
                "image_url": "",
            },
        ],
    },
    {
        "slug": "box-hill-denbies-circular",
        "title": "Box Hill & Denbies Circular",
        "distance": "15 km",
        "duration": "4 hrs 30 min",
        "difficulty": "Challenging",
        "summary": "A classic Surrey Hills circuit combining the famous summit of Box Hill with the vineyard slopes of Denbies — two of the county's great visitor destinations linked by chalk ridge and river valley.",
        "image_url": "",
        "center": [51.2500, -0.3250],
        "zoom": 12,
        "waypoint_zoom": 14,
        "route": [
            [51.2337, -0.3357], [51.2365, -0.3320], [51.2400, -0.3285],
            [51.2440, -0.3240], [51.2490, -0.3200], [51.2530, -0.3175],
            [51.2565, -0.3165], [51.2580, -0.3180], [51.2570, -0.3215],
            [51.2545, -0.3245], [51.2510, -0.3275], [51.2475, -0.3300],
            [51.2445, -0.3320], [51.2410, -0.3340], [51.2370, -0.3350],
            [51.2337, -0.3357],
        ],
        "waypoint_coords": [
            [51.2337, -0.3357], [51.2490, -0.3203], [51.2578, -0.3180], [51.2510, -0.3275],
        ],
        "waypoints": [
            {
                "title": "Denbies Vineyard Start",
                "description": [
                    "The longest and most demanding Denbies walk begins by climbing the full height of the vineyard to the North Downs ridge, following the vine rows in a steady ascent before breaking onto open chalk grassland at the crest. From the ridge the path joins the North Downs Way — one of England's great walking routes stretching from Farnham to Dover.",
                    "The path east along the ridge crosses Ranmore Common — a wide area of National Trust chalk heath and woodland with good populations of nightjar in summer and stonechat year-round. The common is carpeted in heather and gorse in late summer and is one of the finest accessible open spaces in Surrey.",
                ],
                "image_url": "",
            },
            {
                "title": "Westhumble & Stepping Stones",
                "description": [
                    "The descent to Westhumble village brings you to the Stepping Stones across the River Mole — one of the most photographed spots in Surrey and genuinely thrilling when the river runs full after autumn rain. The village of Westhumble has a small car park and a railway station on the line between Dorking and Leatherhead, useful as an escape point if the weather turns.",
                    "From the Stepping Stones, the path climbs steeply up the famous zigzag of the Box Hill escarpment — a sustained climb of 160 metres that rewards effort with increasingly spectacular views. The steps were constructed by the National Trust in the 1970s to manage erosion. Take your time and use the benches placed at intervals on the ascent.",
                ],
                "image_url": "",
            },
            {
                "title": "Box Hill Summit",
                "description": [
                    "At 224 metres, Box Hill is the highest point on the North Downs and one of the most visited open spaces in England — yet it retains a genuine wildness. The summit is covered in ancient box woodland and rare chalk grassland, and provides views across the Weald that on a good day extend to the South Downs 30 kilometres away. The National Trust visitor centre sells hot drinks and snacks.",
                    "The hill is famously the scene of the ill-fated picnic in Jane Austen's Emma, making it a literary pilgrimage as much as a walking destination. The Salomons Memorial viewpoint is the finest on the summit, with the classic panorama over Dorking and the Mole Valley below.",
                ],
                "image_url": "",
            },
            {
                "title": "Return via Mole Valley",
                "description": [
                    "The return to Denbies descends from Box Hill via the Mole Gap, following the valley floor path alongside the river through a corridor of alder and willow. This is the coolest and most sheltered section of the walk — good habitat for dippers and grey wagtails on the river gravels. The path is flat and clear all the way back to the Stepping Stones.",
                    "From Westhumble the route climbs back onto the Denbies estate via the lower vineyard, completing the circuit with a final gentle ascent through the vines. The Conservatory Restaurant will be a very welcome sight — cold Denbies sparkling wine is particularly well earned.",
                ],
                "image_url": "",
            },
        ],
    },
    {
        "slug": "ranmore-common-vineyard",
        "title": "Ranmore Common & Vineyard",
        "distance": "8 km",
        "duration": "2 hrs 15 min",
        "difficulty": "Moderate",
        "summary": "A rewarding circuit from Westhumble Station across Ranmore Common chalk heath, descending through the Denbies vineyard with North Downs panoramas throughout — fully accessible by public transport.",
        "image_url": "",
        "center": [51.2420, -0.3400],
        "zoom": 13,
        "waypoint_zoom": 15,
        "route": [
            [51.2400, -0.3380], [51.2415, -0.3360], [51.2430, -0.3340],
            [51.2448, -0.3320], [51.2465, -0.3340], [51.2470, -0.3360],
            [51.2460, -0.3380], [51.2440, -0.3390], [51.2418, -0.3388],
            [51.2400, -0.3380],
        ],
        "waypoint_coords": [
            [51.2400, -0.3380], [51.2448, -0.3322], [51.2470, -0.3360], [51.2440, -0.3392],
        ],
        "waypoints": [
            {
                "title": "Box Hill & Westhumble Station",
                "description": [
                    "This walk is designed to be done entirely by public transport — trains run frequently from London Victoria, London Bridge, Gatwick and Dorking to Box Hill and Westhumble station (approximately 50 minutes from London). The station sits at the foot of the North Downs in the Mole Gap, with the chalk escarpment rising on both sides.",
                    "From the station, follow the North Downs Way signs westward and begin climbing through beech and yew woodland onto Ranmore Common. The ascent is steady rather than steep and the path excellent, following a broad chalk track surfaced by the National Trust.",
                ],
                "image_url": "",
            },
            {
                "title": "Ranmore Common",
                "description": [
                    "Ranmore Common is a broad area of National Trust chalk heath and woodland on the North Downs ridge, characterised by a distinctive mix of heather, gorse, and acid grassland alongside ancient yew and box woodland. In summer the common is alive with butterflies, grasshoppers and the churring of nightjars at dusk. In winter it is a favourite haunt of redwing and fieldfare feasting on berry-bearing shrubs.",
                    "The parish church of St Barnabas stands alone on the common — a Victorian flint building of considerable charm, always worth a few minutes inside. The churchyard is rich in wildflowers, including early purple orchids in spring.",
                ],
                "image_url": "",
            },
            {
                "title": "North Downs Viewpoint",
                "description": [
                    "The high point of the common offers views south across the Weald that have changed little since the 18th century. On the clearest days the South Downs are visible on the horizon, 30 kilometres away. The Denbies vineyard is visible below to the south, its vine rows following the contours of the chalk slope in orderly green lines.",
                    "This is prime red kite territory — the birds were reintroduced to the Surrey Hills in 2005 and numbers have grown impressively. It is unusual not to see at least one from this viewpoint, soaring on long, bowed wings with their distinctive forked tail. Buzzards, sparrowhawks and occasional peregrines are also regular.",
                ],
                "image_url": "",
            },
            {
                "title": "Denbies Vineyard Descent",
                "description": [
                    "The descent from Ranmore Common through the Denbies vineyard is one of the most satisfying finales of any Surrey walk — the path drops through the vine rows with ever-improving views until the Visitor Centre appears below. In harvest season (September to October) the path brings you through the active harvest, and the smell of fermenting grape juice drifts up from the winery.",
                    "The Denbies Visitor Centre is the ideal end point — the Conservatory Restaurant serves food from 9:30am daily, the Gallery Restaurant opens for lunch Wednesday to Sunday, and the wine shop sells the full estate range with tasting available. The return to Westhumble Station is a 15-minute walk along the valley floor.",
                ],
                "image_url": "",
            },
        ],
    },
]

PLACES_TO_EAT["arundel-castle"] = [
    {
        "slug": "black-rabbit",
        "name": "The Black Rabbit",
        "type": "Pub & Dining",
        "rating": 4.4,
        "guide_price": "£30",
        "open_today": "11–23",
        "distance": "20 min walk",
        "coords": [50.8487, -0.5518],
        "summary": "A legendary riverside pub in South Stoke with one of the great views in West Sussex — Arundel Castle reflected in the still water of the Arun. Named for the white rabbits once bred on the chalk downs, this Fuller's pub serves hearty British food and keeps excellent ale. Arrive by riverside footpath for the full experience.",
        "image_url": "",
    },
    {
        "slug": "parsons-table",
        "name": "The Parsons Table",
        "type": "Fine Dining",
        "rating": 4.8,
        "guide_price": "£65",
        "open_today": "12–14:30, 18–21",
        "distance": "5 min walk",
        "coords": [50.8557, -0.5505],
        "summary": "Arundel's finest restaurant — a Michelin Guide-listed gem in Castle Mews on Tarrant Street, serving a focused, seasonally-driven menu of modern British cooking. Chef patron Lee Williams works closely with local producers, and every plate shows genuine skill and discipline. Booking essential.",
        "image_url": "",
    },
    {
        "slug": "george-burpham",
        "name": "The George at Burpham",
        "type": "Gastropub",
        "rating": 4.6,
        "guide_price": "£40",
        "open_today": "12–15, 18–22",
        "distance": "15 min drive",
        "coords": [50.8697, -0.5320],
        "summary": "A community-owned 17th-century village pub in the quiet hamlet of Burpham, just north of Arundel, serving AA Rosette-standard food in a beautifully relaxed setting. The menu is built on locally sourced ingredients and changes with the seasons. Dog-friendly, with a lovely garden for summer lunches.",
        "image_url": "",
    },
    {
        "slug": "swan-arundel",
        "name": "The Swan Hotel",
        "type": "Pub & Hotel",
        "rating": 4.2,
        "guide_price": "£28",
        "open_today": "12–22",
        "distance": "4 min walk",
        "coords": [50.8558, -0.5498],
        "summary": "A traditional Fuller's inn on the High Street with a solid, unpretentious menu of pub classics cooked well — fish and chips, Sunday roasts, steaks and seasonal specials. The bar is well-stocked and the atmosphere thoroughly convivial. A reliable choice for a relaxed meal after a morning at the castle.",
        "image_url": "",
    },
    {
        "slug": "juniper-cafe",
        "name": "Juniper",
        "type": "Café & Bistro",
        "rating": 4.7,
        "guide_price": "£18",
        "open_today": "8–16",
        "distance": "3 min walk",
        "coords": [50.8555, -0.5500],
        "summary": "A small, beautifully run independent café on Tarrant Street, beloved by locals for its exceptional coffee, freshly baked pastries, seasonal brunch plates and light lunches made with real care. Monthly evening supper clubs sell out fast — check social media for dates. One of the best café experiences in West Sussex.",
        "image_url": "",
    },
    {
        "slug": "tarrant-street-espresso",
        "name": "Tarrant Street Espresso",
        "type": "Speciality Coffee",
        "rating": 4.8,
        "guide_price": "£8",
        "open_today": "8–16",
        "distance": "4 min walk",
        "coords": [50.8553, -0.5507],
        "summary": "A cult independent coffee bar on Tarrant Street, serving some of the finest espresso in Sussex from Square Mile beans with near-obsessive attention to extraction quality. Tiny inside but there are a few outside seats. A must-visit for anyone who takes their coffee seriously.",
        "image_url": "",
    },
    {
        "slug": "belindas-tea-rooms",
        "name": "Belinda's Tea Rooms",
        "type": "Tea Room",
        "rating": 4.3,
        "guide_price": "£16",
        "open_today": "10–17",
        "distance": "3 min walk",
        "coords": [50.8556, -0.5503],
        "summary": "A classic English tea room in the heart of Arundel — lace tablecloths, tiered cake stands, properly brewed loose-leaf tea, and scones served warm with clotted cream and jam. Wonderfully unhurried and a perfect stop after a morning at the castle. Often busy at weekends; try to arrive by half past eleven.",
        "image_url": "",
    },
]

PLACES_TO_EAT["denbies-wine-estate"] = [
    {
        "slug": "gallery-restaurant-denbies",
        "name": "The Gallery Restaurant",
        "type": "Restaurant",
        "rating": 4.5,
        "guide_price": "£40",
        "open_today": "12–15 (Wed–Sun)",
        "distance": "On site",
        "coords": [51.2337, -0.3357],
        "summary": "Denbies' flagship dining room on the third floor of the winery, with panoramic views across all 265 acres of the vineyard through full-height windows. The menu is seasonal British with strong local sourcing, and the wine list is exclusively Denbies — the Sparkling Surrey Gold makes a particularly fine aperitif. Booking recommended at weekends.",
        "image_url": "",
    },
    {
        "slug": "conservatory-restaurant-denbies",
        "name": "The Conservatory Restaurant",
        "type": "Café & Restaurant",
        "rating": 4.2,
        "guide_price": "£18",
        "open_today": "9:30–16",
        "distance": "On site",
        "coords": [51.2337, -0.3357],
        "summary": "The ground-floor all-day dining option at Denbies, open daily from 9:30am for breakfast, morning coffee, light lunches and afternoon tea. The terrace spills outside in fine weather with vineyard views, and the cake selection is particularly good. No booking required.",
        "image_url": "",
    },
    {
        "slug": "sorrel-dorking",
        "name": "Sorrel",
        "type": "Fine Dining",
        "rating": 4.9,
        "guide_price": "£95",
        "open_today": "12–14, 19–21 (Wed–Sat)",
        "distance": "10 min drive",
        "coords": [51.2310, -0.3295],
        "summary": "One of the finest restaurants in South East England — Steve Drake's Michelin-starred, four AA Rosette restaurant on South Street in Dorking delivers cooking of real ambition and finesse in a calm, unpretentious setting. The tasting menu showcases hyper-seasonal ingredients with technical precision. Booking is essential; plan well ahead.",
        "image_url": "",
    },
    {
        "slug": "watermill-pixham",
        "name": "The Watermill",
        "type": "Gastropub",
        "rating": 4.3,
        "guide_price": "£30",
        "open_today": "12–22",
        "distance": "8 min drive",
        "coords": [51.2355, -0.3190],
        "summary": "A charming Surrey Hills gastropub in Pixham — just minutes from Denbies — with a seasonally-changing British menu, excellent ales and a sun-trap garden perfect for summer lunches. The weekday prix fixe is remarkable value. Well suited to walkers arriving off the North Downs Way.",
        "image_url": "",
    },
    {
        "slug": "abinger-hatch",
        "name": "The Abinger Hatch",
        "type": "Country Pub",
        "rating": 4.4,
        "guide_price": "£28",
        "open_today": "12–22",
        "distance": "15 min drive",
        "coords": [51.2140, -0.3805],
        "summary": "A quintessential Surrey countryside pub in Abinger Common, between Dorking and Guildford — exposed beams, log fires in winter, and a garden that is as pleasant a place to sit as any in the Surrey Hills. The menu covers classic pub fare with local sourcing throughout, and the atmosphere is genuinely welcoming.",
        "image_url": "",
    },
    {
        "slug": "holme-stores-dorking",
        "name": "Holme Stores",
        "type": "Café & Deli",
        "rating": 4.6,
        "guide_price": "£14",
        "open_today": "8–16",
        "distance": "10 min drive",
        "coords": [51.2305, -0.3300],
        "summary": "A much-loved Dorking café-deli hybrid with an excellent morning and lunch offer — creative small plates, seasonal salads, superb coffee and a deli counter of sustainably sourced ingredients. The room is small and fills quickly at weekends; a weekday visit is recommended for a more relaxed experience.",
        "image_url": "",
    },
    {
        "slug": "vineyard-restaurant-denbies",
        "name": "The Vineyard Restaurant",
        "type": "Restaurant (Dinner)",
        "rating": 4.3,
        "guide_price": "£45",
        "open_today": "18:30–21:30",
        "distance": "On site",
        "coords": [51.2337, -0.3357],
        "summary": "Denbies' evening dining venue, serving dinner every evening from 6:30pm in a relaxed, candlelit setting within the winery complex. The menu changes with the seasons and pairs well-sourced British dishes with the full range of Denbies wines. A lovely option if you are staying at Denbies Lodge or exploring the estate for a full day.",
        "image_url": "",
    },
]

PLACES_OF_INTEREST["arundel-castle"] = [
    {
        "slug": "arundel-castle-interiors",
        "name": "Arundel Castle",
        "type": "Castle & Gardens",
        "summary": "The seat of the Dukes of Norfolk and one of the great medieval castles of southern England, with origins in the reign of William the Conqueror. Inside, a remarkable collection of portraits, furniture and artefacts includes personal possessions of Mary Queen of Scots, armour from the 14th century, and paintings by Van Dyck and Gainsborough. Open to visitors from April to November, with the gardens beautiful throughout the season.",
        "image_url": "",
    },
    {
        "slug": "arundel-cathedral",
        "name": "Arundel Cathedral",
        "type": "Cathedral",
        "summary": "The Cathedral Church of Our Lady and St Philip Howard is one of the finest Victorian Gothic buildings in England, designed by Joseph Hansom and built between 1869 and 1873 at the personal expense of the 15th Duke of Norfolk. The soaring nave, intricate stained glass and elaborate stonework are impressive by any measure. The shrine of St Philip Howard — a Catholic martyr executed in 1595 — draws pilgrims and visitors year-round.",
        "image_url": "",
    },
    {
        "slug": "wwt-arundel",
        "name": "WWT Arundel Wetland Centre",
        "type": "Nature Reserve",
        "summary": "A 65-acre wildlife reserve managed by the Wildfowl and Wetlands Trust on the eastern edge of Arundel town, covering reedbed, open water, fen and river channels. The site attracts an extraordinary diversity of birds — kingfishers, marsh harriers, bitterns, water rails and over 70 other species have been recorded. Boat safaris, pond dipping and a wildlife play area make it one of the best family nature attractions in the South East.",
        "image_url": "",
    },
    {
        "slug": "swanbourne-lake",
        "name": "Swanbourne Lake",
        "type": "Parkland Lake",
        "summary": "A serene millpond within Arundel Park, enclosed by hanging beech and oak woodland, with the castle towers visible above the treeline. Created in the 12th century to power the castle's grain mill, it is now a tranquil wildlife lake with a resident swan colony, great crested grebes and a summer boat hire concession. The lakeside café is a perfect rest stop on any walk in the park.",
        "image_url": "",
    },
    {
        "slug": "arundel-museum",
        "name": "Arundel Museum",
        "type": "Museum",
        "summary": "A modern museum directly opposite the castle entrance, telling the story of Arundel and its people from prehistoric times to the present. Exhibits cover 500,000 years of history — from flint tools and Roman finds to the medieval port, the castle's ducal history and the town's wartime memories. Admission is free and children's discovery bags and activity trails are available at the desk.",
        "image_url": "",
    },
    {
        "slug": "amberley-village-museum",
        "name": "Amberley Village & Museum",
        "type": "Village & Museum",
        "summary": "One of the most beautiful villages in Sussex, a 30-minute drive or three-hour walk north of Arundel along the Arun. Chalk cottages, a Norman church, and the ruins of Amberley Castle cluster around lanes that have barely changed in two centuries. The nearby Amberley Museum and Heritage Centre is a 36-acre open-air industrial museum with working exhibits including a narrow-gauge railway, vintage buses, and craft workshops.",
        "image_url": "",
    },
    {
        "slug": "hiorne-tower",
        "name": "Hiorne Tower",
        "type": "Folly & Viewpoint",
        "summary": "A Gothic Revival folly on the ridge of Arundel Park, built in 1787 by architect Francis Hiorne in an ultimately unsuccessful bid to impress the 11th Duke of Norfolk. Standing on the chalk ridge above the town, it commands sweeping views across the Arun valley to the sea on one side and across the South Downs on the other. Reached on foot through the park, it makes a fine objective for a half-day walk.",
        "image_url": "",
    },
]

PLACES_OF_INTEREST["denbies-wine-estate"] = [
    {
        "slug": "denbies-winery-tour",
        "name": "Denbies Winery Tour",
        "type": "Vineyard Experience",
        "summary": "The Denbies indoor winery tour takes visitors through the full production process — from vine to bottle — in the purpose-built winery beneath the Visitor Centre. The tour includes a guided tasting of four wines, with expert commentary on how the chalk soils and North Downs microclimate shape each vintage. Tours run hourly daily between 11am and 4pm; the indoor tasting tour (Wednesday to Friday and selected Saturdays) includes a more extensive cellar experience at £45 per person.",
        "image_url": "",
    },
    {
        "slug": "box-hill",
        "name": "Box Hill",
        "type": "National Trust Landmark",
        "summary": "One of the most iconic viewpoints in England, rising to 224 metres above the Mole Gap — visible from the Denbies upper vineyard on the opposite side of the valley. Named for its ancient box woodland, Box Hill is managed by the National Trust and receives over a million visitors a year. The summit panorama across the Weald is extraordinary, and the hill's literary associations — most famously Jane Austen's Emma — add a further dimension. Accessible on foot via the Stepping Stones and the famous zigzag path.",
        "image_url": "",
    },
    {
        "slug": "norbury-park",
        "name": "Norbury Park",
        "type": "Country Park",
        "summary": "A 1,300-acre Surrey County Council estate of ancient woodland, chalk grassland and farmland to the north of Westhumble, with a management history stretching from Bronze Age settlement to the 18th-century manor house. The veteran yew woodland is particularly remarkable — some trees are thought to exceed 400 years in age — and the estate supports fallow deer, pipistrelle bats and a rich assemblage of woodland birds. Seven miles of public footpath cross the estate.",
        "image_url": "",
    },
    {
        "slug": "leith-hill",
        "name": "Leith Hill & Tower",
        "type": "Highest Point & Tower",
        "summary": "Leith Hill is the highest point in South East England at 295 metres, with the 18th-century tower at its summit adding a further 18 metres to give a viewpoint from which — on the clearest days — both the English Channel and the Thames Estuary are visible simultaneously. Managed by the National Trust, the hill is covered in a spectacular carpet of rhododendrons in late spring and supports nesting nightjars in summer. A 20-minute drive from Denbies.",
        "image_url": "",
    },
    {
        "slug": "denbies-art-gallery",
        "name": "Denbies Art Gallery",
        "type": "Gallery",
        "summary": "An on-site art gallery within the Denbies Visitor Centre, displaying a regularly changing programme of work by local and regional artists — paintings, sculpture, ceramics and printmaking inspired by the Surrey Hills landscape. Admission is free and the gallery is open daily during visitor centre hours. Original artwork and limited edition prints are available to purchase.",
        "image_url": "",
    },
    {
        "slug": "village-greens-farm-shop-poi",
        "name": "Village Greens Farm Shop",
        "type": "Farm Shop",
        "summary": "Located within the Denbies complex, Village Greens is a well-stocked farm shop carrying local produce from across Surrey and Sussex — fruit, vegetables, meat, dairy, preserves and prepared foods alongside seasonal specialities. An excellent place to assemble a serious picnic before heading onto the vineyard trails, or to take home a taste of the Surrey Hills.",
        "image_url": "",
    },
    {
        "slug": "mole-gap-stepping-stones",
        "name": "River Mole Stepping Stones",
        "type": "Landmark",
        "summary": "The Stepping Stones across the River Mole at Westhumble are one of Surrey's most iconic landmarks — large stone blocks set across the river on the North Downs Way, used by walkers since the 19th century (the current stones date from 1946). The crossing is thrilling when the river runs full and perfectly safe in normal conditions. The surrounding Mole Gap meadows are excellent for wildflowers, otters and the grey wagtails that bob along the river margins.",
        "image_url": "",
    },
]

FUN_FOR_KIDS["arundel-castle"] = [
    {
        "slug": "wwt-boat-safari",
        "name": "WWT Boat Safari",
        "type": "Wildlife Activity",
        "distance": "10 min walk",
        "coords": [50.8520, -0.5495],
        "summary": "Electric boat trips through the reedbed channels of the WWT Wetland Centre, guided by a naturalist who points out kingfishers, water voles, herons and the aquatic world hidden within the reeds. The 20-minute safari departs regularly throughout the day and costs £3 per person — one of the best wildlife experiences in West Sussex for children.",
        "image_url": "",
    },
    {
        "slug": "wwt-pond-dipping",
        "name": "WWT Pond Dipping",
        "type": "Wildlife Activity",
        "distance": "10 min walk",
        "coords": [50.8520, -0.5495],
        "summary": "Family pond dipping sessions at the WWT Arundel Wetland Centre, led by wildlife educators who help children identify water boatmen, diving beetles, dragonfly larvae and freshwater shrimps. Available on weekends and school holidays — booking recommended for groups. Equipment and instruction provided; just bring wellies.",
        "image_url": "",
    },
    {
        "slug": "swanbourne-boats",
        "name": "Swanbourne Lake Boat Hire",
        "type": "Outdoor Activity",
        "distance": "15 min walk",
        "coords": [50.8598, -0.5465],
        "summary": "Rowing boats and pedalos available for hire on Swanbourne Lake within Arundel Park, at £4 per adult and £3 per child for a 30-minute session. Life jackets are provided and the lake is shallow and calm — a perfect first boating experience for young children. The swan colony investigates at close quarters, which children find thrilling.",
        "image_url": "",
    },
    {
        "slug": "arundel-castle-towers",
        "name": "Arundel Castle Towers & Battlements",
        "type": "Castle Exploration",
        "distance": "1 min walk",
        "coords": [50.8561, -0.5510],
        "summary": "The castle's medieval towers and battlements are a highlight for children of all ages — climbing spiral staircases, peering through arrow loops and imagining the castle under siege. During the events season the castle hosts jousting tournaments, medieval encampments, falconry displays and hands-on warrior training days that bring history alive in the most exciting possible way.",
        "image_url": "",
    },
    {
        "slug": "arundel-museum-families",
        "name": "Arundel Museum Trails",
        "type": "Museum",
        "distance": "3 min walk",
        "coords": [50.8558, -0.5503],
        "summary": "Arundel Museum runs an excellent family programme including I-Spy trails around the town, discovery bags filled with hands-on objects to explore in the galleries, and holiday activity sessions. The museum spans 500,000 years of history in an accessible, well-designed building. Entry is free, making it an ideal stop on a rainy afternoon.",
        "image_url": "",
    },
    {
        "slug": "feed-the-swans",
        "name": "Feed the Swans at Swanbourne",
        "type": "Wildlife",
        "distance": "15 min walk",
        "coords": [50.8595, -0.5480],
        "summary": "The swan colony at Swanbourne Lake is one of the most accessible in Sussex, with up to 20 or more mute swans resident alongside ducks, grebes and coots. Wildbird seed is available from the lakeside kiosk — please use proper seed rather than bread. The birds approach remarkably close to the path and jetty, providing wonderful encounters for younger children.",
        "image_url": "",
    },
    {
        "slug": "amberley-museum-kids",
        "name": "Amberley Museum Narrow Gauge Railway",
        "type": "Heritage Transport",
        "distance": "20 min drive",
        "coords": [50.8878, -0.5415],
        "summary": "The Amberley Museum and Heritage Centre is a 36-acre open-air industrial museum with working exhibits that children love — most notably a narrow-gauge railway that carries passengers around the site. Vintage buses, chalk-pit machinery, print workshops and a reconstructed 1920s village street complete the picture. A full day out and excellent value for family groups.",
        "image_url": "",
    },
]

SHOPPING["arundel-castle"] = [
    {
        "slug": "arundel-bridge-antiques",
        "name": "Arundel Bridge Antiques",
        "type": "Antiques Centre",
        "distance": "5 min walk",
        "coords": [50.8548, -0.5490],
        "hours": "Mon–Sat 10–17, Sun 11–17",
        "website": "https://www.arundelantiques.co.uk",
        "description": "The longest-established antiques centre in Arundel, with over 40 individual traders across a rambling Georgian building at the end of the High Street. Everything from Georgian silver and Victorian watercolours to art deco glass, vintage maps and country furniture. The kind of place that serious collectors return to again and again — something different turns up every visit.",
        "image_url": "",
    },
    {
        "slug": "kims-bookshop",
        "name": "Kim's Bookshop",
        "type": "Bookshop",
        "distance": "4 min walk",
        "coords": [50.8555, -0.5498],
        "hours": "Mon–Sat 9:30–17:30, Sun 10:30–17",
        "website": "",
        "description": "An Arundel institution with over 50,000 new, second-hand and antiquarian books stacked across three floors of a creaking old building on the High Street. Kim's has been trading for more than 40 years and remains fiercely independent. Strong on local history, natural history, architecture and children's books. Allow at least an hour.",
        "image_url": "",
    },
    {
        "slug": "pallant-arundel",
        "name": "Pallant of Arundel",
        "type": "Delicatessen",
        "distance": "4 min walk",
        "coords": [50.8554, -0.5502],
        "hours": "Mon–Sat 9–17:30, Sun 10–16",
        "website": "",
        "description": "A wonderful independent delicatessen championing small producers — outstanding cheeses from across the British Isles, charcuterie, artisan breads, local honey and a well-chosen wine selection. The team is knowledgeable and happy to advise on pairings. Perfect for assembling a picnic before heading into the park or along the river.",
        "image_url": "",
    },
    {
        "slug": "old-print-works",
        "name": "The Old Print Works",
        "type": "Shopping Arcade",
        "distance": "5 min walk",
        "coords": [50.8550, -0.5505],
        "hours": "Daily 10–17",
        "website": "",
        "description": "A characterful collection of independent shops in a converted Victorian print works — a souk-like warren of spaces selling vintage clothing, millinery, vinyl records, retro gifts, antique curios and original art. Each shop is independently run and the overall atmosphere is relaxed and browser-friendly. Particularly good for gifts that are genuinely different.",
        "image_url": "",
    },
    {
        "slug": "castle-shop",
        "name": "Arundel Castle Gift Shop",
        "type": "Gift Shop",
        "distance": "1 min walk",
        "coords": [50.8561, -0.5512],
        "hours": "Apr–Nov: Tue–Sun 10–17",
        "website": "https://www.arundelcastle.org",
        "description": "The official castle shop at the entrance to the castle grounds, selling high-quality gifts, books and souvenirs inspired by the castle's history and art collection. The range includes prints of portraits from the picture collection, books on the Norfolk family and Sussex history, and a selection of quality ceramics, textiles and children's gifts. All purchases support the castle's conservation programme.",
        "image_url": "",
    },
    {
        "slug": "tarrant-street-boutiques",
        "name": "Tarrant Street Boutiques",
        "type": "Independent Boutiques",
        "distance": "4 min walk",
        "coords": [50.8553, -0.5507],
        "hours": "Tue–Sat 10–17",
        "website": "",
        "description": "Tarrant Street is Arundel's most characterful shopping thoroughfare, lined with independent boutiques selling ceramics, jewellery, homewares and fashion alongside Tarrant Street Espresso and Juniper café. The standard of independent retailing here is remarkably high for a town of Arundel's size — a natural morning circuit of coffee, browse and repeat.",
        "image_url": "",
    },
]

SHOPPING["denbies-wine-estate"] = [
    {
        "slug": "denbies-wine-shop",
        "name": "Denbies Wine & Gift Shop",
        "type": "Winery Shop",
        "distance": "On site",
        "coords": [51.2337, -0.3357],
        "hours": "Daily 10–17",
        "website": "https://www.denbies.co.uk",
        "description": "The estate's own wine and gift shop adjacent to the Conservatory Restaurant, stocking the full Denbies range — still and sparkling whites, reds, rosé and dessert wines — alongside branded gifts, wine accessories, books about English wine and artisan food products chosen to complement the wines. Tasting is available and the staff are knowledgeable about the range and vintages.",
        "image_url": "",
    },
    {
        "slug": "village-greens-shop",
        "name": "Village Greens Farm Shop",
        "type": "Farm Shop",
        "distance": "On site",
        "coords": [51.2337, -0.3357],
        "hours": "Daily 9:30–17",
        "website": "",
        "description": "A community-supported farm shop within the Denbies complex carrying local produce from Surrey and Sussex growers — seasonal vegetables, fruit, artisan bread, farmhouse cheeses, free-range meat, and an excellent selection of jams, chutneys and prepared foods. Works directly with local producers to keep the supply chain short and the produce genuinely fresh. Superb for a vineyard picnic.",
        "image_url": "",
    },
    {
        "slug": "dorking-antiques-west-street",
        "name": "Dorking Antiques Quarter",
        "type": "Antiques",
        "distance": "10 min drive",
        "coords": [51.2310, -0.3310],
        "hours": "Mon–Sat 10–17, Sun 11–16",
        "website": "https://www.dorkingantiques.co.uk",
        "description": "West Street in Dorking is one of the finest antiques quarters in the Home Counties — a Victorian street lined with independent dealers specialising in furniture, decorative arts, silver, ceramics, maps and prints spanning several centuries. Dorking Antiques Centre anchors the street with multiple dealers under one roof, while G.B. Elias Antiques — established for over 40 years — is the place for serious furniture buyers.",
        "image_url": "",
    },
    {
        "slug": "wine-unlimited-dorking",
        "name": "Wine Unlimited",
        "type": "Wine Merchant",
        "distance": "10 min drive",
        "coords": [51.2318, -0.3312],
        "hours": "Mon–Sat 10–18",
        "website": "https://www.wineunlimited.co.uk",
        "description": "Dorking's best independent wine merchant, trading from The Vineyard on the High Street for over 20 years. The range spans the world with a particular strength in English wines — Denbies and fellow Surrey vineyards are well represented alongside an excellent selection of Burgundy, Loire and natural wines. Thoughtful advice without condescension.",
        "image_url": "",
    },
    {
        "slug": "british-bookshop-dorking",
        "name": "British Bookshop & Stationers",
        "type": "Bookshop",
        "distance": "10 min drive",
        "coords": [51.2312, -0.3305],
        "hours": "Mon–Sat 9–17:30",
        "website": "https://www.tgjonesonline.co.uk",
        "description": "A proper, well-stocked independent bookshop on Dorking's High Street with an especially good selection of books on local history, the Surrey Hills, gardening and natural history — entirely appropriate reading after a day at Denbies. The stationery range is equally impressive. One of the few remaining independent stationers in Surrey.",
        "image_url": "",
    },
    {
        "slug": "denbies-gallery-shop",
        "name": "Denbies Gallery Shop",
        "type": "Art & Gifts",
        "distance": "On site",
        "coords": [51.2337, -0.3357],
        "hours": "Daily 10–17",
        "website": "https://www.denbies.co.uk",
        "description": "The gallery shop at Denbies sells original artwork, limited edition prints, ceramics and gifts by Surrey and Sussex artists alongside the estate's branded merchandise. The selection changes regularly as the gallery programme rotates. Framed prints of the vineyard and North Downs landscape make particularly distinctive souvenirs of a visit to the estate.",
        "image_url": "",
    },
]


# ── Hurtwood Estate & Loseley Park ──────────────────────────────────────────────────────────

WALKS["hurtwood-estate"] = [
    {
        "slug": "holmbury-hill-circular",
        "title": "Holmbury Hill Circular",
        "distance": "5.8 km",
        "duration": "2 hrs",
        "difficulty": "Moderate",
        "summary": "A classic circuit from Car Park 1 climbing to the Iron Age hillfort summit of Holmbury Hill, dropping into the village of Holmbury St Mary for a pub stop, and returning through Scots pine woodland.",
        "image_url": "",
        "center": [51.1712, -0.4029],
        "zoom": 13,
        "waypoint_zoom": 15,
        "route": [
            [51.1755, -0.3947],  # Car Park 1 (Holmbury Hill)
            [51.1740, -0.3960],
            [51.1720, -0.3990],
            [51.1712, -0.4029],  # Holmbury Hill summit
            [51.1700, -0.4050],
            [51.1685, -0.4063],  # Holmbury St Mary village
            [51.1680, -0.4020],
            [51.1700, -0.4000],
            [51.1720, -0.3980],
            [51.1740, -0.3960],
            [51.1755, -0.3947],  # Return to Car Park 1
        ],
        "waypoint_coords": [
            [51.1755, -0.3947],
            [51.1712, -0.4029],
            [51.1685, -0.4063],
            [51.1700, -0.4000],
        ],
        "waypoints": [
            {
                "title": "Hurtwood Car Park 1 (Holmbury Hill)",
                "description": [
                    "Start at Hurtwood Car Park 1, managed by the Friends of the Hurtwood charity (registered charity no. 200053) and reached by following Radnor Road south from Peaslake village for approximately one mile. The car park sits in the shade of mature Scots pine on a sandy track and is one of 15 free car parks across the Hurtwood open to the public. A voluntary donation box is located near the entrance — contributions go directly toward maintaining the paths and woodland.",
                    "From the car park, take the broad sandy path south-eastward past a small pond on your right, keeping to the main track as it rises steadily through pine and birch. The Hurtwood covers around 3,000 acres of SSSI-designated heathland and woodland and has been freely open to the public since 1926 under a covenant given by Reginald Bray, then Lord of the Manor of Shere.",
                ],
                "image_url": "",
            },
            {
                "title": "Holmbury Hill Summit & Hillfort",
                "description": [
                    "At 261 metres (856 ft), Holmbury Hill is Surrey's fourth-highest point and the site of one of the county's most significant Iron Age hillforts. Excavations in 1929 revealed that the fort was probably occupied from around 100 to 70 BC, constructed by Celtic tribes as a communal gathering and trading hub rather than a permanent settlement. The defensive earthworks are still clearly visible: a double rampart system protects the western and northern approaches, with the outer ditch originally around three metres deep and six metres wide.",
                    "The summit viewpoint is one of the finest in southern England. On a clear day you can see across the Weald to the South Downs ridge, and in exceptional conditions the Shoreham Gap — the sea — is visible to the south. The view north takes in the North Downs escarpment. The summit is open heathland, giving a striking contrast to the dense pine woodland of the approach path. Gorse blooms here in late winter and early spring, bright yellow against the dark trees.",
                ],
                "image_url": "",
            },
            {
                "title": "Holmbury St Mary Village",
                "description": [
                    "The path descends steeply from the summit into the picturesque village of Holmbury St Mary, a small settlement tucked into the south slope of the Greensand Ridge. The village green is overlooked by the Church of St Mary, a Victorian flint-built church by George Edmund Street, the architect responsible for the Royal Courts of Justice in London. The church is worth a few minutes inside.",
                    "Two pubs serve the village. The Royal Oak is a well-established walkers' pub with a warm welcome for muddy boots and dogs on leads, and a reliable menu of homemade food. The Kings Head has recently been refurbished and has a more contemporary feel with a good kitchen. Both have outdoor seating for fine days. This is the ideal lunch stop on the route before the return climb.",
                ],
                "image_url": "",
            },
            {
                "title": "Woodland Return",
                "description": [
                    "From the village green, the return route climbs back northward through the dense Scots pine and birch woodland that makes the Hurtwood so distinctive. The pines were introduced in the 18th century — before that the Hurtwood would have been deciduous forest — and they now create a landscape of real character, especially on misty mornings when the light filters through the canopy in shafts. Keep to the main track as the paths multiply in this section; the route back to Car Park 1 is a steady but manageable climb.",
                    "Watch for roe deer in the woodland margins, especially in the early morning and at dusk. The Hurtwood supports good populations of deer, foxes, and a wide variety of woodland birds including woodpeckers and treecreepers. The sandy, well-drained soils underfoot make this route walkable year-round, though the descent into Holmbury St Mary can be slippery after heavy rain.",
                ],
                "image_url": "",
            },
        ],
    },
    {
        "slug": "pitch-hill-holmbury-loop",
        "title": "Pitch Hill & Holmbury Hill Loop",
        "distance": "9.3 km",
        "duration": "2 hrs 45 min",
        "difficulty": "Challenging",
        "summary": "The best all-day circuit on the Hurtwood, taking in both main summits — the dramatic sandstone spur of Pitch Hill and the Iron Age hillfort of Holmbury Hill — linked by miles of superb pine and heathland trail.",
        "image_url": "",
        "center": [51.1690, -0.4100],
        "zoom": 13,
        "waypoint_zoom": 15,
        "route": [
            [51.1755, -0.4010],  # Car Park 2 (Walking Bottom / Peaslake)
            [51.1730, -0.4020],
            [51.1710, -0.4050],
            [51.1700, -0.4100],  # Holmbury Hill summit
            [51.1685, -0.4063],  # Holmbury St Mary
            [51.1670, -0.4100],
            [51.1650, -0.4180],
            [51.1680, -0.4260],
            [51.1700, -0.4530],  # Pitch Hill summit
            [51.1690, -0.4410],
            [51.1710, -0.4280],
            [51.1730, -0.4150],
            [51.1755, -0.4010],  # Return
        ],
        "waypoint_coords": [
            [51.1755, -0.4010],
            [51.1700, -0.4100],
            [51.1700, -0.4530],
            [51.1710, -0.4280],
        ],
        "waypoints": [
            {
                "title": "Car Park 2 — Walking Bottom, Peaslake",
                "description": [
                    "Start from Hurtwood Car Park 2 (Walking Bottom), the largest and most popular of the Hurtwood's 15 free car parks and situated just south of Peaslake village. It fills by 9:30 am on fine summer weekends, so arrive early or aim for mid-morning once the initial rush has passed. From the car park, walk south through the village briefly, then take the signed footpath into the woodland heading toward Holmbury Hill.",
                    "Peaslake itself is worth a quick stop: the village stores is famous for its homemade cheese straws and pork-and-leek slices, essential fuel for a longer walk. The Hurtwood Inn pub is directly on the central junction and good for a post-walk pint. Surrey Hills Bike Rental operates from the Riders Hub here if any members of your party want to hire bikes and meet you back at the car park.",
                ],
                "image_url": "",
            },
            {
                "title": "Holmbury Hill",
                "description": [
                    "The route climbs first to the Holmbury Hill summit at 261 metres — see the Holmbury Hill Circular walk entry for the full description of the Iron Age fort and viewpoint. From the summit, descend briefly into Holmbury St Mary if you want a pub break, or continue directly west along the ridge path toward Pitch Hill, keeping to the high ground through heather and bracken.",
                ],
                "image_url": "",
            },
            {
                "title": "Pitch Hill Summit",
                "description": [
                    "Pitch Hill sits at approximately 257 metres on a narrow sandstone spur above Ewhurst, reached via a quarry path from Hurtwood Car Park 3 (Mil Plain) or along the ridge from Holmbury Hill. The summit offers spectacular views southward over the Weald to the South Downs, taking in the village of Ewhurst in the valley below. A low wooden viewing platform at the top marks the main vantage point.",
                    "Winterfold and Pitch Hill are dotted with old sandstone quarries. The honey-coloured Hurtwood Stone — a high-quality sandstone from the Hythe Beds, similar to the Bargate Stone used in Guildford — has been quarried here since the 12th century and was used in buildings across Surrey. Look out for the characteristic outcrops of exposed sandstone on the approach to the summit: in the right light they glow a warm amber-gold.",
                ],
                "image_url": "",
            },
            {
                "title": "Winterfold Return",
                "description": [
                    "From Pitch Hill, the return route heads north-east across Winterfold Heath and through Winterfold Wood, some of the most varied and beautiful woodland on the Hurtwood estate. Ancient oaks and beeches mix with the introduced Scots pine, and the understorey of bracken, heather, and bilberry gives it a wild, open character quite different from the denser plantation sections. The route rejoins the outward track near Peaslake for the final stretch back to Car Park 2.",
                    "This section of the walk is also part of the Greensand Way long-distance route, which runs 108 miles from Haslemere in Surrey to Hamstreet in Kent. Look for the green GW waymarkers on the gateposts.",
                ],
                "image_url": "",
            },
        ],
    },
    {
        "slug": "winterfold-wood-circular",
        "title": "Winterfold Wood Circular",
        "distance": "7.7 km",
        "duration": "2 hrs",
        "difficulty": "Moderate",
        "summary": "A quieter, more contemplative circuit through the ancient and planted woodland of Winterfold, passing old quarries, open heathland, and the elevated viewpoint at Reynard's Hill.",
        "image_url": "",
        "center": [51.1640, -0.4320],
        "zoom": 13,
        "waypoint_zoom": 15,
        "route": [
            [51.1670, -0.4390],  # Car Park 5 (Winterfold / Donkins), GU5 9EN
            [51.1650, -0.4350],
            [51.1630, -0.4300],
            [51.1620, -0.4250],
            [51.1630, -0.4200],  # Reynard's Hill viewpoint
            [51.1645, -0.4220],
            [51.1660, -0.4280],
            [51.1665, -0.4340],
            [51.1670, -0.4390],  # Return
        ],
        "waypoint_coords": [
            [51.1670, -0.4390],
            [51.1630, -0.4200],
            [51.1645, -0.4220],
            [51.1660, -0.4280],
        ],
        "waypoints": [
            {
                "title": "Car Park 5 — Winterfold (Donkins)",
                "description": [
                    "Start at Hurtwood Car Park 5, known locally as Donkins, accessed from Winterfold Heath Road near Ewhurst (postcode GU5 9EN). This is one of the quieter Hurtwood car parks and a good choice when the Peaslake parks are full on busy weekends. The car park sits on the edge of Winterfold Heath, with the open heathland and woodland stretching away on all sides. Like all Hurtwood car parks, it is free and managed by the Friends of the Hurtwood; please use the donation box.",
                ],
                "image_url": "",
            },
            {
                "title": "Winterfold Old Quarries",
                "description": [
                    "The early section of the walk passes through an area dotted with old sandstone quarries, now largely reclaimed by birch scrub and heather. The honey-coloured Hurtwood Stone quarried here since the 12th century was prized for its hardness and used across Surrey in church and domestic building. The shallow depressions and low cliffs of exposed sandstone are distinctive and well worth pausing to examine — the layering of the Hythe Beds sandstone, laid down in shallow Cretaceous seas around 120 million years ago, is clearly visible in section.",
                ],
                "image_url": "",
            },
            {
                "title": "Reynard's Hill Viewpoint",
                "description": [
                    "The route climbs to the Reynard's Hill viewpoint, a small clearing offering panoramic views southward across the Weald to the line of the South Downs on the horizon. This is a less-visited viewpoint than those on Holmbury Hill or Pitch Hill but arguably the most peaceful, and on a weekday you may well have it to yourself. The name Reynard is the medieval name for a fox — the area has long been associated with foxes and is still home to them.",
                ],
                "image_url": "",
            },
            {
                "title": "Heathland Return",
                "description": [
                    "The return section crosses open heathland before re-entering the mixed woodland of Winterfold Wood. The heathland here is managed for its ecological value: lowland heath of this quality is a nationally scarce habitat, and the Hurtwood SSSI supports a range of specialist heathland species including stonechat, nightjar (listen for the distinctive churring call on summer evenings), and several scarce invertebrates. The path back to Car Park 5 is broad and well-defined, with the sandy Hythe Beds soil draining freely even after wet weather.",
                ],
                "image_url": "",
            },
        ],
    },
    {
        "slug": "hurtwood-shere-heath-walk",
        "title": "Shere Heath & The Hurtwood",
        "distance": "8 km",
        "duration": "2 hrs 15 min",
        "difficulty": "Moderate",
        "summary": "A varied circuit exploring the heathland fringes of the Hurtwood around Shere Heath and Farley Heath, with the option to visit the site of the most significant Roman temple in Surrey.",
        "image_url": "",
        "center": [51.1900, -0.4100],
        "zoom": 13,
        "waypoint_zoom": 15,
        "route": [
            [51.1990, -0.4050],  # Shere Heath start area
            [51.1950, -0.4050],
            [51.1920, -0.4080],
            [51.1900, -0.4100],
            [51.1870, -0.4140],
            [51.1850, -0.4180],  # Farley Heath Roman temple area
            [51.1860, -0.4220],
            [51.1880, -0.4190],
            [51.1910, -0.4130],
            [51.1940, -0.4090],
            [51.1990, -0.4050],  # Return
        ],
        "waypoint_coords": [
            [51.1990, -0.4050],
            [51.1900, -0.4100],
            [51.1850, -0.4180],
            [51.1880, -0.4190],
        ],
        "waypoints": [
            {
                "title": "Shere Heath",
                "description": [
                    "Shere Heath is the northern fringe of the Hurtwood, a mosaic of open heath and secondary birch woodland between the village of Shere and the main Hurtwood woodland block. The heathland here is part of the 3,000-acre SSSI managed by the Friends of the Hurtwood and is one of the largest remaining areas of Surrey heathland outside the Thursley and Chobham commons. The characteristic plants — heather, gorse, cross-leaved heath, and mat-grass — give it a distinctive purple-gold colouring from late July through September.",
                ],
                "image_url": "",
            },
            {
                "title": "Hurtwood Woodland",
                "description": [
                    "From Shere Heath the path enters the main Hurtwood woodland block, an extraordinary mix of ancient sessile oak and beech with the Scots pine that was introduced in the 18th century and now dominates much of the southern section. The understorey in the old oak sections contains rare plants including wood sorrel, wood anemone, and in some damp hollows, the delicate yellow flowers of greater celandine. The woodland also supports a significant population of roe deer and — less commonly seen — fallow deer.",
                ],
                "image_url": "",
            },
            {
                "title": "Farley Heath — Roman Temple",
                "description": [
                    "The optional detour to Farley Heath brings you to the site of the most significant Romano-British religious monument in Surrey. The Farley Heath Romano-Celtic temple was in use from before the end of the 1st century AD and may have marked the boundary between the territories of the Regnenses (of Sussex and east Surrey) and the Atrebates (of Hampshire). The temple was excavated in the Victorian era by antiquarian Martin Tupper, who recorded finding over 1,200 coins, bronze objects, pottery, and tile in the black mould of what appeared to be a deliberate burning around 450 AD.",
                    "The outer and inner walls of the rectangular temple have been clearly marked out in stone on the heath, making it easy to appreciate the scale and layout of the structure. The open heathland setting, with views across the surrounding woodland, gives a strong sense of why this elevated position would have been chosen for a place of communal religious importance. Farley Heath is also part of Blackheath Common, another area of high ecological value within the Hurtwood SSSI.",
                ],
                "image_url": "",
            },
            {
                "title": "Heathland Circuit Return",
                "description": [
                    "The return section skirts the northern edge of the Hurtwood, crossing sections of regenerating heathland where management by the Friends of the Hurtwood has opened up the canopy to allow the heather and gorse to reassert themselves. Watch overhead for buzzards and kestrels, both resident in the Hurtwood in good numbers. The final section back toward Shere Heath can be linked directly to the village of Shere (approximately 1.5 km further north), where the White Horse pub and several cafés offer a very welcome finish.",
                ],
                "image_url": "",
            },
        ],
    },
]


# ─────────────────────────────────────────────────────────────────────────────
# HURTWOOD ESTATE — PLACES OF INTEREST
# ─────────────────────────────────────────────────────────────────────────────

PLACES_OF_INTEREST["hurtwood-estate"] = [
    {
        "slug": "holmbury-hill-fort",
        "name": "Holmbury Hill Iron Age Hillfort",
        "type": "ancient monument",
        "summary": "The summit of Holmbury Hill at 261 metres (856 ft) contains the well-preserved remains of an Iron Age hillfort dating from approximately 100 to 70 BC. Excavated in 1929, the fort appears to have functioned as a communal gathering and trading place rather than a permanent settlement, and was probably constructed by Celtic tribes of the Greensand Ridge. The defensive earthworks are clearly visible today: a double rampart system protects the western and northern slopes, with outer ditches originally around three metres deep, while the natural sandstone escarpments provided defence on the steeper eastern and southern sides. The summit gives panoramic views across the Weald to the South Downs and, on clear days, to the distant buildings of Canary Wharf to the north.",
        "image_url": "",
    },
    {
        "slug": "farley-heath-roman-temple",
        "name": "Farley Heath Roman Temple",
        "type": "ancient monument",
        "summary": "The most significant Romano-British religious site in Surrey sits on open heathland at Farley Heath, on the southern fringe of the Hurtwood SSSI. The Romano-Celtic temple was in use from at least the late 1st century AD, possibly marking the boundary between the territories of the Regnenses and Atrebates tribes. Victorian excavations by antiquarian Martin Tupper uncovered over 1,200 coins, bronze objects, pottery and tile, with evidence of destruction by fire around 450 AD. The outer and inner walls of the rectangular temple enclosure are marked out clearly in stone on the heathland and are freely accessible to visitors. The setting — open heath with long views and the hum of insects in summer — gives a vivid sense of why this elevated position was chosen for communal worship.",
        "image_url": "",
    },
    {
        "slug": "pitch-hill-viewpoint",
        "name": "Pitch Hill Viewpoint",
        "type": "viewpoint",
        "summary": "Pitch Hill rises to approximately 257 metres on a dramatic narrow sandstone spur above Ewhurst, affording some of the most spectacular panoramas in the Surrey Hills. The summit is an open sandstone terrace with a wooden viewing platform indicating landmarks across the Weald to the South Downs. The approach from Hurtwood Car Park 3 passes old sandstone quarries where the distinctive honey-coloured Hurtwood Stone — quarried here since the 12th century and used in buildings across Surrey — is exposed in section. The surrounding area contains some of the best mountain bike singletrack in south-east England, including the celebrated Supernova and Curly Wurly trails.",
        "image_url": "",
    },
    {
        "slug": "winterfold-wood",
        "name": "Winterfold Wood",
        "type": "woodland",
        "summary": "Winterfold Wood is one of the most diverse and atmospheric sections of the Hurtwood, combining ancient oak and beech woodland with Scots pine plantation, open heathland clearings, and old quarry hollows. The wood occupies the south-western section of the Hurtwood SSSI and is part of the 3,000-acre area managed by the Friends of the Hurtwood for public access and ecological benefit. The varied structure — tall conifers giving way to open heath and then back to ancient broadleaf — supports an exceptional range of wildlife including roe deer, woodpeckers, treecreepers, and on summer evenings the churring call of the nightjar. Reynard's Hill within the wood gives a fine elevated viewpoint southward across the Weald.",
        "image_url": "",
    },
    {
        "slug": "hurtwood-heathland-sssi",
        "name": "Hurtwood Heathland SSSI",
        "type": "wildlife habitat",
        "summary": "The Hurtwood Site of Special Scientific Interest encompasses approximately 3,000 acres of lowland heath, ancient woodland, and secondary birch scrub across Holmbury Hill, Pitch Hill, Winterfold, Shere Heath, Farley Heath, and part of Blackheath Common. Lowland heathland is one of Britain's most threatened habitats — less than 20% of the area that existed 200 years ago survives — and the Hurtwood SSSI is one of the largest and best-managed examples in Surrey. The characteristic heather, gorse, and cross-leaved heath flora supports specialist species including stonechat, nightjar, silver-studded blue butterfly, and the rare heath tiger beetle. The Friends of the Hurtwood carry out ongoing management including scrub clearance, bracken control, and coppicing to maintain the open heathland character.",
        "image_url": "",
    },
    {
        "slug": "peaslake-village",
        "name": "Peaslake Village",
        "type": "village",
        "summary": "The small village of Peaslake is tucked into a valley at the heart of the Hurtwood, surrounded on all sides by the wooded Greensand Hills. It has evolved into one of the most popular walking and mountain biking hubs in south-east England, with two large Hurtwood car parks within easy reach, a celebrated village stores (famous for its cheese straws and homemade pork-and-leek slices), the Hurtwood Inn pub, and Surrey Hills Bike Rental operating from the Riders Hub. Despite the weekend crowds, the village retains a genuine community character and a real sense of place — narrow lanes, old stone cottages, and the sound of birdsong just yards from the car park. The public has had access to the surrounding Hurtwood since 1926, a right given by Reginald Bray, the then Lord of the Manor of Shere.",
        "image_url": "",
    },
    {
        "slug": "greensand-way",
        "name": "The Greensand Way",
        "type": "long-distance route",
        "summary": "The Greensand Way is a 108-mile long-distance walking and cycling route running from Haslemere in Surrey to Hamstreet in Kent, following the Greensand Ridge — a distinct geological band of Upper Greensand and Hythe Beds sandstone that runs parallel to and south of the North Downs. Through the Hurtwood, the route passes over Holmbury Hill and Pitch Hill, two of its most dramatic sections, offering outstanding views in both directions and linking the estate's main points of interest. The Hurtwood section is widely regarded as one of the finest stretches of walking in Surrey. Green GW waymarker arrows are posted on gates and posts throughout the estate.",
        "image_url": "",
    },
]


# ─────────────────────────────────────────────────────────────────────────────
# LOSELEY PARK — WALKS
# ─────────────────────────────────────────────────────────────────────────────

WALKS["loseley-park"] = [
    {
        "slug": "loseley-estate-circular",
        "title": "Loseley Estate Circular",
        "distance": "4.5 km",
        "duration": "1 hr 15 min",
        "difficulty": "Easy",
        "summary": "A lovely self-contained circuit of the Loseley estate exploring the Front Park, the restored lakes, the wildflower meadow, and the moat walk around the Walled Garden — ideal as a standalone walk or as a complement to a house tour.",
        "image_url": "",
        "center": [51.2109, -0.5889],
        "zoom": 14,
        "waypoint_zoom": 16,
        "route": [
            [51.2109, -0.5889],  # Loseley House main entrance area
            [51.2100, -0.5870],
            [51.2090, -0.5855],  # Lower Lake
            [51.2080, -0.5870],
            [51.2075, -0.5890],
            [51.2080, -0.5910],  # Wildflower meadow
            [51.2095, -0.5920],
            [51.2105, -0.5910],  # Moat walk / Walled Garden
            [51.2115, -0.5905],
            [51.2109, -0.5889],  # Return
        ],
        "waypoint_coords": [
            [51.2109, -0.5889],
            [51.2085, -0.5858],
            [51.2080, -0.5910],
            [51.2105, -0.5910],
        ],
        "waypoints": [
            {
                "title": "Loseley House",
                "description": [
                    "Begin at Loseley House, one of the finest Elizabethan manor houses in England, built between 1562 and 1568 by Sir William More using stone salvaged from the ruins of Waverley Abbey. The house has been home to the More-Molyneux family ever since and is still lived in today — it has a remarkably intimate and personal atmosphere quite unlike the large managed properties of the National Trust. Queen Elizabeth I visited five times, staying for five days in August 1583 on one occasion. James I visited twice, and the drawing room's gilded ceiling was commissioned in anticipation of one of his visits.",
                    "The house tour (included with the combined house and garden ticket) takes approximately 45 minutes and is guided, covering the Great Hall with its panelling from Henry VIII's Nonsuch Palace, the chalk fireplace designed by Hans Holbein, the Grinling Gibbons carvings, and a collection of royal portraits including one of the few surviving likenesses of Anne Boleyn. Allow at least four hours in total to see both the house and the gardens fully.",
                ],
                "image_url": "",
            },
            {
                "title": "The Lakes",
                "description": [
                    "The path from the house leads south-west across the Front Park to the restored estate lakes, a pair of historic water bodies that fell into disrepair over the 20th century and were fully restored in recent years. The restoration opened up clear views of Loseley House from across the lower lake and significantly improved water quality. The lakes are now a productive wildlife habitat: kingfishers have returned and can often be seen hunting along the margins, and dragonflies and damselflies are plentiful in summer. New picnic benches along the footpath make this one of the best spots on the estate for a quiet pause.",
                ],
                "image_url": "",
            },
            {
                "title": "Wildflower Meadow",
                "description": [
                    "Beyond the lower lake, the path enters the wildflower meadow planted in 2005 on the far side of the moat. The meadow is at its best from late May through July when ox-eye daisies, knapweed, ragged robin, and field scabious are in full bloom, but it retains interest from early spring with cowslips and early purple orchid. Butterflies — including marbled white, ringlet, and common blue — are abundant on warm days, and the meadow provides important foraging habitat for bees and other pollinators from the estate's own wildflower planting programme. Listen for grasshopper warblers and whitethroats in the surrounding hedgerows.",
                ],
                "image_url": "",
            },
            {
                "title": "Moat Walk & Walled Garden",
                "description": [
                    "The final section of the circuit follows the moat walk, the charming path that runs around the perimeter of the historic moat surrounding the Walled Garden. The moat itself pre-dates the current house and gives the garden a particularly atmospheric quality — the reflections of the old stone wall in the still water, and the sound of the occasional moorhen, are genuinely memorable. The 2.5-acre Walled Garden on your right contains five themed gardens: the rose garden with over 1,000 old-fashioned rose bushes (at its peak in June), a formal herb garden, a white garden with fountain, a fruit and flower garden, and a spectacular organic vegetable garden. The mulberry tree in the garden is believed to have been planted by Elizabeth I herself.",
                    "The Courtyard Tearoom just inside the estate entrance serves lunches and teas from 11am daily during the open season. The on-estate gift shop and plant sales area — where plants grown in the Walled Garden are propagated for sale — are open from 9am to 4pm. Plants from the garden are among the best souvenirs of a visit.",
                ],
                "image_url": "",
            },
        ],
    },
    {
        "slug": "compton-littleton-loseley",
        "title": "Compton, Littleton & Loseley",
        "distance": "7.6 km",
        "duration": "2 hrs",
        "difficulty": "Moderate",
        "summary": "A varied circular walk through the quiet Surrey countryside west of Guildford, linking the Arts and Crafts village of Compton — home to Watts Gallery — with the Loseley estate boundary and the small hamlet of Littleton.",
        "image_url": "",
        "center": [51.2140, -0.5750],
        "zoom": 13,
        "waypoint_zoom": 15,
        "route": [
            [51.2146, -0.5540],  # Compton village / Watts Gallery
            [51.2130, -0.5580],
            [51.2110, -0.5620],
            [51.2095, -0.5680],
            [51.2090, -0.5760],
            [51.2095, -0.5850],  # Loseley estate boundary
            [51.2110, -0.5870],
            [51.2140, -0.5820],  # Littleton
            [51.2160, -0.5710],
            [51.2155, -0.5620],
            [51.2146, -0.5540],  # Return
        ],
        "waypoint_coords": [
            [51.2146, -0.5540],
            [51.2090, -0.5760],
            [51.2110, -0.5870],
            [51.2140, -0.5820],
        ],
        "waypoints": [
            {
                "title": "Compton & Watts Gallery",
                "description": [
                    "Begin the walk in the village of Compton, one of Surrey's most distinctive villages and home to Watts Gallery — Artists' Village, a remarkable Arts and Crafts heritage site on Down Lane (GU3 1DQ). The gallery houses the largest collection of works by the Victorian painter and sculptor G.F. Watts, and the associated buildings include Limnerslease (the Watts' family home), a Mortuary Chapel designed by Mary Watts that is a remarkable exercise in Celtic Revival decoration, a working studio, tea shop, and a woodland playground called the Verey Playwood. Watts Gallery is open Wednesday to Sunday; check opening times before visiting as they vary by season.",
                    "The Withies Inn is also in Compton — a 16th-century pub and restaurant that has built a serious reputation for well-sourced, classically prepared British food. It is rated 4.4 stars by OpenTable users and is one of the best restaurants in the Guildford area.",
                ],
                "image_url": "",
            },
            {
                "title": "Surrey Field Paths",
                "description": [
                    "From Compton, the route follows quiet field paths and farm tracks south-eastward across the open Surrey countryside toward the Loseley estate. This section of the walk traverses a landscape of mixed arable and pastoral farming — the Hog's Back chalk ridge is visible to the north — and the paths are well-maintained and largely free of the weekend crowds that gather further east in the Surrey Hills. Expect livestock, particularly sheep and cattle, in the fields from spring through autumn.",
                ],
                "image_url": "",
            },
            {
                "title": "Loseley Estate Boundary",
                "description": [
                    "The walk reaches the western boundary of the Loseley estate, skirting the parkland and offering distant views of Loseley House across the Front Park. The estate's 1,400 acres of parkland, farmland, and gardens surround the house on all sides and contribute strongly to the character of the landscape between Guildford and Godalming. The estate has been farmed by the More-Molyneux family for over 450 years and is a working farm as well as a visitor attraction — you may see estate vehicles or farm machinery at work depending on the season.",
                ],
                "image_url": "",
            },
            {
                "title": "Littleton Return",
                "description": [
                    "The return leg passes through the tiny hamlet of Littleton, a scattering of old Surrey cottages that appears largely unchanged since the early 20th century. From Littleton the path climbs gently back toward Compton via the North Downs Way, which traverses this section of the chalk ridge. The views from the higher ground back across the Wey valley toward Guildford are particularly good on a clear day. Return to Watts Gallery for tea in the café (open Wednesday to Sunday, 10am to 5pm, with lunch 11am to 3pm).",
                ],
                "image_url": "",
            },
        ],
    },
    {
        "slug": "loseley-artington-river-wey",
        "title": "Loseley, Artington & River Wey",
        "distance": "7.2 km",
        "duration": "1 hr 50 min",
        "difficulty": "Easy",
        "summary": "A flat and rewarding circuit linking Loseley Park with the River Wey towpath, passing through the village of Artington and returning along the ancient drove road of the Pilgrim's Way.",
        "image_url": "",
        "center": [51.2200, -0.5720],
        "zoom": 13,
        "waypoint_zoom": 15,
        "route": [
            [51.2109, -0.5889],  # Loseley House
            [51.2130, -0.5850],
            [51.2160, -0.5800],  # Artington
            [51.2190, -0.5750],
            [51.2220, -0.5680],  # River Wey towpath
            [51.2240, -0.5580],
            [51.2210, -0.5530],
            [51.2180, -0.5550],
            [51.2150, -0.5600],
            [51.2130, -0.5700],
            [51.2109, -0.5889],  # Return
        ],
        "waypoint_coords": [
            [51.2109, -0.5889],
            [51.2160, -0.5800],
            [51.2220, -0.5680],
            [51.2180, -0.5550],
        ],
        "waypoints": [
            {
                "title": "Loseley Park",
                "description": [
                    "Begin at the Loseley Park visitor entrance. This walk does not require a garden or house ticket — the public footpath through the estate grounds is accessible separately. Follow the main track north-east from the house, passing through the Front Park with its veteran parkland trees, some of which are several hundred years old. The parkland was laid out in its present form in the 18th century and has the characteristic open, grazed character of a traditional English deer park, though deer are no longer kept here.",
                ],
                "image_url": "",
            },
            {
                "title": "Artington Village",
                "description": [
                    "The path enters the small village of Artington, a quiet residential settlement on the south-western edge of Guildford with a pleasant mix of old cottages and 20th-century houses. The Church of St Luke is a simple Victorian building in an attractive setting. The village is closely associated with the Loseley estate — the estate's farmland extends into the parish — and has a peaceful, off-the-beaten-track quality despite being only two miles from Guildford town centre.",
                ],
                "image_url": "",
            },
            {
                "title": "River Wey Towpath",
                "description": [
                    "The route drops to the River Wey, one of Surrey's major rivers and the first to be made navigable in England, in 1653. The Wey Navigations — a 20-mile system of river and canal linking Guildford to Weybridge — is now managed by the National Trust and remains open to canoes, narrowboats, and paddleboards. The towpath here is flat, wide, and easy to follow, offering good birdwatching (grey heron, kingfisher, reed bunting, and mute swan are all regular) and the soothing company of the river. In summer, waterlilies cover stretches of the slow-moving water.",
                ],
                "image_url": "",
            },
            {
                "title": "Return via Pilgrims' Way",
                "description": [
                    "The return from the river follows field paths south-westward, joining the approximate line of the Pilgrims' Way — the ancient route along the foot of the North Downs used by medieval pilgrims travelling between Winchester and Canterbury. This section gives good views back toward the North Downs chalk scarp to the north. The final kilometre returns across the Loseley parkland to the house. The Courtyard Tearoom is open for teas and lunches on arrival (open daily during the season from 11am).",
                ],
                "image_url": "",
            },
        ],
    },
    {
        "slug": "shalford-north-downs-loseley",
        "title": "Shalford, North Downs Way & Loseley",
        "distance": "11.7 km",
        "duration": "3 hrs 15 min",
        "difficulty": "Moderate",
        "summary": "A longer circuit from Shalford that climbs to the North Downs ridge for big views before sweeping south through the Loseley estate parkland and returning via field paths and the River Wey.",
        "image_url": "",
        "center": [51.2220, -0.5600],
        "zoom": 12,
        "waypoint_zoom": 14,
        "route": [
            [51.2290, -0.5550],  # Shalford village start
            [51.2310, -0.5450],
            [51.2330, -0.5380],
            [51.2350, -0.5320],  # North Downs / St Martha's Hill direction
            [51.2330, -0.5250],
            [51.2280, -0.5300],
            [51.2200, -0.5480],
            [51.2150, -0.5680],
            [51.2109, -0.5889],  # Loseley House
            [51.2130, -0.5850],
            [51.2200, -0.5750],
            [51.2260, -0.5650],
            [51.2290, -0.5550],  # Return
        ],
        "waypoint_coords": [
            [51.2290, -0.5550],
            [51.2350, -0.5320],
            [51.2109, -0.5889],
            [51.2200, -0.5750],
        ],
        "waypoints": [
            {
                "title": "Shalford",
                "description": [
                    "Start in the village of Shalford, south of Guildford on the A281, with parking available at the village car park. Shalford is a pleasant suburban village with the River Tillingbourne and Shalford Mill — a National Trust-managed 18th-century watermill — just off the main route and worth a short detour. The walk begins by heading eastward along field paths toward the chalk ridge of the North Downs.",
                ],
                "image_url": "",
            },
            {
                "title": "North Downs Ridge",
                "description": [
                    "The route climbs to the North Downs ridge, with panoramic views southward across the Wey valley toward the Greensand Hills and beyond to the South Downs on the horizon. The North Downs Way long-distance footpath traverses this section, waymarked with the distinctive acorn symbol of National Trails. The chalk grassland of the ridge supports specialist flora including horseshoe vetch, clustered bellflower, and in the right conditions the rare man orchid. In clear weather the views are among the best within easy reach of Guildford.",
                ],
                "image_url": "",
            },
            {
                "title": "Loseley Park",
                "description": [
                    "The descent from the North Downs brings the route into the Loseley estate, approaching the house from the north-east across the Front Park. This approach gives the best views of the house's characteristic stone facade, built from Waverley Abbey stone in the warm local buff colour. If you have purchased a garden or house ticket in advance, this is the point to enter the Walled Garden and take the house tour. The Courtyard Tearoom is open from 11am daily during the season.",
                ],
                "image_url": "",
            },
            {
                "title": "Return via River Wey",
                "description": [
                    "The return route heads north-east from Loseley across the parkland and then by field paths to the River Wey, picking up the towpath for the final stretch back toward Shalford. The towpath section is flat and easy, following the canalised river through a quietly beautiful landscape of water meadows and riverside willows. The Wey Navigations attract canoes and narrowboats throughout the season, and the towpath is popular with cyclists and dog walkers as well as walkers.",
                ],
                "image_url": "",
            },
        ],
    },
]


# ─────────────────────────────────────────────────────────────────────────────
# LOSELEY PARK — PLACES OF INTEREST
# ─────────────────────────────────────────────────────────────────────────────

PLACES_OF_INTEREST["loseley-park"] = [
    {
        "slug": "loseley-house",
        "name": "Loseley House",
        "type": "listed building",
        "summary": "Built between 1562 and 1568 from stone salvaged from the ruins of Waverley Abbey, Loseley House is one of England's finest Elizabethan manor houses and has been continuously occupied by the More-Molyneux family for over 450 years. It carries Grade I listed status. The interior is extraordinary: the Great Hall contains panelling from Henry VIII's Nonsuch Palace, carved panels from his banqueting tents, a minstrel's gallery, and Grinling Gibbons carvings. The drawing room features a chalk fireplace carved from a single piece of chalk to a design attributed to Hans Holbein, and a gilded ceiling commissioned for James I's visits. Queen Elizabeth I stayed at Loseley five times; the room she used is still called the Queen's Room. Guided tours of the house run daily from 11am during the open season (combined house and garden tickets available).",
        "image_url": "",
    },
    {
        "slug": "walled-garden",
        "name": "The Walled Garden",
        "type": "historic garden",
        "summary": "The 2.5-acre Walled Garden at Loseley is enclosed by stone walls of similar age to the house and is one of the finest examples of a traditional English walled garden in Surrey. It is laid out as five distinct garden 'rooms', each with its own character: the Rose Garden contains over 1,000 old-fashioned and heritage rose bushes and peaks in June; the White Garden features a central fountain and planting in silver and white; the Herb Garden is intensively planted with culinary and medicinal species; the Flower and Fruit Garden is a riot of colour in summer; and the Organic Vegetable Garden is a working kitchen garden of striking beauty. The design draws on the influence of Gertrude Jekyll, who lived at nearby Munstead Wood. An ancient mulberry tree in the garden is believed to have been planted by Elizabeth I. The moat walk around the garden perimeter is one of the loveliest short walks on the estate.",
        "image_url": "",
    },
    {
        "slug": "loseley-lakes",
        "name": "Loseley Lakes & Wildflower Meadow",
        "type": "wildlife habitat",
        "summary": "The estate's two historic lakes were restored in recent years after falling into disrepair, opening up clear views of the house from across the water and dramatically improving the ecological value of the landscape. Kingfishers — absent for many years — have returned to both lakes. Dragonflies and damselflies are abundant in summer, and the adjacent wildflower meadow, planted in 2005, supports significant populations of butterflies, bumblebees, and grassland birds. The meadow is at its most spectacular from late May to July, when ox-eye daisies, knapweed, field scabious, and ragged robin are in full bloom. New picnic benches along the lakeside footpath make this the ideal spot for a quiet lunch.",
        "image_url": "",
    },
    {
        "slug": "loseley-chapel-st-nicolas",
        "name": "The Loseley Chapel, St Nicolas' Church",
        "type": "listed building",
        "summary": "The More-Molyneux family's memorial chapel, dating from around 1550, is attached to the south side of St Nicolas' Church in Guildford town centre — one of the oldest buildings in Guildford. The chapel contains a remarkable collection of family monuments spanning four and a half centuries and is considered one of the finest private memorial chapels in Surrey. St Nicolas' Church itself, Grade II* listed, dates from the 10th century or earlier, though the present building was consecrated in 1876; it stands at the foot of Guildford High Street on the left bank of the River Wey. The Loseley Chapel is open to visitors by arrangement with the Parish Administrator.",
        "image_url": "",
    },
    {
        "slug": "watts-gallery-compton",
        "name": "Watts Gallery — Artists' Village, Compton",
        "type": "museum and gallery",
        "summary": "Watts Gallery — Artists' Village at Compton, approximately 1.5 miles from Loseley House, is one of Surrey's most distinctive heritage sites. The gallery houses the largest collection of works by the Victorian painter, sculptor, and symbolist G.F. Watts — best known for his monumental paintings Hope and Physical Energy — within the original purpose-built gallery of 1904. The surrounding Arts and Crafts village includes Limnerslease (the Watts' family home), a Mortuary Chapel decorated by Mary Watts in an extraordinary Celtic Revival style, a tea shop, gift shop, and 18 acres of woodland grounds. The Verey Playwood woodland playground makes it exceptionally good for family visits. Open Wednesday to Sunday.",
        "image_url": "",
    },
    {
        "slug": "silent-pool-distillery",
        "name": "Silent Pool Distillery & Bar",
        "type": "visitor attraction",
        "summary": "Silent Pool Distillers, approximately 6 miles from Loseley Park near Albury, sits on the banks of the legendary Silent Pool — a clear spring-fed lake on the Duke of Northumberland's Albury Estate. The distillery launched in 2014 and produces the award-winning Silent Pool Gin using 24 botanicals including local elderflower and honey, distilled in a hand-built copper still powered by a vintage wood-fired steam boiler. The glass-enclosed Terrace Bar opened in 2025 and offers a full menu of gin cocktails overlooking the pool, open Friday to Sunday without booking. Guided distillery tours and tasting masterclasses run Thursday to Sunday and cover the history of gin, the Silent Pool legend, and the four-stage distillation process.",
        "image_url": "",
    },
    {
        "slug": "loseley-park-film-location",
        "name": "Loseley Park Film & TV Locations",
        "type": "film location",
        "summary": "Loseley House has been used as a film and television location for over half a century, and its richly authentic Elizabethan interiors are in constant demand for period productions. Notable productions filmed here include The Crown (2016), The Favourite (2018), Rebecca (2020), and Belgravia (2020), as well as earlier films A Dandy in Aspic (1968) and The Legacy (1978). The estate's combination of Tudor architecture, walled gardens, open parkland, and lake makes it exceptionally versatile, and the More-Molyneux family have long welcomed production companies to the house.",
        "image_url": "",
    },
]


# ─────────────────────────────────────────────────────────────────────────────
# LOSELEY PARK — PLACES TO EAT
# ─────────────────────────────────────────────────────────────────────────────

PLACES_TO_EAT["loseley-park"] = [
    {
        "slug": "courtyard-tearoom-loseley",
        "name": "The Courtyard Tearoom, Loseley Park",
        "type": "tearoom",
        "rating": 4.2,
        "guide_price": "£15",
        "open_today": "Sun–Thu 11–17",
        "distance": "on estate",
        "coords": [51.2109, -0.5889],
        "summary": "The estate's own Courtyard Tearoom serves lunches, afternoon teas, homemade cakes, and hot drinks daily during the open season. Set in the courtyard of the historic house, it is a pleasant stop whether you are visiting the gardens only or completing a full house tour. Cream teas are a particular speciality. Check the estate website for current seasonal opening hours.",
        "image_url": "",
    },
    {
        "slug": "the-farmm-loseley",
        "name": "The Farmm Shop & Café",
        "type": "farm shop",
        "rating": 4.3,
        "guide_price": "£12",
        "open_today": "Tue–Sat 9–17",
        "distance": "2 min drive",
        "coords": [51.2140, -0.5800],
        "summary": "The Farmm is a well-regarded farm shop and café on the Loseley estate (New Pond Road, GU3 1BN), stocking locally sourced and British produce including estate-grown vegetables, rare-breed English Longhorn beef, homemade preserves, fresh flowers, and interior homeware. The café serves what regulars describe as some of the best coffee in the area. Monthly Saturday produce markets in the tithe barn feature homemade cakes, chutneys, and seasonal fruit and vegetables from the estate gardens.",
        "image_url": "",
    },
    {
        "slug": "withies-inn-compton",
        "name": "The Withies Inn",
        "type": "pub",
        "rating": 4.4,
        "guide_price": "£40",
        "open_today": "Tue–Sun 12–14:30, 19–21",
        "distance": "8 min drive",
        "coords": [51.2146, -0.5540],
        "summary": "A 16th-century inn in the tiny hamlet of Compton, subtly modernised to accommodate what has become one of the best restaurant-pubs in Surrey. Low beams, an eclectic interior, and a relaxed atmosphere set the scene for an extensive menu of carefully prepared, locally sourced British classics. Rated 4.4 stars by nearly 900 OpenTable diners. Booking strongly advised for dinner and weekend lunches.",
        "image_url": "",
    },
    {
        "slug": "stag-on-the-river",
        "name": "The Stag on the River",
        "type": "pub",
        "rating": 4.2,
        "guide_price": "£38",
        "open_today": "Mon–Sun 12–21",
        "distance": "10 min drive",
        "coords": [51.1985, -0.5950],
        "summary": "A handsome 17th-century riverside inn at Lower Eashing, near Godalming, on the banks of the River Wey. The Stag combines rustic charm — exposed beams, open fires — with accomplished seasonal British cooking that celebrates local produce. The sun-drenched terrace overlooking the water is one of the finest outdoor dining spots in Surrey. Rated by the Good Hotel Guide. Seven bedrooms available for overnight stays.",
        "image_url": "",
    },
    {
        "slug": "fox-and-finch-godalming",
        "name": "The Fox & Finch",
        "type": "restaurant",
        "rating": 4.3,
        "guide_price": "£42",
        "open_today": "Tue–Sun 12–15, 18–22",
        "distance": "12 min drive",
        "coords": [51.1860, -0.6100],
        "summary": "A stylish gastropub in the heart of Godalming town centre, led by head chef Simon White who cooks over a charcoal Bertha Oven in the rear garden — the results are excellent, with a focus on bold flavours and high-quality local sourcing. The Sunday roast has a strong following. Lively atmosphere, good wine list, and a welcoming space.",
        "image_url": "",
    },
    {
        "slug": "watts-gallery-tea-shop",
        "name": "Watts Gallery Tea Shop",
        "type": "café",
        "rating": 4.0,
        "guide_price": "£16",
        "open_today": "Wed–Sun 10–17, lunch 11–15",
        "distance": "8 min drive",
        "coords": [51.2146, -0.5540],
        "summary": "The café at Watts Gallery — Artists' Village in Compton serves homemade, locally sourced lunches (soups, salads, Welsh Rarebit) and a full range of teas, coffees, and cakes. Set within the Arts and Crafts buildings of the gallery complex, it is a pleasant lunch stop in its own right and an excellent complement to visiting the gallery and Mortuary Chapel. The children's menu makes it suitable for family visits.",
        "image_url": "",
    },
    {
        "slug": "ragged-robin-godalming",
        "name": "The Ragged Robin",
        "type": "pub",
        "rating": 4.1,
        "guide_price": "£35",
        "open_today": "Mon–Sun 12–22",
        "distance": "12 min drive",
        "coords": [51.1880, -0.6080],
        "summary": "A family and dog-friendly gastro pub with bedrooms on the edge of Godalming's historic town centre, set in a riverside location on the Wey. Part of the Heartwood Inns group and awarded a three-star Food Made Good rating from the Sustainable Restaurant Association. Broad menu of honest British food, good ales, and a spacious terrace. Reliably good value for the area.",
        "image_url": "",
    },
]


# ─────────────────────────────────────────────────────────────────────────────
# LOSELEY PARK — FUN FOR KIDS
# ─────────────────────────────────────────────────────────────────────────────

FUN_FOR_KIDS["loseley-park"] = [
    {
        "slug": "walled-garden-explorer",
        "name": "Walled Garden Explorer",
        "type": "Outdoor Activity",
        "distance": "on estate",
        "coords": [51.2109, -0.5889],
        "summary": "The 2.5-acre Walled Garden is divided into five distinct 'rooms', each different enough to keep children genuinely engaged as they move between them. The rose garden, vegetable garden, herb garden, and white garden each have their own character, scale, and sensory appeal — different smells, textures, colours, and sounds. The moat walk around the perimeter adds an extra dimension, and the wildflower meadow just beyond the moat is brilliant for butterfly spotting in summer. Best for children aged 4 and upward; younger children in buggies will manage the paths comfortably.",
        "image_url": "",
    },
    {
        "slug": "lake-wildlife-walk",
        "name": "Lake & Wildlife Walk",
        "type": "Wildlife",
        "distance": "on estate",
        "coords": [51.2090, -0.5858],
        "summary": "The restored estate lakes are an ideal introduction for children to British freshwater wildlife. Kingfishers hunt along the margins and can often be spotted with patience — look for a flash of electric blue low over the water. Dragonflies and damselflies are abundant in summer, and the wildflower meadow edges provide excellent butterfly hunting. New picnic benches alongside the lake make it an easy base for a family picnic. Children aged 5 and over will enjoy hunting for wildlife with a simple identification sheet (available from the estate).",
        "image_url": "",
    },
    {
        "slug": "watts-gallery-verey-playwood",
        "name": "Verey Playwood at Watts Gallery",
        "type": "Outdoor Activity",
        "distance": "8 min drive",
        "coords": [51.2146, -0.5540],
        "summary": "The Verey Playwood is a natural woodland playground at Watts Gallery — Artists' Village in Compton, making the most of 18 acres of woodland with rope swings, stepping stones, and den-building opportunities. A genuinely lovely outdoor space for children of all ages that avoids the plastic-and-primary-colours aesthetic of most commercial play areas. The gallery itself runs family trails, clay workshops, and interactive activities throughout the year. Buggy-friendly pathways, baby changing, and a children's menu in the café. Particularly good for ages 4–12.",
        "image_url": "",
    },
    {
        "slug": "loseley-house-tour",
        "name": "Loseley House Guided Tour",
        "type": "Museum",
        "distance": "on estate",
        "coords": [51.2109, -0.5889],
        "summary": "The guided house tour (approximately 45 minutes, included with the combined ticket) brings Loseley's extraordinary history to life with stories of Elizabeth I, Henry VIII's furniture, and the chalk fireplace attributed to Holbein. Children who enjoy history — and those who simply enjoy grand rooms with good stories — will find it engaging. Guides are experienced at adapting their commentary for younger visitors. Best for children aged 7 and over; under 5s free.",
        "image_url": "",
    },
    {
        "slug": "moat-walk-wildlife",
        "name": "Moat Walk & Pond Dipping",
        "type": "Wildlife",
        "distance": "on estate",
        "coords": [51.2105, -0.5910],
        "summary": "The historic moat surrounding the Walled Garden is home to moorhens, coots, and a variety of aquatic invertebrates. The moat walk path runs right alongside the water's edge and offers close views of the waterfowl, particularly in spring when adults are feeding young chicks. Informal pond dipping along the moat is possible with a simple net — children reliably find water boatmen, pond skaters, freshwater snails, and occasionally newt larvae. Suitable for all ages; push-chair-friendly surface.",
        "image_url": "",
    },
    {
        "slug": "wildflower-meadow-butterflies",
        "name": "Wildflower Meadow — Butterfly Hunting",
        "type": "Wildlife",
        "distance": "on estate",
        "coords": [51.2080, -0.5910],
        "summary": "The 2005-planted wildflower meadow beyond the moat is one of the estate's most rewarding spots for children interested in nature. From late May through August, the meadow supports marbled white, ringlet, common blue, small tortoiseshell, and on warm days the spectacular chalk hill blue butterfly. A simple identification sheet helps children tick off species. The meadow is also home to several grasshopper species — children enjoy the hunt for them in the tall grass. Ages 4 and upward.",
        "image_url": "",
    },
    {
        "slug": "the-farmm-ice-cream",
        "name": "Ice Cream at The Farmm",
        "type": "Food & Drink",
        "distance": "2 min drive",
        "coords": [51.2140, -0.5800],
        "summary": "The Farmm shop and café on the estate road serves Loseley ice cream — the famous Surrey Hills brand originally made on the Loseley estate from Jersey cream — alongside its own baked goods and locally sourced food. An ice cream from The Farmm is a near-mandatory part of any Loseley Park family visit. The café also sells hot drinks and homemade cakes, and the shop stocks local produce including estate-grown vegetables and freshly baked bread.",
        "image_url": "",
    },
]


# ─────────────────────────────────────────────────────────────────────────────
# LOSELEY PARK — SHOPPING
# ─────────────────────────────────────────────────────────────────────────────

SHOPPING["loseley-park"] = [
    {
        "slug": "loseley-estate-gift-shop",
        "name": "Loseley Estate Gift Shop",
        "type": "Gift Shop",
        "distance": "on estate",
        "coords": [51.2109, -0.5889],
        "hours": "Mon–Sun 9–16",
        "website": "https://loseleypark.co.uk",
        "description": "The estate's own gift shop sells a curated range of Loseley-branded gifts, books about the house and garden, prints, stationery, and locally produced items. A good source of well-considered souvenirs that are more directly connected to the estate than typical visitor centre fare. Located at the estate entrance, open during house and garden visiting hours.",
        "image_url": "",
    },
    {
        "slug": "loseley-plant-sales",
        "name": "Loseley Plant Sales",
        "type": "Garden Centre",
        "distance": "on estate",
        "coords": [51.2109, -0.5889],
        "hours": "Open during garden season — check estate website",
        "website": "https://loseleypark.co.uk",
        "description": "Plants propagated from the Walled Garden are sold in the plant sales area alongside the greenhouses, making this one of the few places in Surrey where you can buy cultivars directly descended from a historically significant garden collection. The rose garden — with its 1,000-plus heritage and old-fashioned bushes — is particularly well represented. Plant sales are open seasonally; check the estate website for current availability.",
        "image_url": "",
    },
    {
        "slug": "the-farmm-shop",
        "name": "The Farmm Shop",
        "type": "Farm Shop",
        "distance": "2 min drive",
        "coords": [51.2140, -0.5800],
        "hours": "Tue–Sat 9–17",
        "website": "https://www.thefarmm.co.uk",
        "description": "A well-stocked farm shop and café on the Loseley estate (Mellersh Farm, New Pond Road, GU3 1BN) selling locally sourced produce including estate-grown seasonal vegetables, rare-breed English Longhorn beef (available in 5 kg and 10 kg boxes), homemade preserves and chutneys, fresh flowers, and interior accessories. Monthly Saturday markets in the tithe barn feature additional homemade goods. Also operates stalls at Guildford Market and Farncombe Market.",
        "image_url": "",
    },
    {
        "slug": "silent-pool-distillers-shop",
        "name": "Silent Pool Distillers Shop & Bar",
        "type": "Specialist Shop",
        "distance": "15 min drive",
        "coords": [51.2213, -0.4540],
        "hours": "Thu–Sun 10–18 (bar Fri 12–17, Sat 12–19, Sun 12–17)",
        "website": "https://silentpooldistillers.com",
        "description": "The distillery shop at Silent Pool near Albury sells the full range of Silent Pool Gin products alongside other small-batch spirits including Wry Vodka and Admiral Collingwood Navy Gin. The glass-enclosed Terrace Bar overlooks the legendary Silent Pool and serves cocktails, gin tastings, and light food. Distillery tours and masterclasses (gin-making, bee-keeping, Martini masterclass) run Thursday to Sunday. One of the best visitor experiences in the wider Guildford area and an excellent choice for a gift.",
        "image_url": "",
    },
    {
        "slug": "loseley-bakery",
        "name": "Loseley Bakery (Estate Stockists)",
        "type": "Food Producer",
        "distance": "on estate",
        "coords": [51.2109, -0.5889],
        "hours": "Supplied through on-site café and local stockists",
        "website": "https://www.loseleybakery.co.uk",
        "description": "Loseley Bakery operates from the estate, producing hand-baked cakes, quiches, scones, and luxury ice cream (including Loseley and Marshfield brands) supplied to cafés and retailers within a 30-mile radius of Guildford. Estate-baked goods are available through the on-site Courtyard Tearoom and The Farmm shop. Look out for the vintage Loseley ice cream trailer, which operates at estate events.",
        "image_url": "",
    },
]


# ── Highclere Castle & Beaulieu Estate ────────────────────────────────────────────────────

WALKS["highclere-castle"] = [
    {
        "slug": "beacon-hill",
        "title": "Beacon Hill Iron Age Fort",
        "distance": "4.5 km",
        "duration": "1.5 hrs",
        "difficulty": "Moderate",
        "summary": "A bracing climb to the summit of Beacon Hill — an Iron Age hillfort at 261 m — with sweeping views across the Highclere estate and far into Hampshire and Berkshire.",
        "image_url": "",
        "center": [51.3230, -1.3620],
        "zoom": 14,
        "waypoint_zoom": 16,
        "route": [
            [51.3162,-1.3520],[51.3170,-1.3530],[51.3180,-1.3545],[51.3192,-1.3560],
            [51.3205,-1.3575],[51.3218,-1.3590],[51.3228,-1.3602],[51.3237,-1.3612],
            [51.3245,-1.3620],[51.3252,-1.3628],[51.3258,-1.3635],[51.3263,-1.3640],
            [51.3258,-1.3635],[51.3252,-1.3628],[51.3245,-1.3620],[51.3237,-1.3612],
            [51.3228,-1.3602],[51.3218,-1.3590],[51.3205,-1.3575],[51.3192,-1.3560],
            [51.3180,-1.3545],[51.3170,-1.3530],[51.3162,-1.3520]
        ],
        "waypoint_coords": [
            [51.3162, -1.3520],
            [51.3200, -1.3567],
            [51.3263, -1.3640],
            [51.3230, -1.3605]
        ],
        "waypoints": [
            {
                "title": "Beacon Hill Car Park",
                "description": [
                    "The walk begins at the National Trust car park at the foot of Beacon Hill, signed off the A34 just south of Highclere village. The car park sits in a shallow hollow of chalk downland — already above the surrounding farmland — and gives an immediate sense of the open, wind-scoured country ahead. The postcode for the car park is RG20 9LR.",
                    "From the rear of the car park, pass through the gate and begin climbing. The path steepens almost immediately, through a mix of chalk grassland and scrub. In spring and early summer the hillside is carpeted with cowslips, and the song of skylarks rises almost continuously from the open ground. In autumn, the smells of chalk and damp bracken make this a particularly atmospheric start to any walk.",
                ],
                "image_url": ""
            },
            {
                "title": "The Iron Age Ramparts",
                "description": [
                    "As you climb higher the great earthwork ramparts of the Iron Age hillfort become visible — a series of deep, concentric ditches cut into the chalk around 700 BC, now softened by two and a half millennia of weathering into gentle curves that still dominate the hilltop. The fort would have been a commanding presence across the surrounding countryside, its defenders able to see for many miles in every direction.",
                    "The inner ditch and bank are the best preserved, and it is worth taking a slow circuit of the perimeter to appreciate their full scale. The enclosure covers about six hectares — large enough to have sheltered a substantial community of Iron Age Britons along with their livestock. Archaeological finds from the site include pottery, animal bones, and the occasional iron tool, most of which are now in the Hampshire Cultural Trust collections in Winchester.",
                ],
                "image_url": ""
            },
            {
                "title": "The Summit Viewpoint",
                "description": [
                    "The summit of Beacon Hill at 261 metres is one of the great viewpoints of Hampshire. On a clear day the view extends across the Hampshire Downs in every direction — south towards Winchester and the distant glint of Southampton Water, north into the Berkshire Downs, and west toward the edge of Salisbury Plain. Most compellingly, the view to the north-east drops directly down onto the Highclere Estate, with the Victorian towers of Highclere Castle rising magnificently from the parkland trees, exactly as it appears in the opening credits of Downton Abbey.",
                    "A Bronze Age burial mound crowns the very summit — one of a number of round barrows on this ridge that predate the Iron Age fort by more than a thousand years. The barrow is fenced but clearly visible, a quiet reminder that this hilltop has been a place of significance for at least four thousand years.",
                ],
                "image_url": ""
            },
            {
                "title": "Old Burghclere & Return",
                "description": [
                    "Descend via the eastern flank of the hill toward the hamlet of Old Burghclere, whose flint-walled cottages and medieval church of St Mary sit in a sheltered combe below the fort. The church is one of the oldest in Hampshire and contains some remarkable carved stonework in the chancel — it is usually unlocked during daylight hours and is well worth five minutes.",
                    "Return to the car park by retracing the route up the escarpment, or by taking the lower bridleway that skirts the base of the hill through mixed woodland. The bridleway adds roughly a kilometre to the walk but is sheltered and pleasant in wet weather. Either way, allow around thirty minutes for the descent from the summit.",
                ],
                "image_url": ""
            },
        ]
    },
    {
        "slug": "highclere-park-public-walk",
        "title": "Highclere Park & Dunsmere Lake",
        "distance": "5 km",
        "duration": "1.5 hrs",
        "difficulty": "Easy",
        "summary": "A gentle circuit through the Capability Brown parkland, skirting the woods above Dunsmere Lake and passing the Temple of Diana — open during the summer season.",
        "image_url": "",
        "center": [51.3275, -1.3600],
        "zoom": 14,
        "waypoint_zoom": 16,
        "route": [
            [51.3275,-1.3600],[51.3280,-1.3615],[51.3285,-1.3630],[51.3288,-1.3650],
            [51.3290,-1.3670],[51.3288,-1.3690],[51.3282,-1.3705],[51.3274,-1.3712],
            [51.3265,-1.3710],[51.3258,-1.3700],[51.3252,-1.3688],[51.3248,-1.3672],
            [51.3250,-1.3655],[51.3255,-1.3638],[51.3262,-1.3622],[51.3268,-1.3610],
            [51.3275,-1.3600]
        ],
        "waypoint_coords": [
            [51.3275, -1.3600],
            [51.3285, -1.3658],
            [51.3265, -1.3710],
            [51.3255, -1.3638]
        ],
        "waypoints": [
            {
                "title": "The Castle & Formal Gardens",
                "description": [
                    "The walk begins at the castle's main visitor entrance and sets off southward through the formal gardens, which are planted in a style that reflects the Victorian taste of the 3rd Earl of Carnarvon, who commissioned Sir Charles Barry — the architect of the Houses of Parliament — to rebuild the house in its current Italianate Gothic form between 1839 and 1842. The gardens immediately around the castle are laid to smooth grass terraces edged with seasonal bedding and herbaceous borders of considerable beauty.",
                    "Looking back from the first terrace, the south front of the castle rises against the sky in a series of towers and turrets that have become one of the most recognised silhouettes in English country house architecture. It is worth pausing here before the walk takes you into the wider parkland.",
                ],
                "image_url": ""
            },
            {
                "title": "The Capability Brown Parkland",
                "description": [
                    "The parkland surrounding the castle was designed by Lancelot 'Capability' Brown in 1770–71 and is listed Grade I on the Historic England Register of Parks and Gardens. Brown's genius here, as elsewhere, was in creating a landscape that appears entirely natural while being entirely artificial — every copse, every swell of ground, every view has been calculated to appear as if nature arranged it herself.",
                    "The park is a patchwork of wood pasture, open grassland, and veteran oak and cedar trees. Many of the cedars of Lebanon visible from the castle terrace were planted in the 18th century and are now among the finest specimens in England. In summer the parkland is grazed by cattle and a small herd of deer, adding to the atmosphere of a working, breathing estate rather than a museum piece.",
                ],
                "image_url": ""
            },
            {
                "title": "Temple of Diana & Dunsmere Lake",
                "description": [
                    "The path descends to the southern end of Dunsmere Lake — one of two lakes in the parkland — and continues to the Temple of Diana, a circular garden building constructed in the late 18th century with Ionic columns salvaged from Devonshire House in Piccadilly. The temple stands on a low rise overlooking the lake and the wooded hillside beyond, and the view back across the water toward the castle is one of the estate's finest.",
                    "Dunsmere Lake is fringed by reed beds and patches of marsh that support a wide range of wildfowl. Mandarin ducks are regularly seen here, along with the more familiar mallard, tufted duck, and grey heron. In spring, great crested grebes perform their extraordinary courtship displays on the open water — a spectacular thing to stumble upon on a quiet walk.",
                ],
                "image_url": ""
            },
            {
                "title": "The Woodland Path & Return",
                "description": [
                    "The return leg follows a broad woodland path along the eastern edge of the park, passing through mixed planting of beech, oak, and sweet chestnut. At intervals, gaps in the trees frame carefully composed views back toward the castle — a characteristic Capability Brown device that ensures the house is always present as the emotional centre of the landscape.",
                    "As you near the castle on the return, look out for the Ha-ha — the sunken wall that runs along the edge of the formal garden, designed to keep livestock out of the pleasure grounds without breaking the view from the castle windows. It is one of the best-preserved examples in Hampshire and easy to miss if you are not looking for it.",
                ],
                "image_url": ""
            },
        ]
    },
    {
        "slug": "wayfarers-walk-sidown-hill",
        "title": "Wayfarer's Walk & Sidown Hill",
        "distance": "8 km",
        "duration": "2.5 hrs",
        "difficulty": "Moderate",
        "summary": "A fine circular walk along a section of the Wayfarer's Walk long-distance trail, climbing Sidown Hill through the Highclere Estate with wide views across the North Hampshire Downs.",
        "image_url": "",
        "center": [51.3180, -1.3780],
        "zoom": 13,
        "waypoint_zoom": 15,
        "route": [
            [51.3140,-1.3680],[51.3148,-1.3700],[51.3158,-1.3722],[51.3165,-1.3740],
            [51.3170,-1.3760],[51.3172,-1.3782],[51.3175,-1.3802],[51.3180,-1.3818],
            [51.3185,-1.3832],[51.3192,-1.3842],[51.3200,-1.3848],[51.3208,-1.3845],
            [51.3215,-1.3838],[51.3220,-1.3825],[51.3218,-1.3808],[51.3212,-1.3792],
            [51.3205,-1.3775],[51.3198,-1.3760],[51.3192,-1.3742],[51.3185,-1.3722],
            [51.3178,-1.3702],[51.3168,-1.3688],[51.3155,-1.3680],[51.3140,-1.3680]
        ],
        "waypoint_coords": [
            [51.3140, -1.3680],
            [51.3172, -1.3780],
            [51.3200, -1.3848],
            [51.3198, -1.3760]
        ],
        "waypoints": [
            {
                "title": "Crux Easton Start",
                "description": [
                    "The walk begins in the hamlet of Crux Easton, which can be reached via country lanes from the A343 between Newbury and Andover. There is limited roadside parking near the hamlet; please take care to park considerately without blocking farm gates. The approximate postcode is RG20 9QG.",
                    "Crux Easton is a tiny settlement of flint and brick cottages surrounded by arable farmland — archetypal North Hampshire downland country, quietly beautiful and almost completely unvisited. The Wayfarer's Walk long-distance trail passes through the hamlet, and this walk follows it east and then north across the Highclere Estate toward Sidown Hill.",
                ],
                "image_url": ""
            },
            {
                "title": "Into the Highclere Estate",
                "description": [
                    "The path climbs steadily eastward from Crux Easton, crossing open arable land before entering the wooded parkland of the Highclere Estate through a wooden gate. The change in character is immediate — the noise of the road fades, the air cools, and the path becomes a broad ride through mixed woodland of oak, ash, and beech. This section of the estate is less visited than the area immediately around the castle and has a pleasantly wild feel.",
                    "The estate covers roughly 5,000 acres in total, of which the Inner Park that most visitors see is only a fraction. The outer parkland and farmland traversed on this walk have the character of classic managed Hampshire countryside — a working landscape that has supported the Carnarvon family for centuries and continues to do so today.",
                ],
                "image_url": ""
            },
            {
                "title": "Sidown Hill Summit",
                "description": [
                    "The path climbs to the open summit of Sidown Hill — at around 210 metres, a significant viewpoint across the Highclere Estate and the surrounding downland. The views here are arguably even more intimate than those from Beacon Hill: rather than looking across the estate from outside, you are standing within it, the parkland trees spread below and the castle visible to the north-east.",
                    "The hill gives its name to the Etruscan Temple that stands in the parkland below — the Temple on Siddown Hill, one of six 18th-century garden buildings placed across the estate by the 1st Earl to frame and punctuate the views. From the summit, the careful geometry of Brown's parkland design becomes apparent in a way it never quite does at ground level.",
                ],
                "image_url": ""
            },
            {
                "title": "Return through Woodland",
                "description": [
                    "The return descends via the northern flank of Sidown Hill, following a waymarked bridleway through old woodland before rejoining the outward route near the estate boundary. The descent is gentle and the path firm underfoot even after wet weather. Allow about 45 minutes from the summit back to Crux Easton.",
                    "This section of the walk passes through an area of particularly fine old beeches, many with the characteristic grey, smooth bark that indicates trees several hundred years old. In autumn the beech colour is exceptional — golds and coppers that make the return leg the best part of the day. The path rejoins the lane into Crux Easton beside a pair of brick-and-flint estate cottages that would not look out of place in a Constable painting.",
                ],
                "image_url": ""
            },
        ]
    },
    {
        "slug": "highclere-village-loop",
        "title": "Highclere Village & Estate Lane",
        "distance": "3.5 km",
        "duration": "1 hr",
        "difficulty": "Easy",
        "summary": "A quiet loop through Highclere village and along the estate lane, passing the church of St Michael and All Angels and offering a classic view of the castle from the public road.",
        "image_url": "",
        "center": [51.3295, -1.3635],
        "zoom": 15,
        "waypoint_zoom": 17,
        "route": [
            [51.3318,-1.3615],[51.3312,-1.3628],[51.3305,-1.3638],[51.3295,-1.3645],
            [51.3285,-1.3650],[51.3275,-1.3648],[51.3268,-1.3640],[51.3262,-1.3628],
            [51.3260,-1.3615],[51.3265,-1.3602],[51.3272,-1.3595],[51.3282,-1.3590],
            [51.3292,-1.3592],[51.3302,-1.3598],[51.3310,-1.3607],[51.3318,-1.3615]
        ],
        "waypoint_coords": [
            [51.3318, -1.3615],
            [51.3295, -1.3645],
            [51.3262, -1.3628],
            [51.3302, -1.3598]
        ],
        "waypoints": [
            {
                "title": "Highclere Village",
                "description": [
                    "Highclere village is a scattered estate village strung along the lanes north of the castle, with a mix of Victorian estate cottages and older farm buildings that give it a pleasantly unspoilt character. The village has grown up entirely in the shadow of the castle and estate, and many of the families who live here have connections to the Carnarvon family going back several generations.",
                    "The walk begins at the junction near the Yew Tree pub and heads south along the lane toward the castle entrance. The verges along this stretch are wide and grassy — good for children to walk — and the lane is quiet enough for this to be a relaxed, unhurried stroll at almost any time of day.",
                ],
                "image_url": ""
            },
            {
                "title": "St Michael and All Angels Church",
                "description": [
                    "The church of St Michael and All Angels stands on a slight rise in the centre of the village and dates from the 12th century, though it was substantially rebuilt in the 19th century under the direction of the 3rd Earl of Carnarvon, who is buried here. The church is a handsome flint building with a square tower and a peaceful, well-maintained churchyard that includes the graves of several members of the Carnarvon family.",
                    "Inside, the church contains some fine stained glass and a notable memorial to the 5th Earl of Carnarvon — the Egyptologist who co-discovered the tomb of Tutankhamun in 1922. The Earl died in Cairo just a few months after the discovery, giving rise to the legend of the 'Curse of Tutankhamun'. He is buried in the churchyard, on the hill called Heaven's Gate above the castle.",
                ],
                "image_url": ""
            },
            {
                "title": "The Castle View",
                "description": [
                    "As the lane curves south toward the main castle entrance, a gap in the estate planting opens to give the classic view of Highclere Castle — the one seen in the opening credits of Downton Abbey — across an expanse of parkland. The castle sits on a slight rise, its silhouette of towers and turrets designed by Barry to be seen from exactly this angle, and on a sunny day the golden Bath stone glows against the Hampshire sky.",
                    "You do not need a ticket to see the castle from the public road — this view is freely available to anyone who walks or drives past. Many visitors find that this glimpse across the parkland, combined with a walk through the surrounding countryside, gives a perfectly satisfying sense of the estate without the need to go inside.",
                ],
                "image_url": ""
            },
            {
                "title": "Heaven's Gate & Return",
                "description": [
                    "The return leg climbs briefly north to the promontory known as Heaven's Gate, from which there is a particularly elevated view back across the park and castle. This is where the 5th Earl of Carnarvon is buried — a simple grave marker on the hilltop, in a spot he chose himself. The view he would have woken to every morning of his childhood is spread below you here: the castle, the park, the cedar trees, and the rolling Hampshire countryside stretching away in every direction.",
                    "From Heaven's Gate, the path descends back through the estate woods to Highclere village and the start. The full loop including the detour to Heaven's Gate adds about twenty minutes, but it is the finest viewpoint on this walk and not to be missed.",
                ],
                "image_url": ""
            },
        ]
    },
]


# ── BEAULIEU ESTATE ───────────────────────────────────────────────────────────

WALKS["beaulieu-estate"] = [
    {
        "slug": "beaulieu-to-bucklers-hard",
        "title": "Beaulieu to Buckler's Hard",
        "distance": "7.5 km",
        "duration": "2 hrs",
        "difficulty": "Easy",
        "summary": "The classic New Forest riverside walk — a gentle, flat trail along the wildlife-rich Beaulieu River to the historic 18th-century shipbuilding village of Buckler's Hard.",
        "image_url": "",
        "center": [50.8042, -1.4375],
        "zoom": 13,
        "waypoint_zoom": 15,
        "route": [
            [50.8167,-1.4583],[50.8155,-1.4555],[50.8140,-1.4528],[50.8125,-1.4502],
            [50.8112,-1.4478],[50.8098,-1.4455],[50.8082,-1.4435],[50.8068,-1.4415],
            [50.8052,-1.4398],[50.8038,-1.4382],[50.8025,-1.4370],[50.8012,-1.4360],
            [50.8000,-1.4352],[50.7988,-1.4345],[50.7975,-1.4340],[50.7962,-1.4335],
            [50.7950,-1.4332]
        ],
        "waypoint_coords": [
            [50.8167, -1.4583],
            [50.8095, -1.4452],
            [50.8020, -1.4365],
            [50.7950, -1.4332]
        ],
        "waypoints": [
            {
                "title": "Beaulieu Village",
                "description": [
                    "The walk begins in the heart of Beaulieu village, picking up the Solent Way long-distance footpath at the old mill bridge over the Beaulieu River. The river here is tidal — a consequence of the estate's remarkable geography, with the river rising on the New Forest heathland to the north but flowing into the sheltered estuary at Buckler's Hard and ultimately into the Solent. The tidal reach brings salt marsh species up into the village, and the water level changes noticeably over the course of a two-hour walk.",
                    "New Forest ponies regularly wander through the village and down to the river bank — there are no cattle grids on the main street, so they come and go as they please. Do not feed them and do not approach them from behind; they are entirely wild animals, despite their apparently tame behaviour. They are one of the great charms of any walk in this part of the Forest.",
                ],
                "image_url": ""
            },
            {
                "title": "The Beaulieu River Estuary",
                "description": [
                    "The path south from Beaulieu follows the west bank of the river through a sequence of habitats that change with remarkable speed — starting in woodland, then passing through tidal grassland where cattle and ponies graze in summer, then out onto open saltmarsh as the estuary widens. This transition between freshwater, brackish and saltwater habitats is rare in England, and the combination supports an extraordinary diversity of bird species.",
                    "Wading birds are the main attraction on the estuary sections: redshank, curlew, lapwing and oystercatcher are resident year-round, and in winter the mudflats attract thousands of wintering wildfowl including teal, wigeon and dark-bellied brent geese from Siberia. The patient observer with binoculars will rarely be disappointed here.",
                    "The Beaulieu River is one of the few rivers in England with a completely private foreshore. The Montagu Estate has owned and managed the entire river since the Dissolution of the Monasteries, when it passed to Thomas Wriothesley with the Abbey. The result is an exceptionally clean, unspoilt waterway.",
                ],
                "image_url": ""
            },
            {
                "title": "The Woodland Stretch",
                "description": [
                    "After about three kilometres the path enters a section of ancient oak and beech woodland that runs along the river for nearly a mile. The canopy overhead creates a cathedral effect, and the ground beneath is rich in spring flowers — wood anemone, bluebell, and wild garlic carpeting the floor in April and May.",
                    "This woodland has been part of the Beaulieu Estate since it was granted to the Cistercian monks by King John in 1204, and it has probably been managed as coppice and timber woodland since that time. The gnarled oak pollards along the river bank are likely several hundred years old, the result of centuries of cyclical cutting that encourages wide, spreading canopies rather than tall, straight trunks.",
                ],
                "image_url": ""
            },
            {
                "title": "Buckler's Hard",
                "description": [
                    "The walk ends at Buckler's Hard, one of the most atmospheric places in Hampshire — a perfectly preserved 18th-century shipbuilding village consisting of two rows of Georgian cottages facing each other across a wide green that runs down to the river. The village was built in the 1740s by the 2nd Duke of Montagu as a planned settlement around a proposed Caribbean sugar trade that never materialised; it found its true purpose instead as a shipyard, producing warships for the Royal Navy throughout the second half of the 18th century.",
                    "Nelson's favourite ship, HMS Agamemnon — a 64-gun man-of-war launched here in 1781 from 2,000 New Forest oaks — was built on this slip. She went on to fight at the Battle of Trafalgar and served the Royal Navy for nearly thirty years before being wrecked off Uruguay in 1809. The Maritime Museum at Buckler's Hard tells the full story of the village and its ships; it is small but excellent, and well worth the admission. River cruises depart from the jetty in summer.",
                ],
                "image_url": ""
            },
        ]
    },
    {
        "slug": "beaulieu-heath-hatchet-pond",
        "title": "Beaulieu Heath & Hatchet Pond",
        "distance": "6 km",
        "duration": "1.5 hrs",
        "difficulty": "Easy",
        "summary": "A gentle circuit across open New Forest heathland to the wildfowl-rich waters of Hatchet Pond, with a good chance of seeing free-roaming ponies, donkeys, and the ancient Bronze Age barrows of the Heath.",
        "image_url": "",
        "center": [50.8050, -1.4900],
        "zoom": 13,
        "waypoint_zoom": 15,
        "route": [
            [50.8100,-1.4780],[50.8090,-1.4810],[50.8078,-1.4838],[50.8065,-1.4862],
            [50.8052,-1.4882],[50.8038,-1.4898],[50.8025,-1.4910],[50.8010,-1.4918],
            [50.7998,-1.4922],[50.7988,-1.4920],[50.7980,-1.4912],[50.7975,-1.4900],
            [50.7978,-1.4885],[50.7985,-1.4870],[50.7995,-1.4858],[50.8008,-1.4848],
            [50.8022,-1.4840],[50.8038,-1.4832],[50.8055,-1.4822],[50.8070,-1.4808],
            [50.8082,-1.4795],[50.8092,-1.4785],[50.8100,-1.4780]
        ],
        "waypoint_coords": [
            [50.8100, -1.4780],
            [50.8045, -1.4890],
            [50.7988, -1.4920],
            [50.8058, -1.4822]
        ],
        "waypoints": [
            {
                "title": "Rans Wood Car Park",
                "description": [
                    "The walk starts from the Forestry England car park at Rans Wood, at the end of Furzey Lane — a turning off the B3054 between Beaulieu and Lymington. The car park is free and gives immediate access to the open heathland of Beaulieu Heath, one of the largest areas of lowland heath in the New Forest and a Site of Special Scientific Interest.",
                    "Beaulieu Heath is at its most spectacular in late summer — August and early September — when the heather comes into flower and the whole landscape turns a deep, warm purple. At other times of year the heath has a subtler beauty: the bleached gold of winter grass, the pale green of new growth in spring, and the wide, open skies that make this one of the finest landscapes for unimpeded views in southern England.",
                ],
                "image_url": ""
            },
            {
                "title": "Bronze Age Barrows",
                "description": [
                    "As the path crosses the open heath, look for the low, rounded mounds that appear periodically in the landscape — these are Bronze Age burial barrows, around 3,500 years old, of which there are more than 200 scattered across the New Forest. The barrows on Beaulieu Heath are among the best preserved, since the open heathland has never been ploughed.",
                    "Each barrow marks the burial site of a high-status individual from the Early Bronze Age — the period of Stonehenge and the Avebury monuments. The New Forest concentrations are among the densest in Britain, suggesting this landscape was considered particularly significant in the Bronze Age. Walking among them gives a vivid, direct connection to a world more than three millennia gone.",
                ],
                "image_url": ""
            },
            {
                "title": "Hatchet Pond",
                "description": [
                    "Hatchet Pond is the largest natural body of water in the New Forest and a favourite haunt of wildfowl. Geese, swans, mallard, tufted duck and coot are present year-round, and in winter the pond attracts pochard, goldeneye, and occasionally rarer diving ducks. New Forest ponies come regularly to drink at the water's edge, and the scene — ponies, open water, heathland horizon — is quintessentially New Forest.",
                    "The Forestry England car park on the far side of the pond is a popular spot, and the pond can be busy at weekends. The path on the south bank, away from the car park, is quieter and gives better views across the water. The reed beds at the eastern end are worth a slow look — bittern have been recorded here, and reed bunting is resident throughout the year.",
                ],
                "image_url": ""
            },
            {
                "title": "Return across the Heath",
                "description": [
                    "The return route crosses the open heath by a different path, giving a wide circular view of the landscape from a slightly elevated ridge. On a clear day the Isle of Wight is visible to the south — the distinctive shape of the Needles chalk stack rising above the Solent. Looking back toward Beaulieu, the tower of Beaulieu Abbey is visible above the treeline, confirming just how flat and open this landscape really is.",
                    "The heath is grazed by New Forest ponies, cattle, and occasionally donkeys throughout the year under the commoners' ancient grazing rights — a system of animal husbandry that dates back to the Norman period and is fundamental to maintaining the open heathland character of the Forest. Without the grazing, the heath would rapidly revert to scrub and woodland.",
                ],
                "image_url": ""
            },
        ]
    },
    {
        "slug": "beaulieu-village-abbey-walk",
        "title": "Beaulieu Village & Abbey Circuit",
        "distance": "2.5 km",
        "duration": "45 min",
        "difficulty": "Easy",
        "summary": "A short, leisurely loop around Beaulieu village taking in the Abbey ruins, Palace House, the river mill pond, and the medieval village green — perfect for families with young children.",
        "image_url": "",
        "center": [50.8167, -1.4583],
        "zoom": 16,
        "waypoint_zoom": 17,
        "route": [
            [50.8172,-1.4592],[50.8168,-1.4580],[50.8162,-1.4572],[50.8155,-1.4565],
            [50.8150,-1.4560],[50.8145,-1.4558],[50.8142,-1.4562],[50.8140,-1.4570],
            [50.8142,-1.4580],[50.8148,-1.4590],[50.8155,-1.4598],[50.8162,-1.4603],
            [50.8170,-1.4602],[50.8175,-1.4598],[51.8176,-1.4592]
        ],
        "waypoint_coords": [
            [50.8172, -1.4592],
            [50.8150, -1.4560],
            [50.8140, -1.4570],
            [50.8165, -1.4600]
        ],
        "waypoints": [
            {
                "title": "The Village Green & Mill Pond",
                "description": [
                    "The walk starts at the village green, the central open space around which Beaulieu's old houses and cottages cluster. The green slopes gently toward the river and is bounded on one side by the mill pond — a picturesque body of water formed by the old monastic mill dam that the Cistercian monks constructed shortly after founding the Abbey in 1204. The mill itself, rebuilt in the 18th century, still stands at the end of the pond and is one of the most photographed buildings in the village.",
                    "New Forest ponies are regularly found on the green and around the pond — a completely normal part of life in Beaulieu, where the ancient commoners' grazing rights mean that ponies, donkeys and cattle can wander freely. Please do not feed or touch them, and do not approach foals.",
                ],
                "image_url": ""
            },
            {
                "title": "Beaulieu Abbey Ruins",
                "description": [
                    "The Abbey ruins occupy the eastern end of the village and are included in a general admission ticket to the Beaulieu attraction complex. What survives is impressive — the outline of the great church can be traced clearly in the standing walls and foundation stones, and the scale of the building, one of the largest Cistercian abbeys in England, is still apparent. At its peak, the Abbey was home to nearly a hundred monks and novices, supported by a large community of lay brothers on the surrounding farms.",
                    "The refectory — the monks' dining hall — survives almost intact and is now used as the parish church of Beaulieu, one of the few examples in England of an abbey building being continuously used by a local congregation since the Dissolution. The building retains its medieval roof timbers and a remarkable pulpit from which a monk would have read aloud during meals. The intimacy of the interior is striking after the expansive ruins outside.",
                ],
                "image_url": ""
            },
            {
                "title": "Palace House & Gardens",
                "description": [
                    "Palace House began as the 14th-century Great Gatehouse of Beaulieu Abbey — the main ceremonial entrance to the monastery complex. After the Dissolution in 1538, Henry VIII sold the entire estate to Thomas Wriothesley, 1st Earl of Southampton, who converted the gatehouse into a private house. The house has been continuously extended and modified ever since, and it remains the home of the Montagu family today.",
                    "The gardens around Palace House are beautifully maintained and include a walled kitchen garden, herbaceous borders, and fine views down to the river and mill pond. The Victorian kitchen, restored to working condition, gives a vivid impression of the domestic scale of the house in its 19th-century heyday, when a staff of thirty or more would have kept the place running.",
                ],
                "image_url": ""
            },
            {
                "title": "The High Street & River",
                "description": [
                    "The walk returns via the High Street — a short but characterful thoroughfare lined with independent shops, the Chocolate Studio, Norris of Beaulieu, and the entrance to the Montagu Arms Hotel. The High Street has no cattle grid, so ponies wander in and out at will, creating the extraordinary spectacle of free-roaming animals browsing the pavement outside the shops.",
                    "At the bottom of the High Street, the bridge over the Beaulieu River gives a good vantage point across the mill pond and back toward the Abbey. This is a good spot for watching the tidal flow — at low tide the river bed is visible and wading birds probe the mud below the bridge. At high tide the river fills to its banks and the surface has the glassy stillness of a lake.",
                ],
                "image_url": ""
            },
        ]
    },
    {
        "slug": "beaulieu-to-exbury",
        "title": "Beaulieu to Exbury Gardens",
        "distance": "9 km",
        "duration": "2.5 hrs",
        "difficulty": "Easy",
        "summary": "A rewarding linear walk south through New Forest woodland and along quiet lanes to the celebrated Rothschild gardens at Exbury — world-famous for their rhododendrons and azaleas in spring.",
        "image_url": "",
        "center": [50.8000, -1.4250],
        "zoom": 13,
        "waypoint_zoom": 15,
        "route": [
            [50.8167,-1.4583],[50.8145,-1.4548],[50.8122,-1.4515],[50.8100,-1.4480],
            [50.8078,-1.4448],[50.8055,-1.4418],[50.8032,-1.4390],[50.8010,-1.4365],
            [50.7988,-1.4342],[50.7965,-1.4320],[50.7940,-1.4300],[50.7915,-1.4282],
            [50.7890,-1.4268],[50.7862,-1.4258],[50.7835,-1.4250],[50.8030,-1.3990]
        ],
        "waypoint_coords": [
            [50.8167, -1.4583],
            [50.8078, -1.4448],
            [50.7940, -1.4300],
            [50.8030, -1.3990]
        ],
        "waypoints": [
            {
                "title": "Beaulieu & The Solent Way",
                "description": [
                    "The walk south from Beaulieu follows the Solent Way long-distance coastal path, which runs for 100 kilometres from Milford-on-Sea to Emsworth along the Hampshire coast and tidal inlets. The first section out of Beaulieu is pleasantly varied — passing along the edge of the estate parkland before entering open arable farmland with wide views toward the Solent.",
                    "This route makes an excellent linear walk if a car can be left at Exbury. For a circular return, either retrace the outward route or take the minor lanes back via East Boldre — adding roughly 4 km to the total distance but offering a pleasant contrast between the woodland path south and the open lane north.",
                ],
                "image_url": ""
            },
            {
                "title": "New Forest Woodland",
                "description": [
                    "The central section of the walk passes through a long stretch of managed New Forest woodland — the ancient oaks and beeches that were once the raw material for the Royal Navy's warships. Buckler's Hard, three miles back up the river, consumed 2,000 mature oaks to build HMS Agamemnon alone in 1781; the trees being felled and carted along tracks very similar to the paths you are walking.",
                    "The woodland is managed by a combination of the Forestry England and the Beaulieu Estate, and the ancient commoners' grazing rights mean that ponies and cattle move freely through the trees year-round. This light grazing keeps the woodland floor open, allowing a remarkable diversity of ground-layer plants — wood sorrel, bluebells, cow-wheat, and in wetter hollows, stands of royal fern.",
                ],
                "image_url": ""
            },
            {
                "title": "The Beaulieu Estuary Views",
                "description": [
                    "As the path descends toward the Exbury peninsula, views open southward across the Beaulieu River estuary toward the Solent and, on a clear day, the western end of the Isle of Wight and the Needles. The estuary here is wide and shallow, with extensive mudflats at low tide that attract enormous numbers of wading birds and wildfowl — particularly in winter, when brent geese arrive in their thousands from their arctic breeding grounds.",
                    "The village of Exbury itself, separated from Beaulieu by three miles of lanes, has a quiet, unhurried character — a handful of estate cottages and a small church — that makes it feel entirely removed from the busy tourist routes of the central New Forest.",
                ],
                "image_url": ""
            },
            {
                "title": "Exbury Gardens",
                "description": [
                    "Exbury Gardens are among the finest woodland gardens in England, created from the 1920s onwards by Lionel de Rothschild on a 200-acre estate on the east bank of the Beaulieu River. Rothschild was one of the great plant collectors and hybridisers of the 20th century, and his collection of rhododendrons, azaleas, camellias and magnolias — now numbering more than 200 species and hybrids — is world-famous.",
                    "The spring display, from late March through May, is one of the botanical spectacles of southern England — a cascade of colour through the woodland that is unlike anything else in the region. The gardens are open daily from February to November; a steam railway runs through the grounds for younger visitors. Admission is charged, and booking ahead at weekends is advisable in spring.",
                ],
                "image_url": ""
            },
        ]
    },
]


# ── PLACES TO EAT ─────────────────────────────────────────────────────────────

PLACES_TO_EAT["highclere-castle"] = [
    {
        "slug": "yew-tree-inn",
        "name": "The Yew Tree Inn",
        "type": "pub & restaurant",
        "rating": 4.5,
        "guide_price": "£45",
        "open_today": "12–15, 18–22",
        "distance": "2 min drive",
        "coords": [51.3315, -1.3612],
        "summary": "A handsome 17th-century country inn on the Andover Road in Highclere village, moments from the castle entrance. The restaurant has held two AA Rosettes and specialises in fresh fish sourced daily from Devon, alongside beautifully cooked British classics. Low beams, an open fire in winter, and a proper country-pub atmosphere make it the natural choice after a walk in the parkland. Booking strongly recommended at weekends.",
        "image_url": "",
    },
    {
        "slug": "the-pheasant-highclere",
        "name": "The Pheasant",
        "type": "pub & inn",
        "rating": 4.7,
        "guide_price": "£40",
        "open_today": "12–15, 18–22",
        "distance": "3 min drive",
        "coords": [51.3322, -1.3625],
        "summary": "A charming 17th-century pub with rooms, right in the heart of Highclere village. The Pheasant has huge wood-burning fireplaces, eclectic decor and a menu that leans on fresh, local Hampshire produce — venison pie, scallops, ribeye steak. Relaxed and genuinely welcoming, it regularly tops local dining lists and is one of the best dog-friendly pubs in the area.",
        "image_url": "",
    },
    {
        "slug": "carnarvon-arms",
        "name": "The Carnarvon Arms",
        "type": "hotel & restaurant",
        "rating": 4.3,
        "guide_price": "£38",
        "open_today": "7–22",
        "distance": "5 min drive",
        "coords": [51.3380, -1.3658],
        "summary": "A former coaching inn directly associated with the Highclere Estate, set in the hamlet of Whitway a short drive from the castle. The kitchen produces confident modern British cooking with local sourcing at its heart — the Sunday roast is a particular draw. The hotel's beer garden is one of the most pleasant spots for an outdoor lunch in the area. Rooms available for overnight stays.",
        "image_url": "",
    },
    {
        "slug": "highclere-castle-tearoom",
        "name": "Highclere Castle Coach House Tea Room",
        "type": "tearoom",
        "rating": 4.4,
        "guide_price": "£18",
        "open_today": "9:30–17:00",
        "distance": "On site",
        "coords": [51.3275, -1.3600],
        "summary": "Located in the castle's courtyard, the Coach House Tea Room is open to all visitors during castle opening hours. Morning coffee and pastries give way to a menu of handmade sandwiches, salads, cakes and scones throughout the day. A pre-bookable afternoon tea — finger sandwiches, pastries, scones and a glass of champagne — is offered during summer months and makes a memorably elegant pause between the Egyptian Exhibition and the gardens.",
        "image_url": "",
    },
    {
        "slug": "wellington-arms-baughurst",
        "name": "The Wellington Arms",
        "type": "pub & restaurant",
        "rating": 4.8,
        "guide_price": "£55",
        "open_today": "12–14:30, 18–21",
        "distance": "15 min drive",
        "coords": [51.3408, -1.2542],
        "summary": "One of the finest country gastropubs in Hampshire, tucked away in the village of Baughurst east of Highclere. The Wellington Arms grows an extraordinary range of its own vegetables, salads and herbs in the kitchen garden, keeps its own pigs and bees, and sources everything else from named farms nearby. The cooking is assured and seasonal, the puddings are outstanding, and the dining room — in a converted pub with views over the garden — is genuinely lovely. Book well ahead.",
        "image_url": "",
    },
    {
        "slug": "the-rampant-cat",
        "name": "The Rampant Cat",
        "type": "pub",
        "rating": 4.2,
        "guide_price": "£28",
        "open_today": "11–23",
        "distance": "10 min drive",
        "coords": [51.3450, -1.3120],
        "summary": "A traditional local pub in Kingsclere, about ten minutes from Highclere, that serves straightforward pub food without pretension — good burgers, proper pies, and decent pints of local ale. It is exactly what you want after a long walk: unpretentious, cheerful, and reliably open. A useful back-pocket option when the smarter restaurants are full.",
        "image_url": "",
    },
    {
        "slug": "woodspeen-restaurant",
        "name": "The Woodspeen",
        "type": "restaurant & cookery school",
        "rating": 4.7,
        "guide_price": "£65",
        "open_today": "12–14, 18:30–21",
        "distance": "20 min drive",
        "coords": [51.4082, -1.3592],
        "summary": "A Michelin-recognised restaurant in a beautifully converted barn at Woodspeen, north of Newbury — about 20 minutes from Highclere. Chef John Campbell's cooking is rooted in seasonal produce from the kitchen garden and local estates, presented with considerable skill. The cookery school attached to the restaurant is one of the best in southern England. The wine list is exceptional. An occasion meal that rewards the short drive.",
        "image_url": "",
    },
]


PLACES_TO_EAT["beaulieu-estate"] = [
    {
        "slug": "montys-inn",
        "name": "Monty's Inn",
        "type": "pub",
        "rating": 4.4,
        "guide_price": "£32",
        "open_today": "12–15, 18–21",
        "distance": "2 min walk",
        "coords": [50.8165, -1.4578],
        "summary": "The informal pub arm of the Montagu Arms Hotel, right in the heart of Beaulieu village. Monty's serves hearty, satisfying pub food — burgers, pies, fish and chips, and weekly specials — all made from locally sourced ingredients including pork from Pondhead Farm, beef from Alderstone Farm and real ales from Ringwood Brewery. Wooden floors, a cosy atmosphere, and a welcome that extends to muddy boots, dogs, and children make it the natural choice after a river walk.",
        "image_url": "",
    },
    {
        "slug": "montagu-arms-terrace",
        "name": "The Terrace at The Montagu Arms",
        "type": "hotel restaurant",
        "rating": 4.4,
        "guide_price": "£60",
        "open_today": "12–14, 19–21",
        "distance": "3 min walk",
        "coords": [50.8162, -1.4574],
        "summary": "The formal dining room at the Montagu Arms Hotel — an AA Rosette restaurant that was voted Hampshire Restaurant of the Year by the Which? Good Food Guide. Chef Matt Whitfield's menu showcases the finest seasonal produce from the New Forest coastline and hinterland: South Coast fish, local game, and vegetables from the hotel's own kitchen garden. The Edwardian dining room, with full-length windows opening onto the garden, is one of the loveliest settings for a serious meal in Hampshire. Book ahead.",
        "image_url": "",
    },
    {
        "slug": "bucklers-hard-hotel",
        "name": "The Master Builder's House Hotel",
        "type": "hotel & bar",
        "rating": 4.1,
        "guide_price": "£30",
        "open_today": "12–22",
        "distance": "45 min walk",
        "coords": [50.7950, -1.4332],
        "summary": "A bar and brasserie in the historic Master Builder's House Hotel at Buckler's Hard — the natural terminus of the riverside walk from Beaulieu. The bar serves light lunches, platters and afternoon snacks in a setting overlooking the Beaulieu River. In summer the terrace above the river is one of the most pleasant outdoor eating spots in Hampshire. The full brasserie menu is available at dinner.",
        "image_url": "",
    },
    {
        "slug": "beaulieu-chocolate-studio-cafe",
        "name": "Beaulieu Chocolate Studio",
        "type": "café & confectioner",
        "rating": 4.6,
        "guide_price": "£12",
        "open_today": "10–17",
        "distance": "2 min walk",
        "coords": [50.8170, -1.4580],
        "summary": "A genuinely special shop on the High Street — part artisan chocolate workshop, part café — where Trevor has been hand-making over 30 varieties of filled chocolate on the premises since 2006. The workshop is visible through a large window, so you can watch the process while you eat. Hot drinks, cakes and light bites are served in a friendly, relaxed atmosphere. An irresistible stop for anyone with a sweet tooth, and the chocolates make an excellent gift.",
        "image_url": "",
    },
    {
        "slug": "turfcutters-arms-east-boldre",
        "name": "The Turfcutters Arms",
        "type": "pub",
        "rating": 4.3,
        "guide_price": "£28",
        "open_today": "12–15, 18–21",
        "distance": "10 min drive",
        "coords": [50.8100, -1.4750],
        "summary": "A classic, unspoilt New Forest pub in the hamlet of East Boldre — a short drive from Beaulieu. The Turfcutters Arms is the kind of place that appears in pub-of-the-year lists for being genuinely itself: exposed beams, a log fire, simple food cooked properly, and good local ales. The garden backs onto the Forest, and free-roaming ponies are occasionally spotted outside. Dog-friendly, family-friendly, and reliably good value.",
        "image_url": "",
    },
    {
        "slug": "kings-head-lyndhurst",
        "name": "The Kings Head",
        "type": "pub & restaurant",
        "rating": 4.2,
        "guide_price": "£32",
        "open_today": "11–23",
        "distance": "15 min drive",
        "coords": [50.8745, -1.5680],
        "summary": "A solid, well-run pub in the centre of Lyndhurst — the 'capital' of the New Forest and about 15 minutes from Beaulieu. The menu covers all the pub essentials with a local slant: New Forest game, local fish, and a Sunday carvery that draws regulars from across the area. The beer garden is large and family-friendly, and the pub serves food all day during the summer season — useful for later arrivals.",
        "image_url": "",
    },
    {
        "slug": "stanwell-house-lymington",
        "name": "Stanwell House",
        "type": "hotel & restaurant",
        "rating": 4.5,
        "guide_price": "£48",
        "open_today": "12–14:30, 18:30–21:30",
        "distance": "20 min drive",
        "coords": [50.7571, -1.5365],
        "summary": "A stylish boutique hotel with a well-regarded restaurant on the High Street in Lymington — one of the loveliest small towns on the Hampshire coast, 20 minutes from Beaulieu. The cooking is broadly modern British with a Mediterranean sensibility, and the terrace bar overlooking the walled garden is one of the most pleasant spots in the area for a summer lunch. The hotel's bar serves excellent cocktails and a good selection of local and regional wines.",
        "image_url": "",
    },
]


# ── PLACES OF INTEREST ────────────────────────────────────────────────────────

PLACES_OF_INTEREST["highclere-castle"] = [
    {
        "slug": "highclere-castle-house",
        "name": "Highclere Castle",
        "type": "Historic House",
        "summary": "The centrepiece of the estate — a magnificent Italianate Gothic mansion designed by Sir Charles Barry, the architect of the Houses of Parliament, between 1839 and 1842 for the 3rd Earl of Carnarvon. The castle replaced an earlier Georgian house and is built of golden Bath stone with a dramatic skyline of towers and pinnacles. The State Rooms include the Library, the Saloon, the Dining Room, and the Drawing Room, all furnished with significant collections of art and furniture accumulated by successive Earls. Highclere is internationally known as the principal filming location for Downton Abbey, and many of the rooms are immediately recognisable to fans of the series.",
        "image_url": "",
    },
    {
        "slug": "egyptian-exhibition",
        "name": "Egyptian Exhibition",
        "type": "Museum Exhibition",
        "summary": "Located in the basement cellars of the castle, this remarkable exhibition tells the story of the 5th Earl of Carnarvon's passion for Egyptology and his role in funding Howard Carter's excavation of the Valley of the Kings. On 4 November 1922, Carter discovered the steps leading to the sealed tomb of Tutankhamun — the most intact royal burial ever found in Egypt. The Earl died in Cairo just five months later, giving rise to the legend of the Pharaoh's Curse. The six-room exhibition includes exact replicas of the sarcophagus, the death mask, and the middle coffin, along with the Carnarvon family's own Egyptian artefacts and a reproduction of the north wall mural from the tomb. It is one of the most absorbing small museum experiences in southern England.",
        "image_url": "",
    },
    {
        "slug": "capability-brown-parkland",
        "name": "Capability Brown Parkland",
        "type": "Historic Landscape",
        "summary": "The 1,000-acre parkland surrounding the castle was designed by Lancelot 'Capability' Brown in 1770–71 and is listed Grade I on the Historic England Register of Parks and Gardens — the highest designation available. Brown's design is a masterwork of the English landscape tradition: naturalistic, apparently effortless, and entirely composed. The park contains two lakes, ancient veteran oaks, magnificent cedars of Lebanon, six 18th-century garden follies (including the Temple of Diana and Jackdaw's Castle), and an Ha-ha that separates the formal gardens from the wider parkland. Several public footpaths cross the estate, including sections of the Wayfarer's Walk and Brenda Parker Way long-distance trails.",
        "image_url": "",
    },
    {
        "slug": "temple-of-diana",
        "name": "Temple of Diana",
        "type": "Garden Folly",
        "summary": "A circular garden building on the hillside above Dunsmere Lake, constructed in the late 18th century with Ionic columns salvaged from Devonshire House in Piccadilly. The Temple was positioned by the 1st Earl to frame a precise view across the water back toward the castle — a characteristic device of the period, when every vista in a great park was calculated as a composed picture. The building has been beautifully restored and the view from its steps at dusk, with the castle silhouetted against the western sky, is one of the finest on the estate.",
        "image_url": "",
    },
    {
        "slug": "beacon-hill-iron-age-fort",
        "name": "Beacon Hill Iron Age Fort",
        "type": "Ancient Monument",
        "summary": "Beacon Hill at 261 metres is the highest point in Hampshire and one of the best-preserved Iron Age hillforts in southern England. The concentric earthwork ditches and banks were constructed around 700 BC and enclose an area of about six hectares. The summit is crowned by a Bronze Age burial barrow more than 3,500 years old, making this one of the few places in England where the layered accumulation of human history — Bronze Age, Iron Age, and beyond — can be read directly in the landscape. The view from the summit encompasses the whole of the Highclere Estate, the Hampshire Downs, and on clear days extends to the North Downs in Surrey and beyond.",
        "image_url": "",
    },
    {
        "slug": "highclere-castle-gardens",
        "name": "The Secret Garden & Walled Garden",
        "type": "Historic Garden",
        "summary": "Within the formal gardens immediately around the castle, the Secret Garden is a walled enclosure of Victorian planting — roses, herbaceous perennials, and climbers in a design that has been carefully restored by the current Lady Carnarvon. The Walled Kitchen Garden beyond produces vegetables, fruit, and cutting flowers that supply the castle's tea rooms and events. The gardens as a whole are included in the castle admission and are open during all public opening dates. Lady Carnarvon's extensive writing about the estate — she has published several books on Highclere's history — draws heavily on the gardens as a lens through which the castle's story is told.",
        "image_url": "",
    },
]


PLACES_OF_INTEREST["beaulieu-estate"] = [
    {
        "slug": "beaulieu-abbey-ruins",
        "name": "Beaulieu Abbey Ruins",
        "type": "Medieval Ruins",
        "summary": "Founded in 1204 by King John and settled by thirty Cistercian monks sent from the mother house at Cîteaux in France, Beaulieu Abbey was once one of the largest and most important monasteries in England. Construction took four decades and the completed church — dedicated in 1246 in the presence of Henry III — was over 70 metres long. The abbey was dissolved by Henry VIII in 1538, and much of the stonework was plundered for building material, but the ruins that survive are extensive and atmospheric. The lay brothers' dormitory (the Domus) now houses an excellent exhibition on monastic life; the monks' refectory survives intact as the village parish church.",
        "image_url": "",
    },
    {
        "slug": "national-motor-museum",
        "name": "National Motor Museum",
        "type": "Museum",
        "summary": "One of the finest automotive collections in the world, with more than 280 vehicles spanning the entire history of motoring from the earliest steam-powered vehicles to Formula 1 cars and land speed record breakers. The museum was founded in 1952 by the 3rd Lord Montagu as a tribute to his father — a pioneering motoring enthusiast who befriended King Edward VII — and has grown into a world-class institution. Highlights include the Bluebird land speed record cars, Veteran and Edwardian motorcars, and the On Screen Cars exhibition featuring vehicles from James Bond films and many other productions. Included in the general Beaulieu admission ticket.",
        "image_url": "",
    },
    {
        "slug": "palace-house",
        "name": "Palace House",
        "type": "Historic House",
        "summary": "Palace House began as the 14th-century Great Gatehouse of Beaulieu Abbey — the ceremonial entrance to one of England's great monasteries. After the Dissolution of 1538, Thomas Wriothesley converted it into a private house, and it has been continuously extended and inhabited ever since. It remains the family home of the Montagu family, and the rooms open to the public are furnished with family portraits, treasures, and personal collections that span six centuries of continuous occupation. The recently restored Victorian kitchen gives a vivid sense of domestic life in the house's 19th-century heyday.",
        "image_url": "",
    },
    {
        "slug": "secret-army-exhibition",
        "name": "Secret Army Exhibition",
        "type": "Museum Exhibition",
        "summary": "During the Second World War, the Beaulieu Estate was requisitioned by the Special Operations Executive (SOE) — Churchill's 'Secret Army' — and used as a Group B finishing school for agents being prepared for insertion into occupied Europe. Over 3,000 agents passed through the estate between 1941 and 1945, trained in the arts of sabotage, counter-surveillance, and covert communication before being dropped behind enemy lines by parachute or motor torpedo boat. Many went on to perform some of the war's most daring operations. The exhibition tells their stories with remarkable intimacy; the mixture of heroism, tragedy, and moral complexity makes it one of the most affecting small exhibitions in Hampshire.",
        "image_url": "",
    },
    {
        "slug": "beaulieu-river",
        "name": "The Beaulieu River",
        "type": "Natural Feature",
        "summary": "The Beaulieu River rises on the New Forest heathland to the north and flows southward for about twelve miles to the Solent at Beaulieu estuary. It is one of the few rivers in England with a completely private foreshore — the Montagu Estate has owned and managed the entire river since the Dissolution — and the result is an exceptionally clean, unspoilt waterway. The tidal estuary south of Beaulieu village supports nationally important populations of wading birds and wildfowl, and the river corridor is rich in otters, kingfishers, and a wide range of aquatic insects. River cruises operate from Buckler's Hard from Easter to September.",
        "image_url": "",
    },
    {
        "slug": "bucklers-hard-village",
        "name": "Buckler's Hard",
        "type": "Historic Village",
        "summary": "A perfectly preserved 18th-century planned industrial village at the navigable head of the Beaulieu River estuary, where ships for the Royal Navy were built from New Forest timber throughout the latter half of the 18th century. The village consists of two rows of Georgian labourers' cottages facing each other across a wide green that slopes down to the river slipways — unchanged in layout since the 1740s. HMS Agamemnon, Nelson's favourite ship, was built here from 2,000 Forest oaks and launched in 1781. The Maritime Museum tells the full story of the village and its ships; river cruises and guided tours are available from Easter to September.",
        "image_url": "",
    },
]


# ── FUN FOR KIDS ──────────────────────────────────────────────────────────────

FUN_FOR_KIDS["highclere-castle"] = [
    {
        "slug": "egyptian-exhibition-kids",
        "name": "Egyptian Exhibition",
        "type": "Museum",
        "distance": "On site",
        "coords": [51.3275, -1.3600],
        "summary": "The six-room Egyptian Exhibition in the castle cellars is one of the most child-friendly museum experiences in Hampshire — the reproductions of Tutankhamun's death mask, sarcophagus, and golden shrines are genuinely spectacular at close range, and the story of the discovery in 1922 is irresistible to most children. The scale of the objects, the dramatic lighting, and the tangible sense of buried treasure all conspire to produce a walk-in experience that few children forget. A useful audio guide is available for older children and adults.",
        "image_url": "",
    },
    {
        "slug": "downton-abbey-spotting",
        "name": "Downton Abbey Location Spotting",
        "type": "Activity",
        "distance": "On site",
        "coords": [51.3275, -1.3600],
        "summary": "Children who know the series will delight in recognising rooms and vistas from Downton Abbey — the Saloon, the Library, the grand staircase, and the south front are all immediately recognisable. The estate provides a dedicated Downton Abbey guide that helps visitors locate the key filming spots. Even non-fans find the experience of being inside an actual Victorian castle compelling, and the combination of real history and screen history gives plenty to talk about.",
        "image_url": "",
    },
    {
        "slug": "beacon-hill-kids",
        "name": "Beacon Hill Hillfort Climb",
        "type": "Outdoor Activity",
        "distance": "5 min drive",
        "coords": [51.3162, -1.3520],
        "summary": "The climb to Beacon Hill is well within the range of most children over about five, and the reward — an Iron Age hillfort with great views and the sense of standing on top of history — is an excellent one. The earthwork ramparts are dramatic enough to ignite the imagination of anyone who has ever played at castles, and the open summit is a wonderful place for a packed lunch with a panoramic view of the Highclere Estate spread below. Download a brief description of the Iron Age fort from the National Trust website before you go.",
        "image_url": "",
    },
    {
        "slug": "highclere-castle-shop-kids",
        "name": "Highclere Castle Gift Shop",
        "type": "Shopping",
        "distance": "On site",
        "coords": [51.3275, -1.3600],
        "summary": "The castle gift shop in the courtyard stocks an excellent range of children's gifts — the Finse Explores the World series of books by Lady Carnarvon, Egyptian-themed toys and games, Downton Abbey keepsakes, and a wide variety of practical and decorative souvenirs. The shop also sells the famous Highclere Gin and Lady Carnarvon's books for adults. All products are available online if you run out of time on the day.",
        "image_url": "",
    },
    {
        "slug": "new-forest-wildlife",
        "name": "New Forest Wildlife Walks",
        "type": "Wildlife",
        "distance": "20 min drive",
        "coords": [50.8745, -1.5680],
        "summary": "The New Forest National Park — a 20-minute drive from Highclere — is the best place in southern England for an unscripted encounter with wild animals. Free-roaming ponies, cattle, pigs in autumn pannage season, and fellow deer wander the forest and heathland completely at liberty. Walking on the open heath near Burley or Brockenhurst offers a reliable chance of seeing ponies at close range in their natural habitat. Children find the experience surprisingly powerful — there are no barriers, no keepers, and no feeding schedules.",
        "image_url": "",
    },
    {
        "slug": "highclere-estate-picnic",
        "name": "Parkland Picnic",
        "type": "Outdoor Activity",
        "distance": "On site",
        "coords": [51.3275, -1.3600],
        "summary": "A picnic in the Highclere parkland on a fine day is one of the most pleasurable things the estate offers. During public opening periods, the south lawn provides a spectacular foreground — the castle rising behind you, the parkland trees framing the view, and the deer occasionally grazing in the middle distance. The castle tea rooms supply everything needed for a self-assembled picnic, and the grass is perfectly maintained. Families often find that an afternoon on the lawn, with the castle visible but not crowded, is the defining memory of their visit.",
        "image_url": "",
    },
]


FUN_FOR_KIDS["beaulieu-estate"] = [
    {
        "slug": "national-motor-museum-kids",
        "name": "National Motor Museum",
        "type": "Museum",
        "distance": "On site",
        "coords": [50.8167, -1.4583],
        "summary": "Few children are unmoved by 280 vehicles in a single building — from early steam cars that look like something from a steam-punk fantasy to Bluebird, the land speed record car, and screen-famous vehicles from James Bond and other films. The On Screen Cars exhibition is a particular hit with older children and teenagers. The museum is large enough to fill a morning but well paced, with plenty of interactive displays and scale models that keep younger children engaged.",
        "image_url": "",
    },
    {
        "slug": "new-forest-ponies-beaulieu",
        "name": "Free-Roaming Ponies & Donkeys",
        "type": "Wildlife",
        "distance": "In village",
        "coords": [50.8167, -1.4583],
        "summary": "Beaulieu village has no cattle grids on its High Street, which means that New Forest ponies, donkeys and cattle wander in freely from the surrounding forest — past the shops, across the green, and down to the river. For children, the sight of a pony ambling past the chocolate shop is unforgettable. Please note that all free-roaming animals in the New Forest are wild: do not feed them, do not stroke them, and keep children at a respectful distance. The experience of watching them go about their business entirely on their own terms is the real thing.",
        "image_url": "",
    },
    {
        "slug": "monorail-little-beaulieu",
        "name": "Aerial Monorail & Little Beaulieu Play Area",
        "type": "Ride & Play",
        "distance": "On site",
        "coords": [50.8167, -1.4583],
        "summary": "Included in the Beaulieu admission ticket, the aerial monorail gives a bird's-eye circuit of the grounds above the motor museum — a gentle, slow ride that gives younger children a memorable overview of the whole estate. Little Beaulieu is an impressive wooden adventure play area adjacent to the monorail, with climbing frames, slides, and play equipment calibrated for a range of ages. It is one of the most popular features of the estate for families with children under ten.",
        "image_url": "",
    },
    {
        "slug": "bucklers-hard-river-cruise",
        "name": "Beaulieu River Cruise",
        "type": "Boat Trip",
        "distance": "45 min walk (or drive)",
        "coords": [50.7950, -1.4332],
        "summary": "From Easter to September, river cruises depart from the jetty at Buckler's Hard on a gentle 45-minute trip up the Beaulieu River and back. The boat passes through the tidal estuary, with commentary on the history of the shipyard and the wildlife of the river. Children enjoy spotting birds on the mudflats and the occasional seal in the estuary. Tickets are available at Buckler's Hard and do not require advance booking, though they can sell out quickly on summer weekends.",
        "image_url": "",
    },
    {
        "slug": "abbey-ruins-explorer",
        "name": "Beaulieu Abbey Ruins Explorer",
        "type": "Historic Site",
        "distance": "2 min walk",
        "coords": [50.8162, -1.4572],
        "summary": "The Abbey ruins are an excellent introduction to medieval history for children — the sheer scale of what was once here, communicated through the surviving walls and the clearly traced outline of the great church, gives a vivid sense of how powerful the monastery once was. The Domus exhibition inside the lay brothers' dormitory is well pitched for family audiences, with displays on monastic life, the Cistercian order, and the extraordinary story of the Abbey's dissolution. The ruins are open ground, so children can explore freely.",
        "image_url": "",
    },
    {
        "slug": "chocolate-studio-beaulieu",
        "name": "Beaulieu Chocolate Studio",
        "type": "Food Experience",
        "distance": "2 min walk",
        "coords": [50.8170, -1.4580],
        "summary": "Watching hand-made chocolates being created through the workshop window at the Chocolate Studio is an experience that hooks children immediately. The studio makes over 30 varieties of filled chocolate, with the production process visible and explained to passers-by. Buying a small box of hand-made chocolates to eat on the walk home is one of the defining pleasures of a day in Beaulieu — and a much better souvenir than anything you can buy in a gift shop.",
        "image_url": "",
    },
]


# ── SHOPPING ──────────────────────────────────────────────────────────────────

SHOPPING["highclere-castle"] = [
    {
        "slug": "highclere-castle-gift-shop",
        "name": "Highclere Castle Gift Shop",
        "type": "Castle Gift Shop",
        "distance": "On site",
        "coords": [51.3275, -1.3600],
        "hours": "From 9:30 on open days",
        "website": "https://highclerecastleshop.co.uk",
        "description": "The official castle gift shop, set in the courtyard and open to all visitors during public opening hours. The range is thoughtfully curated by Lady Carnarvon and covers everything from Egyptian-themed souvenirs and Downton Abbey keepsakes to Lady Carnarvon's own books, Highclere Estate Gin, cashmere scarves, fine bone china, and homewares. Many products are exclusive to Highclere. The online shop ships worldwide.",
        "image_url": "",
    },
    {
        "slug": "highclere-gin-estate-shop",
        "name": "Highclere Estate Gin",
        "type": "Local Produce",
        "distance": "On site",
        "coords": [51.3275, -1.3600],
        "hours": "Available in the gift shop",
        "website": "https://highclerecastleshop.co.uk",
        "description": "Highclere Castle Gin is produced in partnership with a Hampshire distillery using botanicals grown on or near the estate — including lavender from the walled garden. The signature expression is a beautifully balanced London Dry style with floral notes; a flavoured variation using Highclere lavender is also available. Both are sold in the gift shop and online, and make an exceptional memento of a visit.",
        "image_url": "",
    },
    {
        "slug": "highclere-farm-shop",
        "name": "Highclere Estate Produce",
        "type": "Local Produce",
        "distance": "On site",
        "coords": [51.3275, -1.3600],
        "hours": "Available in the gift shop and tearoom",
        "website": "https://highclerecastleshop.co.uk",
        "description": "The castle gift shop and tea room stock a range of estate-branded produce — jams, preserves, biscuits, chocolates, honey, and afternoon tea sets. Lady Carnarvon's range of home and kitchen products, inspired by the castle's 19th-century domestic traditions, is particularly popular. Most items are produced to Lady Carnarvon's own recipes and specifications and are exclusive to Highclere.",
        "image_url": "",
    },
    {
        "slug": "newbury-town-centre",
        "name": "Newbury Town Centre",
        "type": "Town Shopping",
        "distance": "15 min drive",
        "coords": [51.4014, -1.3228],
        "hours": "Mon–Sat 9–17:30, Sun 10:30–16:30",
        "website": "",
        "description": "Newbury is the nearest significant town to Highclere — about 15 minutes by car. The town centre has a good mix of independent shops and high-street brands, a covered market, and several well-regarded independent food and drink retailers. The Kennet Shopping Centre provides a broad range of high-street fashion and homeware. For foodies, the Saturday farmers' market on the Wharf is one of the best in Berkshire.",
        "image_url": "",
    },
    {
        "slug": "chapel-row-curiosities",
        "name": "Chapel Row & Surrounding Villages",
        "type": "Antiques & Curiosities",
        "distance": "10 min drive",
        "coords": [51.3878, -1.2950],
        "hours": "Varies by shop",
        "website": "",
        "description": "The village lanes around Highclere — Chapel Row, Ashford Hill, Kingsclere — contain several interesting antique dealers, farm shops, and independent retailers that reward the kind of aimless exploration that is best done after visiting the castle. Many are only open on certain days, so a quick call ahead is worthwhile. The farm shops in this area are particularly good for local meat, game in season, and Hampshire produce.",
        "image_url": "",
    },
]


SHOPPING["beaulieu-estate"] = [
    {
        "slug": "norris-of-beaulieu",
        "name": "Norris of Beaulieu",
        "type": "General & Gift Store",
        "distance": "2 min walk",
        "coords": [50.8172, -1.4585],
        "hours": "Mon–Sat 10–17, Sun 10–16",
        "website": "",
        "description": "One of the village's oldest established shops, Norris stocks over 40 locally crafted items alongside clothing, gifts, books, and furnishings. It is the kind of shop that defies easy categorisation — part gift shop, part clothing boutique, part local curiosity — and stocks a well-chosen selection of New Forest-themed gifts, books about the area, and practical country clothing. The staff are knowledgeable and helpful, and the stock is refreshed regularly.",
        "image_url": "",
    },
    {
        "slug": "beaulieu-gift-shops",
        "name": "Beaulieu Estate Gift Shops",
        "type": "Attraction Gift Shops",
        "distance": "On site",
        "coords": [50.8167, -1.4583],
        "hours": "Daily 10–17 (or dusk if earlier)",
        "website": "https://www.beaulieu.co.uk/plan-your-visit/gift-shops/",
        "description": "The Beaulieu attraction complex has several gift shops integrated with the motor museum and Palace House. The motor museum shop is excellent for model cars, motoring books, driving-themed gifts, and official Beaulieu merchandise. The Palace House shop sells more traditionally country-house gifts — fine ceramics, textiles, local produce, and New Forest-themed items. The children's section in both shops stocks cuddly New Forest ponies, model cars, and age-appropriate activity books.",
        "image_url": "",
    },
    {
        "slug": "beaulieu-chocolate-studio-shop",
        "name": "Beaulieu Chocolate Studio",
        "type": "Artisan Confectioner",
        "distance": "2 min walk",
        "coords": [50.8170, -1.4580],
        "hours": "Daily 10–17",
        "website": "https://beaulieuchocolatestudio.co.uk",
        "description": "The High Street's most distinctive shop — a hand-made chocolate workshop and studio where Trevor produces over 30 varieties of filled chocolate and a wide range of chocolate bars and gifts, all made on the premises and visible through the workshop window. The chocolates make exceptional gifts and are presented in beautiful handmade boxes. New flavours are added constantly, and the quality is consistently outstanding. A must-visit.",
        "image_url": "",
    },
    {
        "slug": "beaulieu-village-high-street",
        "name": "Beaulieu High Street",
        "type": "Independent Shops",
        "distance": "2 min walk",
        "coords": [50.8170, -1.4582],
        "hours": "Varies by shop, generally 10–17",
        "website": "https://www.beaulieuvillagehighstreet.com",
        "description": "Beaulieu's short High Street contains a surprising number of excellent independent shops for a village of its size — a florist, a boutique clothing shop, an antiques dealer, a well-stocked garden centre, and the Chocolate Studio. The atmosphere is calm and unhurried, and browsing the High Street is a genuine pleasure. Parking is available in the village car park off the B3054. Check the village website for the latest shop listings and seasonal opening hours.",
        "image_url": "",
    },
    {
        "slug": "lymington-market",
        "name": "Lymington Saturday Market",
        "type": "Farmers' & Craft Market",
        "distance": "20 min drive",
        "coords": [50.7571, -1.5459],
        "hours": "Saturdays, from 8:00",
        "website": "",
        "description": "Lymington's Saturday market on the High Street has operated continuously for over 700 years and is one of the finest traditional street markets in southern England. Stalls sell fresh produce, fish, cheese, meat, and local crafts alongside a wide range of clothing, antiques, and bric-a-brac. The market fills the full length of the wide Georgian High Street and draws visitors from across the New Forest. Well worth the short drive from Beaulieu, particularly if combined with lunch at one of the High Street restaurants.",
        "image_url": "",
    },
]


# ── Goodwood Estate & Cowdray Park ────────────────────────────────────────────────────

WALKS["goodwood-estate"] = [
    {
        "slug": "trundle-charlton-circular",
        "title": "The Trundle & Charlton Circular",
        "distance": "9.5 km",
        "duration": "2.5 hrs",
        "difficulty": "Moderate",
        "summary": "A classic South Downs circuit from the Fox Goes Free in Charlton, climbing to The Trundle Iron Age hillfort for 360° views over Goodwood Racecourse, Chichester and the Solent.",
        "image_url": "",
        "center": [50.8970, -0.7510],
        "zoom": 13,
        "waypoint_zoom": 15,
        "route": [
            [50.8937, -0.7435], [50.8940, -0.7455], [50.8947, -0.7480],
            [50.8955, -0.7510], [50.8965, -0.7540], [50.8972, -0.7560],
            [50.8980, -0.7570], [50.8992, -0.7570], [50.9000, -0.7555],
            [50.9005, -0.7535], [50.9005, -0.7505], [50.8998, -0.7490],
            [50.8990, -0.7480], [50.8985, -0.7460], [50.8980, -0.7445],
            [50.8972, -0.7438], [50.8960, -0.7432], [50.8950, -0.7430],
            [50.8940, -0.7433], [50.8937, -0.7435]
        ],
        "waypoint_coords": [
            [50.8937, -0.7435], [50.8992, -0.7570], [50.9005, -0.7510], [50.8960, -0.7435]
        ],
        "waypoints": [
            {
                "title": "The Fox Goes Free, Charlton",
                "description": [
                    "The walk begins at The Fox Goes Free, a 400-year-old Grade II listed country pub tucked into the village of Charlton at the foot of Levin Down — one mile south of Goodwood Racecourse. It is one of the finest pubs in West Sussex, and if you are here on a weekday morning you will share the car park only with dog walkers and the occasional gamekeeper. From the pub, turn left (west) along Charlton Road and take the first lane on the right heading north, where the tarmac quickly gives way to chalk downland track.",
                    "The village of Charlton has its own quiet history. It was the home of the celebrated Charlton Hunt, which in the early 18th century attracted half the nobility of England to this corner of West Sussex. Charles Lennox, the 2nd Duke of Richmond — who brought cricket and horse racing to Goodwood — was a leading figure in the Hunt and it was the pursuit of foxes across these hills that first drew the Lennox family to the area.",
                ],
                "image_url": ""
            },
            {
                "title": "The Trundle (St Roche's Hill)",
                "description": [
                    "The Trundle is the commanding summit of St Roche's Hill at 206 metres, and it is one of the most dramatic viewpoints in the South Downs. The Iron Age hillfort dates from around 500 BC, though its origins go much deeper — a Neolithic causewayed enclosure from around 3000 BC underlies the later ramparts, making this one of the most layered prehistoric sites in Sussex. The double ring of chalk ramparts and ditches are clearly visible and in excellent condition.",
                    "From the summit the view on a clear day is extraordinary: the entire sweep of Goodwood Racecourse lies directly below to the east, with Chichester Cathedral's spire pointing up from the coastal plain beyond, the Isle of Wight floating on the horizon to the south, and the forested Weald rolling north toward Surrey. It is easy to understand why every generation from Neolithic farmers to Second World War radar operators has wanted to occupy this hill.",
                ],
                "image_url": ""
            },
            {
                "title": "Goodwood Racecourse & The Monarch's Way",
                "description": [
                    "Descending east from The Trundle along the Monarch's Way long-distance trail, the path drops towards the road opposite the entrance to Goodwood Racecourse. The racecourse itself dates from 1802, established by the 3rd Duke of Richmond on the downland above his house. King Edward VII memorably described it as 'a garden party with racing tacked on,' and the phrase remains the most accurate encapsulation of Glorious Goodwood's particular social atmosphere.",
                    "The Monarch's Way traces a section of the escape route taken by King Charles II after his defeat at the Battle of Worcester in 1651, and the path here follows the same ridge line he would have used to navigate south toward the coast. The going is open and breezy, with the circuit's perimeter fence close by and fine views west back toward The Trundle.",
                ],
                "image_url": ""
            },
            {
                "title": "Levin Down Nature Reserve",
                "description": [
                    "The return leg crosses the western flanks of Levin Down, a Site of Special Scientific Interest managed by the Sussex Wildlife Trust. This chalk grassland has never been ploughed — an increasingly rare distinction — and is consequently home to plant communities that have vanished almost everywhere else in lowland England. In summer the slopes are alive with chalk heath wildflowers: harebells, chalk milkwort, sheep's fescue and the scattered purple of wild thyme. Exmoor ponies and Herdwick sheep graze the turf in rotation, keeping it short enough for the specialist flora to thrive.",
                    "The path descends gently through the reserve and drops back into Charlton via a track past the old village ponds, returning to the Fox Goes Free after roughly 20 minutes. A post-walk pint here is strongly recommended — the ales are well-kept and the menu is reliably good. Note that the walk is best avoided on race days at Goodwood, when the road and parking near the racecourse become congested.",
                ],
                "image_url": ""
            },
        ]
    },
    {
        "slug": "seeley-copse-farm-trail",
        "title": "Seeley Copse & Home Farm Trail",
        "distance": "4.2 km",
        "duration": "1 hr",
        "difficulty": "Easy",
        "summary": "The estate's signposted red route from The Goodwood Hotel through 20 acres of semi-ancient woodland and past the organic Home Farm — flat, well-surfaced, and suitable for all ages.",
        "image_url": "",
        "center": [50.8992, -0.7442],
        "zoom": 14,
        "waypoint_zoom": 16,
        "route": [
            [50.8982, -0.7420], [50.8985, -0.7435], [50.8988, -0.7450],
            [50.8990, -0.7465], [50.8988, -0.7480], [50.8985, -0.7495],
            [50.8980, -0.7505], [50.8975, -0.7510], [50.8968, -0.7508],
            [50.8962, -0.7500], [50.8958, -0.7490], [50.8960, -0.7475],
            [50.8965, -0.7460], [50.8968, -0.7445], [50.8972, -0.7435],
            [50.8978, -0.7425], [50.8982, -0.7420]
        ],
        "waypoint_coords": [
            [50.8982, -0.7420], [50.8990, -0.7470], [50.8975, -0.7508], [50.8965, -0.7460]
        ],
        "waypoints": [
            {
                "title": "The Goodwood Hotel",
                "description": [
                    "The walk begins at The Goodwood Hotel, the estate's four-star hotel set at the heart of the 12,000-acre estate. Free parking is available here for walkers, and the Tapsters Paddock — a new three-acre secure dog-walking field named after Tapster, a hound immortalised in a 1733 portrait by John Wootton — is accessible for those arriving with dogs. From the hotel, follow the red waymarked route south-east along the gravelled path, which passes the back of the cricket ground within the first few minutes.",
                    "The Goodwood cricket ground has been active since a receipt for brandy, dated 1702, recorded the first game on the estate — making it one of the oldest continuously used cricket grounds in England. The thatched pavilion is a delight, and on summer weekends you may catch Goodwood Cricket Club in action on the square.",
                ],
                "image_url": ""
            },
            {
                "title": "Seeley Copse Ancient Woodland",
                "description": [
                    "Seeley Copse is a 7.5-hectare tract of semi-ancient woodland that forms the centrepiece of the red walking route. The classification 'semi-ancient' means that woodland has existed here continuously since at least 1600, and in parts likely much longer — the variety of field layer plants, including bluebell, wood anemone and dog's mercury, is a reliable indicator of woodland antiquity. The path through the copse is well-maintained and largely flat.",
                    "The canopy is predominantly oak and ash, with hazel coppice at the margins and some fine specimen trees along the main path. Roe deer are frequently seen here in the early morning, and woodpeckers — both great spotted and green — are year-round residents. In spring the bluebells are outstanding and the copse becomes a popular short walk in its own right.",
                ],
                "image_url": ""
            },
            {
                "title": "Goodwood Home Farm",
                "description": [
                    "The route passes close to Goodwood Home Farm, one of the most celebrated organic farms in Britain and described as one of the only genuinely self-sustaining organic farms in Europe. The farm has been supplying the estate with food for over 300 years and converted to organic production in 2000 under the 11th Duke of Richmond. It maintains its own dairy and butchery, rearing beef, pork, lamb and venison to the highest welfare standards.",
                    "The Farm Shop is a short detour from the main route and well worth the visit. It stocks the full range of Home Farm produce — organic meat, award-winning cheeses, home-baked sourdough using heritage flour grown on the estate, and a milk vending machine dispensing fresh raw milk and flavoured milkshakes. The estate's own gin and beer, made with homegrown hops and juniper, are also available. A click-and-collect service is offered online for those who wish to take something home.",
                ],
                "image_url": ""
            },
            {
                "title": "Goodwood Estate Grounds",
                "description": [
                    "The final section of the red route returns through the wider estate grounds, passing stands of mature parkland timber including 300-year-old cedar trees that were planted when the house was first extended in the early 18th century. The path eventually rejoins the gravelled track near the back of the hotel, completing a circuit that takes in woodland, farmland, and the managed pleasure grounds of the estate in a single, unhurried hour.",
                    "The estate's walking routes are open to visitors year-round and are colour-coded throughout. Dogs are welcome but must be kept on leads across all sections — a rule enforced partly because the Home Farm livestock grazes within sight of the path in several places. The Farmer, Butcher, Chef restaurant at the hotel is an excellent choice for lunch after the walk.",
                ],
                "image_url": ""
            },
        ]
    },
    {
        "slug": "halnaker-windmill-walk",
        "title": "Halnaker Windmill & Tree Tunnel",
        "distance": "6.3 km",
        "duration": "1.5 hrs",
        "difficulty": "Moderate",
        "summary": "A rewarding circular walk from Halnaker village via the famous Tree Tunnel on Stane Street to the 18th-century Halnaker Windmill, with views across Chichester and the South Downs.",
        "image_url": "",
        "center": [50.8820, -0.7250],
        "zoom": 13,
        "waypoint_zoom": 15,
        "route": [
            [50.8793, -0.7303], [50.8800, -0.7290], [50.8810, -0.7275],
            [50.8820, -0.7258], [50.8832, -0.7248], [50.8842, -0.7238],
            [50.8850, -0.7220], [50.8856, -0.7205], [50.8858, -0.7190],
            [50.8855, -0.7175], [50.8848, -0.7165], [50.8838, -0.7162],
            [50.8828, -0.7165], [50.8818, -0.7172], [50.8810, -0.7185],
            [50.8805, -0.7200], [50.8802, -0.7220], [50.8798, -0.7255],
            [50.8795, -0.7280], [50.8793, -0.7303]
        ],
        "waypoint_coords": [
            [50.8793, -0.7303], [50.8832, -0.7245], [50.8858, -0.7190], [50.8820, -0.7165]
        ],
        "waypoints": [
            {
                "title": "Halnaker Village",
                "description": [
                    "The walk begins in the hamlet of Halnaker on the A285, where the Anglesey Arms — a handsome listed Georgian pub — makes an ideal start or finish point. From the village, the route picks up the old Roman road of Stane Street heading north-east, which has been in continuous use since at least AD 70. The agger — the raised central spine of the Roman road — is clearly visible underfoot in several places, a remarkable survival after nearly 2,000 years.",
                    "Halnaker itself is a tiny community of farmhouses and estate cottages on the south-eastern edge of the Goodwood Estate. The Goodwood Motor Circuit perimeter is less than a mile to the north, and on weekdays you will often hear the distant sound of test cars and track days drifting across the downs — a peculiarly evocative backdrop to a walk on an ancient road.",
                ],
                "image_url": ""
            },
            {
                "title": "The Halnaker Tree Tunnel",
                "description": [
                    "The approach to Halnaker Mill from the south-west is one of the most photographed paths in West Sussex: a long, straight avenue of mature beech trees whose canopies have grown to arch overhead, creating a cathedral-like green tunnel in summer and a dramatic skeletal corridor in winter. This is a section of Stane Street, the Roman road linking Chichester (Noviomagus) with London, and the beeches were most likely planted in the 18th century to line the approach to the mill.",
                    "The trees are very old and in places lean dramatically, their roots gripping the chalky trackway. In early morning light filtered through a leaf canopy, or on a misty winter's day when the bare branches lace against a pale sky, the tunnel is genuinely magical — one of those English landscapes that makes visitors stop and stand quietly for a few minutes.",
                ],
                "image_url": ""
            },
            {
                "title": "Halnaker Windmill",
                "description": [
                    "Halnaker Mill is a Grade II listed tower mill perched on the ridge at 80 metres, with views across Chichester, the coastal plain and the Solent on clear days. The mill was first mentioned in records as early as 1540 as the feudal mill of the Goodwood Estate, though the current four-storey brick tower dates from the 1740s. It was struck by lightning in 1905, damaging the sails, and fell derelict before being restored in 1934 as a memorial to the wife of local landowner Sir William Bird.",
                    "Visitors cannot enter the mill itself, but the path around its base offers fine views in all directions. Rudyard Kipling walked here and wrote the poem 'Ha'naker Mill' in 1902, lamenting the then-ruined state of the structure. The mill has been repaired several times since and its distinctive white cap is a landmark visible from the Goodwood Racecourse stands on the opposite hill.",
                ],
                "image_url": ""
            },
            {
                "title": "Boxgrove Priory",
                "description": [
                    "The return route can be extended via the village of Boxgrove, a 20-minute walk to the east, where the remains of Boxgrove Priory — a Benedictine priory founded around 1117 — stand in exceptional condition. The guest house and retainer's lodge survive as roofless but substantial ruins, and the priory church, now the parish church of St Mary and St Blaise, contains one of the finest medieval painted stone ceilings in England, dating from around 1530.",
                    "Boxgrove is also the site of the most significant hominid discovery in British prehistory: Homo heidelbergensis fossils and worked flint tools dating to around 500,000 years ago were excavated in the gravel pits to the west of the village in the 1990s. A tibia bone and two teeth from 'Boxgrove Man' are held in the Natural History Museum and represent the oldest well-documented human remains found in Britain.",
                ],
                "image_url": ""
            },
        ]
    },
    {
        "slug": "goodwood-park-golf-woodland",
        "title": "Goodwood Park & Woodland Circuit",
        "distance": "7.5 km",
        "duration": "2 hrs",
        "difficulty": "Easy",
        "summary": "The estate's blue walking route from The Goodwood Hotel through the parkland golf course grounds, past The Kennels and into the estate woodland — gentle going with fine open views.",
        "image_url": "",
        "center": [50.8992, -0.7442],
        "zoom": 13,
        "waypoint_zoom": 15,
        "route": [
            [50.8982, -0.7420], [50.8978, -0.7410], [50.8972, -0.7400],
            [50.8965, -0.7392], [50.8958, -0.7388], [50.8950, -0.7390],
            [50.8942, -0.7398], [50.8938, -0.7412], [50.8938, -0.7430],
            [50.8942, -0.7448], [50.8948, -0.7462], [50.8955, -0.7472],
            [50.8962, -0.7478], [50.8970, -0.7476], [50.8978, -0.7465],
            [50.8983, -0.7452], [50.8984, -0.7438], [50.8982, -0.7425],
            [50.8982, -0.7420]
        ],
        "waypoint_coords": [
            [50.8982, -0.7420], [50.8950, -0.7390], [50.8938, -0.7430], [50.8970, -0.7476]
        ],
        "waypoints": [
            {
                "title": "The Goodwood Hotel & Cricket Ground",
                "description": [
                    "Begin at The Goodwood Hotel and follow the blue waymarked route south along the gravelled path behind the hotel, passing the cricket ground on the left within the first few hundred metres. The thatched pavilion here is one of the most charming estate buildings, and a board at the ground lists the historical records that suggest cricket has been played on this site since at least 1702 — making it a strong contender for the oldest continuously used cricket ground in England.",
                    "The 2nd Duke of Richmond was one of the great early patrons of cricket and helped codify the laws of the game in the 1720s. The estate's association with the sport runs deep: the ground hosted significant matches involving W.G. Grace in the 19th century, and Goodwood Cricket Club continues to play here through the summer.",
                ],
                "image_url": ""
            },
            {
                "title": "The Park Golf Course",
                "description": [
                    "The blue route skirts the fairways of the Park Course, one of two 18-hole courses on the estate. Golf has been played at Goodwood since 1892, making it one of the earlier golf facilities in the south of England. The Park Course was laid out on the estate's pleasure grounds and retains a parkland character — wide, undulating fairways lined with veteran oaks and sweet chestnuts, with fine views across the course toward Chichester and the coastal plain.",
                    "The adjacent woodland along the blue route provides a beautiful fringe to the course and in spring the understorey is particularly good: wood anemone, primrose and patches of wild garlic flower in succession before the canopy closes. The path is clear and well maintained, keeping respectful distance from the golf play at all times.",
                ],
                "image_url": ""
            },
            {
                "title": "The Kennels",
                "description": [
                    "The Kennels is one of the finest estate buildings at Goodwood and its history is remarkable. Built in 1787 by the architect James Wyatt to house the 3rd Duke of Richmond's pack of foxhounds — at a time when hunting was the primary social currency of the aristocracy — it was described by contemporaries as the most luxurious dog house in England, complete with central heating for the hounds. By the 20th century the dogs were long gone, and the building served for decades as the Goodwood Golf Clubhouse.",
                    "Today The Kennels houses a smart restaurant and serves as the hub of the estate's sporting memberships. The building retains its handsome Georgian character and the interior is well worth seeing. The restaurant serves lunch daily in elegant, unhurried surroundings — an excellent reason to time the end of the walk to coincide with the kitchen's opening hours.",
                ],
                "image_url": ""
            },
            {
                "title": "Goodwood Estate Woodland",
                "description": [
                    "The final section of the blue route passes through the estate woodland east of The Kennels, where a series of management coupes in different stages of growth create a varied and wildlife-rich habitat. The estate manages its woodland using a combination of traditional coppice techniques and continuous-cover forestry, providing both timber and habitat in a single system. The results are impressive: the woodland holds good numbers of dormice, bats and woodland birds, and the herb layer is rich and diverse.",
                    "The route returns to the hotel via a broad ride that passes close to the Goodwood House perimeter. The house itself is visible through the trees in winter — a substantial Regency building in stone, flanked by its copper-domed turrets, set in a landscape of rolling parkland that has barely changed since the late 18th century. Guided tours of the house are available on Sundays and Mondays from March to October.",
                ],
                "image_url": ""
            },
        ]
    },
]


# =============================================================================
# COWDRAY PARK — WALKS
# =============================================================================

WALKS["cowdray-park"] = [
    {
        "slug": "cowdray-ruins-river-rother-circular",
        "title": "Cowdray Ruins & River Rother Circular",
        "distance": "11 km",
        "duration": "2.5 hrs",
        "difficulty": "Moderate",
        "summary": "A rewarding estate circuit from the Farm Shop car park, looping east through parkland and forest to Benbow Pond, then south to the River Rother at Ambersham Bridge, returning via ancient polo ground avenues.",
        "image_url": "",
        "center": [51.0167, -0.7200],
        "zoom": 13,
        "waypoint_zoom": 15,
        "route": [
            [51.0167, -0.7200], [51.0172, -0.7188], [51.0178, -0.7172],
            [51.0183, -0.7155], [51.0187, -0.7138], [51.0190, -0.7120],
            [51.0188, -0.7100], [51.0183, -0.7085], [51.0175, -0.7075],
            [51.0165, -0.7068], [51.0155, -0.7072], [51.0148, -0.7082],
            [51.0143, -0.7095], [51.0140, -0.7115], [51.0142, -0.7135],
            [51.0148, -0.7155], [51.0155, -0.7175], [51.0160, -0.7192],
            [51.0163, -0.7200], [51.0167, -0.7200]
        ],
        "waypoint_coords": [
            [51.0167, -0.7200], [51.0190, -0.7120], [51.0143, -0.7095], [51.0155, -0.7175]
        ],
        "waypoints": [
            {
                "title": "Cowdray Farm Shop & Café",
                "description": [
                    "The walk begins at the large free car park beside the Cowdray Farm Shop and Café — the social and commercial heart of the Cowdray Estate. The café, which won the FARMA Best On-Farm Café-Restaurant Award, is an ideal place to breakfast before setting out: the sourdough bread is baked in-house daily from Cowdray wheat, and the estate's own beef, lamb and venison appear on the changing seasonal menu. The farm shop itself stocks a superb range of estate produce, artisan cheese, and deli provisions.",
                    "From the car park, the path heads north-east along a wide gravelled track past the edge of the polo grounds. Polo has been played on these lawns for over a century, and in summer months the distant sound of hoofbeats and the crack of mallets drifts across the estate. The grass polo pitches are among the finest in Europe, maintained to immaculate standards for the summer season.",
                ],
                "image_url": ""
            },
            {
                "title": "Benbow Pond & The Arboretum",
                "description": [
                    "The path eventually reaches Benbow Pond, a lovely and peaceful stretch of water set within the 16-acre John Cowdray Arboretum — a collection of over 140 species of trees planted in honour of the 3rd Viscount Cowdray and now reaching fine maturity. The pond is home to swans, mallards, moorhens, and in winter flocks of tufted duck. In the right season a cormorant can often be seen perched on a dead branch at the water's edge, wings spread in characteristic fashion to dry after diving.",
                    "The arboretum's pathways are mown through grass and are ideal for families — children are free to explore the extraordinary variety of tree shapes and textures, from the broad plates of a spreading cedar to the small-leaved delicacy of a Japanese maple in autumn colour. A memorial plaque near the pond edge marks the origin of the planting.",
                ],
                "image_url": ""
            },
            {
                "title": "The Queen Elizabeth Oak & Forest Paths",
                "description": [
                    "The route passes through the estate's older woodland, where one of the most remarkable trees in Sussex stands in the undergrowth: the Queen Elizabeth Oak, estimated at between 800 and 1,000 years old and recognised as the third oldest Sessile Oak in England. It is named after Queen Elizabeth I, who visited Cowdray in 1591 during one of her summer progresses, and the tree would already have been a mature specimen when she passed beneath it.",
                    "The surrounding forest paths take the walk through a varied mosaic of oak woodland, conifer plantation, and open rides where you are likely to encounter the estate's deer population — roe and fallow both inhabit the forest. The horses and ponies visible in the paddocks beyond the treeline are used for the polo matches on the Lawns and for the Polo Academy, which offers lessons to riders of all abilities.",
                ],
                "image_url": ""
            },
            {
                "title": "The River Rother & Ambersham Bridge",
                "description": [
                    "The southern arc of the walk reaches the River Rother at Ambersham Bridge — a quiet and beautiful spot where the river winds through water meadows fringed with crack willow and alder. The Rother is a classic lowland river, slow-moving and clear in summer, with brook lamprey, brown trout, and occasional otters. The fly fishery on this stretch is managed by the estate, but non-fishing walkers are welcome on the public path along the bank.",
                    "From the bridge the route turns west, following the riverbank and then cutting north through Todham Rough before crossing Crosters Brook and completing the circuit back to the Farm Shop car park. The final section passes through open parkland with clear views back toward the silhouette of the Cowdray Ruins on the horizon — a deeply atmospheric end to one of the finest estate walks in West Sussex.",
                ],
                "image_url": ""
            },
        ]
    },
    {
        "slug": "cowdray-estate-family-loop",
        "title": "Cowdray Estate Family Loop",
        "distance": "2.4 km",
        "duration": "45 min",
        "difficulty": "Easy",
        "summary": "The short, flat, gravelled loop from the Farm Shop past the polo grounds and Cowdray Ruins — perfect for pushchairs and young children, with a play area extension to Easebourne Park.",
        "image_url": "",
        "center": [51.0170, -0.7185],
        "zoom": 15,
        "waypoint_zoom": 17,
        "route": [
            [51.0167, -0.7200], [51.0169, -0.7190], [51.0172, -0.7182],
            [51.0175, -0.7175], [51.0178, -0.7168], [51.0180, -0.7160],
            [51.0178, -0.7152], [51.0174, -0.7145], [51.0169, -0.7140],
            [51.0163, -0.7145], [51.0160, -0.7155], [51.0160, -0.7168],
            [51.0162, -0.7180], [51.0165, -0.7192], [51.0167, -0.7200]
        ],
        "waypoint_coords": [
            [51.0167, -0.7200], [51.0178, -0.7165], [51.0169, -0.7140], [51.0162, -0.7180]
        ],
        "waypoints": [
            {
                "title": "Farm Shop Start",
                "description": [
                    "The family loop starts at the Cowdray Farm Shop and Café car park (postcode GU29 0AJ), where toilets, a café and a dog-friendly outdoor terrace make it an ideal base for families with young children. The paths are mostly wide, gravelled and level — suitable for pushchairs throughout, though a couple of short sections near the polo ground fence are better walked around than through for wheel users.",
                    "From the car park, a wide surfaced path leads through a gate and begins to follow the edge of the polo grounds. In the polo season — April to September — you may be lucky enough to catch a practice chukka on the adjacent pitch, with riders exercising their ponies in the morning light. Even outside the season the scale of the manicured polo lawns is impressive: these are among the finest playing surfaces in world polo.",
                ],
                "image_url": ""
            },
            {
                "title": "The Polo Grounds",
                "description": [
                    "The route follows a surfaced path alongside the polo grounds, with the immaculate green lawns stretching away to the east and the forested hillside of the estate rising beyond. Polo at Cowdray has been played since 1910 and the estate hosts around 400 matches each summer. The highlight of the polo calendar is the British Open Polo Championship for the Cowdray Gold Cup, held in July — a spectacular event that draws players and spectators from across the world.",
                    "Children often want to stop and watch whatever is happening on the grounds, and there is usually enough going on — polo ponies being walked, groundsmen working the pitches, lorries moving equipment — to keep small observers occupied. The backdrop of the Cowdray Ruins visible through the trees to the south adds an atmospheric counterpoint to the sporting scene.",
                ],
                "image_url": ""
            },
            {
                "title": "Cowdray Heritage Ruins",
                "description": [
                    "The path brings the ruins of Cowdray House into view — the shell of one of England's most important early Tudor great houses, built by Sir David Owen in the 1520s and expanded into a palatial residence that rivalled Hampton Court in its time. Both Henry VIII and Elizabeth I visited Cowdray during royal progresses, the latter famously staying for six days in 1591 and hunting deer in the park. On 25 September 1793, a fire of unknown origin destroyed the house overnight, leaving the picturesque shell that stands today.",
                    "The ruins can be viewed from the path over the boundary fence — the visitor centre is open weekends only and closed for conservation works in certain seasons; check the Cowdray website before visiting. The Kitchen Tower is the most complete surviving element, rising three storeys above the surrounding rubble. The Heritage Lottery Fund invested £2.7 million in stabilising and opening the ruins to the public in 2007.",
                ],
                "image_url": ""
            },
            {
                "title": "Easebourne Park Extension",
                "description": [
                    "The main family loop returns to the Farm Shop car park via a straight path through the estate, completing the circuit in a comfortable 45 minutes. For families with energetic children who want more, a two-minute walk beyond the loop reaches Easebourne Park — a generously equipped children's play area designed by Wildwood UK using natural oak materials, with a scooter track, mini castle, wildlife pond, and climbing structures built from timber trunks. Eco-friendly toilets are on site and the car park is free.",
                    "The play area can also be reached directly from the A272 and is a popular destination for families from Midhurst and the surrounding villages. Its natural, adventure-playground aesthetic sits well in the estate landscape — a thoughtful piece of provision that sits between the wild and the formal, much like the Cowdray Estate itself.",
                ],
                "image_url": ""
            },
        ]
    },
    {
        "slug": "midhurst-heritage-trail",
        "title": "Midhurst Heritage Trail & St Ann's Hill",
        "distance": "4.5 km",
        "duration": "1.25 hrs",
        "difficulty": "Easy",
        "summary": "A self-guided town walk tracing Midhurst's 900 years of history — Roman routes, Tudor ruins, a Norman motte, and the elegant Georgian townscape — starting and finishing in the Market Square.",
        "image_url": "",
        "center": [51.0000, -0.7380],
        "zoom": 15,
        "waypoint_zoom": 16,
        "route": [
            [51.0003, -0.7375], [51.0006, -0.7380], [51.0009, -0.7388],
            [51.0012, -0.7395], [51.0016, -0.7400], [51.0020, -0.7402],
            [51.0025, -0.7398], [51.0028, -0.7390], [51.0030, -0.7380],
            [51.0028, -0.7370], [51.0022, -0.7363], [51.0015, -0.7360],
            [51.0008, -0.7363], [51.0004, -0.7370], [51.0003, -0.7375]
        ],
        "waypoint_coords": [
            [51.0003, -0.7375], [51.0025, -0.7398], [51.0028, -0.7380], [51.0015, -0.7360]
        ],
        "waypoints": [
            {
                "title": "Market Square & The Old Market Hall",
                "description": [
                    "The walk begins in Midhurst Market Square, a place of commerce and community since the medieval period and still the beating heart of the town. The most photographed building here is the Old Market Hall — a 16th-century timber-framed jettied structure whose overhanging upper storey creates a covered walkway at street level. It now serves as an annexe to the neighbouring Spread Eagle, one of England's oldest coaching inns, first documented in records from 1430.",
                    "Midhurst contains around 100 listed buildings, representing an extraordinary density of historic architecture for a market town of its size. The variety is striking: Tudor timber frames sit beside Georgian brick frontages, which give way to Victorian Italianate terraces. The town escaped significant modernisation in the 20th century largely because of its position within the South Downs National Park landscape, and the result is one of the most complete historic townscapes in West Sussex.",
                ],
                "image_url": ""
            },
            {
                "title": "Cowdray Ruins from the Town",
                "description": [
                    "From the Market Square, the route follows the signed Heritage Trail toward the River Rother and the eastern fringe of the town, where the dramatic silhouette of the Cowdray Ruins comes into view across the water meadows. The approach on foot from the town is one of the most atmospheric ways to appreciate the scale and romance of the ruined house — the gatehouse towers rise above the river trees with the hill-woodland behind, and in early morning mist the scene could belong to a Romantic landscape painting.",
                    "The 1.5-mile walk from the town centre to the ruins is a designated route through the South Downs National Park, passing open polo fields and riverside meadows rich in wildflowers in summer. For those who wish to explore the ruins themselves, the visitor centre operates guided heritage events from the River Ground Stables, Midhurst, GU29 9AL — weekend opening, heritage@cowdray.co.uk for details.",
                ],
                "image_url": ""
            },
            {
                "title": "St Ann's Hill & The Norman Motte",
                "description": [
                    "The trail climbs briefly to St Ann's Hill, a modest but historically significant eminence above the river where the earthwork mound of a Norman motte-and-bailey castle survives in good condition. The castle was built around 1066 to command views over the River Rother valley and the approaches to the town, and it remained an important defensible position until the more comfortable accommodation of Cowdray House made it redundant in the 16th century. The motte is grassy and unexcavated, its full potential still hidden.",
                    "From the top of St Ann's Hill — which takes only a few minutes to climb — the views over the town and the Rother valley are excellent. The roofscape of Midhurst laid out below, with the South Downs rising beyond, gives a clear sense of why this was a valued strategic position. The church of St Mary Magdalene and St Denys, part-medieval and part-Victorian, stands at the hill's foot and is usually open during the day.",
                ],
                "image_url": ""
            },
            {
                "title": "North Street & The Spread Eagle",
                "description": [
                    "The return route brings the walk back through North Street — the town's secondary commercial spine — and past the Spread Eagle Hotel, which has been receiving travellers at this corner since the early 15th century. Sloping floors, inglenook fireplaces and oak beams have survived the intervening centuries with remarkable completeness, and the hotel's restaurant continues to serve guests in a dining room whose atmosphere is genuinely historic. Afternoon tea here, at £31 per person, is an agreeable way to conclude the town walk.",
                    "Midhurst is a town that rewards unhurried exploration: the Heritage Trail leaflet, available at the South Downs Visitor Centre on North Street, identifies over 30 points of interest within the town boundary. H.G. Wells attended school here at the Midhurst Grammar School (now a private house), and the town features as a setting in several of his early novels, most notably 'Tono-Bungay.'",
                ],
                "image_url": ""
            },
        ]
    },
    {
        "slug": "benbow-pond-arboretum-loop",
        "title": "Benbow Pond & Arboretum Loop",
        "distance": "3.5 km",
        "duration": "1 hr",
        "difficulty": "Easy",
        "summary": "A gentle, flat circuit of Benbow Pond and the John Cowdray Arboretum — 16 acres of ornamental water and over 140 species of trees, with mown grass paths and wildlife watching throughout.",
        "image_url": "",
        "center": [51.0200, -0.7150],
        "zoom": 15,
        "waypoint_zoom": 16,
        "route": [
            [51.0200, -0.7150], [51.0203, -0.7138], [51.0207, -0.7125],
            [51.0210, -0.7112], [51.0210, -0.7098], [51.0207, -0.7085],
            [51.0202, -0.7078], [51.0195, -0.7078], [51.0189, -0.7085],
            [51.0185, -0.7097], [51.0185, -0.7112], [51.0188, -0.7126],
            [51.0193, -0.7137], [51.0198, -0.7147], [51.0200, -0.7150]
        ],
        "waypoint_coords": [
            [51.0200, -0.7150], [51.0210, -0.7105], [51.0195, -0.7078], [51.0188, -0.7128]
        ],
        "waypoints": [
            {
                "title": "Benbow Pond Car Park",
                "description": [
                    "Benbow Pond is accessible directly from the A272 east of Midhurst, with a free car park immediately adjacent (postcode GU28 0AZ). The pond is a popular and entirely unpretentious destination — families spread out on the grass bank to feed the swans and ducks, walkers pause on the bench by the water's edge, and the general atmosphere is one of relaxed, good-natured informality. Swans, mallards, Canada geese, moorhens, tufted duck and occasionally cormorants all use the pond, and the bird life is abundant enough to absorb children for a good while.",
                    "The pond and surrounding 16-acre arboretum are named for Admiral John Benbow (1653–1702), the celebrated and ferociously determined naval commander who fought a legendary action in the Caribbean against a French squadron despite losing his leg to chainshot, continuing to command from his cabin until his eventual death from wounds. A memorial to the 3rd Viscount Cowdray near the pond edge recalls a later chapter in the estate's history.",
                ],
                "image_url": ""
            },
            {
                "title": "John Cowdray Arboretum",
                "description": [
                    "The arboretum wraps around the northern end of the pond and extends into open parkland beyond, with mown grass pathways threading between over 140 species of trees. The collection was planted in 2012 and already contains some impressive specimens — the variety of forms, textures and seasonal colours makes this a rewarding place to visit in any season, but it is particularly fine in autumn when the maples, liquidambars and cherries turn red and gold.",
                    "Young children enjoy the arboretum as a place to simply run about in — the mown paths give freedom and the varied tree shapes provide endless interest. There are no specific labels on every tree, but a leaflet available at the Cowdray Farm Shop identifies the main species and helps visitors make sense of what they are looking at. The walk around the full perimeter of the pond and arboretum takes a comfortable hour.",
                ],
                "image_url": ""
            },
            {
                "title": "Woodland Fringe & Wildlife",
                "description": [
                    "The western edge of the loop passes through the woodland fringe of the arboretum, where the planted trees give way to more established native woodland — oak, ash, hazel and field maple — with a good understorey of shrubs. Roe deer are frequently seen here in the early morning, and the pond edge holds reed buntings and occasional kingfishers in suitable seasons. The walk is quiet enough that wildlife encounters are genuinely likely for those who move slowly.",
                    "The path emerges from the woodland to rejoin the pond's southern bank, completing the loop with a final stretch along the water's edge. The resident swans are accustomed to people and will approach closely — particularly if children are carrying the duck pellets sold at the Farm Shop. Please note that bread is actively harmful to waterfowl: the Farm Shop stocks proper pellet food for visitors to use.",
                ],
                "image_url": ""
            },
            {
                "title": "Return to the Pond Car Park",
                "description": [
                    "The circuit ends back at the pond car park, which is free and has plenty of space even at weekends. The Cowdray Farm Shop and Café at GU29 0AJ — a five-minute drive west along the A272 — is the natural next stop, particularly for those who have worked up an appetite. The café offers breakfast and lunch seven days a week, and the farm shop's deli, butchery and artisan bread counter make it an excellent place to stock up for a picnic on the return visit.",
                    "For those who want to extend the walk, the Midhurst Way long-distance path intersects with the arboretum circuit and can be picked up from the northern end of the pond. The Way runs 29 miles from Haslemere to Arundel and this section through the Cowdray Estate is among its most attractive stretches.",
                ],
                "image_url": ""
            },
        ]
    },
]


# =============================================================================
# GOODWOOD ESTATE — PLACES TO EAT
# =============================================================================

PLACES_TO_EAT["goodwood-estate"] = [
    {
        "slug": "farmer-butcher-chef",
        "name": "Farmer, Butcher, Chef",
        "type": "restaurant",
        "rating": 4.7,
        "guide_price": "£55",
        "open_today": "Breakfast 8–10:30, Lunch Fri–Sat 12–14:30, Dinner daily",
        "distance": "on estate",
        "coords": [50.8982, -0.7420],
        "summary": "The flagship restaurant at The Goodwood Hotel, awarded two AA Rosettes, built entirely around the beef, pork and lamb reared at Goodwood Home Farm. The Butcher's Boards are the signature — great slabs of estate-reared meat carved at the table — and the wider seasonal menu changes constantly to reflect what the farm is producing. Booking essential.",
        "image_url": "",
    },
    {
        "slug": "goodwood-bar-and-grill",
        "name": "The Goodwood Bar & Grill",
        "type": "restaurant",
        "rating": 4.4,
        "guide_price": "£35",
        "open_today": "All-day dining",
        "distance": "on estate",
        "coords": [50.8982, -0.7420],
        "summary": "The more relaxed all-day dining room at The Goodwood Hotel, serving breakfast through to dinner from a seasonal menu rooted in organic Home Farm produce and local suppliers. Family-friendly, informal, and open to non-hotel guests. A good option when Farmer, Butcher, Chef is fully booked.",
        "image_url": "",
    },
    {
        "slug": "the-kennels-restaurant",
        "name": "The Kennels Restaurant",
        "type": "restaurant",
        "rating": 4.5,
        "guide_price": "£45",
        "open_today": "Lunch daily",
        "distance": "on estate",
        "coords": [50.8960, -0.7432],
        "summary": "Set inside the Grade II listed former foxhound kennels — built by James Wyatt in 1787 — this is one of the most atmospheric dining rooms on the Goodwood Estate. Serves a refined lunch menu in surroundings that are elegant without being stuffy. Particularly well placed for golfers finishing the Park or Downs course.",
        "image_url": "",
    },
    {
        "slug": "aerodrome-cafe",
        "name": "Aerodrome Café",
        "type": "cafe",
        "rating": 4.2,
        "guide_price": "£12",
        "open_today": "Daily from morning",
        "distance": "on estate",
        "coords": [50.8592, -0.7601],
        "summary": "A relaxed daytime café at Goodwood Aerodrome with views over the runway and motor circuit — an ideal spot for aviation enthusiasts and families. Serves breakfast, light lunches and snacks in a casual indoor-outdoor format, with aircraft movements to watch throughout the day. Open to all visitors, no booking required.",
        "image_url": "",
    },
    {
        "slug": "fox-goes-free",
        "name": "The Fox Goes Free",
        "type": "pub",
        "rating": 4.6,
        "guide_price": "£35",
        "open_today": "Mon–Sat 11–23, Sun 12–22:30",
        "distance": "5 min drive",
        "coords": [50.8980, -0.7510],
        "summary": "A 400-year-old Grade II listed country pub in the village of Charlton, one mile from Goodwood Racecourse and close to the foot of The Trundle. Widely regarded as the finest pub near the estate, with a well-earned reputation for home-cooked food, real ales and an excellent wine list. The Sunday roast is a serious affair. Book ahead for weekends.",
        "image_url": "",
    },
    {
        "slug": "royal-oak-east-lavant",
        "name": "The Royal Oak Inn",
        "type": "pub",
        "rating": 4.5,
        "guide_price": "£38",
        "open_today": "Daily 12–22",
        "distance": "5 min drive",
        "coords": [50.8820, -0.7630],
        "summary": "A stylish pub with rooms in the village of East Lavant, three miles north of Chichester and just over a mile from Goodwood. The menu is modern British with strong seasonal sourcing from Sussex farms, the wine list is thoughtful, and the garden is one of the most pleasant in the county on a summer evening. Popular with the Goodwood set during Festival of Speed and Revival.",
        "image_url": "",
    },
    {
        "slug": "anglesey-arms-halnaker",
        "name": "The Anglesey Arms",
        "type": "pub",
        "rating": 4.4,
        "guide_price": "£30",
        "open_today": "Mon–Thu 12–22, Fri–Sat 12–22:30, Sun 12–19",
        "distance": "5 min drive",
        "coords": [50.8793, -0.7303],
        "summary": "A handsome Georgian listed pub on Stane Street in the hamlet of Halnaker, on the south-eastern edge of the Goodwood Estate. Offers a highly regarded prix fixe menu (two courses £17.45, three courses £19.95) served all day Monday to Friday, alongside a full seasonal à la carte. The garden is excellent in summer and the pub has a warm, unpretentious character.",
        "image_url": "",
    },
    {
        "slug": "goodwood-home-farm-shop-cafe",
        "name": "Goodwood Home Farm Shop",
        "type": "farm shop",
        "rating": 4.6,
        "guide_price": "£10",
        "open_today": "Daily",
        "distance": "on estate",
        "coords": [50.8968, -0.7445],
        "summary": "As much a destination as a shop — the Home Farm Shop stocks the full breadth of Goodwood's organic estate produce, from butchered meats and award-winning cheeses to sourdough bread, estate gin and fresh milk from the vending machine. The click-and-collect service allows online ordering for collection on the day. Well worth combining with one of the estate walks.",
        "image_url": "",
    },
]


# =============================================================================
# COWDRAY PARK — PLACES TO EAT
# =============================================================================

PLACES_TO_EAT["cowdray-park"] = [
    {
        "slug": "cowdray-farm-shop-cafe",
        "name": "Cowdray Farm Shop & Café",
        "type": "cafe",
        "rating": 4.5,
        "guide_price": "£15",
        "open_today": "Mon–Sat 8–18, Sun 9–17",
        "distance": "on estate",
        "coords": [51.0167, -0.7200],
        "summary": "The hub of the Cowdray Estate for visitors — an award-winning café and traditional farm shop serving breakfast, lunch and afternoon tea from a seasonal menu using estate beef, lamb, venison and game, with bread baked in-house daily from Cowdray wheat. The Friday night wood-fired pizza evenings have a devoted local following. Dogs are welcome outside.",
        "image_url": "",
    },
    {
        "slug": "spread-eagle-hotel",
        "name": "The Spread Eagle Hotel & Spa",
        "type": "hotel restaurant",
        "rating": 4.4,
        "guide_price": "£45",
        "open_today": "Breakfast, Lunch, Dinner daily; Afternoon Tea",
        "distance": "3 min walk",
        "coords": [51.0003, -0.7375],
        "summary": "England's oldest coaching inn — parts of the building date to 1430 — with a restaurant serving modern classic British cuisine from Head Chef Richard Cave-Toye. Sloping floors, inglenook fireplaces and oak beams create a genuinely historic atmosphere. Three-course dinner £42.50; afternoon tea £31 per person. Right in the heart of Midhurst.",
        "image_url": "",
    },
    {
        "slug": "white-horse-easebourne",
        "name": "The White Horse",
        "type": "pub",
        "rating": 4.3,
        "guide_price": "£28",
        "open_today": "Daily 12–22",
        "distance": "5 min walk",
        "coords": [51.0167, -0.7210],
        "summary": "A former coaching inn on Easebourne Street at the edge of the Cowdray Estate — welcoming, unfussy and reliably good value. Serves traditional and contemporary pub dishes, with a well-tended garden. A local favourite that is much quieter and easier to walk into than the better-publicised options in Midhurst town centre.",
        "image_url": "",
    },
    {
        "slug": "greyhound-cocking-causeway",
        "name": "The Greyhound",
        "type": "pub",
        "rating": 4.4,
        "guide_price": "£28",
        "open_today": "Daily 12–22",
        "distance": "5 min drive",
        "coords": [50.9935, -0.7400],
        "summary": "A well-regarded freehouse on the A286 at Cocking Causeway, south of Midhurst, run by the same licensee for over 23 years. The kitchen works with a daily-changing menu built around fresh seasonal produce from local suppliers — fish, game and Sussex beef all feature regularly. The large conservatory and extensive garden are well suited to families.",
        "image_url": "",
    },
    {
        "slug": "frauleins-midhurst",
        "name": "Faustinos",
        "type": "restaurant",
        "rating": 4.3,
        "guide_price": "£30",
        "open_today": "Lunch and dinner Tue–Sun",
        "distance": "5 min walk",
        "coords": [51.0000, -0.7378],
        "summary": "A popular and cheerful Spanish restaurant in Midhurst town centre offering a broad range of tapas, paella and traditional Spanish dishes in a lively setting. Good for groups and informal evenings; the kitchen is generous with portions and the wine list is primarily Iberian. No booking needed for smaller parties on weekdays.",
        "image_url": "",
    },
    {
        "slug": "cafe-24-cowdray",
        "name": "The Polo Club Terrace",
        "type": "cafe",
        "rating": 4.1,
        "guide_price": "£12",
        "open_today": "Seasonal, polo season Apr–Sep",
        "distance": "on estate",
        "coords": [51.0160, -0.7195],
        "summary": "During the polo season, refreshments and light meals are served at the polo ground for spectators watching the matches — an informal and enjoyable way to experience the sport without any prior knowledge of polo. Cowdray polo is open to the public throughout the summer, with the Gold Cup in July the highlight of the calendar.",
        "image_url": "",
    },
    {
        "slug": "lime-and-spice-midhurst",
        "name": "Lime & Spice",
        "type": "restaurant",
        "rating": 4.2,
        "guide_price": "£25",
        "open_today": "Daily dinner, Fri–Sun lunch",
        "distance": "5 min walk",
        "coords": [51.0005, -0.7372],
        "summary": "A well-established Indian restaurant in Midhurst serving both traditional and contemporary Indian cuisine from a wide menu. Reliably good and popular with locals — a useful option when the town's pub-restaurants are full. Takeaway also available.",
        "image_url": "",
    },
]


# =============================================================================
# GOODWOOD ESTATE — PLACES OF INTEREST
# =============================================================================

PLACES_OF_INTEREST["goodwood-estate"] = [
    {
        "slug": "goodwood-house",
        "name": "Goodwood House",
        "type": "Country House",
        "summary": "The principal seat of the Dukes of Richmond since 1697, Goodwood House is a Grade I listed Regency mansion built around an earlier Jacobean structure, with two great wings added by James Wyatt after 1800 to house the collection rescued from a fire at Richmond House in London. The house contains one of the most significant private art collections in Britain, including works by Stubbs, Canaletto and Van Dyck — the Stubbs sporting paintings, commissioned by the 3rd Duke who was one of the artist's most important early patrons, are particularly outstanding. The house is open to the public for guided tours on Sundays and Mondays from March to October; afternoon tea and tour packages are also available.",
        "image_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/5/58/Goodwood_House.jpg/1280px-Goodwood_House.jpg",
    },
    {
        "slug": "the-trundle",
        "name": "The Trundle (St Roche's Hill)",
        "type": "Iron Age Hillfort",
        "summary": "One of the most dramatically situated prehistoric sites in the South Downs, The Trundle crowns St Roche's Hill at 206 metres with double rings of chalk ramparts and ditches dating from around 500 BC. Beneath the Iron Age hillfort lies a Neolithic causewayed enclosure from approximately 3000 BC, making this one of the most chronologically layered prehistoric monuments in Sussex. The summit commands a 360-degree panorama encompassing Goodwood Racecourse directly below, Chichester Cathedral's spire on the coastal plain, the Isle of Wight across the Solent, and the forested Weald to the north. The site is freely accessible via footpath from a car park on Town Lane.",
        "image_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/4/4a/The_Trundle_from_Singleton_hill_-_geograph.org.uk_-_1217555.jpg/1280px-The_Trundle_from_Singleton_hill_-_geograph.org.uk_-_1217555.jpg",
    },
    {
        "slug": "goodwood-motor-circuit",
        "name": "Goodwood Motor Circuit",
        "type": "Motorsport Circuit",
        "summary": "The 2.4-kilometre Goodwood Motor Circuit began life as the perimeter track of RAF Westhampnett airfield, constructed during the Second World War, and hosted its first race meeting on 18 September 1948. It is the only classic circuit in the world to remain entirely in its original layout, and it is now home to the Goodwood Revival — widely regarded as the finest historic motorsport event in the world, held annually in September with all participants and many thousands of spectators in period dress. The Festival of Speed, held each summer in the grounds of Goodwood House, is a separate event featuring a celebrated hillclimb on the estate driveway.",
        "image_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/a/ab/Goodwood_Motor_Circuit.jpg/1280px-Goodwood_Motor_Circuit.jpg",
    },
    {
        "slug": "goodwood-racecourse",
        "name": "Goodwood Racecourse",
        "type": "Racecourse",
        "summary": "Established in 1802 by the 3rd Duke of Richmond on the high downland above the house, Goodwood Racecourse occupies one of the most beautiful natural settings of any flat racecourse in the world. The five-day summer festival known as 'Glorious Goodwood,' held each July, has been a fixture of the English social and sporting calendar for over two centuries — King Edward VII memorably described it as 'a garden party with racing tacked on,' and the description has stuck. Racing takes place across several meetings through the summer, with grandstand tickets available to the general public.",
        "image_url": "",
    },
    {
        "slug": "goodwood-art-foundation",
        "name": "Goodwood Art Foundation",
        "type": "Contemporary Art Gallery",
        "summary": "Launched in May 2025 by the Duke of Richmond on the site of the former Cass Sculpture Foundation, the Goodwood Art Foundation is a non-profit contemporary art organisation with 70 acres of outdoor exhibition space — including wildflower meadow, a cherry grove and newly planted woodland — alongside an indoor gallery. It continues the Goodwood Estate's long engagement with public art and sculpture, commissioning and exhibiting work by living artists in a landscape setting that is itself a significant piece of the estate's heritage. Entry to the outdoor grounds is included in the Café 24 ticket.",
        "image_url": "",
    },
    {
        "slug": "halnaker-windmill",
        "name": "Halnaker Windmill",
        "type": "Historic Windmill",
        "summary": "Halnaker Mill is a Grade II listed four-storey tower mill perched on the ridge east of the Goodwood Estate, first documented in 1540 as the feudal mill of the Goodwood estate and built for the Duke of Richmond. The surviving structure dates from the 1740s and was working until struck by lightning in 1905. Restored in 1934 as a memorial to the wife of Sir William Bird, it is now maintained by West Sussex County Council and is one of the most photographed landmarks in the area. The approach from the south-west via the Halnaker Tree Tunnel — a centuries-old beech avenue on the line of the Roman Stane Street — is one of the most beautiful woodland paths in West Sussex.",
        "image_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/3/3b/Halnaker_windmill_2008.jpg/640px-Halnaker_windmill_2008.jpg",
    },
    {
        "slug": "levin-down-nature-reserve",
        "name": "Levin Down Nature Reserve",
        "type": "Nature Reserve / SSSI",
        "summary": "Levin Down is a Site of Special Scientific Interest managed by the Sussex Wildlife Trust, lying between the villages of Charlton and Singleton in the upper Lavant Valley adjacent to the Goodwood Estate. Its chalk grassland has never been ploughed — an increasingly rare distinction in lowland England — and supports plant communities of extraordinary richness, including chalk heath (heather growing on chalk), a globally scarce habitat type. Herdwick sheep and Exmoor ponies graze the turf to maintain the short sward needed by the specialist flora, which includes harebells, chalk milkwort and wild thyme. The reserve is freely accessible via the network of public footpaths crossing the estate.",
        "image_url": "",
    },
]


# =============================================================================
# COWDRAY PARK — PLACES OF INTEREST
# =============================================================================

PLACES_OF_INTEREST["cowdray-park"] = [
    {
        "slug": "cowdray-heritage-ruins",
        "name": "Cowdray Heritage Ruins",
        "type": "Tudor Ruins",
        "summary": "Cowdray House was one of the most magnificent Tudor great houses in England — a palatial residence begun by Sir David Owen in the 1520s and expanded to rival Hampton Court in scale and ambition. Both Henry VIII (1538) and Elizabeth I (1591, for a six-day visit) stayed here on royal progresses. On 25 September 1793 a fire destroyed the house overnight, reducing it to the roofless but substantial shell that survives today. The Kitchen Tower is the most complete remaining element; the gatehouse and courtyard walls give a vivid impression of the building's original grandeur. The Heritage Lottery Fund invested £2.7 million in stabilising and opening the ruins in 2007. A visitor centre and guided heritage events operate seasonally — check cowdray.co.uk.",
        "image_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/7/7d/Cowdray_House_ruins_2012.jpg/1280px-Cowdray_House_ruins_2012.jpg",
    },
    {
        "slug": "cowdray-park-polo-grounds",
        "name": "Cowdray Park Polo Club",
        "type": "Polo Club",
        "summary": "Polo has been played at Cowdray since 1910, and the estate has grown into England's polo capital — indeed one of the most important polo venues in the world. Around 400 matches are played across the estate's four grounds each summer season (April to September), and spectating is free for many fixtures throughout the week. The highlight of the calendar is the British Open Polo Championship for the Cowdray Gold Cup, contested in July on the Lawns ground against the backdrop of the ruined house — a spectacular and uniquely English spectacle. The Polo Academy offers lessons to riders of all abilities.",
        "image_url": "",
    },
    {
        "slug": "benbow-pond-arboretum",
        "name": "Benbow Pond & John Cowdray Arboretum",
        "type": "Nature & Garden",
        "summary": "A 16-acre ornamental landscape of pond and parkland on the A272 east of Midhurst, with a 140-species arboretum planted in 2012 and named in memory of the 3rd Viscount Cowdray. The pond is home to a rich variety of waterbirds year-round and the mown pathways through the arboretum make it an accessible and enjoyable destination for families and wildlife watchers alike. Free parking adjacent to the pond (GU28 0AZ). The collection is in its vigorous youth and will become finer as the trees mature — already worth visiting in any season.",
        "image_url": "",
    },
    {
        "slug": "queen-elizabeth-oak",
        "name": "The Queen Elizabeth Oak",
        "type": "Ancient Tree",
        "summary": "Hidden in the older woodland of the Cowdray Estate, the Queen Elizabeth Oak is estimated to be between 800 and 1,000 years old, making it the third oldest Sessile Oak in England. It bears the name of Elizabeth I, who visited Cowdray in 1591 and would have passed through this woodland — the tree was already several centuries old when the queen arrived. Ancient oaks of this age are ecological monuments in their own right, hosting hundreds of species of insects, lichens, fungi and birds in and around their decaying timber. The tree is visible from the estate's longer walking routes.",
        "image_url": "",
    },
    {
        "slug": "midhurst-market-town",
        "name": "Midhurst Historic Town Centre",
        "type": "Historic Town",
        "summary": "Midhurst is a remarkably intact medieval market town with around 100 listed buildings encompassing Tudor, Georgian and Victorian architecture in a townscape that has changed little in two centuries. The 16th-century timber-framed Old Market Hall (now an annexe to the Spread Eagle), the Spread Eagle Hotel itself — first documented in 1430 — and the medieval church of St Mary Magdalene and St Denys are the headline set pieces, but the real pleasure is in the unhurried exploration of streets where independent shops, tearooms and gallery spaces occupy buildings of genuine age. H.G. Wells attended school here in the 1880s.",
        "image_url": "",
    },
    {
        "slug": "cowdray-golf-course",
        "name": "Cowdray Park Golf Club",
        "type": "Golf Course",
        "summary": "An 18-hole, par-72 championship parkland course stretching 6,625 yards across 160 acres of the estate, established in 1904 and in continuous use since. The course plays through mature parkland timber with strategic water hazards and fine views of the South Downs ridgeline. Visitor green fees are available and the Golf Lodge provides accommodation for those who wish to make a full golf break of a visit. The course's sandy soil base means it drains well and plays in good condition throughout the year.",
        "image_url": "",
    },
    {
        "slug": "st-anns-hill-midhurst",
        "name": "St Ann's Hill",
        "type": "Norman Motte & Castle",
        "summary": "Rising above the River Rother on the south side of Midhurst, St Ann's Hill preserves the earthwork mound of a Norman motte-and-bailey castle constructed around 1066 to command views over the river valley and the town. The castle was the predecessor of Cowdray House as the principal defensible residence of the local lord, and its earthworks survive in good condition though unexcavated. The summit offers excellent views over the Rother water meadows and the roofscape of the historic town. The church of St Mary Magdalene and St Denys stands at the hill's foot.",
        "image_url": "",
    },
]


# =============================================================================
# GOODWOOD ESTATE — FUN FOR KIDS
# =============================================================================

FUN_FOR_KIDS["goodwood-estate"] = [
    {
        "slug": "forest-adventures",
        "name": "Forest Adventures (Goodwood Education Trust)",
        "type": "Outdoor Activity",
        "distance": "on estate",
        "coords": [50.8988, -0.7480],
        "summary": "Seasonal woodland activity sessions run by the Goodwood Education Trust, offering children fire lighting, den building, nature crafts and marshmallow toasting in the estate's semi-ancient woodland. Available during school holidays and half terms — programmes vary by season. Booking required via the Goodwood Hotel.",
        "image_url": "",
    },
    {
        "slug": "horse-groom-ride",
        "name": "Horse Groom & Ride Experience",
        "type": "Animal Experience",
        "distance": "on estate",
        "coords": [50.8980, -0.7430],
        "summary": "Children aged 4–10 can learn to groom and care for a Goodwood horse before saddling up for a short ride around the estate. Run by the Goodwood Hotel's activity programme during school holidays, this is a particularly popular experience given the estate's deep equestrian heritage — booking ahead is essential as places fill quickly.",
        "image_url": "",
    },
    {
        "slug": "junior-golf",
        "name": "Junior Golf at The Copse",
        "type": "Sport",
        "distance": "on estate",
        "coords": [50.8965, -0.7440],
        "summary": "The Goodwood short game course at The Copse offers a fun introduction to golf for children aged 5–13, with Little Golfers programmes and Junior Golf Camps running during school holidays. Expert coaching is provided in a relaxed and encouraging environment, with the Goodwood estate's parkland setting making this a genuinely enjoyable experience even for complete beginners.",
        "image_url": "",
    },
    {
        "slug": "tapsters-paddock",
        "name": "Tapsters Paddock Dog Walking Field",
        "type": "Outdoor Activity",
        "distance": "on estate",
        "coords": [50.8980, -0.7418],
        "summary": "A three-acre fully fenced secure paddock next to The Goodwood Hotel, opened for dog owners to let their dogs run free. Named after Tapster — a hound immortalised in a 1733 John Wootton portrait — the paddock has a secure six-foot perimeter fence with a double-gated entry. Children who love dogs will enjoy the freedom this gives their companions. Book online; a fee applies.",
        "image_url": "",
    },
    {
        "slug": "goodwood-racecourse-visit",
        "name": "A Day at Goodwood Races",
        "type": "Event / Day Out",
        "distance": "on estate",
        "coords": [50.8915, -0.7388],
        "summary": "Children under 18 go free to all Goodwood Racecourse meetings, making this one of the most accessible and genuinely exciting family days out in West Sussex. The atmosphere at Glorious Goodwood in July is extraordinary — the setting on the high downland is unlike any other racecourse — and smaller meetings through the season are relaxed and easy to navigate with families. Advance tickets recommended for peak fixtures.",
        "image_url": "",
    },
    {
        "slug": "festival-of-speed-family",
        "name": "Festival of Speed Family Area",
        "type": "Event / Day Out",
        "distance": "on estate",
        "coords": [50.8982, -0.7420],
        "summary": "The Goodwood Festival of Speed in July is one of the great family motorsport events in the world, and children aged 12 and under are admitted free. The dedicated Family Area between The Grid and the Startline Bridge offers activities, entertainment and an unrivalled spectacle of historic and modern racing cars climbing the famous hillclimb. The Revival in September adds a traditional fairground — big wheel, helter-skelter, carousel — to the mix.",
        "image_url": "",
    },
    {
        "slug": "goodwood-swimming",
        "name": "Hotel Swimming Pool & Family Activities",
        "type": "Leisure",
        "distance": "on estate",
        "coords": [50.8982, -0.7420],
        "summary": "The Goodwood Hotel pool is open to hotel guests and offers family swim sessions during school holidays, with floats and supervised activities for younger children. The hotel's half-term and Easter programmes typically include a range of additional activities including RC car racing, drone coding sessions, Kwik Cricket on the estate ground, and nature crafts — check the Goodwood website for current school holiday programming.",
        "image_url": "",
    },
]


# =============================================================================
# COWDRAY PARK — FUN FOR KIDS
# =============================================================================

FUN_FOR_KIDS["cowdray-park"] = [
    {
        "slug": "cowdray-maize-maze",
        "name": "Cowdray Maize Maze",
        "type": "Seasonal Attraction",
        "distance": "on estate",
        "coords": [51.0167, -0.7200],
        "summary": "A seasonal summer attraction on the Cowdray Estate, the Maize Maze features a themed stamp trail through the crop with six stations to find, followed by a sunflower and wildflower patch where children can pick their own bunch to take home. The Maze Café serves hot food, ice cream and drinks. Runs approximately July to September — check cowdray.co.uk for opening dates each year.",
        "image_url": "",
    },
    {
        "slug": "easebourne-play-park",
        "name": "Easebourne Adventure Play Park",
        "type": "Playground",
        "distance": "5 min walk",
        "coords": [51.0175, -0.7180],
        "summary": "A generously equipped natural play park at Easebourne designed by Wildwood UK using oak timber structures — a scooter road system, mini castle, wildlife pond, heather and wildflower planting, and complex climbing structures made from tree trunks. Eco toilets, a covered pavilion and free parking on site. One of the better-designed children's play areas in West Sussex, with enough variety to keep children busy for a full morning.",
        "image_url": "",
    },
    {
        "slug": "benbow-pond-wildlife",
        "name": "Benbow Pond Duck Feeding",
        "type": "Wildlife",
        "distance": "5 min drive",
        "coords": [51.0200, -0.7150],
        "summary": "Benbow Pond on the A272 is a perennial favourite with families for its entirely approachable resident waterfowl — swans, ducks, geese and moorhens will all come close for food. Duck and swan pellets (rather than bread) are sold at the Cowdray Farm Shop nearby. The surrounding arboretum paths and pond-edge grass make this an ideal picnic spot, and the free car park immediately adjacent keeps it very accessible.",
        "image_url": "",
    },
    {
        "slug": "watch-polo-free",
        "name": "Watch Polo at Cowdray (Free)",
        "type": "Sport",
        "distance": "on estate",
        "coords": [51.0165, -0.7185],
        "summary": "Between April and September, polo matches are played on the Cowdray Lawns most days and spectating is free for many fixtures — simply walk to the polo ground from the Farm Shop car park. For children encountering polo for the first time, the speed, the horses and the sheer athleticism of the sport make for a genuinely thrilling and memorable afternoon. The Cowdray Gold Cup in July is the highlight, drawing international teams and a festive atmosphere.",
        "image_url": "",
    },
    {
        "slug": "cowdray-wildlife-tours",
        "name": "Cowdray Estate Wildlife Tours",
        "type": "Guided Activity",
        "distance": "on estate",
        "coords": [51.0167, -0.7200],
        "summary": "Guided wildlife tours of the Cowdray Estate are led by an experienced ranger across the 16,500 acres of farmland, woodland and riverbank. Deer, red kites, barn owls and a wide variety of farmland birds are regularly encountered. Particularly good for older children and teenagers with a genuine interest in nature — a far more engaging experience than a standard country walk. Book in advance via enquiries@cowdray.co.uk.",
        "image_url": "",
    },
    {
        "slug": "cowdray-polo-academy",
        "name": "Cowdray Polo Academy",
        "type": "Sport",
        "distance": "on estate",
        "coords": [51.0160, -0.7190],
        "summary": "The Cowdray Park Polo Club Academy offers polo lessons for complete beginners upward, including sessions specifically designed for younger riders. Instruction covers stick work, riding technique and basic polo tactics in a structured and safe environment. Group, individual and corporate sessions are all available — a genuinely unique sporting experience on one of the world's finest polo estates.",
        "image_url": "",
    },
    {
        "slug": "midhurst-town-explore",
        "name": "Exploring Midhurst Town",
        "type": "Town Walk",
        "distance": "3 min walk",
        "coords": [51.0003, -0.7375],
        "summary": "Midhurst's independent shops, tea rooms and market square make for an enjoyable short expedition for children who like exploration. The Old Market Hall's overhanging timber frame, the ruins visible from the town bridge, and the variety of historic buildings along North Street and Church Hill give the town a natural curiosity that rewards young explorers. The South Downs Visitor Centre on North Street has a free exhibition and local walks information.",
        "image_url": "",
    },
]


# =============================================================================
# GOODWOOD ESTATE — SHOPPING
# =============================================================================

SHOPPING["goodwood-estate"] = [
    {
        "slug": "goodwood-home-farm-shop",
        "name": "Goodwood Home Farm Shop",
        "type": "Farm Shop",
        "distance": "on estate",
        "coords": [50.8968, -0.7445],
        "hours": "Daily",
        "website": "https://www.goodwood.com/visit-eat-stay/farm-shop/",
        "description": "One of the most celebrated farm shops in southern England, stocking the full range of Goodwood's certified organic estate produce: butchered beef, pork and lamb, award-winning cheeses, estate-grown sourdough bread, estate gin and beer, flavoured milkshakes from a vending machine dispensing fresh organic milk, and a wide range of store-cupboard provisions. Click-and-collect ordering is available online for 48-hour turnaround.",
        "image_url": "",
    },
    {
        "slug": "goodwood-shop-motor-circuit",
        "name": "The Goodwood Shop (Motor Circuit)",
        "type": "Motorsport Merchandise",
        "distance": "on estate",
        "coords": [50.8592, -0.7601],
        "hours": "Daily 10–16 (excluding holidays and event dates)",
        "website": "https://shop.goodwood.com/",
        "description": "The official Goodwood merchandise store at the motor circuit entrance, stocking the full Festival of Speed and Revival collections alongside year-round estate branded clothing and accessories. From vintage-inspired overalls and racing caps to silver cufflinks and estate memorabilia, this is the place for gifts with genuine Goodwood provenance. Extended hours during motorsport event weekends.",
        "image_url": "",
    },
    {
        "slug": "goodwood-online-shop",
        "name": "The Goodwood Shop (Online)",
        "type": "Online Retailer",
        "distance": "on estate",
        "coords": [50.8982, -0.7420],
        "hours": "Online 24/7",
        "website": "https://shop.goodwood.com/",
        "description": "The full Goodwood retail offer — clothing, accessories, motorsport memorabilia, farm produce and estate gifts — is available through the online shop with delivery across the UK. A useful option for visitors who want to browse and order from home, or pick up last-minute gifts that are not available on the day of their visit.",
        "image_url": "",
    },
    {
        "slug": "fox-goes-free-retail",
        "name": "The Fox Goes Free (Pub Shop)",
        "type": "Pub / Local Retail",
        "distance": "5 min drive",
        "coords": [50.8980, -0.7510],
        "hours": "Mon–Sat 11–23, Sun 12–22:30",
        "website": "https://www.thefoxgoesfree.com/",
        "description": "The Fox Goes Free at Charlton stocks a small but well-chosen range of local ales, wines and artisan food products for visitors who want to take something home from the area. The pub's own branded goods — glassware, condiments, and seasonal hamper items — make good gifts for those visiting from outside the county.",
        "image_url": "",
    },
    {
        "slug": "goodwood-art-foundation-shop",
        "name": "Goodwood Art Foundation",
        "type": "Art Gallery & Shop",
        "distance": "on estate",
        "coords": [50.9020, -0.7420],
        "hours": "Check goodwood.com for current opening",
        "website": "https://www.goodwood.com/",
        "description": "The Goodwood Art Foundation, launched in 2025, includes exhibition and retail space where work by commissioned artists is available for purchase. The 70-acre outdoor sculpture park setting — including wildflower meadow, cherry grove and woodland — makes for an engaging visit in its own right, and the Café 24 small plates restaurant is the best place on the estate for a light artistic lunch.",
        "image_url": "",
    },
]


# =============================================================================
# COWDRAY PARK — SHOPPING
# =============================================================================

SHOPPING["cowdray-park"] = [
    {
        "slug": "cowdray-farm-shop",
        "name": "Cowdray Farm Shop",
        "type": "Farm Shop & Deli",
        "distance": "on estate",
        "coords": [51.0167, -0.7200],
        "hours": "Mon–Sat 8–18, Sun 9–17",
        "website": "https://www.cowdray.co.uk/cowdray-farm-shop/",
        "description": "An award-winning farm shop and traditional butchery on the Cowdray Estate, stocking estate-reared beef, lamb, venison and game, artisan cheeses from the deli counter, freshly baked bread and pastries made in-house daily from Cowdray wheat, honey, jams, marmalades, chutneys, apple juice and estate charcuterie. The FARMA Award-winning operation is much more than a shop — a genuine destination in its own right.",
        "image_url": "",
    },
    {
        "slug": "cowdray-lifestyle",
        "name": "Cowdray Lifestyle",
        "type": "Gifts & Homeware",
        "distance": "on estate",
        "coords": [51.0168, -0.7202],
        "hours": "Daily (same hours as Farm Shop)",
        "website": "https://www.cowdray.co.uk/cowdray-shop/cowdray-living/",
        "description": "Situated directly opposite the Farm Shop, Cowdray Lifestyle stocks a curated selection of homeware, lifestyle goods and estate-branded gifts: Cowdray candles and diffusers, premium rugs, luxury bath products, unusual stationery, children's books and toys from local artisans, and fashion accessories. Also sells online at cowdray.co.uk. A much more interesting gift shop than the estate's understated exterior suggests.",
        "image_url": "",
    },
    {
        "slug": "cowdray-polo-shop",
        "name": "Cowdray Park Polo Club Shop",
        "type": "Polo Merchandise",
        "distance": "on estate",
        "coords": [51.0160, -0.7190],
        "hours": "Polo season only, Apr–Sep",
        "website": "https://cowdraypolo.co.uk/",
        "description": "The Cowdray Park Polo Club retails official polo merchandise and branded goods during the polo season. Items range from clothing and accessories to polo equipment for those who want to take up the sport. A useful stop for visitors attending matches who want a memento of the Gold Cup or a weekend of polo at one of the world's great polo venues.",
        "image_url": "",
    },
    {
        "slug": "spread-eagle-hotel-shop",
        "name": "The Spread Eagle Hotel",
        "type": "Hotel & Gifts",
        "distance": "3 min walk",
        "coords": [51.0003, -0.7375],
        "hours": "Daily",
        "website": "https://www.hshotels.co.uk/spread-eagle",
        "description": "England's oldest coaching inn stocks a small but well-chosen selection of local books, Sussex produce and hotel-branded gifts in the reception and bar areas. A convenient stop for visitors exploring Midhurst town centre who want to pick up something with genuine local provenance — and a visit to the historic interiors is worthwhile in its own right.",
        "image_url": "",
    },
    {
        "slug": "midhurst-independent-shops",
        "name": "Midhurst Town Centre Shops",
        "type": "Independent Retail",
        "distance": "3 min walk",
        "coords": [51.0003, -0.7375],
        "hours": "Mon–Sat 9–17 (most shops)",
        "website": "https://www.thegreatsussexway.org/about-the-area/midhurst/",
        "description": "Midhurst's town centre supports a range of independent retailers across North Street, Knockhundred Row and the Market Square — including delicatessens, bookshops, clothing boutiques and antique dealers. The town has deliberately resisted chain retail and the result is a shopping experience with genuine local character. The weekly market adds further interest on market days.",
        "image_url": "",
    },
]








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
            "image_url": "/static/images/lychgate.jpg",
        },
        {
            "slug": "orchard-corner",
            "name": "The Orchard Corner",
            "status": "new",
            "description": "A peaceful spot at the eastern end of the estate orchard, where the footpath curves through old apple and pear trees. Beautiful in blossom season and tranquil year-round.",
            "image_url": "https://s0.geograph.org.uk/photos/00/38/003846_441a3fd5.jpg",
        },
        {
            "slug": "north-downs-view",
            "name": "North Downs Viewpoint",
            "status": "new",
            "description": "The highest bench position on the estate, on the ridge path with a clear view south across the Tillingbourne valley to the wooded hills beyond. Exposed but spectacular, especially at dawn and dusk.",
            "image_url": "https://s0.geograph.org.uk/photos/28/37/283739_29d19de1.jpg",
        },
        {
            "slug": "cricket-boundary",
            "name": "Cricket Ground Boundary",
            "status": "sponsor",
            "description": "A painted hardwood bench on the boundary of the cricket ground. Currently in need of restoration. The sponsorship includes full refurbishment, new slats, and a fresh plaque.",
            "image_url": "https://shererec.org/wp-content/uploads/2024/10/shere-rec-pavilion-e1729580779341.jpg",
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


def _get_estate(slug: str):
    return ESTATES.get(slug)


def _get_page_content_html(car_park, page_key: str) -> str:
    """Return owner-saved HTML for a sub-page content block, or empty string."""
    import json as _json
    if not car_park or not getattr(car_park, "page_contents", None):
        return ""
    try:
        contents = _json.loads(car_park.page_contents)
        return contents.get(page_key, "")
    except Exception:
        return ""


def _resolve_features(car_park, estate: dict) -> list:
    """Return features list: use car_park.custom_features if set, else ESTATES dict."""
    import json as _json
    if car_park and getattr(car_park, "custom_features", None):
        try:
            return _json.loads(car_park.custom_features)
        except Exception:
            pass
    return estate.get("features", [])


def _get_brand(estate: dict, car_park) -> dict:
    """Return brand colours: car_park DB values if onboarded, else per-estate defaults."""
    if car_park:
        return {
            "primary": car_park.brand_primary or estate.get("brand_primary", "#111"),
            "accent":  car_park.brand_accent  or estate.get("brand_accent",  "#B89A5A"),
            "text":    car_park.brand_text    or "#ffffff",
        }
    return {
        "primary": estate.get("brand_primary", "#111"),
        "accent":  estate.get("brand_accent",  "#B89A5A"),
        "text":    "#ffffff",
    }


def _base_ctx(request, slug: str, estate: dict, car_park, page_name: str = "") -> dict:
    """Common template context shared by every visitor page."""
    return {
        "request":    request,
        "slug":       slug,
        "estate":     estate,
        "estate_name": car_park.owner.name if car_park else estate["name"],
        "car_park_name": page_name,
        "logo_url":   (getattr(car_park, "logo_url", None) or "") if car_park else "",
        "cp_slug":    estate.get("car_park_slug", "") or "",
        "brand":      _get_brand(estate, car_park),
        "features":   _resolve_features(car_park, estate),
    }


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
    cp_slug = estate.get("car_park_slug")
    car_park = db.query(CarPark).filter(CarPark.slug == cp_slug).first() if cp_slug else None
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
    cp_slug = estate.get("car_park_slug")
    car_park = db.query(CarPark).filter(CarPark.slug == cp_slug).first() if cp_slug else None
    ctx = _base_ctx(request, slug, estate, car_park, "Welcome")
    ctx.update({
        "welcome_text": (getattr(car_park, "welcome_text", None) or "") if car_park else "",
        "car_park_tagline": (car_park.tagline or "") if car_park else estate["tagline"],
    })
    return templates.TemplateResponse("location/visitor/welcome.html", ctx)


@router.get("/{slug}/visitor/parking-select", response_class=HTMLResponse)
def visitor_parking_select(request: Request, slug: str, db: Session = Depends(get_db)):
    estate = _get_estate(slug)
    if not estate:
        return RedirectResponse(url="/", status_code=302)
    cp_slug = estate.get("car_park_slug")
    car_park = db.query(CarPark).filter(CarPark.slug == cp_slug).first() if cp_slug else None
    # All active car parks for this owner
    all_cps = []
    if car_park:
        all_cps = (db.query(CarPark)
                   .filter(CarPark.owner_id == car_park.owner_id, CarPark.is_active == True)
                   .order_by(CarPark.id).all())
    return templates.TemplateResponse("location/visitor/parking_select.html", {
        "request": request,
        "slug": slug,
        "estate_name": car_park.owner.name if car_park else estate["name"],
        "car_park_name": "Parking Locations",
        "logo_url": (getattr(car_park, "logo_url", None) or "") if car_park else "",
        "car_parks": all_cps,
    })


def _parking_response(request, slug, car_park_name_override, db, target_cp_slug=None):
    estate = _get_estate(slug)
    if not estate:
        return RedirectResponse(url="/", status_code=302)
    cp_slug = target_cp_slug or estate["car_park_slug"]
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
        "car_park_name": car_park_name_override or car_park.name,
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
    cp_slug = estate.get("car_park_slug")
    car_park = db.query(CarPark).filter(CarPark.slug == cp_slug).first() if cp_slug else None
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
    cp_slug = estate.get("car_park_slug")
    car_park = db.query(CarPark).filter(CarPark.slug == cp_slug).first() if cp_slug else None
    return templates.TemplateResponse("location/visitor/parking_roadside.html", {
        "request": request,
        "slug": slug,
        "estate_name": car_park.owner.name if car_park else estate["name"],
        "car_park_name": "Roadside Parking",
        "logo_url": (getattr(car_park, "logo_url", None) or "") if car_park else "",
    })


@router.get("/{slug}/visitor/parking/{car_park_slug}", response_class=HTMLResponse)
def visitor_parking_by_slug(request: Request, slug: str, car_park_slug: str, db: Session = Depends(get_db)):
    return _parking_response(request, slug, None, db, target_cp_slug=car_park_slug)


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
    cp_slug = estate.get("car_park_slug")
    car_park = db.query(CarPark).filter(CarPark.slug == cp_slug).first() if cp_slug else None
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
    cp_slug = estate.get("car_park_slug")
    car_park = db.query(CarPark).filter(CarPark.slug == cp_slug).first() if cp_slug else None
    walks = WALKS.get(slug, [])
    ctx = _base_ctx(request, slug, estate, car_park, "Walking Routes")
    ctx.update({"walks": walks, "page_content_html": _get_page_content_html(car_park, "walking")})
    return templates.TemplateResponse("location/visitor/walking_list.html", ctx)


@router.get("/{slug}/visitor/walking/{walk_slug}", response_class=HTMLResponse)
def visitor_walking_detail(request: Request, slug: str, walk_slug: str, db: Session = Depends(get_db)):
    estate = _get_estate(slug)
    if not estate:
        return RedirectResponse(url="/", status_code=302)
    cp_slug = estate.get("car_park_slug")
    car_park = db.query(CarPark).filter(CarPark.slug == cp_slug).first() if cp_slug else None
    walks = WALKS.get(slug, [])
    walk = next((w for w in walks if w["slug"] == walk_slug), None)
    if not walk:
        raise HTTPException(status_code=404)
    ctx = _base_ctx(request, slug, estate, car_park, walk["title"])
    ctx["walk"] = walk
    return templates.TemplateResponse("location/visitor/walking_detail.html", ctx)


@router.get("/{slug}/visitor/movies", response_class=HTMLResponse)
def visitor_movies(request: Request, slug: str, db: Session = Depends(get_db)):
    estate = _get_estate(slug)
    if not estate:
        return RedirectResponse(url="/", status_code=302)
    cp_slug = estate.get("car_park_slug")
    car_park = db.query(CarPark).filter(CarPark.slug == cp_slug).first() if cp_slug else None
    ctx = _base_ctx(request, slug, estate, car_park, "Movie Connections")
    ctx["page_content_html"] = _get_page_content_html(car_park, "movies")
    return templates.TemplateResponse("location/visitor/movies.html", ctx)


@router.get("/{slug}/visitor/history-test", response_class=HTMLResponse)
def visitor_history_test(request: Request, slug: str, db: Session = Depends(get_db)):
    estate = _get_estate(slug)
    if not estate:
        return RedirectResponse(url="/", status_code=302)
    cp_slug = estate.get("car_park_slug")
    car_park = db.query(CarPark).filter(CarPark.slug == cp_slug).first() if cp_slug else None
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
    cp_slug = estate.get("car_park_slug")
    car_park = db.query(CarPark).filter(CarPark.slug == cp_slug).first() if cp_slug else None
    ctx = _base_ctx(request, slug, estate, car_park, "Our History")
    ctx["page_content_html"] = _get_page_content_html(car_park, "history")
    return templates.TemplateResponse("location/visitor/history.html", ctx)


@router.get("/{slug}/visitor/places-of-interest", response_class=HTMLResponse)
def visitor_places_of_interest(request: Request, slug: str, db: Session = Depends(get_db)):
    estate = _get_estate(slug)
    if not estate:
        return RedirectResponse(url="/", status_code=302)
    cp_slug = estate.get("car_park_slug")
    car_park = db.query(CarPark).filter(CarPark.slug == cp_slug).first() if cp_slug else None
    places = PLACES_OF_INTEREST.get(slug, [])
    ctx = _base_ctx(request, slug, estate, car_park, "Places of Interest")
    ctx.update({"places": places, "page_content_html": _get_page_content_html(car_park, "places-of-interest")})
    return templates.TemplateResponse("location/visitor/places_of_interest.html", ctx)


@router.get("/{slug}/visitor/fun-for-kids", response_class=HTMLResponse)
def visitor_fun_for_kids(request: Request, slug: str, db: Session = Depends(get_db)):
    estate = _get_estate(slug)
    if not estate:
        return RedirectResponse(url="/", status_code=302)
    cp_slug = estate.get("car_park_slug")
    car_park = db.query(CarPark).filter(CarPark.slug == cp_slug).first() if cp_slug else None
    places = FUN_FOR_KIDS.get(slug, [])
    ctx = _base_ctx(request, slug, estate, car_park, "Fun for Kids")
    ctx.update({"places": places, "page_content_html": _get_page_content_html(car_park, "fun-for-kids")})
    return templates.TemplateResponse("location/visitor/fun_for_kids.html", ctx)


@router.get("/{slug}/visitor/places-to-eat", response_class=HTMLResponse)
def visitor_places_to_eat(request: Request, slug: str, db: Session = Depends(get_db)):
    estate = _get_estate(slug)
    if not estate:
        return RedirectResponse(url="/", status_code=302)
    cp_slug = estate.get("car_park_slug")
    car_park = db.query(CarPark).filter(CarPark.slug == cp_slug).first() if cp_slug else None
    places = PLACES_TO_EAT.get(slug, [])
    ctx = _base_ctx(request, slug, estate, car_park, "Places to Eat")
    ctx.update({"places": places, "page_content_html": _get_page_content_html(car_park, "places-to-eat")})
    return templates.TemplateResponse("location/visitor/places_to_eat.html", ctx)


@router.get("/{slug}/visitor/merch", response_class=HTMLResponse)
def visitor_merch(request: Request, slug: str):
    return RedirectResponse(url=f"/location/{slug}/visitor/shopping", status_code=301)


@router.get("/{slug}/visitor/shopping", response_class=HTMLResponse)
def visitor_shopping(request: Request, slug: str, db: Session = Depends(get_db)):
    estate = _get_estate(slug)
    if not estate:
        return RedirectResponse(url="/", status_code=302)
    cp_slug = estate.get("car_park_slug")
    car_park = db.query(CarPark).filter(CarPark.slug == cp_slug).first() if cp_slug else None
    ctx = _base_ctx(request, slug, estate, car_park, "Shopping")
    ctx.update({
        "shops": SHOPPING.get(slug, []),
        "local_produce": LOCAL_PRODUCE.get(slug, []),
        "page_content_html": _get_page_content_html(car_park, "shopping"),
    })
    return templates.TemplateResponse("location/visitor/shopping.html", ctx)


@router.get("/{slug}/visitor/sponsor-a-bench", response_class=HTMLResponse)
def visitor_bench(request: Request, slug: str, db: Session = Depends(get_db)):
    estate = _get_estate(slug)
    if not estate:
        return RedirectResponse(url="/", status_code=302)
    cp_slug = estate.get("car_park_slug")
    car_park = db.query(CarPark).filter(CarPark.slug == cp_slug).first() if cp_slug else None
    ctx = _base_ctx(request, slug, estate, car_park, "Sponsor a Bench")
    ctx.update({
        "tiers": BENCH_TIERS,
        "bench_types": BENCH_TYPES,
        "bench_locations": BENCH_LOCATIONS.get(slug, []),
        "page_content_html": _get_page_content_html(car_park, "sponsor-a-bench"),
    })
    return templates.TemplateResponse("location/visitor/bench.html", ctx)


@router.get("/{slug}/visitor/legacy", response_class=HTMLResponse)
def visitor_legacy(request: Request, slug: str, db: Session = Depends(get_db)):
    estate = _get_estate(slug)
    if not estate:
        return RedirectResponse(url="/", status_code=302)
    cp_slug = estate.get("car_park_slug")
    car_park = db.query(CarPark).filter(CarPark.slug == cp_slug).first() if cp_slug else None
    ctx = _base_ctx(request, slug, estate, car_park, "Legacy")
    ctx["page_content_html"] = _get_page_content_html(car_park, "legacy")
    return templates.TemplateResponse("location/visitor/legacy.html", ctx)


@router.get("/{slug}/visitor/parking-receipt", response_class=HTMLResponse)
def visitor_parking_receipt(request: Request, slug: str, db: Session = Depends(get_db)):
    estate = _get_estate(slug)
    if not estate:
        return RedirectResponse(url="/", status_code=302)
    cp_slug = estate.get("car_park_slug")
    car_park = db.query(CarPark).filter(CarPark.slug == cp_slug).first() if cp_slug else None
    accent = (car_park.brand_accent or "#8B3A2A") if car_park else "#8B3A2A"
    return templates.TemplateResponse("driver/receipt_placeholder.html", {
        "request": request,
        "slug": slug,
        "estate_name": car_park.owner.name if car_park else "",
        "car_park_name": car_park.name if car_park else "",
        "logo_url": (getattr(car_park, "logo_url", None) or "") if car_park else "",
        "brand": {"accent": accent},
    })
