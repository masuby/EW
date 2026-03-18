package com.ew.system.api.dto;

import java.util.List;

import com.fasterxml.jackson.databind.JsonNode;

/**
 * Draw interaction sends a geometry; backend computes intersection and returns
 * selected region/district display names.
 */
public class SpatialIntersectionRequest {
    public String level; // "regions" or "districts"
    public JsonNode geometry; // GeoJSON geometry (Polygon/MultiPolygon)
    public List<String> selectedCurrent; // optional; used by UI for toggling behavior
}

