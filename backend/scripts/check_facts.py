"""Checks the recommended plants' facts against their live sources and writes a report.

    venv\\Scripts\\python scripts/check_facts.py data/fl_recommendations.json ../docs/fact-check-report.md

For each plant it checks that every source link opens, that each quoted line (the moisture and care
"basis") appears word for word on its source page, that the animals and numbers in each fact appear
on that fact's source page, and that the USF Atlas lists the plant as native and present in
Palm Beach County. It never edits the data.
"""
import html
import json
import re
import sys
import time
from datetime import date

import requests

PALM_BEACH_FIPS = "12099"
ATLAS_COUNTIES = "https://florida.plantatlas.usf.edu/api/services/app/PlantSpecies/GetDistributionFIPSForSpecies"
HEADERS = {"User-Agent": "EcoLoco fact checker (+https://github.com/Aydin-codes/EcoLoco-FL)"}
_LABEL_BREAK = re.compile(r"(?<=[.!?])\s+(?=[A-Z][A-Za-z ]{2,40}:)")
_QUOTES = str.maketrans({"‘": "'", "’": "'", "“": '"', "”": '"', "–": "-", "—": "-", " ": " "})


def page_text(raw_html):
    text = re.sub(r"<(script|style)\b.*?</\1>", " ", raw_html, flags=re.S | re.I)
    return normalize(html.unescape(re.sub(r"<[^>]+>", " ", text)))


def normalize(text):
    return re.sub(r"\s+", " ", text.translate(_QUOTES)).strip().casefold()


def quote_pieces(basis):
    return [piece.strip() for piece in _LABEL_BREAK.split(basis) if piece.strip()]


def missing_quotes(basis, text):
    return [piece for piece in quote_pieces(basis) if normalize(piece) not in text]


def _stem(word):
    word = word.casefold()
    if word.endswith("ies") and len(word) > 4:
        return word[:-3] + "y"
    if word.endswith(("ches", "shes", "sses", "xes")):
        return word[:-2]
    if word.endswith("s") and not word.endswith("ss") and len(word) > 3:
        return word[:-1]
    return word


def missing_animals(animals, text):
    words = {_stem(w) for w in re.findall(r"[a-z']+", text)}
    return [a for a in animals if not all(_stem(w) in words for w in re.findall(r"[A-Za-z']+", a) if len(w) > 3)]


def missing_numbers(fact, text):
    return [n for n in re.findall(r"\d+(?:\.\d+)?", fact) if not re.search(r"(?<![\d.])%s(?![\d])" % re.escape(n), text)]


def atlas_id(url):
    match = re.search(r"/plant/species/(\d+)", url or "")
    return match.group(1) if match else None


def atlas_status(text):
    match = re.search(r"\bstatus (native|not native|exotic|introduced)\b", text)
    return match.group(1) if match else None


def facts_of(plant):
    """(label, fact text, animals, source) for every sourced fact on a plant."""
    helps = plant.get("helps") or {}
    out = [("helps", helps.get("text", ""), helps.get("animals", []), helps.get("source"))]
    buying = plant.get("buying") or {}
    if buying.get("avoid"):
        out.append(("buying", buying["avoid"], [], buying.get("source")))
    out += [("watch out", w["text"], [], w.get("source")) for w in plant.get("watch_out", [])]
    return [f for f in out if f[3] and f[3].get("url")]


class Fetcher:
    def __init__(self, get=requests.get, pause=1.0):
        self.get, self.pause, self.pages, self.counties = get, pause, {}, {}

    def page(self, url):
        if url not in self.pages:
            try:
                response = self.get(url, headers=HEADERS, timeout=30)
                self.pages[url] = (response.status_code, page_text(response.text) if response.ok else "")
            except requests.RequestException as err:
                self.pages[url] = (type(err).__name__, "")
            time.sleep(self.pause)
        return self.pages[url]

    def county_codes(self, species_id):
        if species_id not in self.counties:
            try:
                response = self.get(ATLAS_COUNTIES, params={"id": species_id}, headers=HEADERS, timeout=30)
                self.counties[species_id] = response.json().get("result") if response.ok else None
            except (requests.RequestException, ValueError):
                self.counties[species_id] = None
            time.sleep(self.pause)
        return self.counties[species_id]


