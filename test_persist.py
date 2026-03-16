"""Test: verify drawn shapes persist on the map across reruns."""
import streamlit as st
import folium
from folium.plugins import Draw
from streamlit_folium import st_folium

st.title("Draw Persistence Test")

# Session state
if "saved" not in st.session_state:
    st.session_state["saved"] = []

saved = st.session_state["saved"]
st.write(f"**Saved drawings count:** {len(saved)}")

# Build map
m = folium.Map(location=[-6.5, 34.5], zoom_start=6, tiles="CartoDB positron")

# Re-add saved drawings as GeoJson layers on the map
if saved:
    for i, feat in enumerate(saved):
        folium.GeoJson(
            feat,
            style_function=lambda _: {
                "stroke": True, "color": "#000000", "weight": 2.5,
                "fill": True, "fillColor": "#FFA500", "fillOpacity": 0.55,
            },
        ).add_to(m)
    st.write(f"Added {len(saved)} saved shape(s) to map as GeoJson")

fg = folium.FeatureGroup(name="drawings")

Draw(
    draw_options={
        "polyline": False,
        "polygon": {"shapeOptions": {"color": "#FF0000", "fillColor": "#FFA500",
                                      "fill": True, "fillOpacity": 0.6}},
        "rectangle": {"shapeOptions": {"color": "#FF0000", "fillColor": "#FFA500",
                                        "fill": True, "fillOpacity": 0.6}},
        "circle": {"shapeOptions": {"color": "#FF0000", "fillColor": "#FFA500",
                                     "fill": True, "fillOpacity": 0.6}},
        "circlemarker": False,
        "marker": False,
    },
    export=True,
).add_to(m)

result = st_folium(
    m, height=400, key="persist_test",
    feature_group_to_add=fg,
    returned_objects=["all_drawings"],
)

# Debug output
ad = result.get("all_drawings") if result else None
st.write(f"**all_drawings:** {type(ad).__name__} = {ad}")

# Process new drawings with flag-guarded rerun
_flag = "persist_test_redrawn"
if result and result.get("all_drawings"):
    new_features = []
    for d in result["all_drawings"]:
        if not isinstance(d, dict):
            continue
        if d.get("type") == "Feature":
            new_features.append(d)
        elif d.get("geometry"):
            new_features.append({
                "type": "Feature",
                "properties": d.get("properties", {}),
                "geometry": d["geometry"],
            })
    if new_features:
        count_changed = len(new_features) != len(saved)
        st.session_state["saved"] = new_features
        st.write(f"Saved {len(new_features)} features (count changed: {count_changed})")
        if count_changed and not st.session_state.get(_flag):
            st.session_state[_flag] = True
            st.write("Triggering rerun to show saved shapes on map...")
            st.rerun()

# Clear rerun flag
st.session_state.pop(_flag, None)

col1, col2 = st.columns(2)
with col1:
    if st.button("Clear all"):
        st.session_state["saved"] = []
        st.rerun()
with col2:
    if st.button("Force rerun"):
        st.rerun()

st.write(f"**Final saved:** {len(st.session_state['saved'])}")
