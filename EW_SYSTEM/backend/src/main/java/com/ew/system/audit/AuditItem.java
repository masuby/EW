package com.ew.system.audit;

import java.time.Instant;
import java.util.Map;

public class AuditItem {
    public String id;
    public String action;
    public String username;
    public String displayName;
    public Instant createdAt;
    public Map<String, Object> metadata;
}

