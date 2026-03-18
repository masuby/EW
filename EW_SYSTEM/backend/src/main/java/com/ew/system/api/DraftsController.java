package com.ew.system.api;

import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import com.ew.system.drafts.DraftService;
import com.fasterxml.jackson.databind.JsonNode;
import com.ew.system.audit.AuditService;

import org.springframework.security.core.context.SecurityContextHolder;

@RestController
@RequestMapping("/api/drafts")
public class DraftsController {
    private final DraftService draftService;
    private final AuditService auditService;

    public DraftsController(DraftService draftService, AuditService auditService) {
        this.draftService = draftService;
        this.auditService = auditService;
    }

    @PostMapping("/{type}/autosave")
    public ResponseEntity<Void> autosave(@PathVariable("type") String type, @RequestBody JsonNode payload) {
        draftService.saveDraft(type, payload);
        String username = SecurityContextHolder.getContext().getAuthentication() == null
                ? "unknown"
                : SecurityContextHolder.getContext().getAuthentication().getName();
        auditService.record("draft_autosave_" + type, username, null, java.util.Map.of("type", type));
        return ResponseEntity.ok().build();
    }

    @GetMapping("/{type}/restore")
    public ResponseEntity<JsonNode> restore(@PathVariable("type") String type) {
        String username = SecurityContextHolder.getContext().getAuthentication() == null
                ? "unknown"
                : SecurityContextHolder.getContext().getAuthentication().getName();
        auditService.record("draft_restore_" + type, username, null, java.util.Map.of("type", type));
        return ResponseEntity.ok(draftService.loadDraft(type));
    }

    @PostMapping("/{type}/restore")
    public ResponseEntity<JsonNode> restorePost(@PathVariable("type") String type, @RequestBody(required = false) JsonNode ignored) {
        String username = SecurityContextHolder.getContext().getAuthentication() == null
                ? "unknown"
                : SecurityContextHolder.getContext().getAuthentication().getName();
        auditService.record("draft_restore_" + type, username, null, java.util.Map.of("type", type));
        return ResponseEntity.ok(draftService.loadDraft(type));
    }
}

