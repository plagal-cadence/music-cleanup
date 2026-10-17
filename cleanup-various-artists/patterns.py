"""Extract a candidate Artist from a track title.

Compilation rips encode the artist in the title in several incompatible ways,
and the direction flips between albums:

    Bach: Minuet in G                            -> composer before a colon
    Sviatoslav Richter: Tchaikovsky- Piano Con..  -> composer between colon and dash
    Chris Rice - Love Like Crazy                 -> artist before a dash
    Love Kills - Freddie Mercury                 -> artist after a dash
    Moonlight Sonata-Beethoven                   -> composer after a bare dash
    Stranger on the shore (Mr. Acker Bilk)       -> artist in trailing parentheses
    Glenn Miller/ Elmer's Tune                   -> artist before a slash

Each strategy below is deliberately naive. Choosing between them is done per
album in 02-resolve.py, by testing candidates against Spotify, because no single
rule can tell "Love Kills - Freddie Mercury" from "Chris Rice - Love Like Crazy".
"""

import re

from tags import normalize

# Surnames as they appear on compilation sleeves. Used to accept a composer
# without a network round trip; anything absent here still works, it just has to
# be corroborated by Spotify instead.
KNOWN_COMPOSERS = {
    "albinoni", "bach", "barber", "bartok", "beethoven", "berlioz", "bizet",
    "boccherini", "borodin", "brahms", "britten", "bruch", "bruckner", "byrd",
    "chabrier", "charpentier", "chopin", "copland", "corelli", "couperin",
    "debussy", "delibes", "dowland", "dukas", "dvorak", "elgar", "enescu",
    "falla", "faure", "franck", "gershwin", "gibbons", "glazunov", "glinka",
    "gluck", "gounod", "grieg", "handel", "haydn", "hindemith", "holst",
    "humperdinck", "ippolitovivanov", "ivanovici", "janacek", "joplin",
    "kabalevsky", "khachaturian", "kodaly", "lalo", "lehar", "leoncavallo",
    "liadov", "liszt", "lully", "macdowell", "mahler", "marcello",
    "mascagni", "massenet", "mendelssohn", "messiaen", "meyerbeer",
    "monteverdi", "mozart", "mussorgsky", "nicolai", "offenbach", "orff",
    "pachelbel", "paganini", "palestrina", "ponchielli", "poulenc",
    "praetorius", "prokofiev", "puccini", "purcell", "rachmaninoff",
    "rachmaninov", "rameau", "ravel", "respighi", "rimskykorsakov",
    "rodrigo", "rossini", "rubinstein", "saintsaens", "sarasate", "satie",
    "scarlatti", "schubert", "schumann", "shostakovich", "sibelius",
    "smetana", "sousa", "stravinsky", "strauss", "suppe", "tallis",
    # "thomas" is deliberately absent: Ambroise Thomas is rare on compilations,
    # while Rob Thomas and B.J. Thomas would be misread as composers.
    "tchaikovsky", "telemann", "vaughanwilliams", "verdi",
    "vivaldi", "wagner", "waldteufel", "walton", "weber", "wieniawski",
    # Also seen on these particular compilations.
    "albeniz", "alford", "arensky", "boellmann", "chaminade", "coates",
    "delius", "dinicu", "flotow", "gade", "granados", "grofe", "guilmant",
    "ketelbey", "lecuona", "mouret", "paderewski", "pergolesi", "pierne",
    "schmidt", "sullivan", "tarrega", "vierne", "weill", "widor", "yradier",
}

# Parenthetical content that is part of the work, not a performer credit.
NON_ARTIST_WORDS = {
    "arr", "arranged", "bonus", "cd", "disc", "edit", "excerpt", "feat",
    "featuring", "from", "instrumental", "live", "major", "medley", "minor",
    "mix", "movement", "no", "op", "part", "piano", "remaster", "remastered",
    "remix", "reprise", "traditional", "version", "vocal", "vol",
}

TRACK_PREFIX = re.compile(r"^\s*\d{1,3}(?:[.\-_ ]\d{1,3})?\s*[.\-_)]\s*")
SPACED_DASH = re.compile(r"\s+[-–—]\s+")
TRAILING_PAREN = re.compile(r"[(\[]([^()\[\]]{2,60})[)\]]\s*$")


def strip_track_prefix(text: str) -> str:
    return TRACK_PREFIX.sub("", text).strip()


def looks_like_name(value: str) -> bool:
    """Reject obvious non-names before spending a Spotify call on them."""
    candidate = value.strip(" .,-–—")
    if not 2 < len(candidate) <= 60:
        return False
    if not normalize(candidate):
        return False
    words = re.findall(r"[^\s]+", candidate)
    if not 1 <= len(words) <= 6:
        return False
    if re.search(r"\d", candidate) and len(words) > 1:
        return False
    if any(normalize(word) in NON_ARTIST_WORDS for word in words):
        return False
    # Work titles are usually sentence-like; artist credits rarely are.
    return not candidate.casefold().startswith(("the ", "a ", "an "))


def _clean(value: str | None) -> str:
    if not value:
        return ""
    return value.strip(" .,;:-–—/([{").strip()


def composer_colon(title: str) -> str:
    """'Bach: Minuet in G' -> 'Bach'."""
    if ":" not in title:
        return ""
    head = title.split(":", 1)[0]
    return _clean(head)


def composer_colon_dash(title: str) -> str:
    """'Sviatoslav Richter: Tchaikovsky- Piano Concerto No. 1' -> 'Tchaikovsky'."""
    if ":" not in title:
        return ""
    tail = title.split(":", 1)[1]
    match = re.split(r"[-–—]", tail, maxsplit=1)
    if len(match) < 2:
        return ""
    return _clean(match[0])


