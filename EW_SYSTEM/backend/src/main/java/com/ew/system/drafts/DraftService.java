package com.ew.system.drafts;

import org.springframework.security.core.Authentication;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.stereotype.Service;

import com.ew.system.storage.StorageService;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;

@Service
public class DraftService {
    private final StorageService storageService;
    private final ObjectMapper objectMapper;

    public DraftService(StorageService storageService, ObjectMapper objectMapper) {
        this.storageService = storageService;
        this.objectMapper = objectMapper;
    }

    public void saveDraft(String type, JsonNode draftJson) {
        try {
            Authentication auth = SecurityContextHolder.getContext().getAuthentication();
            String username = auth == null ? "unknown" : auth.getName();

            String key = draftKey(username, type);
            byte[] bytes = objectMapper.writeValueAsBytes(draftJson);
            storageService.putBytes(key, bytes, "application/json");
        } catch (Exception e) {
            throw new RuntimeException("Failed saving draft", e);
        }
    }

    public JsonNode loadDraft(String type) {
        try {
            Authentication auth = SecurityContextHolder.getContext().getAuthentication();
            String username = auth == null ? "unknown" : auth.getName();

            String key = draftKey(username, type);
            if (!storageService.exists(key)) return objectMapper.createObjectNode();
            return objectMapper.readTree(storageService.getBytes(key));
        } catch (Exception e) {
            throw new RuntimeException("Failed loading draft", e);
        }
    }

    private String draftKey(String username, String type) {
        return "drafts/" + username + "/" + type + "/latest.json";
    }
}

