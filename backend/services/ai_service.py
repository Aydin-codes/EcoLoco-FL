import re
from concurrent.futures import ThreadPoolExecutor

from services import openai_client
from services.fl_plants_service import STATUS_LABELS, plant_option
from services.identification_service import identify_species
from services.name_guard import mentions_new_names

UNIDENTIFIED_MESSAGE = "Couldn't identify this. Try a close-up of one leaf, or a flower"


def _options(ranked, location):
    with ThreadPoolExecutor(max_workers=5) as pool:
        return list(pool.map(
            lambda c: plant_option(c["scientific_name"], c["common_name"], c["confidence"], location), ranked))


def identify_plant(images, location):
    species = identify_species(images, location)
    base = {"state": species["state"], "suggested": species["suggested"], "id_source": species["source"],
            "ai_unavailable": species.get("ai_unavailable", False),
            "suggested_confidence": species.get("suggested_confidence"), "agreed_status": None}
    if species["state"] == "unidentified":
        return {
            **base, "options": [], "message": UNIDENTIFIED_MESSAGE,
            "plant_name": "", "scientific_name": "", "confidence": 0.0, "status": "unknown",
            "status_label": STATUS_LABELS["unknown"], "source": "unknown", "source_label": None, "why": None,
        }
    options = _options(species["ranked"], location)
    statuses = {option["status"] for option in options}
    if species["state"] == "confirm" and len(statuses) == 1 and "unknown" not in statuses:
        base["agreed_status"] = statuses.pop()
    return {**options[0], **base, "options": options, "message": None}


def choose_plant(scientific_name, common_name, location):
    option = plant_option(scientific_name, common_name, None, location)
    return {
        **option, "state": "identified", "options": [option], "suggested": 0, "suggested_confidence": None,
        "agreed_status": None, "id_source": "by_name", "ai_unavailable": False, "message": None,
    }


INVASIVE_WHY = "It is on Florida's official list of invasive plants."
FISC_SOURCE = {"name": "Florida Invasive Species Council 2026 Plant List",
               "url": "https://www.floridainvasives.org/wp-content/uploads/2026/07/FISC-2026-Plant-List-Cat-I-II_April2026.pdf"}

RECIPIENTS = {
    "principal": {
        "audience": "a student eco-club writing to their school principal", "we": True,
        "greeting": "Dear [PRINCIPAL_NAME],",
        "checked": "The [SCHOOL_NAME] eco-club checked the plants on our campus",
        "ask": "We'd like to ask for a few changes that would help local wildlife.",
        "closing": "We'd be glad to share our full list of plants and talk about next steps. Thank you for considering this.",
        "signoff": "Sincerely,\n\n[STUDENT_NAME]\n[SCHOOL_NAME] Eco-Club",
    },
    "hoa": {
        "audience": "a resident writing to their homeowners association board",
        "greeting": "Dear [HOA_NAME] Board,",
        "checked": "I checked the plants in our neighborhood's shared areas",
        "ask": "I'd like to ask the board to consider a few changes that would help local wildlife.",
        "closing": "I'd be glad to share my full list of plants or bring this to the next board meeting. Thank you for considering this.",
        "signoff": "Sincerely,\n\n[YOUR_NAME]\n[YOUR_ADDRESS]",
    },
    "city": {
        "audience": "a resident writing to their city or county parks department",
        "greeting": "Dear [PARKS_DEPARTMENT],",
        "checked": "I checked the plants at [PARK_NAME]",
        "ask": "I'd like to ask the parks department to consider a few changes that would help local wildlife.",
        "closing": "I'd be glad to share my full list of plants or help with a volunteer planting day. Thank you for considering this.",
        "signoff": "Sincerely,\n\n[YOUR_NAME]\n[YOUR_EMAIL]",
    },
    "landlord": {
        "audience": "a tenant writing to their landlord or property manager",
        "greeting": "Dear [LANDLORD_NAME],",
        "checked": "I checked the plants around [PROPERTY_ADDRESS]",
        "ask": "I'd like to ask for your OK on a few changes that would help local wildlife.",
        "closing": "I'd be glad to share my full list of plants and talk about who would do the work. Thank you for considering this.",
        "signoff": "Sincerely,\n\n[YOUR_NAME]\n[YOUR_UNIT]",
    },
    "neighbor": {
        "audience": "a neighbor writing a friendly note to the people next door",
        "greeting": "Hi [NEIGHBOR_NAME],",
        "checked": "I checked the plants around our homes",
        "ask": "I wanted to share a few changes that would help local wildlife, in case you're interested.",
        "closing": "I'd be happy to share my full list of plants, or even help with the work. Thanks for reading!",
        "signoff": "Best,\n\n[YOUR_NAME]\n[YOUR_ADDRESS]",
    },
    "other": {
        "audience": "someone writing to the person who looks after a piece of land",
        "greeting": "Dear [NAME],",
        "checked": "I checked the plants at [PLACE_NAME]",
        "ask": "I'd like to ask you to consider a few changes that would help local wildlife.",
        "closing": "I'd be glad to share my full list of plants and talk about next steps. Thank you for considering this.",
        "signoff": "Sincerely,\n\n[YOUR_NAME]",
    },
}

