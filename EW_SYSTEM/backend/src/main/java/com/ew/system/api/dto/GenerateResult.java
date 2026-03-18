package com.ew.system.api.dto;

import java.util.Map;

public class GenerateResult {
    public String docxUrl;
    public String pdfUrl;
    public double durationSeconds;
    public Map<String, String> files;
    public String error;
    public String logs;
}

