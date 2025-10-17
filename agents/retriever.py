from tavily import TavilyClient
import os


client = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))

def retrieve(state):
    # Example: we search specific Seattle sites
    query = state.get("query", "Seattle AI news")

    results = client.search(query=query, sites=["https://www.greaterseattleonthecheap.com/this-week/", 
                                                "https://www.seattlecenter.com/events/event-calendar",
                                                "https://www.events12.com/seattle/",
                                                "https://www.eventbrite.com/d/wa--seattle/free--events/",
                                                "https://everout.com/seattle/events/?category=community",
                                                "https://do206.com/free-events-seattle"])
    

    # Save URLs
    print("RESULTS", results)
    state["search_results"] = [r["url"] for r in results.get("results", []) if "url" in r]
    print("IN RETRIEVER PRINTING STATE RESULTS", state["search_results"])
    state["full content"] = results
    return state
