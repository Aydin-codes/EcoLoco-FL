import json

from scripts import check_facts as cf
from services.species_service import DATA_DIR

SOURCE = {"name": "IRC", "url": "https://irc.example/coontie"}
ATLAS = "https://florida.plantatlas.usf.edu/plant/species/2105"
IRC_PAGE = ("<html><script>var x=1;</script><p>Soils: Moist, well-drained sandy soils.</p>"
            "<p>Nutritional Requirements: Moderate.</p><p>Drought Tolerance: High; does not require "
            "any supplemental water once established.</p><p>Larval host plant for atala butterflies. "
            "Grows 1 to 4 feet tall.</p></html>")
ATLAS_PAGE = "<div>Status</div> <div>Native</div>"


class FakeResponse:
    def __init__(self, status, body):
        self.status_code, self.ok = status, status == 200
        self.text = body if isinstance(body, str) else json.dumps(body)
        self._body = body

    def json(self):
        return self._body


def fetcher(pages, counties=("12099",)):
    def get(url, params=None, **kwargs):
        if url == cf.ATLAS_COUNTIES:
            return FakeResponse(200, {"result": list(counties)})
        return FakeResponse(200, pages[url]) if url in pages else FakeResponse(404, "")
    return cf.Fetcher(get=get, pause=0)


def plant(**overrides):
    base = {
        "common_name": "Coontie", "scientific_name": "Zamia integrifolia", "verified": True, "atlas_url": ATLAS,
        "helps": {"animals": ["atala butterflies"], "text": "Atala caterpillars eat it.", "source": SOURCE},
        "moisture": {"basis": "Soils: Moist, well-drained sandy soils. Drought Tolerance: High; does not "
                              "require any supplemental water once established.", "source": SOURCE},
    }
    return {**base, **overrides}


def test_page_text_drops_tags_and_scripts():
    assert cf.page_text("<p>A&amp;B</p><script>secret()</script>") == "a&b"


def test_basis_splits_at_each_label():
    assert cf.quote_pieces("Soils: Moist. Drought Tolerance: High; none needed.") == [
        "Soils: Moist.", "Drought Tolerance: High; none needed."]


def test_quotes_must_match_word_for_word():
    text = cf.page_text(IRC_PAGE)
    assert cf.missing_quotes("Soils: Moist, well-drained sandy soils.", text) == []
    assert cf.missing_quotes("Soils: Wet clay.", text) == ["Soils: Wet clay."]


def test_curly_quotes_and_spacing_do_not_matter():
    assert cf.missing_quotes("It’s  fine.", cf.page_text("<p>It's fine.</p>")) == []


def test_animals_match_singular_or_plural():
    text = cf.page_text("<p>Larval host for the atala butterfly and bees.</p>")
    assert cf.missing_animals(["atala butterflies", "bee"], text) == []
    assert cf.missing_animals(["woodpeckers"], text) == ["woodpeckers"]


def test_numbers_must_appear_on_the_page():
    text = cf.page_text("<p>Grows 1 to 40 feet.</p>")
    assert cf.missing_numbers("Grows 1 to 4 feet.", text) == ["4"]
    assert cf.missing_numbers("Grows 1 to 40 feet.", text) == []


def test_atlas_status_and_id():
    assert cf.atlas_status(cf.page_text(ATLAS_PAGE)) == "native"
    assert cf.atlas_status(cf.page_text("<b>Status</b> Not Native")) == "not native"
    assert cf.atlas_id(ATLAS) == "2105"
    assert cf.atlas_id(None) is None


def test_clean_plant_has_nothing_to_look_at():
    result = cf.check_plant(plant(), fetcher({SOURCE["url"]: IRC_PAGE, ATLAS: ATLAS_PAGE}))
    assert result["problems"] == []
    assert (result["quotes"], result["quotes_found"]) == (2, 2)
    assert result["native"] and result["palm_beach"]


def test_flags_missing_quote_animal_county_and_broken_link():
    p = plant(helps={"animals": ["woodpeckers"], "text": "Woodpeckers nest in it.", "source": SOURCE},
              buying={"avoid": "Skip it.", "source": {"name": "Gone", "url": "https://gone.example"}})
    p["moisture"] = {"basis": "Soils: Wet clay.", "source": SOURCE}
    result = cf.check_plant(p, fetcher({SOURCE["url"]: IRC_PAGE, ATLAS: ATLAS_PAGE}, counties=["12086"]))
    problems = "\n".join(result["problems"])
    assert "Link didn't open (404): https://gone.example" in problems
    assert 'moisture quote not on its source page: "Soils: Wet clay."' in problems
    assert '"woodpeckers" not named' in problems
    assert "doesn't list it in Palm Beach County" in problems
    assert result["palm_beach"] is False


def test_each_page_is_fetched_once():
    calls = []
    inner = fetcher({SOURCE["url"]: IRC_PAGE, ATLAS: ATLAS_PAGE}).get
    fetch = cf.Fetcher(get=lambda url, **kw: calls.append(url) or inner(url, **kw), pause=0)
    cf.check_plant(plant(), fetch)
    cf.check_plant(plant(), fetch)
    assert calls.count(SOURCE["url"]) == 1


def test_report_counts_agreement_with_hand_checks():
    good = {"name": "A", "scientific_name": "A a", "hand_checked": True, "native": True, "palm_beach": True,
            "quotes": 3, "quotes_found": 3, "problems": [], "notes": []}
    bad = {**good, "name": "B", "palm_beach": False, "quotes_found": 2, "problems": ["x | y"]}
    text = cf.report([good, bad], "2026-11-25")
    assert "| 1 of 2 |" in text
    assert "| Quoted lines found word for word on their source page | 5 of 6 |" in text
    assert "x \\| y" in text


def test_every_recommended_plant_has_what_the_checker_needs():
    plants = json.loads((DATA_DIR / "fl_recommendations.json").read_text(encoding="utf-8"))["species"]
    for p in plants:
        assert cf.atlas_id(p.get("atlas_url")), p["common_name"]
        assert cf.facts_of(p), p["common_name"]
