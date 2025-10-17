from tavily import TavilyClient
import re
import json

import os

client = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))


def extract(state):

    urls = state.get("search_results", [])
    print
    events = []

    for url in urls:
        extracted = client.extract(url, extract_depth="advanced")
        print("EXTRACTED INFO, RESULTS", extracted['results'])
        print("PASS")
        # Tavily may return different fields depending on page
        # Use 'title' for event name, 'date', 'time', 'location' if available
        print('TESTING VALUE OF EXTRACTED[0]', extracted['results'][0])
        events.append({
            "url": extracted['results'][0]['url'],
            "date": extracted.get("date", "No date"),
            "time": extracted.get("time", None),
            "content": extracted['results'][0]['raw_content'],
            "location": extracted.get("location", None),
            "url": url
        })

    state["events"] = events
    # print()
    # print("EXTRACTOR", events)
    return state
