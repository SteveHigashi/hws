"""Crawler classes and the five stance options (wording approved 2026-09-20).

A stance is what the owner asked for; it changes what the reading recommends, never
what is measured. Each stance refuses a set of crawler classes. `ai_stance` (found /
search_only / block_all) is the older three-way value that Live keys and old reports
still carry; `LEGACY_TO_STANCE` says what each of those meant in the copy of the time.
"""
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Stephen Higashi / JotNotes
# MIT, not AGPL — see backend/higashi_reading/LICENSE. Shared with Higashi Live.
from __future__ import annotations

CLASSES = ("search", "answer_fetcher", "training", "seo_tools", "other")

CLASS_LABELS = {
    "search": "search crawlers",
    "answer_fetcher": "answer fetchers (a person asked an AI about a page)",
    "training": "training crawlers",
    "seo_tools": "SEO tools",
    "other": "other named crawlers",
}

# Lower-case name (or prefix) -> class. Names not listed are "other".
_KNOWN: dict[str, str] = {
    # search: the same crawlers feed Google's and Bing's AI answers
    "googlebot": "search", "bingbot": "search", "duckduckbot": "search", "applebot": "search",
    "yandexbot": "search", "baiduspider": "search", "slurp": "search",
    # answer fetchers: fetch one page because a person asked
    "chatgpt-user": "answer_fetcher", "oai-searchbot": "answer_fetcher", "perplexitybot": "answer_fetcher",
    "perplexity-user": "answer_fetcher", "claude-user": "answer_fetcher", "claude-searchbot": "answer_fetcher",
    "duckassistbot": "answer_fetcher",
    # training
    "gptbot": "training", "claudebot": "training", "anthropic-ai": "training", "bytespider": "training",
    "ccbot": "training", "google-extended": "training", "applebot-extended": "training", "amazonbot": "training",
    "cohere-ai": "training", "diffbot": "training", "meta-externalagent": "training", "facebookbot": "training",
    "omgili": "training", "omgilibot": "training", "timpibot": "training", "youbot": "training",
    "petalbot": "training", "imagesiftbot": "training", "ai2bot": "training", "webzio": "training",
    # SEO tools
    "ahrefsbot": "seo_tools", "semrushbot": "seo_tools", "mj12bot": "seo_tools", "dotbot": "seo_tools",
    "dataforseobot": "seo_tools", "blexbot": "seo_tools", "screaming frog": "seo_tools", "sitebulb": "seo_tools",
    "seokicks": "seo_tools", "serpstatbot": "seo_tools",
}


def crawler_class(name: str) -> str:
    key = (name or "").casefold().strip()
    if key in _KNOWN:
        return _KNOWN[key]
    for prefix, cls in _KNOWN.items():
        if key.startswith(prefix):
            return cls
    return "other"


STANCES: dict[str, dict] = {
    "allow_all": {
        "label": "Allow all known crawlers",
        "does": "Keeps search crawlers, answer fetchers, training crawlers and SEO tools available under your current site rules.",
        "does_not": "It does not refuse any crawler class.",
        "cost": "Training and SEO crawlers can keep requesting pages.",
        "legacy": "found",
        "refuses": frozenset(),
    },
    "refuse_training": {
        "label": "Refuse training crawlers",
        "does": "Recommends refusing training crawlers such as GPTBot, ClaudeBot, Bytespider and CCBot while leaving search, answer fetchers and SEO tools available.",
        "does_not": "It does not remove the site from Google or Bing search, their AI answers, or person-triggered fetches such as ChatGPT-User and PerplexityBot.",
        "cost": "Training crawlers cannot fetch pages where you enforce the refusal.",
        "legacy": "found",
        "refuses": frozenset({"training"}),
    },
    "refuse_training_seo": {
        "label": "Refuse training crawlers and SEO tools",
        "does": "Recommends refusing training crawlers and SEO tools while leaving Googlebot, Bingbot, ChatGPT-User and PerplexityBot available.",
        "does_not": "It does not remove the site from Google or Bing search, their AI answers, or answers that need those person-triggered fetchers.",
        "cost": "SEO services that need to crawl the site may lose access where you enforce the refusal.",
        "legacy": "found",
        "refuses": frozenset({"training", "seo_tools"}),
    },
    "keep_search_only": {
        "label": "Keep search only",
        "does": "Keeps Googlebot and Bingbot available, so the site can remain in Google and Bing search and in the AI answers that use those same crawlers.",
        "does_not": "It does not keep person-triggered fetchers such as ChatGPT-User and PerplexityBot, or training crawlers and SEO tools.",
        "cost": "Where you enforce the refusal, the site can disappear from answers that need those fetchers, and the visitors those answers could have sent will not arrive.",
        "legacy": "search_only",
        "refuses": frozenset({"answer_fetcher", "training", "seo_tools"}),
    },
    "refuse_all": {
        "label": "Refuse all crawler classes",
        "does": "Recommends refusing search crawlers, answer fetchers, training crawlers and SEO tools.",
        "does_not": "It does not preserve Google or Bing search or their AI answers, because Googlebot and Bingbot are the same crawlers used for both.",
        "cost": "Where you enforce the refusal, search visibility, answer visibility and the visitors those sources could have sent are given up.",
        "legacy": "block_all",
        "refuses": frozenset({"search", "answer_fetcher", "training", "seo_tools"}),
    },
}

STANCE_IDS = tuple(STANCES)

# What the three old values meant in the copy that offered them: "Fine, I want to be found"
# allowed everything; "Fine for search engines, not for AI training" refused training;
# "Block AI training bots (Google/Bing answers still see you)" kept search and refused the rest.
# The reverse of STANCES[*]["legacy"]. `test_every_legacy_value_round_trips_through_its_stance`
# holds the two in agreement: they were written by hand at opposite ends of this file and
# drifted, so `block_all` (refuse everything) resolved to `keep_search_only`.
LEGACY_TO_STANCE = {"found": "allow_all", "search_only": "keep_search_only", "block_all": "refuse_all"}


def stance_of(report) -> str:
    """The five-way stance for a report: its own `stance`, else the meaning of its `ai_stance`."""
    stance = getattr(report, "stance", None)
    if stance in STANCES:
        return stance
    return LEGACY_TO_STANCE.get(getattr(report, "ai_stance", ""), "allow_all")


def refused_classes(report) -> frozenset[str]:
    return STANCES[stance_of(report)]["refuses"]


def legacy_value(stance: str) -> str:
    """The three-way value an older Live schema or key expects for a five-way stance."""
    return STANCES.get(stance, STANCES["allow_all"])["legacy"]


# The internal values are plumbing. A customer must never read one in a reading, so
# the model is handed labels instead and `prompt.py` refuses prose containing these.
# "found" is deliberately absent: it is a legacy value and also an ordinary English
# word ("Higashi found 900 visits"), so matching it would reject correct prose.
RAW_STANCE_TOKENS = (
    "allow_all", "refuse_training_seo", "refuse_training", "keep_search_only",
    "refuse_all", "search_only", "block_all",
)


def stance_context(report) -> dict:
    """What the model is told about the owner's choice — labels and classes, no enums."""
    stance = STANCES[stance_of(report)]
    refuses = [CLASS_LABELS[c] for c in CLASSES if c in stance["refuses"]]
    allows = [CLASS_LABELS[c] for c in CLASSES if c not in stance["refuses"]]
    return {
        "chose": stance["label"],
        "means": stance["does"],
        "does_not_mean": stance["does_not"],
        "what_it_costs": stance["cost"],
        "refuses": refuses or ["nothing — every class is allowed"],
        "allows": allows or ["nothing — every class is refused"],
    }