LETTER_SYSTEM = (
    "You help people write a short, polite letter. Write at about a 7th-grade reading level, in short, "
    "friendly sentences. Use everyday words, not science words. Do not add any plant, animal, place, number "
    "or fact that is not in the paragraph you are given. Keep every number exactly as it is, and keep every "
    "word in square brackets like [SCHOOL_NAME] exactly as it is. "
    "Swap these words: say \"trimming\" instead of \"pruning\"; \"caterpillars eat its leaves\" instead of "
    "\"host plant\"; \"one of the most important plants for wildlife here\" instead of \"keystone\"; "
    "\"butterflies and moths\" instead of \"Lepidoptera\"; \"a different version sold in stores\" instead of "
    "\"cultivar\"; \"after its first year\" instead of \"established\"; \"officially listed as invasive in Florida\" "
    "instead of \"FISC Category I\"."
)
REPHRASE_PROMPT = "Rewrite this opening paragraph for {audience} so it reads naturally. The letter already has a greeting, so do not add one. Return only the paragraph."


def _percent_sentence(summary, we=True):
    now, with_plan = summary.get("percent_native"), summary.get("percent_native_with_plan")
    if now is None or with_plan is None:
        return f"{'We' if we else 'I'} couldn't identify enough plants to give a percentage yet."
    kinds = summary.get("percent_native_kinds")
    sentence = f"Of the plants {'we' if we else 'I'} checked, {now}% are native to Florida."
    if with_plan != now:
        sentence += f" With these changes, it would be {with_plan}%."
    if kinds is not None and kinds != now:
        sentence += f" Counting each kind of plant once, {kinds}% are native now."
    return sentence


def _opening(plan, zip_code, recipient):
    r = RECIPIENTS[recipient]
    return (f"{r['checked']} (ZIP {zip_code}) against Florida's official plant lists. "
            f"{_percent_sentence(plan['summary'], r.get('we', False))} {r['ask']}")


def _sections(plan, we=True):
    sources, parts = {}, []
    our = "we'd" if we else "I'd"

    def cite(source):
        if source and source.get("url"):
            sources.setdefault(source["url"], source["name"])

    if plan["remove"]:
        lines = [f"What {our} like to remove:"]
        for card in plan["remove"]:
            cite(FISC_SOURCE)
            safety = card["removal_safety"]
            cite(safety.get("source"))
            lines.append(f"- {card['plant_name']}: {card['why'] or INVASIVE_WHY} Safety: {safety['text']}")
        parts.append("\n".join(lines))
    if plan["add"]:
        lines = [f"What {our} like to plant:"]
        for card in plan["add"]:
            cite(card["helps"]["source"])
            buying = card["buying"]
            avoid = f" {buying['avoid']}" if buying.get("avoid") else ""
            if avoid:
                cite(buying.get("source"))
            lines.append(f"- {card['common_name']}: {card['helps']['text']} Buying it: ask for {buying['ask_for']}.{avoid}")
        parts.append("\n".join(lines))
    if sources:
        parts.append("Sources:\n" + "\n".join(f"- {name}: {url}" for url, name in sources.items()))
    return parts


def _letter(opening, plan, recipient):
    r = RECIPIENTS[recipient]
    return "\n\n".join([r["greeting"], opening, *_sections(plan, r.get("we", False)), r["closing"], r["signoff"]])


def letter_facts(plan, zip_code, recipient="principal"):
    return _letter(_opening(plan, zip_code, recipient), plan, recipient)


def _same_numbers(a, b):
    return sorted(re.findall(r"\d+", a)) == sorted(re.findall(r"\d+", b))


def _same_blanks(a, b):
    return sorted(re.findall(r"\[[A-Z_]+\]", a)) == sorted(re.findall(r"\[[A-Z_]+\]", b))


def generate_letter(plan, zip_code, recipient="principal"):
    opening = _opening(plan, zip_code, recipient)
    prompt = REPHRASE_PROMPT.format(audience=RECIPIENTS[recipient]["audience"])
    try:
        reply = openai_client.chat(f"{prompt}\n\n{opening}", system=LETTER_SYSTEM)
    except openai_client.AIUnavailable:
        return _letter(opening, plan, recipient), True
    reply = str(reply).strip()
    if reply and not mentions_new_names(reply, opening) and _same_numbers(reply, opening) and _same_blanks(reply, opening):
        opening = reply
    return _letter(opening, plan, recipient), False
