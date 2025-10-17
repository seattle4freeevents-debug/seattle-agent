from datetime import datetime

def normalize(state):
    events = state.get("events", [])
    seen = set()
    clean = []

    for e in events:
        # Deduplicate by event name + date
        key = (e.get("name"), e.get("date"))
        if key not in seen:
            seen.add(key)
            
            # Normalize date
            try:
                e["date"] = datetime.strptime(e["date"], "%Y-%m-%d").date()
            except:
                pass  # leave as is if parsing fails

            clean.append(e)

    # Sort events by date
    clean.sort(key=lambda x: x.get("date") or datetime.max.date())
    state["events_clean"] = clean
    return state
