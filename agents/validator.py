# agents/validator.py
"""
Validator node for LangGraph pipeline tailored to extractor output:
Each candidate is expected to be a dict with keys:
  "name", "date", "time", "location", "url"

Behavior:
- If a event is missing required info (no name OR none of date/time/location),
  call Tavily.extract(url) to attempt to fill those fields.
- Merge any returned fields into candidate only when missing.
- Produce:
    state["events_valid"] -> list of candidates (possibly filled)
    state["needs_fallback"] -> list of indices still missing required info
    state["validator_meta"] -> metadata about calls made
"""

from dotenv import load_dotenv
import os
import logging
from copy import deepcopy

# Load .env from project root (works even when this file is in agents/)
_this_dir = os.path.dirname(__file__)
_project_root_env = os.path.join(_this_dir, "..", ".env")
# try default first, then explicit path fallback
try:
    load_dotenv()
    if not os.getenv("TAVILY_API_KEY"):
        load_dotenv(_project_root_env)
except Exception:
    # safe to continue even if dotenv not present
    pass

# Initialize Tavily client if key present (defensive)
TAVILY_KEY = os.getenv("TAVILY_API_KEY")
client = None
if TAVILY_KEY:
    try:
        from tavily import TavilyClient
        client = TavilyClient(api_key=TAVILY_KEY)
    except Exception as e:
        logging.warning(f"Could not initialize TavilyClient: {e}")
        client = None
else:
    logging.warning("TAVILY_API_KEY not set. Validator will not call Tavily.extract()")

# Helper: decide whether item needs fallback
def _needs_fallback(item):
    if not item or not isinstance(item, dict):
        return True
    name = (item.get("name") or "").strip()
    if not name:
        return True
    # require at least one of date/time/location
    if not any(((item.get("date") or "").strip() if isinstance(item.get("date"), str) else item.get("date"),
                (item.get("time") or "").strip() if isinstance(item.get("time"), str) else item.get("time"),
                (item.get("location") or "").strip() if isinstance(item.get("location"), str) else item.get("location"))):
        return True
    return False

# Helper: merge extracted response into candidate
def _merge_extracted(candidate, extracted):
    """
    Only fill missing fields in candidate using extracted dict.
    Expect extracted may have keys like: title/name, date, time, location, content
    """
    if not extracted:
        return candidate
    merged = deepcopy(candidate)
    # title/name
    if not (merged.get("name") and str(merged.get("name")).strip()):
        for k in ("title", "name"):
            if extracted.get(k):
                merged["name"] = extracted.get(k)
                break
    # date
    if not (merged.get("date") and str(merged.get("date")).strip()):
        for k in ("date", "date_str", "event_date"):
            if extracted.get(k):
                merged["date"] = extracted.get(k)
                break
    # time
    if not (merged.get("time") and str(merged.get("time")).strip()):
        for k in ("time", "time_str", "event_time"):
            if extracted.get(k):
                merged["time"] = extracted.get(k)
                break
    # location
    if not (merged.get("location") and str(merged.get("location")).strip()):
        for k in ("location", "venue", "address"):
            if extracted.get(k):
                merged["location"] = extracted.get(k)
                break
    # preserve url
    if not merged.get("url") and extracted.get("url"):
        merged["url"] = extracted.get("url")

    # optional: fill snippet/content if candidate lacks it
    if not merged.get("snippet") and extracted.get("content"):
        merged["snippet"] = (extracted.get("content")[:400]) if isinstance(extracted.get("content"), str) else None

    return merged

def validate(state, attempt_fallback=True, max_fallback_per_run=10):
    """
    LangGraph node signature: validate(state) -> state

    Params:
      attempt_fallback: whether to call Tavily.extract for missing items
      max_fallback_per_run: safety cap for number of Tavily calls per run
    """
    events = state.get("events") or []   # expects extractor to populate state["events"]
    print()
    print("EVENTS", events)
    validated = []
    needs_fallback = []
    fallback_calls = 0

    for idx, cand in enumerate(events):
        cand = cand or {}
        # quick accept if already valid
        if not _needs_fallback(cand):
            validated.append(cand)
            continue

        # try Tavily.extract only if allowed, client exists, and url present
        extracted = None
        if attempt_fallback and client and cand.get("url") and fallback_calls < max_fallback_per_run:
            try:
                extracted = client.extract(cand["url"])
                fallback_calls += 1
                logging.info(f"Validator: called Tavily.extract on {cand.get('url')}")
            except Exception as e:
                logging.warning(f"Validator: Tavily.extract failed for {cand.get('url')}: {e}")
                extracted = None

        merged = _merge_extracted(cand, extracted)
        # after merging try decision again
        if not _needs_fallback(merged):
            validated.append(merged)
        else:
            # still missing required fields
            validated.append(merged)   # keep candidate (filled as much as possible)
            needs_fallback.append(idx)

    # write back to state
    state["events_valid"] = validated
    state["needs_fallback"] = needs_fallback
    state["validator_meta"] = {
        "total_candidates": len(events),
        "fallback_calls_made": fallback_calls,
        "needs_fallback_count": len(needs_fallback)
    }
    return state
