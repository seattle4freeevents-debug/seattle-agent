from dotenv import load_dotenv 

# Load .env file
load_dotenv("/Users/Dharma/projects/seattle-agent/.env")

from langgraph.graph import StateGraph, END
from agents.retriever import retrieve
from agents.extractor import extract
from agents.normalizer import normalize
from agents.validator import validate
from agents.reasoner import reason
from agents.synthesizer import synthesize

import os



print(os.getenv("TAVILY_API_KEY"))

# Read the keys
OPENAI_KEY = os.getenv("OPENAI_API_KEY")
TAVILY_KEY = os.getenv("TAVILY_API_KEY")


graph = StateGraph(dict)
graph.add_node("retriever", retrieve)
graph.add_node("extractor", extract)
graph.add_node("normalizer", normalize)
graph.add_node("validator", validate)
graph.add_node("reasoner", reason)
graph.add_node("synthesizer", synthesize)

graph.add_edge("retriever", "extractor")
graph.add_edge("extractor", "normalizer")
graph.add_edge("normalizer", "validator")
graph.add_edge("validator","reasoner")
graph.add_edge("reasoner", "synthesizer")
graph.add_edge("synthesizer", END)

graph.set_entry_point("retriever")

app = graph.compile()

state = {"query": "Seattle free events"}
result = app.invoke(state)

print(result["report"])

print(OPENAI_KEY[:4] + "…")  # just to check it loaded
print(TAVILY_KEY[:4] + "…")
