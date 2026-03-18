package com.ew.system.history;

import java.time.Instant;
import java.util.ArrayList;
import java.util.Collections;
import java.util.Comparator;
import java.util.List;
import java.util.Map;
import java.util.UUID;

import org.springframework.stereotype.Service;

import com.ew.system.storage.StorageService;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;

@Service
public class HistoryService {
    private final StorageService storageService;
    private final ObjectMapper objectMapper;

    public HistoryService(StorageService storageService, ObjectMapper objectMapper) {
        this.storageService = storageService;
        this.objectMapper = objectMapper;
    }

    public void record(String bulletinType, String username, String displayName,
                        String issueDate, String docxKey, String pdfKey) {
        List<HistoryItem> current = loadIndex(bulletinType);

        HistoryItem item = new HistoryItem();
        item.id = UUID.randomUUID().toString();
        item.bulletinType = bulletinType;
        item.username = username;
        item.displayName = displayName;
        item.issueDate = issueDate;
        item.docxKey = docxKey;
        item.pdfKey = pdfKey;
        item.createdAt = Instant.now();

        current.add(0, item);
        saveIndex(bulletinType, current);
    }

    public List<HistoryItem> list(String bulletinType) {
        List<HistoryItem> items = loadIndex(bulletinType);
        items.sort(Comparator.comparing((HistoryItem h) -> h.createdAt, Comparator.nullsLast(Comparator.reverseOrder())));

        // Resolve download URLs (presigned for S3, internal for local).
        for (HistoryItem item : items) {
            if (item.docxKey != null) {
                item.docxUrl = storageService.getDownloadUrl(item.docxKey, 3600);
            }
            if (item.pdfKey != null) {
                item.pdfUrl = storageService.getDownloadUrl(item.pdfKey, 3600);
            }
        }
        return items;
    }

    private List<HistoryItem> loadIndex(String bulletinType) {
        String key = historyKey(bulletinType);
        if (!storageService.exists(key)) {
            return new ArrayList<>();
        }
        try {
            byte[] bytes = storageService.getBytes(key);
            if (bytes == null || bytes.length == 0) return new ArrayList<>();
            return objectMapper.readValue(bytes, new TypeReference<List<HistoryItem>>() {});
        } catch (Exception e) {
            return new ArrayList<>();
        }
    }

    private void saveIndex(String bulletinType, List<HistoryItem> items) {
        String key = historyKey(bulletinType);
        try {
            byte[] bytes = objectMapper.writeValueAsBytes(items);
            storageService.putBytes(key, bytes, "application/json");
        } catch (Exception e) {
            // Best-effort; history shouldn't break generation.
        }
    }

    private String historyKey(String bulletinType) {
        return "history/" + bulletinType + "/index.json";
    }
}

