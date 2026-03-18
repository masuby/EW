package com.ew.system.templates;

import java.util.Map;

import org.springframework.stereotype.Service;

import com.ew.system.storage.StorageService;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;

@Service
public class TemplateService {
    private final StorageService storageService;
    private final ObjectMapper objectMapper;

    public TemplateService(StorageService storageService, ObjectMapper objectMapper) {
        this.storageService = storageService;
        this.objectMapper = objectMapper;
    }

    public void saveTemplate(String type, JsonNode templateJson) {
        try {
            String key = templateKey(type);
            byte[] bytes = objectMapper.writeValueAsBytes(templateJson);
            storageService.putBytes(key, bytes, "application/json");
        } catch (Exception e) {
            throw new RuntimeException("Failed saving template", e);
        }
    }

    public JsonNode loadTemplate(String type) {
        try {
            String key = templateKey(type);
            if (!storageService.exists(key)) return objectMapper.createObjectNode();
            byte[] bytes = storageService.getBytes(key);
            return objectMapper.readTree(bytes);
        } catch (Exception e) {
            throw new RuntimeException("Failed loading template", e);
        }
    }

    private String templateKey(String type) {
        return "templates/" + type + "/latest.json";
    }
}

