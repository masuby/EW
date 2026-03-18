package com.ew.system.api;

import java.time.Instant;
import java.util.Map;

import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import com.ew.system.bridges.BridgeService;
import com.fasterxml.jackson.databind.JsonNode;
import com.ew.system.audit.AuditService;

import org.springframework.security.core.context.SecurityContextHolder;

@RestController
@RequestMapping("/api/bridges")
public class BridgesController {
    private final BridgeService bridgeService;
    private final AuditService auditService;

    public BridgesController(BridgeService bridgeService, AuditService auditService) {
        this.bridgeService = bridgeService;
        this.auditService = auditService;
    }

    @PostMapping("/{type}/latest")
    public ResponseEntity<Void> saveLatest(@PathVariable("type") String type, @RequestBody JsonNode payload) {
        bridgeService.saveLatest(type, payload);
        String username = SecurityContextHolder.getContext().getAuthentication() == null
                ? "unknown"
                : SecurityContextHolder.getContext().getAuthentication().getName();
        auditService.record("bridge_save_" + type, username, null, java.util.Map.of("type", type));
        return ResponseEntity.ok().build();
    }

    @GetMapping("/{type}/latest")
    public ResponseEntity<Map<String, Object>> loadLatest(@PathVariable("type") String type) {
        JsonNode payload = bridgeService.loadLatest(type);
        Instant updatedAt = bridgeService.loadLatestUpdatedAt(type);
        return ResponseEntity.ok(Map.of(
                "payload", payload,
                "updatedAt", updatedAt
        ));
    }
}

