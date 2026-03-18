package com.ew.system.bridges;

import java.time.Instant;

import org.springframework.stereotype.Service;

import com.ew.system.storage.StorageService;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;

@Service
public class BridgeService {
    private final StorageService storageService;
    private final ObjectMapper objectMapper;

    public BridgeService(StorageService storageService, ObjectMapper objectMapper) {
        this.storageService = storageService;
        this.objectMapper = objectMapper;
    }

    public void saveLatest(String bridgeType, JsonNode payload) {
        try {
            String dataKey = latestDataKey(bridgeType);
            byte[] bytes = objectMapper.writeValueAsBytes(payload);
            storageService.putBytes(dataKey, bytes, "application/json");

            ObjectNode meta = objectMapper.createObjectNode();
            meta.put("updatedAt", Instant.now().toString());
            storageService.putBytes(latestMetaKey(bridgeType), objectMapper.writeValueAsBytes(meta), "application/json");
        } catch (Exception e) {
            throw new RuntimeException("Failed saving bridge snapshot", e);
        }
    }

    public JsonNode loadLatest(String bridgeType) {
        try {
            String dataKey = latestDataKey(bridgeType);
            if (!storageService.exists(dataKey)) return objectMapper.createObjectNode();
            return objectMapper.readTree(storageService.getBytes(dataKey));
        } catch (Exception e) {
            throw new RuntimeException("Failed loading bridge snapshot", e);
        }
    }

    public Instant loadLatestUpdatedAt(String bridgeType) {
        try {
            String metaKey = latestMetaKey(bridgeType);
            if (!storageService.exists(metaKey)) return null;
            JsonNode meta = objectMapper.readTree(storageService.getBytes(metaKey));
            if (meta == null || !meta.has("updatedAt")) return null;
            return Instant.parse(meta.get("updatedAt").asText());
        } catch (Exception e) {
            return null;
        }
    }

    private String latestDataKey(String bridgeType) {
        return "bridges/" + bridgeType + "/latest.json";
    }

    private String latestMetaKey(String bridgeType) {
        return "bridges/" + bridgeType + "/latest_meta.json";
    }
}

