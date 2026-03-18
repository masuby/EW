package com.ew.system.spatial;

import java.util.ArrayList;
import java.util.List;

import org.locationtech.jts.geom.Geometry;
import org.locationtech.jts.io.geojson.GeoJsonReader;
import org.springframework.stereotype.Service;

import com.fasterxml.jackson.databind.JsonNode;
import com.ew.system.spatial.GeoDataLoader.DistrictFeature;
import com.ew.system.spatial.GeoDataLoader.RegionFeature;

@Service
public class SpatialIntersectionService {
    private final GeoDataLoader loader;
    private final GeoJsonReader geoJsonReader = new GeoJsonReader();

    public SpatialIntersectionService(GeoDataLoader loader) {
        this.loader = loader;
    }

    public List<String> intersect(String level, JsonNode geometryNode) {
        if (level == null) return List.of();

        Geometry drawGeom = parseDrawGeometry(geometryNode);
        if (drawGeom == null || drawGeom.isEmpty()) return List.of();

        if (level.equalsIgnoreCase("districts")) {
            List<String> selected = new ArrayList<>();
            for (DistrictFeature d : loader.getDistricts()) {
                if (d.geometry().intersects(drawGeom)) {
                    selected.add(d.displayName());
                }
            }
            selected.sort(String::compareTo);
            return selected;
        }

        // Default to regions
        List<String> selected = new ArrayList<>();
        for (RegionFeature r : loader.getRegions()) {
            if (r.geometry().intersects(drawGeom)) {
                selected.add(r.displayName());
            }
        }
        selected.sort(String::compareTo);
        return selected;
    }

    private Geometry parseDrawGeometry(JsonNode node) {
        if (node == null) return null;

        try {
            // Accept either a GeoJSON Feature or a bare geometry.
            if (node.has("type") && "Feature".equalsIgnoreCase(node.get("type").asText())) {
                JsonNode geom = node.get("geometry");
                if (geom == null) return null;
                return geoJsonReader.read(geom.toString());
            }
            return geoJsonReader.read(node.toString());
        } catch (Exception e) {
            // Frontend may send a geometry that needs cleaning; fail safe.
            return null;
        }
    }
}

