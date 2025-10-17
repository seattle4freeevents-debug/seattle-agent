def reason(state):
    events = state.get("events_clean", [])
    categorized = {
        "Event": [],
        "Art": [],
        "Music": [],
        "Festival": [],
        "Other": []
    }

    # Keywords to detect categories
    keywords = {
        "Art": ["art", "gallery", "exhibit", "museum", "painting", "sculpture"],
        "Music": ["music", "concert", "band", "live show", "performance"],
        "Festival": ["festival", "fair", "celebration", "parade"]
    }

    for e in events:
        name = e.get("name", "").lower()
        category_assigned = False

        for cat, words in keywords.items():
            if any(word in name for word in words):
                categorized[cat].append(e)
                category_assigned = True
                break
        
        if not category_assigned:
            categorized["Event"].append(e)  # default to "Event"

    state["events_by_category"] = categorized
    return state
