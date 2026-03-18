package com.ew.system.audit;

import java.time.Instant;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.Map;
import java.util.UUID;

import org.springframework.stereotype.Service;

import com.ew.system.storage.StorageService;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;

@Service
public class AuditService {
    private final StorageService storageService;
    private final ObjectMapper objectMapper;

    public AuditService(StorageService storageService, ObjectMapper objectMapper) {
        this.storageService = storageService;
        this.objectMapper = objectMapper;
    }

    public void record(String action, String username, String displayName, Map<String, Object> metadata) {
        try {
            List<AuditItem> current = loadIndex();

            AuditItem item = new AuditItem();
            item.id = UUID.randomUUID().toString();
            item.action = action;
            item.username = username;
            item.displayName = displayName;
            item.createdAt = Instant.now();
            item.metadata = metadata;

            current.add(0, item);
            saveIndex(current);
        } catch (Exception ignored) {
            // Best-effort.
        }
    }

    public List<AuditItem> list() {
        List<AuditItem> items = loadIndex();
        items.sort(Comparator.comparing((AuditItem a) -> a.createdAt, Comparator.nullsLast(Comparator.reverseOrder())));
        return items;
    }

    private List<AuditItem> loadIndex() {
        String key = "audit/index.json";
        try {
            if (!storageService.exists(key)) {
                return new ArrayList<>();
            }
            byte[] bytes = storageService.getBytes(key);
            if (bytes == null || bytes.length == 0) return new ArrayList<>();
            return objectMapper.readValue(bytes, new TypeReference<List<AuditItem>>() {});
        } catch (Exception e) {
            return new ArrayList<>();
        }
    }

    private void saveIndex(List<AuditItem> items) {
        try {
            String key = "audit/index.json";
            byte[] bytes = objectMapper.writeValueAsBytes(items);
            storageService.putBytes(key, bytes, "application/json");
        } catch (Exception ignored) {
        }
    }
}

