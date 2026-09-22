from io import StringIO

import pandas as pd
import requests
import streamlit as st


st.set_page_config(page_title="Economics Explorer", layout="wide")

st.title("Economics Explorer")
st.write("Compare GDP per person across countries and over time.")

SOURCE_URL = "https://ourworldindata.org/grapher/gdp-per-capita-worldbank"
DATA_URL = SOURCE_URL + ".csv"

st.caption(
    "GDP per person, adjusted for inflation and purchasing power. "
    "Units: international dollars at 2021 prices."
)
st.markdown(f"[Source and methodology: Our World in Data]({SOURCE_URL})")


@st.cache_data(ttl=3600)
def load_data():
    response = requests.get(DATA_URL, timeout=60)
    response.raise_for_status()

    df = pd.read_csv(StringIO(response.text))

    required = {"Entity", "Code", "Year"}
    if not required.issubset(df.columns):
        raise ValueError("The source data format has changed.")

    # Accept either column name used by this data source.
    supported_names = [
        "GDP per capita",
        "GDP per capita, PPP (constant 2021 international $)",
    ]

    gdp_column = next(
        (name for name in supported_names if name in df.columns),
        None,
    )

    if gdp_column is None:
        raise ValueError(
            f"GDP column not found. Available columns: {list(df.columns)}"
        )

    # Select only the columns our app needs.
    df = df[["Entity", "Code", "Year", gdp_column]].copy()

    df = df.rename(columns={
        "Entity": "Country",
        gdp_column: "GDP per person",
    })

    df["Year"] = pd.to_numeric(df["Year"], errors="coerce")
    df["GDP per person"] = pd.to_numeric(
        df["GDP per person"], errors="coerce"
    )

    df = df.dropna(subset=["Country", "Year", "GDP per person"])
    df["Year"] = df["Year"].astype(int)

    # Keep three-letter country/territory codes; exclude regional aggregates.
    df = df[df["Code"].fillna("").str.fullmatch(r"[A-Z]{3}")]

    if df.empty:
        raise ValueError("No usable country data was returned.")

    return df.sort_values(["Country", "Year"])


if st.sidebar.button("Fetch fresh data"):
    load_data.clear()

try:
    with st.spinner("Loading economic data..."):
        data = load_data()
except Exception as error:
    st.error(f"Could not load the data: {error}")
    st.info("Check your internet connection and try fetching again.")
    st.stop()

countries = sorted(data["Country"].unique())
defaults = [
    country
    for country in ["India", "United Kingdom", "United States"]
    if country in countries
]

selected = st.sidebar.multiselect(
    "Countries / territories",
    options=countries,
    default=defaults,
)

minimum_year = int(data["Year"].min())
maximum_year = int(data["Year"].max())

start_year, end_year = st.sidebar.slider(
    "Year range",
    min_value=minimum_year,
    max_value=maximum_year,
    value=(max(minimum_year, 2000), maximum_year),
)

if not selected:
    st.info("Select at least one country in the sidebar.")
    st.stop()

filtered = data[
    data["Country"].isin(selected)
    & data["Year"].between(start_year, end_year)
]

if filtered.empty:
    st.warning("No data is available for this selection.")
    st.stop()

st.subheader("GDP per person over time")

chart_data = filtered.pivot(
    index="Year",
    columns="Country",
    values="GDP per person",
)
st.line_chart(chart_data)

st.subheader(f"Comparison in {end_year}")
comparison = (
    filtered[filtered["Year"] == end_year]
    [["Country", "GDP per person"]]
    .sort_values("GDP per person", ascending=False)
)

if comparison.empty:
    st.info("No observations are available for the selected end year.")
else:
    st.dataframe(comparison, hide_index=True)

missing = sorted(set(selected) - set(comparison["Country"]))
if missing:
    st.caption(f"No observation in {end_year} for: {', '.join(missing)}.")

st.subheader("Explore the underlying data")
st.dataframe(
    filtered[["Country", "Year", "GDP per person"]],
    hide_index=True,
)

st.download_button(
    label="Download selected data as CSV",
    data=filtered.to_csv(index=False).encode("utf-8"),
    file_name="selected_economic_data.csv",
    mime="text/csv",
)

st.caption(
    "Data is cached for one hour. After expiry, the next app interaction "
    "fetches it again. Use 'Fetch fresh data' to refresh immediately."
)