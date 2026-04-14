# All estates in the LandMarque network.
# features controls which blocks appear on the visitor welcome page.
# car_park_slug links to a CarPark record in the database (only set when onboarded).

ESTATES = {

    # ── Surrey — private estates ─────────────────────────────────────────────────

    "shere-manor-estate": {
        "name": "Shere Manor Estate",
        "tagline": "A historic estate at the heart of one of England's most beautiful villages.",
        "description": "Shere Manor Estate manages public facilities around the picturesque village of Shere in the Surrey Hills AONB. Visitors enjoy walking, history, and filming locations used in major Hollywood productions.",
        "county": "Surrey",
        "lat": 51.2164, "lng": -0.4444,
        "car_park_slug": "shere-manor",
        "features": ["parking", "history", "movies", "places-to-eat", "walking", "places-of-interest", "fun-for-kids", "shopping", "benches", "legacy"],
    },
    "hurtwood-estate": {
        "name": "Hurtwood Estate",
        "tagline": "The largest private open space in the Surrey Hills — over 1,500 acres of moorland and woodland.",
        "description": "The Hurtwood Estate is one of the most significant private landholdings in the Surrey Hills AONB, covering moorland, ancient woodland, and heathland around Peaslake, Holmbury Hill, and Ewhurst. The estate generously allows public access to the majority of its land and manages several car parks serving the Surrey Hills walking and cycling community.",
        "county": "Surrey",
        "lat": 51.1834, "lng": -0.3883,
        "features": ["parking", "walking", "cycling", "places-of-interest", "benches", "legacy"],
    },
    "albury-estate": {
        "name": "Albury Estate",
        "tagline": "A private Capability Brown landscape in the Tillingbourne valley — neighbour to Shere.",
        "description": "Albury Park is a private estate in the Tillingbourne valley immediately east of Shere, landscaped by John Evelyn in the seventeenth century. The estate includes a remarkable series of terraced gardens, a Pugin chapel, and the former parish church of St Peter and St Paul — one of Surrey's finest Saxon buildings.",
        "county": "Surrey",
        "lat": 51.2133, "lng": -0.4233,
        "features": ["history", "walking", "places-of-interest", "benches", "legacy"],
    },
    "wotton-estate": {
        "name": "Wotton Estate",
        "tagline": "John Evelyn's ancestral home — a historic landscape garden at the foot of Leith Hill.",
        "description": "Wotton House near Dorking is the ancestral home of the Evelyn family, most famous for the diarist John Evelyn who created the gardens here before lending his expertise to Albury Park. The estate grounds, with their temples, terraces, and ponds, were designed by Evelyn himself and restored in the late twentieth century.",
        "county": "Surrey",
        "lat": 51.2048, "lng": -0.4069,
        "features": ["history", "walking", "places-of-interest", "benches", "legacy"],
    },
    "denbies-wine-estate": {
        "name": "Denbies Wine Estate",
        "tagline": "England's largest single-estate winery — 265 acres of vines on the North Downs above Dorking.",
        "description": "Denbies Wine Estate near Dorking is England's largest single-estate winery, with 265 acres of vines on the chalk slopes of the North Downs. The estate offers vineyard tours, a winery, gallery, restaurant, and accommodation, and is one of Surrey's most popular visitor attractions.",
        "county": "Surrey",
        "lat": 51.2337, "lng": -0.3357,
        "features": ["history", "walking", "places-of-interest", "places-to-eat", "shopping", "events", "benches", "legacy"],
    },
    "abinger-estate": {
        "name": "Abinger Estate",
        "tagline": "A historic village estate in the Surrey Hills, centred on one of England's oldest villages.",
        "description": "The Abinger Estate encompasses the villages of Abinger Common and Abinger Hammer in the Surrey Hills, with ancient woodland, the Friday Street hammer pond, and walking routes onto Leith Hill. The estate has strong associations with E.M. Forster, who spent much of his life in the area.",
        "county": "Surrey",
        "lat": 51.2070, "lng": -0.3980,
        "features": ["history", "walking", "places-of-interest", "places-to-eat", "benches", "legacy"],
    },
    "loseley-park": {
        "name": "Loseley Park",
        "tagline": "A privately owned Elizabethan manor farmed by the same family for 450 years.",
        "description": "Loseley Park is a working farm and Elizabethan manor house on the edge of Guildford, home to the More-Molyneux family since 1562. The walled garden, built from stone salvaged from Waverley Abbey, is one of the finest in Surrey.",
        "county": "Surrey",
        "lat": 51.2109, "lng": -0.5889,
        "features": ["history", "walking", "places-of-interest", "benches", "legacy", "events"],
    },
    # ── West Sussex — private estates ────────────────────────────────────────────

    "arundel-castle": {
        "name": "Arundel Castle",
        "tagline": "A medieval castle and ducal seat rising above the River Arun in West Sussex.",
        "description": "Arundel Castle is the ancestral home of the Duke of Norfolk, one of the premier peers of England. The castle dates from the eleventh century and houses a remarkable collection of paintings, furniture, and personal possessions of Mary Queen of Scots.",
        "county": "West Sussex",
        "lat": 50.8561, "lng": -0.5510,
        "features": ["history", "walking", "places-of-interest", "benches", "legacy", "events", "places-to-eat"],
    },
    "goodwood-estate": {
        "name": "Goodwood Estate",
        "tagline": "A 12,000-acre estate home to the world's greatest motorsport and horseracing events.",
        "description": "Goodwood Estate in West Sussex is one of Britain's most celebrated sporting estates, home to the Festival of Speed, Goodwood Revival, and the Glorious Goodwood horseracing festival. The estate farm, hotel, and golf course support a year-round visitor offer.",
        "county": "West Sussex",
        "lat": 50.8651, "lng": -0.7554,
        "features": ["history", "walking", "places-of-interest", "benches", "legacy", "events", "places-to-eat", "cycling"],
    },
    "cowdray-park": {
        "name": "Cowdray Estate",
        "tagline": "A 16,500-acre West Sussex estate — home to world-class polo and haunted Tudor ruins.",
        "description": "Cowdray Estate near Midhurst is a 16,500-acre sporting estate and one of Britain's leading polo venues. The estate contains the dramatic ruins of Cowdray House, destroyed by fire in 1793, and a working farm. The annual Cowdray Park Polo Gold Cup is one of the most prestigious in the world.",
        "county": "West Sussex",
        "lat": 50.9900, "lng": -0.7400,
        "features": ["history", "walking", "places-of-interest", "benches", "legacy", "events"],
    },
    "parham-house": {
        "name": "Parham House",
        "tagline": "A great Elizabethan house in a deer park below the South Downs.",
        "description": "Parham House is a privately owned Elizabethan house near Pulborough, set in a deer park below the South Downs. The house contains a collection of fine art, needlework, and furniture, and the four-acre walled garden is among the finest in Sussex.",
        "county": "West Sussex",
        "lat": 50.9330, "lng": -0.4420,
        "features": ["history", "walking", "places-of-interest", "benches", "legacy", "events"],
    },
    "leonardslee-gardens": {
        "name": "Leonardslee Gardens",
        "tagline": "A valley woodland garden of rare beauty — one of the largest private gardens in England.",
        "description": "Leonardslee Gardens near Horsham is a privately owned woodland garden in a steep valley, created by Sir Edmund Loder from 1889. Famous for its bluebells, rhododendrons, and wallabies, the garden reopened after restoration in 2019 and includes a luxury hotel and restaurant.",
        "county": "West Sussex",
        "lat": 51.0280, "lng": -0.2710,
        "features": ["history", "walking", "places-of-interest", "benches", "legacy", "events", "places-to-eat"],
    },
    # ── East Sussex — private estates ────────────────────────────────────────────

    "firle-place": {
        "name": "Firle Place",
        "tagline": "A flint-faced Tudor and Georgian house in the South Downs — home to the Gage family for 500 years.",
        "description": "Firle Place is a privately owned country house in East Sussex, home to the Gage family since the fifteenth century. The house contains an outstanding collection of Old Master paintings and is set in the South Downs National Park below the chalk escarpment of Firle Beacon.",
        "county": "East Sussex",
        "lat": 50.8470, "lng": 0.0830,
        "features": ["history", "walking", "places-of-interest", "benches", "legacy", "events"],
    },
    "glynde-place": {
        "name": "Glynde Place",
        "tagline": "A sixteenth-century flint manor house near Glyndebourne, still in private occupation.",
        "description": "Glynde Place is a privately owned sixteenth-century house near Lewes, built from knapped flint and overlooking the South Downs. The house has been home to the Trevor and Brand families and retains an intimate, lived-in character.",
        "county": "East Sussex",
        "lat": 50.8660, "lng": 0.0520,
        "features": ["history", "walking", "places-of-interest", "benches", "legacy"],
    },

    # ── Kent — private estates ────────────────────────────────────────────────────

    "penshurst-place": {
        "name": "Penshurst Place",
        "tagline": "A medieval baron's hall and a garden enclosed by a mile of yew hedge.",
        "description": "Penshurst Place has been home to the Sidney family since 1552, one of England's finest examples of a medieval baron's hall with rooms and furniture dating back to the fourteenth century. The walled gardens are among the oldest in England.",
        "county": "Kent",
        "lat": 51.1734, "lng": 0.1697,
        "features": ["history", "walking", "places-of-interest", "benches", "legacy", "events", "fun-for-kids"],
    },
    "hever-castle": {
        "name": "Hever Castle",
        "tagline": "Anne Boleyn's childhood home — a double-moated castle in the Kentish Weald.",
        "description": "Hever Castle was the childhood home of Anne Boleyn, the second wife of Henry VIII. The thirteenth-century castle was later acquired by William Waldorf Astor, who added the award-winning gardens. Today the castle and grounds offer one of Kent's finest visitor experiences.",
        "county": "Kent",
        "lat": 51.1908, "lng": 0.1097,
        "features": ["history", "walking", "places-of-interest", "benches", "legacy", "events", "places-to-eat", "fun-for-kids"],
    },
    "lullingstone-castle": {
        "name": "Lullingstone Castle",
        "tagline": "A Tudor gatehouse and a World Garden — five centuries of one family in the Darent valley.",
        "description": "Lullingstone Castle is a privately owned Tudor and Georgian house in the Darent valley, home to the Hart Dyke family. The estate is home to the World Garden of Plants, created by Tom Hart Dyke after his capture in the Darien Gap, containing plants from every country in the world.",
        "county": "Kent",
        "lat": 51.3810, "lng": 0.1610,
        "features": ["history", "walking", "places-of-interest", "benches", "legacy", "events", "fun-for-kids"],
    },
    "groombridge-place": {
        "name": "Groombridge Place",
        "tagline": "A seventeenth-century moated manor with enchanted forest and formal walled gardens.",
        "description": "Groombridge Place is a privately owned seventeenth-century moated manor on the Kent-Sussex border, with formal walled gardens designed by John Evelyn and an enchanted forest attraction. The manor was used as the location for the 1993 film of The Secret Garden.",
        "county": "Kent",
        "lat": 51.1120, "lng": 0.1740,
        "features": ["history", "walking", "places-of-interest", "benches", "legacy", "movies", "fun-for-kids", "events"],
    },

    # ── Hampshire — private estates ───────────────────────────────────────────────

    "highclere-castle": {
        "name": "Highclere Castle",
        "tagline": "The real Downton Abbey — a Victorian Gothic mansion in Hampshire parkland.",
        "description": "Highclere Castle is the ancestral home of the Earl of Carnarvon and the filming location for all series of Downton Abbey. The Gothic Revival mansion sits in 1,000 acres of Capability Brown parkland and attracts over 200,000 visitors a year.",
        "county": "Hampshire",
        "lat": 51.3247, "lng": -1.3635,
        "features": ["history", "walking", "places-of-interest", "benches", "legacy", "events", "places-to-eat", "movies", "fun-for-kids"],
    },
    "beaulieu-estate": {
        "name": "Beaulieu Estate",
        "tagline": "A riverside New Forest estate with a palace house, abbey ruins, and the National Motor Museum.",
        "description": "Beaulieu is a private estate in the New Forest, home to the Montagu family and the National Motor Museum. The estate includes Palace House, the ruins of Beaulieu Abbey, and extensive grounds on the Beaulieu River.",
        "county": "Hampshire",
        "lat": 50.8143, "lng": -1.4562,
        "features": ["history", "walking", "places-of-interest", "benches", "legacy", "events", "places-to-eat", "fun-for-kids"],
    },
    "exbury-gardens": {
        "name": "Exbury Gardens",
        "tagline": "A 200-acre woodland garden famous for the world's largest collection of rhododendrons.",
        "description": "Exbury Gardens in the New Forest was created by Lionel de Rothschild in the 1920s and contains one of the world's great collections of rhododendrons, azaleas, camellias, and magnolias. The steam railway and seasonal events make it one of Hampshire's leading visitor attractions.",
        "county": "Hampshire",
        "lat": 50.7999, "lng": -1.3699,
        "features": ["history", "walking", "places-of-interest", "benches", "legacy", "events", "places-to-eat", "fun-for-kids"],
    },
    "broadlands-estate": {
        "name": "Broadlands Estate",
        "tagline": "The Palladian home of Lord Mountbatten, set in parkland on the banks of the River Test.",
        "description": "Broadlands is a Palladian mansion near Romsey, the ancestral home of Lord Mountbatten and the honeymoon retreat of both The Queen and Prince Philip, and Princess Anne. The estate grounds run down to the River Test.",
        "county": "Hampshire",
        "lat": 51.0232, "lng": -1.5000,
        "features": ["history", "walking", "places-of-interest", "benches", "legacy"],
    },
    "stratfield-saye-estate": {
        "name": "Stratfield Saye Estate",
        "tagline": "The Duke of Wellington's Hampshire estate — given to the Iron Duke by a grateful nation.",
        "description": "Stratfield Saye is the ancestral home of the Duke of Wellington, given to the first Duke by the nation following his victory at Waterloo. The house retains its Regency character and the estate runs a regular events and open day programme.",
        "county": "Hampshire",
        "lat": 51.3432, "lng": -1.0778,
        "features": ["history", "walking", "places-of-interest", "benches", "legacy", "events"],
    },
    "avington-park": {
        "name": "Avington Park",
        "tagline": "A privately owned Georgian mansion above the Itchen valley — once a royal retreat.",
        "description": "Avington Park is a privately owned Georgian house near Winchester, set in parkland above the chalk stream of the River Itchen. The house was visited by Charles II and is one of a small number of privately owned houses that open to the public on a regular basis.",
        "county": "Hampshire",
        "lat": 51.0720, "lng": -1.2700,
        "features": ["history", "walking", "places-of-interest", "benches", "legacy", "events"],
    },

    # ── Berkshire — private estates ───────────────────────────────────────────────

    "englefield-estate": {
        "name": "Englefield Estate",
        "tagline": "A 12,000-acre private estate on the Thames with a renowned garden and working farms.",
        "description": "Englefield Estate near Theale is one of the largest private estates in Berkshire, owned by the Benyon family. The house dates from the sixteenth century and the garden includes a walled kitchen garden and extensive woodland.",
        "county": "Berkshire",
        "lat": 51.4270, "lng": -1.1110,
        "features": ["history", "walking", "places-of-interest", "benches", "legacy", "events"],
    },
    "welford-park": {
        "name": "Welford Park",
        "tagline": "A Queen Anne house in the Lambourn valley with one of England's greatest snowdrop displays.",
        "description": "Welford Park is a privately owned Queen Anne house in the Lambourn valley near Newbury, with grounds that attract thousands of visitors each February for what is considered one of England's finest snowdrop gardens.",
        "county": "Berkshire",
        "lat": 51.4290, "lng": -1.4100,
        "features": ["history", "walking", "places-of-interest", "benches", "legacy", "events", "places-to-eat"],
    },

}
