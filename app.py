# app.py
import os
from dotenv import load_dotenv
load_dotenv()

import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
from io import StringIO

# LangGraph imports (your nodes)
from langgraph.graph import StateGraph, END

# Import your agent node functions (adjust names if different)
from agents.retriever import retrieve
from agents.extractor import extract
from agents.normalizer import normalize
from agents.validator import validate
from agents.reasoner import reason
from agents.synthesizer import synthesize

# -------------------------
# Helper: build & run graph
# -------------------------
@st.cache_data(ttl=300)
def run_pipeline(query: str, use_validator: bool = True):
    """
    Build the LangGraph using your nodes and run the pipeline once.
    Cache results for 5 minutes to avoid repeated API calls when demoing.
    Returns a pandas.DataFrame (events) and the full state dict.
    """
    graph = StateGraph(dict)
    graph.add_node("retriever", retrieve)
    graph.add_node("extractor", extract)
    graph.add_node("normalizer", normalize)
    if use_validator:
        graph.add_node("validator", validate)
    graph.add_node("reasoner", reason)
    graph.add_node("synthesizer", synthesize)

    # edges
    graph.add_edge("retriever", "extractor")
    graph.add_edge("extractor", "normalizer")
    if use_validator:
        print("in the validator")
        graph.add_edge("normalizer", "validator")
        graph.add_edge("validator", "reasoner")
    else:
        print()
        graph.add_edge("normalizer", "reasoner")
    graph.add_edge("reasoner", "synthesizer")
    graph.add_edge("synthesizer", END)

    graph.set_entry_point("retriever")
    app = graph.compile()

    state = {"query": query}
    try:
        result = app.invoke(state)
    except Exception as e:
        return pd.DataFrame(), {"error": str(e)}

    # prefer events_df from synthesizer, else events_valid / events
    df = None
    if result.get("events_df") is not None:
        df = result["events_df"]
        if not isinstance(df, pd.DataFrame):
            df = pd.DataFrame(df)
    elif result.get("events_valid") is not None:
        df = pd.DataFrame(result["events_valid"])
    elif result.get("events") is not None:
        df = pd.DataFrame(result["events"])
    else:
        # fallback: empty
        df = pd.DataFrame()

    # Normalize columns
    if "content" not in df.columns and "title" in df.columns:
        df["content"] = df["content"]
    if "date" in df.columns:
        df["date_parsed"] = pd.to_datetime(df["date"], errors="coerce").dt.date
    else:
        df["date_parsed"] = pd.NaT
    if "time" in df.columns:
        df["time_parsed"] = pd.to_datetime(df["time"].fillna(""), errors="coerce").dt.time
    else:
        df["time_parsed"] = pd.NaT
    if "category" not in df.columns:
        # if reasoner produced separate structure, you may need to generate 'category' column earlier
        df["category"] = df.get("category", "Event")

    # lat/lon numeric
    if "lat" in df.columns and "lon" in df.columns:
        df["lat"] = pd.to_numeric(df["lat"], errors="coerce")
        df["lon"] = pd.to_numeric(df["lon"], errors="coerce")

    return df, result

# -------------------------
# Streamlit UI layout
# -------------------------
st.set_page_config(page_title="Seattle Events Explorer", layout="wide")
st.title("Seattle Events Explorer")

with st.sidebar:
    st.header("Search Controls")
    query = st.text_input("Query", value="Seattle free events")
    use_validator = st.checkbox("Use Validator (Tavily fallback)", value=True)
    run_button = st.button("Find Events")
    st.markdown("---")
    st.markdown("**Display options**")
    cat_filter = st.multiselect("Category", options=["Event","Art","Music","Festival"], default=["Event","Art","Music","Festival"])
    date_min = st.date_input("From date", value=None)
    date_max = st.date_input("To date", value=None)
    st.markdown("---")
    st.write("Tip: The pipeline is cached for 5 minutes to avoid repeated API calls.")

# empty state
df = pd.DataFrame()
state = {}

if run_button:
    with st.spinner("Running pipeline — fetching & extracting (this may call Tavily)..."):
        df, state = run_pipeline(query, use_validator=use_validator)

# if run_button not pressed but cache exists, you could optionally run automatically
if df is None:
    print("cache exists")
    df = pd.DataFrame()
    print("Data Frame", pd.DataFrame)

# -------------------------
# Filtering & derived cols
# -------------------------
if not df.empty:
    display_df = df.copy()

    # Filter category
    if "category" in display_df.columns:
        display_df = display_df[display_df["category"].isin(cat_filter)]

    # Filter by date range
    if date_min:
        display_df = display_df[display_df["date_parsed"] >= date_min]
    if date_max:
        display_df = display_df[display_df["date_parsed"] <= date_max]

    # Show table
    st.subheader(f"Events — {len(display_df)} found")
    st.dataframe(display_df[["date_parsed","content","category","url"]].rename(columns={
        "date_parsed":"Date","content":"Content","category":"Category","url":"URL"
    }), use_container_width=True)

    # Download CSV
    csv_buf = StringIO()
    display_df.to_csv(csv_buf, index=False)
    csv_bytes = csv_buf.getvalue().encode()
    st.download_button("Download CSV", data=csv_bytes, file_name="seattle_events.csv", mime="text/csv")

    # Timeline visualization (simple grouped by date)
    if "date_parsed" in display_df.columns and display_df["date_parsed"].notna().any():
        timeline_df = display_df.dropna(subset=["date_parsed"]).copy()
        # create display start (date + optional time)
        timeline_df["start_dt"] = pd.to_datetime(timeline_df["date_parsed"].astype(str) + " " + timeline_df.get("time", "").fillna(""), errors="coerce")
        # fallback: use date only as start
        timeline_df["start_dt"] = timeline_df["start_dt"].fillna(pd.to_datetime(timeline_df["date_parsed"]))
        # For simple bar-length, set end = start + 1 hour if no end
        timeline_df["end_dt"] = timeline_df["start_dt"] + pd.Timedelta(hours=1)
        fig = px.timeline(timeline_df, x_start="start_dt", x_end="end_dt", y="category",
                          hover_data=["content","location","url"], color="category")
        fig.update_yaxes(autorange="reversed")  # so earliest is top
        st.subheader("Timeline")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No parsable dates found for timeline. Try a broader query or check event pages.")

    # Map view if lat/lon present
    if "lat" in display_df.columns and display_df["lat"].notna().any():
        st.subheader("Map")
        st.map(display_df[["lat","lon"]].dropna())
else:
    st.info("No data — run the pipeline or adjust the query.")

# -------------------------
# Debug / raw output
# -------------------------
with st.expander("Raw pipeline state (debug)"):
    print(state)
    st.write(state)
