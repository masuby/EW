package com.ew.system.api;

import java.util.List;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import com.ew.system.audit.AuditItem;
import com.ew.system.audit.AuditService;

import org.springframework.web.bind.annotation.RequestParam;

@RestController
@RequestMapping("/api")
public class AuditController {
    private final AuditService auditService;

    public AuditController(AuditService auditService) {
        this.auditService = auditService;
    }

    @GetMapping("/audit")
    public List<AuditItem> list() {
        return auditService.list();
    }
}

