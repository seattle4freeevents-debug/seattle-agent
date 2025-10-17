def synthesize(state):
    events_by_date = state.get("events_by_date", {})
    report = ""

    for date, events in sorted(events_by_date.items()):
        report += f"=== {date} ===\n"
        for e in events:
            report += f"{e['name']} at {e.get('location', 'Unknown')} ({e.get('time', 'Unknown')})\n"
        report += "\n"

    state["report"] = report
    return state
