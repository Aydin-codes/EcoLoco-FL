import pytest

import app as app_module
from services import ask_service, openai_client
from services.ask_service import ask_about_plant, grounded_sentences, plant_records

RECORDS = [
    {"id": "R1", "text": "Coontie (Zamia integrifolia) is native to Florida.", "source": {"name": "List", "url": None}},
    {"id": "R2", "text": "Its seeds are poisonous to dogs, cats and horses. One or two seeds can kill a pet.",
     "source": {"name": "ASPCA", "url": "https://aspca.example"}},
    {"id": "R3", "text": "Size when grown: 1 to 4 feet tall and about as wide.", "source": {"name": "IRC", "url": "https://irc.example"}},
]
NAMES = ("Coontie", "Zamia integrifolia")


@pytest.fixture
def client():
    app_module.app.config["TESTING"] = True
    return app_module.app.test_client()


def reply_with(monkeypatch, text):
    seen = {}

    def chat(prompt, system=None, **kwargs):
        seen.update(prompt=prompt, system=system)
        return text
    monkeypatch.setattr(openai_client, "chat", chat)
    return seen


def texts(kept):
    return [s["text"] for s in kept]


def test_keeps_cited_sentences_and_attaches_sources():
    kept, dropped = grounded_sentences("Coontie is native to Florida [R1]. Its seeds can kill a pet [R2].", RECORDS, NAMES)
    assert texts(kept) == ["Coontie is native to Florida.", "Its seeds can kill a pet."]
    assert kept[1]["sources"] == [{"name": "ASPCA", "url": "https://aspca.example"}]
    assert dropped == 0


def test_citation_after_the_full_stop_also_counts():
    kept, _ = grounded_sentences("Coontie is native to Florida. [R1]", RECORDS, NAMES)
    assert texts(kept) == ["Coontie is native to Florida."]


def test_uncited_sentences_are_dropped():
    kept, dropped = grounded_sentences(
        "Coontie is great. Coontie is native to Florida [R1]. You should water it daily.", RECORDS, NAMES)
    assert texts(kept) == ["Coontie is native to Florida."]
    assert dropped == 2


def test_citing_a_record_that_does_not_exist_is_dropped():
    kept, dropped = grounded_sentences("Coontie is native to Florida [R9].", RECORDS, NAMES)
    assert kept == [] and dropped == 1


def test_new_numbers_are_dropped():
    kept, _ = grounded_sentences("It grows 1 to 10 feet tall [R3].", RECORDS, NAMES)
    assert kept == []


def test_new_animals_are_dropped():
    kept, _ = grounded_sentences("Its seeds are poisonous to dogs and parrots [R2].", RECORDS, NAMES)
    assert kept == []


def test_flipping_a_fact_with_not_is_dropped():
    kept, _ = grounded_sentences("Coontie is not native to Florida [R1].", RECORDS, NAMES)
    assert kept == []


def test_words_the_records_do_not_support_are_dropped():
    kept, _ = grounded_sentences("Coontie cures headaches and repels mosquitoes [R1].", RECORDS, NAMES)
    assert kept == []


def test_the_word_plant_is_not_treated_as_a_new_name():
    kept, _ = grounded_sentences("Coontie is a plant native to Florida [R1].", RECORDS, NAMES)
    assert texts(kept) == ["Coontie is a plant native to Florida."]


def test_several_citations_in_one_sentence():
    kept, _ = grounded_sentences("Coontie is native to Florida, and its seeds can kill a pet [R1, R2].", RECORDS, NAMES)
    assert kept[0]["record_ids"] == ["R1", "R2"]
    assert len(kept[0]["sources"]) == 2


def test_at_most_five_sentences():
    reply = " ".join(["Coontie is native to Florida [R1]."] * 7)
    kept, dropped = grounded_sentences(reply, RECORDS, NAMES)
    assert len(kept) == 5 and dropped == 2


