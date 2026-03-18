package com.ew.system.api;

import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import com.ew.system.templates.TemplateService;
import com.fasterxml.jackson.databind.JsonNode;
import com.ew.system.audit.AuditService;
import org.springframework.security.core.context.SecurityContextHolder;

@RestController
@RequestMapping("/api/templates")
public class TemplatesController {
    private final TemplateService templateService;
    private final AuditService auditService;

    public TemplatesController(TemplateService templateService, AuditService auditService) {
        this.templateService = templateService;
        this.auditService = auditService;
    }

    @PostMapping("/{type}/save")
    public ResponseEntity<Void> save(@PathVariable("type") String type, @RequestBody JsonNode payload) {
        templateService.saveTemplate(type, payload);

        String username = SecurityContextHolder.getContext().getAuthentication() == null
                ? "unknown"
                : SecurityContextHolder.getContext().getAuthentication().getName();
        auditService.record("template_save_" + type, username, null, java.util.Map.of(
                "type", type
        ));
        return ResponseEntity.ok().build();
    }

    @PostMapping("/{type}/load")
    public ResponseEntity<JsonNode> load(@PathVariable("type") String type) {
        return ResponseEntity.ok(templateService.loadTemplate(type));
    }
}

