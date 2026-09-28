"""Curated OSRS pet options for tile condition forms.

The submitted value must match the Dink PET payload's ``extra.petName``.
Labels are organiser-facing helpers in the format ``Source - Pet``.

Generic follower pets are intentionally excluded. This list covers:
- Boss pets
- Skilling pets
- Other collection-log pets
"""

OSRS_PET_OPTIONS = (
    # Boss pets
    {"label": "Abyssal Sire - Abyssal orphan", "value": "Abyssal orphan"},
    {"label": "Mad Angel - Aggy", "value": "Aggy"},
    {"label": "Giant Mole - Baby mole", "value": "Baby mole"},
    {"label": "Duke Sucellus - Baron", "value": "Baron"},
    {"label": "Royal Titans - Bran", "value": "Bran"},
    {"label": "Brutus - Beef", "value": "Beef"},
    {"label": "Vardorvis - Butch", "value": "Butch"},
    {
        "label": "Callisto / Artio - Callisto cub",
        "value": "Callisto cub",
    },
    {"label": "Doom of Mokhaiotl - Dom", "value": "Dom"},
    {"label": "Shellbane Gryphon - Gull", "value": "Gull"},
    {"label": "Cerberus - Hellpuppy", "value": "Hellpuppy"},
    {"label": "The Hueycoatl - Huberte", "value": "Huberte"},
    {
        "label": "Alchemical Hydra - Ikkle hydra",
        "value": "Ikkle hydra",
    },
    {"label": "Inferno - Jal-nib-rek", "value": "Jal-nib-rek"},
    {
        "label": "Kalphite Queen - Kalphite princess",
        "value": "Kalphite princess",
    },
    {"label": "Theatre of Blood - Lil' zik", "value": "Lil' zik"},
    {"label": "The Leviathan - Lil'viathan", "value": "Lil'viathan"},
    {
        "label": "The Nightmare / Phosani's Nightmare - Little nightmare",
        "value": "Little nightmare",
    },
    {
        "label": "Maggot King - Maggot marquess",
        "value": "Maggot marquess",
    },
    {"label": "Amoxliatl - Moxi", "value": "Moxi"},
    {"label": "Phantom Muspah - Muphin", "value": "Muphin"},
    {"label": "Nex - Nexling", "value": "Nexling"},
    {"label": "Araxxor - Nid", "value": "Nid"},
    {"label": "Grotesque Guardians - Noon", "value": "Noon"},
    {"label": "Chambers of Xeric - Olmlet", "value": "Olmlet"},
    {
        "label": "Chaos Elemental / Chaos Fanatic - Pet chaos elemental",
        "value": "Pet chaos elemental",
    },
    {
        "label": "Dagannoth Prime - Pet dagannoth prime",
        "value": "Pet dagannoth prime",
    },
    {
        "label": "Dagannoth Rex - Pet dagannoth rex",
        "value": "Pet dagannoth rex",
    },
    {
        "label": "Dagannoth Supreme - Pet dagannoth supreme",
        "value": "Pet dagannoth supreme",
    },
    {
        "label": "Corporeal Beast - Pet dark core",
        "value": "Pet dark core",
    },
    {
        "label": "General Graardor - Pet general graardor",
        "value": "Pet general graardor",
    },
    {
        "label": "K'ril Tsutsaroth - Pet k'ril tsutsaroth",
        "value": "Pet k'ril tsutsaroth",
    },
    {"label": "Kraken - Pet kraken", "value": "Pet kraken"},
    {"label": "Kree'arra - Pet kree'arra", "value": "Pet kree'arra"},
    {
        "label": "Thermonuclear smoke devil - Pet smoke devil",
        "value": "Pet smoke devil",
    },
    {"label": "Zulrah - Pet snakeling", "value": "Pet snakeling"},
    {
        "label": "Commander Zilyana - Pet zilyana",
        "value": "Pet zilyana",
    },
    {"label": "Wintertodt - Phoenix", "value": "Phoenix"},
    {
        "label": "King Black Dragon - Prince black dragon",
        "value": "Prince black dragon",
    },
    {"label": "Scorpia - Scorpia's offspring", "value": "Scorpia's offspring"},
    {"label": "Scurrius - Scurry", "value": "Scurry"},
    {"label": "Skotizo - Skotos", "value": "Skotos"},
    {"label": "Zalcano - Smolcano", "value": "Smolcano"},
    {"label": "Sol Heredit - Smol heredit", "value": "Smol heredit"},
    {"label": "Sarachnis - Sraracha", "value": "Sraracha"},
    {"label": "Tempoross - Tiny tempor", "value": "Tiny tempor"},
    {
        "label": "Tombs of Amascut - Tumeken's guardian",
        "value": "Tumeken's guardian",
    },
    {"label": "TzHaar Fight Cave - Tzrek-jad", "value": "Tzrek-jad"},
    {
        "label": "Venenatis / Spindel - Venenatis spiderling",
        "value": "Venenatis spiderling",
    },
    {
        "label": "Vet'ion / Calvar'ion - Vet'ion jr.",
        "value": "Vet'ion jr.",
    },
    {"label": "Vorkath - Vorki", "value": "Vorki"},
    {"label": "The Whisperer - Wisp", "value": "Wisp"},
    {"label": "Yama - Yami", "value": "Yami"},
    {"label": "The Gauntlet - Youngllef", "value": "Youngllef"},

    # Skilling pets
    {"label": "Hunter - Baby chinchompa", "value": "Baby chinchompa"},
    {"label": "Woodcutting - Beaver", "value": "Beaver"},
    {"label": "Agility - Giant squirrel", "value": "Giant squirrel"},
    {"label": "Fishing - Heron", "value": "Heron"},
    {"label": "Wyrmscraig Goats - Mr mcgroot", "value": "Mr mcgroot"},
    {"label": "Runecraft - Rift guardian", "value": "Rift guardian"},
    {"label": "Mining - Rock golem", "value": "Rock golem"},
    {"label": "Thieving - Rocky", "value": "Rocky"},
    {"label": "Sailing - Soup", "value": "Soup"},
    {"label": "Farming - Tangleroot", "value": "Tangleroot"},

    # Other collection-log pets
    {
        "label": "Guardians of the Rift - Abyssal protector",
        "value": "Abyssal protector",
    },
    {"label": "Master clue scrolls - Bloodhound", "value": "Bloodhound"},
    {"label": "Chompy birds - Chompy chick", "value": "Chompy chick"},
    {"label": "Herbiboars - Herbi", "value": "Herbi"},
    {"label": "Soul Wars - Lil' creator", "value": "Lil' creator"},
    {
        "label": "Barbarian Assault - Pet penance queen",
        "value": "Pet penance queen",
    },
    {"label": "Hunter guild rumours - Quetzin", "value": "Quetzin"},
)


def get_osrs_pet_options():
    """Return a fresh list of pet dropdown option dictionaries."""

    return [dict(option) for option in OSRS_PET_OPTIONS]
