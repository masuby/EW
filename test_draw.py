"""Minimal test: draw shapes on folium map with fill colors."""
import streamlit as st
import folium
from folium.plugins import Draw
from streamlit_folium import st_folium

st.title("Draw Test v2")

color = "#FFA500"  # orange - very visible

m = folium.Map(location=[-6.5, 34.5], zoom_start=6)

shape_opts = {
    "stroke": True,
    "color": "#FF0000",
    "weight": 3,
    "opacity": 1.0,
    "fill": True,
    "fillColor": color,
    "fillOpacity": 0.6,
}
Draw(
    draw_options={
        "polyline": False,
        "polygon": {"allowIntersection": False, "shapeOptions": shape_opts},
        "rectangle": {"shapeOptions": shape_opts},
        "circle": {"shapeOptions": shape_opts},
        "circlemarker": False,
        "marker": False,
    },
    edit_options={"edit": True, "remove": True},
    export=True,
).add_to(m)

st.write("**Test 1**: returned_objects=None (return everything)")
result1 = st_folium(m, height=400, key="test1", returned_objects=None)
st.write("Result keys:", list(result1.keys()) if result1 else "None")
st.write("all_drawings:", result1.get("all_drawings") if result1 else "N/A")
st.write("last_active_drawing:", result1.get("last_active_drawing") if result1 else "N/A")

st.divider()

st.write("**Test 2**: returned_objects=['all_drawings']")
m2 = folium.Map(location=[-6.5, 34.5], zoom_start=6)
Draw(
    draw_options={
        "polyline": False,
        "polygon": {"allowIntersection": False, "shapeOptions": shape_opts},
        "rectangle": {"shapeOptions": shape_opts},
        "circle": {"shapeOptions": shape_opts},
        "circlemarker": False,
        "marker": False,
    },
    edit_options={"edit": True, "remove": True},
    export=True,
).add_to(m2)
result2 = st_folium(m2, height=400, key="test2", returned_objects=["all_drawings"])
st.write("all_drawings:", result2.get("all_drawings") if result2 else "N/A")

st.divider()
st.write("**Test 3**: feature_group approach")
m3 = folium.Map(location=[-6.5, 34.5], zoom_start=6)
fg = folium.FeatureGroup(name="drawings")
fg.add_to(m3)
Draw(
    draw_options={
        "polyline": False,
        "polygon": {"allowIntersection": False, "shapeOptions": shape_opts},
        "rectangle": {"shapeOptions": shape_opts},
        "circle": {"shapeOptions": shape_opts},
        "circlemarker": False,
        "marker": False,
    },
    edit_options={"edit": True, "remove": True, "featureGroup": "drawings"},
    export=True,
).add_to(m3)
result3 = st_folium(m3, height=400, key="test3", feature_group_to_add=fg)
st.write("all_drawings:", result3.get("all_drawings") if result3 else "N/A")