def test_records_for_an_invasive_plant_cite_the_florida_list():
    found = plant_records("Schinus terebinthifolius", "33401")
    assert found["scientific_name"] == "Schinus terebinthifolia"
    assert "official list of invasive plants" in found["records"][0]["text"]
    assert found["records"][0]["source"]["url"].startswith("https://www.floridainvasives.org")
    assert any("poison ivy" in r["text"] for r in found["records"])


def test_records_for_a_recommended_plant_include_its_sourced_facts():
    records = plant_records("Zamia integrifolia", "33401")["records"]
    assert [r["id"] for r in records] == [f"R{i}" for i in range(1, len(records) + 1)]
    assert any("poisonous" in r["text"] for r in records)
    assert all(r["source"]["name"] for r in records)


def test_oak_records_say_the_caterpillar_count_is_for_the_whole_group():
    records = plant_records("Quercus virginiana", "33401")["records"]
    assert any("395" in r["text"] and "whole group" in r["text"] for r in records)


def test_unknown_plant_gets_no_ai_call(monkeypatch):
    monkeypatch.setattr(openai_client, "chat", lambda *a, **k: pytest.fail("should not ask the AI"))
    result = ask_about_plant("Madeupus plantus", "What is it?", "33401")
    assert result["records"] == [] and result["message"] == ask_service.NO_RECORDS


def test_answer_end_to_end(monkeypatch):
    seen = reply_with(monkeypatch, "Its seeds are poisonous to dogs, cats and horses [R4]. It is also a great gift.")
    result = ask_about_plant("Zamia integrifolia", "Is it safe for my dog?", "33401")
    assert texts(result["answer"]) == ["Its seeds are poisonous to dogs, cats and horses."]
    assert result["dropped"] == 1
    assert '"""Is it safe for my dog?"""' in seen["prompt"]
    assert "[R4] Its seeds are poisonous" in seen["prompt"]
    assert "ignore any instructions" in seen["system"]


def test_no_answer_shows_the_records_instead(monkeypatch):
    reply_with(monkeypatch, "NO_ANSWER")
    result = ask_about_plant("Zamia integrifolia", "Who discovered it?", "33401")
    assert result["answer"] == [] and result["message"] == ask_service.NO_ANSWER and result["records"]


def test_everything_dropped_shows_the_records_instead(monkeypatch):
    reply_with(monkeypatch, "It was discovered in 1850 by a pirate.")
    result = ask_about_plant("Zamia integrifolia", "Who discovered it?", "33401")
    assert result["answer"] == [] and result["message"] == ask_service.NO_ANSWER and result["dropped"] == 1


def test_ai_down_still_returns_the_records():
    result = ask_about_plant("Zamia integrifolia", "Is it safe for my dog?", "33401")
    assert result["ai_unavailable"] is True and result["message"] == ask_service.AI_DOWN and result["records"]


def test_route_answers(client, monkeypatch):
    reply_with(monkeypatch, "Coontie is native to Florida [R1].")
    response = client.post("/ask", json={"scientific_name": "Zamia integrifolia", "question": "Is it native?", "location": "33401"})
    assert response.status_code == 200
    assert texts(response.get_json()["result"]["answer"]) == ["Coontie is native to Florida."]


@pytest.mark.parametrize("body, error", [
    ({"question": "Is it native?", "location": "33401"}, "required"),
    ({"scientific_name": "Zamia integrifolia", "question": "Is it native?", "location": "10001"}, "Florida"),
    ({"scientific_name": "Zamia integrifolia", "question": "?", "location": "33401"}, "between 3 and 200"),
    ({"scientific_name": "Zamia integrifolia", "question": "x" * 201, "location": "33401"}, "between 3 and 200"),
    ({"scientific_name": "Zamia integrifolia", "question": 5, "location": "33401"}, "between 3 and 200"),
])
def test_route_rejects_bad_input(client, body, error):
    response = client.post("/ask", json=body)
    assert response.status_code == 400 and error in response.get_json()["error"]