def check_plant(plant, fetch):
    problems, notes = [], []
    urls = {f[3]["url"] for f in facts_of(plant)}
    urls |= {plant[k]["source"]["url"] for k in ("moisture", "care") if (plant.get(k) or {}).get("source")}
    if (plant.get("growing_source") or {}).get("url"):
        urls.add(plant["growing_source"]["url"])
    for url in sorted(urls):
        status, _ = fetch.page(url)
        if status != 200:
            problems.append(f"Link didn't open ({status}): {url}")

    quotes = found = 0
    for key in ("moisture", "care"):
        block = plant.get(key) or {}
        if not block.get("basis") or not (block.get("source") or {}).get("url"):
            continue
        status, text = fetch.page(block["source"]["url"])
        if status != 200:
            continue
        pieces = quote_pieces(block["basis"])
        missing = missing_quotes(block["basis"], text)
        quotes, found = quotes + len(pieces), found + len(pieces) - len(missing)
        problems += [f"{key} quote not on its source page: \"{m}\"" for m in missing]

    for label, fact, animals, source in facts_of(plant):
        status, text = fetch.page(source["url"])
        if status != 200:
            continue
        problems += [f"{label}: \"{a}\" not named on {source['name']}" for a in missing_animals(animals, text)]
        problems += [f"{label}: the number {n} isn't on {source['name']}" for n in missing_numbers(fact, text)]

    species_id = atlas_id(plant.get("atlas_url"))
    native = in_palm_beach = None
    if not species_id:
        problems.append("No USF Atlas link")
    else:
        status, text = fetch.page(plant["atlas_url"])
        native = atlas_status(text) if status == 200 else None
        if native != "native":
            problems.append(f"USF Atlas status is {native or 'not found'}, not Native")
        counties = fetch.county_codes(species_id)
        if counties is None:
            problems.append("Couldn't read the USF Atlas county list")
        else:
            in_palm_beach = PALM_BEACH_FIPS in counties
            notes.append(f"found in {len(counties)} Florida counties")
            if not in_palm_beach:
                problems.append("USF Atlas doesn't list it in Palm Beach County")
    return {"name": plant["common_name"], "scientific_name": plant["scientific_name"],
            "hand_checked": plant.get("verified") is True, "native": native == "native",
            "palm_beach": in_palm_beach, "quotes": quotes, "quotes_found": found,
            "problems": problems, "notes": notes}


def report(results, today):
    hand = [r for r in results if r["hand_checked"]]
    agree = [r for r in hand if r["native"] and r["palm_beach"]]
    quotes = sum(r["quotes"] for r in results)
    found = sum(r["quotes_found"] for r in results)
    clean = [r for r in results if not r["problems"]]
    lines = [
        "# Fact check report",
        "",
        f"Made by `backend/scripts/check_facts.py` on {today}. It reads the live source pages; it never changes the data.",
        "",
        "| Check | Result |",
        "|---|---|",
        f"| Plants checked | {len(results)} |",
        f"| Hand-checked plants the USF Atlas also lists as native in Palm Beach County | {len(agree)} of {len(hand)} |",
        f"| Quoted lines found word for word on their source page | {found} of {quotes} |",
        f"| Plants with nothing to look at | {len(clean)} of {len(results)} |",
        "",
        "What this can and can't prove: quotes are matched word for word, and Atlas status and county come from "
        "the Atlas itself. Facts written in our own words (what a plant helps, what to watch out for) can't be "
        "matched word for word, so the script only checks that the animals and numbers they mention appear on "
        "the source page. A person still reads those.",
        "",
        "## Plants",
        "",
        "| Plant | Atlas: native in Palm Beach | Quotes found | To look at |",
        "|---|---|---|---|",
    ]
    for r in results:
        atlas = "yes" if r["native"] and r["palm_beach"] else "no"
        todo = "<br>".join(p.replace("|", "\\|") for p in r["problems"]) or "nothing"
        lines.append(f"| {r['name']} (*{r['scientific_name']}*) | {atlas} | {r['quotes_found']} of {r['quotes']} | {todo} |")
    return "\n".join(lines) + "\n"


def main(data_path, report_path):
    plants = json.loads(open(data_path, encoding="utf-8").read())["species"]
    fetch = Fetcher()
    results = []
    for plant in plants:
        print(f"Checking {plant['common_name']}...", flush=True)
        results.append(check_plant(plant, fetch))
    with open(report_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(report(results, date.today().isoformat()))
    bad = [r for r in results if r["problems"]]
    print(f"{len(results) - len(bad)} of {len(results)} plants have nothing to look at. Report: {report_path}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2])
