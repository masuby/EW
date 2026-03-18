package com.ew.system.spatial;

import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.zip.ZipEntry;
import java.util.zip.ZipInputStream;

import org.locationtech.jts.geom.Geometry;
import org.locationtech.jts.io.geojson.GeoJsonReader;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;

@Service
public class GeoDataLoader {
    private final ObjectMapper objectMapper = new ObjectMapper();

    private final Path geodataDir;
    private final GeoJsonReader geoJsonReader = new GeoJsonReader();

    private volatile List<RegionFeature> regions;
    private volatile List<DistrictFeature> districts;

    public GeoDataLoader(@Value("${ew.assets.geodataDir:assets/geodata}") String geodataDir) {
        this.geodataDir = Path.of(geodataDir);
    }

    public List<RegionFeature> getRegions() {
        if (regions == null) {
            synchronized (this) {
                if (regions == null) {
                    regions = loadRegions();
                }
            }
        }
        return regions;
    }

    public List<DistrictFeature> getDistricts() {
        if (districts == null) {
            synchronized (this) {
                if (districts == null) {
                    districts = loadDistricts();
                }
            }
        }
        return districts;
    }

    private List<RegionFeature> loadRegions() {
        Path zipPath = geodataDir.resolve("gadm41_TZA_1.json.zip");
        if (!Files.exists(zipPath)) {
            throw new IllegalStateException("Missing geodata zip: " + zipPath);
        }

        JsonNode featureCollection = readSingleJsonFromZip(zipPath, "gadm41_TZA_1.json");
        List<RegionFeature> out = new ArrayList<>();

        for (JsonNode feature : featureCollection.get("features")) {
            JsonNode props = feature.get("properties");
            String rawName = props.get("NAME_1").asText();
            String displayName = cleanRegionName(rawName);
            Geometry geom = parseGeometry(feature.get("geometry"));
            out.add(new RegionFeature(displayName, geom));
        }
        return out;
    }

    private List<DistrictFeature> loadDistricts() {
        Path zipPath = geodataDir.resolve("gadm41_TZA_2.json.zip");
        if (!Files.exists(zipPath)) {
            throw new IllegalStateException("Missing geodata zip: " + zipPath);
        }

        JsonNode featureCollection = readSingleJsonFromZip(zipPath, "gadm41_TZA_2.json");
        List<DistrictFeature> out = new ArrayList<>();

        for (JsonNode feature : featureCollection.get("features")) {
            JsonNode props = feature.get("properties");
            String rawRegion = props.get("NAME_1").asText();
            String region = cleanRegionName(rawRegion);
            String rawDistrictName = props.get("NAME_2").asText();
            String displayName = cleanDistrictName(rawDistrictName);
            Geometry geom = parseGeometry(feature.get("geometry"));
            out.add(new DistrictFeature(displayName, region, geom));
        }
        return out;
    }

    private JsonNode readSingleJsonFromZip(Path zipPath, String expectedEntryName) {
        try (InputStream is = Files.newInputStream(zipPath);
             ZipInputStream zis = new ZipInputStream(is)) {
            ZipEntry entry;
            while ((entry = zis.getNextEntry()) != null) {
                if (entry.getName().equals(expectedEntryName)) {
                    byte[] bytes = zis.readAllBytes();
                    return objectMapper.readTree(new String(bytes, StandardCharsets.UTF_8));
                }
            }
        } catch (Exception e) {
            throw new RuntimeException("Failed reading geodata from zip: " + zipPath, e);
        }
        throw new RuntimeException("Expected entry not found in zip: " + zipPath + " -> " + expectedEntryName);
    }

    private Geometry parseGeometry(JsonNode geometryNode) {
        try {
            // GeoJsonReader expects a full geometry object with type+coordinates.
            return geoJsonReader.read(geometryNode.toString());
        } catch (Exception e) {
            throw new RuntimeException("Failed parsing geometry GeoJSON", e);
        }
    }

    private String cleanRegionName(String name) {
        // Mirror dashboard/config.py and map_widget.py region cleaning.
        Map<String, String> mappings = new HashMap<>();
        mappings.put("DaresSalaam", "Dar es Salaam");
        mappings.put("KaskaziniPemba", "Kaskazini Pemba");
        mappings.put("KaskaziniUnguja", "Kaskazini Unguja");
        mappings.put("KusiniPemba", "Kusini Pemba");
        mappings.put("KusiniUnguja", "Kusini Unguja");
        mappings.put("MjiniMagharibi", "Mjini Magharibi");
        return mappings.getOrDefault(name, name);
    }

    private String cleanDistrictName(String name) {
        // Insert spaces before capital letters in camelCase names
        // Example: "KorogweTown" -> "Korogwe Town"
        return name.replaceAll("(?<=[a-z])(?=[A-Z])", " ");
    }

    public record RegionFeature(String displayName, Geometry geometry) {}
    public record DistrictFeature(String displayName, String region, Geometry geometry) {}
}

