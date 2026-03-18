package com.ew.system.history;

import java.time.Instant;

public class HistoryItem {
    public String id;
    public String bulletinType;
    public String username;
    public String displayName;
    public String issueDate;
    public String docxKey;
    public String pdfKey;
    public String docxUrl;
    public String pdfUrl;
    public Instant createdAt;
}

