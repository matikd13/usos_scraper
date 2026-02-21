# AGH USOS plan URL builder. Per program: "prefix" (grupa_kod prefix) + label -> (grupa_part, term)
BASE = "https://web.usos.agh.edu.pl/kontroler.php?_action=katalog2/przedmioty/pokazPlanGrupyPrzedmiotow"
YEAR = "25/26"


def plan_url(prefix: str, grupa_part: str, term: str = "Z") -> str:
    """Build plan URL from prefix (e.g. 230-TEI), group part (e.g. 1S_sem1) and term (Z or L)."""
    cdyd = YEAR.replace("/", "%2F") + "-" + term
    return f"{BASE}&grupa_kod={prefix}_{grupa_part}&cdyd_kod={cdyd}"


PLANS = {
    "teleinformatyka": {
        "prefix": "230-TEI",
        "I Stopień, 1 Sem": ("1S_sem1", "Z"),
        "I Stopień, 2 Sem": ("1S_sem2", "L"),
        "I Stopień, 3 Sem": ("1S_sem3", "Z"),
        "I Stopień, 4 Sem": ("1S_sem4", "L"),
        "I Stopień, 5 Sem": ("1S_sem5", "Z"),
        "I Stopień, 6 Sem": ("1S_sem6", "L"),
        "I Stopień, 7 Sem": ("1S_sem7", "Z"),
        "II stopień, 1 Sem": ("2S_sem1", "L"),
        "II stopień, 2 Sem": ("2S_sem2", "Z"),
        "II stopień, 3 Sem": ("2S_sem3", "L"),
    },
}

URLS = {
    program: {
        label: plan_url(data["prefix"], part, term)
        for label, (part, term) in (x for x in data.items() if x[0] != "prefix")
    }
    for program, data in PLANS.items()
}