def artist_dash_prefix(title: str) -> str:
    """'Chris Rice - Love Like Crazy' -> 'Chris Rice'."""
    parts = SPACED_DASH.split(title, maxsplit=1)
    if len(parts) < 2:
        parts = title.split("-", 1)
        if len(parts) < 2:
            return ""
    return _clean(parts[0])


def artist_dash_suffix(title: str) -> str:
    """'Moonlight Sonata-Beethoven' -> 'Beethoven'."""
    parts = SPACED_DASH.split(title)
    if len(parts) < 2:
        parts = title.rsplit("-", 1)
        if len(parts) < 2:
            return ""
    return _clean(parts[-1])


def artist_paren_suffix(title: str) -> str:
    """'Stranger on the shore (Mr. Acker Bilk)' -> 'Mr. Acker Bilk'."""
    match = TRAILING_PAREN.search(title)
    return _clean(match.group(1)) if match else ""


def artist_slash_prefix(title: str) -> str:
    """\"Glenn Miller/ Elmer's Tune\" -> 'Glenn Miller'."""
    if "/" not in title:
        return ""
    return _clean(title.split("/", 1)[0])


# Order matters only as a tie-break; scoring in 02-resolve.py picks the winner.
STRATEGIES: dict[str, callable] = {
    "composer_colon": composer_colon,
    "composer_colon_dash": composer_colon_dash,
    "artist_dash_prefix": artist_dash_prefix,
    "artist_dash_suffix": artist_dash_suffix,
    "artist_paren_suffix": artist_paren_suffix,
    "artist_slash_prefix": artist_slash_prefix,
}

# Strategies whose output is a composer surname, so KNOWN_COMPOSERS can vouch
# for it offline.
COMPOSER_STRATEGIES = {"composer_colon", "composer_colon_dash", "artist_dash_suffix"}


def is_known_composer(value: str) -> bool:
    return normalize(value) in KNOWN_COMPOSERS


# Sleeve credits carry decoration Spotify does not: "Mr. Acker Bilk" is listed as
# "Acker Bilk", and "Jan Morks Quartet" as "Jan Morks".
HONORIFICS = re.compile(r"^(?:mr|mrs|ms|miss|dr|sir|the)\.?\s+", re.IGNORECASE)
ENSEMBLE_SUFFIX = re.compile(
    r"\s+(?:quartet|quintet|sextet|septet|octet|trio|duo|band|orchestra|orch|"
    r"ensemble|singers|choir|chorus|chorale|group|combo|players|consort|"
    r"big\s+band|and\s+his\s+orchestra|with\s+his\s+orchestra)$",
    re.IGNORECASE,
)
CREDIT_SPLIT = re.compile(r"\s*(?:\+|&|/|,|\bfeat\.?\b|\bwith\b|\band\b)\s*", re.IGNORECASE)


DISC_SUFFIX = re.compile(
    r"[\s,\-–—]*[(\[]?\s*(?:disc|disk|cd|volume|vol)\.?\s*[ivx\d]+\s*[)\]]?\s*$",
    re.IGNORECASE,
)


def album_search_names(album: str) -> list[str]:
    """Album name plus a disc/volume-stripped form, so 'X - Disc 1' can find 'X'."""
    names = [album.strip()]
    trimmed = album.strip()
    for _ in range(2):  # "Favourites, Vol 2 (Disc 1)"
        stripped = DISC_SUFFIX.sub("", trimmed).strip(" -–—,:")
        if stripped == trimmed:
            break
        trimmed = stripped
        if trimmed and trimmed not in names:
            names.append(trimmed)
    return [name for name in names if len(name) > 2]


# Composer surnames that are also common performer surnames. Fine for vouching
# for a name the user's own title supplied, but they must never let an arbitrary
# Spotify artist be mistaken for a composer: Janis Joplin is not Scott Joplin,
# and Maxine Sullivan is not Arthur Sullivan.
AMBIGUOUS_SURNAMES = {
    "alford", "barber", "byrd", "coates", "franck", "gade", "gibbons", "joplin",
    "schmidt", "sullivan", "walton", "weber",
}


def composer_in(artist_name: str) -> bool:
    """True when this Spotify artist name ends in an unambiguous composer surname."""
    tokens = [normalize(word) for word in artist_name.split() if normalize(word)]
    if not tokens:
        return False
    surname = tokens[-1]
    return surname in KNOWN_COMPOSERS and surname not in AMBIGUOUS_SURNAMES


def name_variants(value: str) -> list[str]:
    """Progressively plainer forms of a credit, best first, for artist lookups."""
    variants: list[str] = []

    def add(candidate: str) -> None:
        candidate = candidate.strip(" .,;:-–—")
        if candidate and candidate not in variants:
            variants.append(candidate)

    add(value)
    stripped = HONORIFICS.sub("", value).strip()
    add(stripped)
    for base in (value, stripped):
        add(ENSEMBLE_SUFFIX.sub("", base))
    # "Mr. Acker Bilk + Bent Fabric" -> the first credited act.
    for base in (stripped, value):
        parts = CREDIT_SPLIT.split(base)
        if len(parts) > 1 and parts[0].strip():
            add(parts[0])
            add(ENSEMBLE_SUFFIX.sub("", parts[0]))
    return variants


def extract(strategy: str, title: str) -> str:
    candidate = STRATEGIES[strategy](title)
    if not candidate or not looks_like_name(candidate):
        return ""
    return candidate


__all__ = [
    "COMPOSER_STRATEGIES",
    "KNOWN_COMPOSERS",
    "STRATEGIES",
    "extract",
    "is_known_composer",
    "looks_like_name",
    "name_variants",
    "strip_track_prefix",
]
