package com.ew.system.api;

import com.ew.system.api.dto.GenerateDmdMultiriskRequest;
import com.ew.system.api.dto.GenerateResult;
import com.ew.system.api.dto.GenerateTma722e4Request;

import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.security.access.prepost.PreAuthorize;

import com.fasterxml.jackson.databind.JsonNode;

import java.nio.file.Path;
import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Set;

import com.ew.system.spatial.MapRenderingService;
import com.ew.system.docx.DocxGenerationService;
import com.ew.system.pdf.PdfConversionService;
import com.ew.system.storage.StorageService;
import com.ew.system.history.HistoryService;
import com.ew.system.audit.AuditService;

import org.springframework.security.core.context.SecurityContextHolder;

@RestController
@RequestMapping("/api/bulletins")
public class BulletinController {
    private final MapRenderingService mapRenderingService;
    private final DocxGenerationService docxGenerationService;
    private final PdfConversionService pdfConversionService;
    private final StorageService storageService;
    private final HistoryService historyService;
    private final AuditService auditService;

    public BulletinController(MapRenderingService mapRenderingService,
                               DocxGenerationService docxGenerationService,
                               PdfConversionService pdfConversionService,
                               StorageService storageService,
                               HistoryService historyService,
                               AuditService auditService) {
        this.mapRenderingService = mapRenderingService;
        this.docxGenerationService = docxGenerationService;
        this.pdfConversionService = pdfConversionService;
        this.storageService = storageService;
        this.historyService = historyService;
        this.auditService = auditService;
    }

    @PostMapping("/tma/722e4/generate")
    @PreAuthorize("hasRole('TMA') or hasRole('ADMIN')")
    public GenerateResult generateTma(@RequestBody GenerateTma722e4Request req) {
        long start = System.nanoTime();
        GenerateResult out = new GenerateResult();

        Path baseOutput = Path.of(System.getProperty("user.dir"), "output");
        Path mapsDir = baseOutput.resolve("maps");
        Path tmaDocxDir = baseOutput.resolve("tma");
        List<String> generatedMaps = new ArrayList<>();

        // Expected input schema matches the Python dashboard output (issue_date, issue_time, days[])
        JsonNode payload = req.payload;
        String issueDate = payload.has("issue_date") ? payload.get("issue_date").asText() : null;
        String dateStr = issueDate == null ? "unknown" : issueDate.replace("-", "");

        JsonNode days = payload.get("days");
        if (days != null && days.isArray()) {
            int dayCount = Math.min(days.size(), 5);
            for (int i = 0; i < dayCount; i++) {
                JsonNode day = days.get(i);
                JsonNode hazards = day.get("hazards");
                Set<String> regions = new HashSet<>();

                // Determine max alert level
                int maxTier = 0; // NO_WARNING=0, ADVISORY=1, WARNING=2, MAJOR_WARNING=3
                if (hazards != null && hazards.isArray()) {
                    for (JsonNode hazard : hazards) {
                        String alert = hazard.has("alert_level") ? hazard.get("alert_level").asText() : "ADVISORY";
                        int tier =
                                switch (alert) {
                                    case "MAJOR_WARNING" -> 3;
                                    case "WARNING" -> 2;
                                    case "ADVISORY" -> 1;
                                    default -> 0;
                                };
                        if (tier > maxTier) maxTier = tier;

                        JsonNode regionArr = hazard.get("regions");
                        if (regionArr != null && regionArr.isArray()) {
                            for (JsonNode r : regionArr) {
                                if (r != null && r.isTextual()) regions.add(r.asText());
                            }
                        }
                    }
                }

                // If hazards are empty, render a blank map
                boolean noWarningDay = (hazards == null || !hazards.isArray() || hazards.size() == 0);
                if (noWarningDay) regions.clear();

                String fillHex =
                        switch (maxTier) {
                            case 3 -> "#FF0000"; // MAJOR_WARNING
                            case 2 -> "#FFA500"; // WARNING
                            case 1 -> "#FFFF00"; // ADVISORY
                            default -> "#FFFF00"; // default
                        };

                String outputName = "722e4_" + dateStr + "_day" + (i + 1) + ".png";
                Path outPath = mapsDir.resolve(outputName);

                int w = (i == 0) ? 1100 : 900;
                int h = (i == 0) ? 900 : 750;
                mapRenderingService.renderRegionMap(regions, fillHex, outPath, w, h);
                generatedMaps.add(outPath.toString());
            }
        }

        // Placeholder implementation: in the rewrite, this will be replaced by
        // real validation, map rendering, DOCX generation, and PDF conversion.
        Path docxPath = docxGenerationService.generateTma722e4Docx(payload, mapsDir, tmaDocxDir);
        out.docxUrl = docxPath.toString();
        out.pdfUrl = null;
        String pdfConversionError = null;
        java.util.Map<String, String> files = new java.util.HashMap<>();

        // Upload generated files to storage (local or S3) and return download URLs.
        String runId = java.util.UUID.randomUUID().toString();
        String username = SecurityContextHolder.getContext().getAuthentication() == null
                ? "unknown"
                : SecurityContextHolder.getContext().getAuthentication().getName();
        String displayName = null;
        Object details = SecurityContextHolder.getContext().getAuthentication() == null
                ? null
                : SecurityContextHolder.getContext().getAuthentication().getDetails();
        if (details instanceof java.util.Map<?, ?> m) {
            Object dn = m.get("displayName");
            if (dn instanceof String s) displayName = s;
        }

        String docxKey = "generated/tma/722e4/" + runId + "/" + docxPath.getFileName().toString();
        storageService.putFile(docxPath, docxKey, "application/vnd.openxmlformats-officedocument.wordprocessingml.document");
        out.docxUrl = storageService.getDownloadUrl(docxKey, 3600);
        files.put("docx", out.docxUrl);

        try {
            Path pdfDir = baseOutput.resolve("pdf").resolve("tma");
            Path pdfPath = pdfConversionService.convertDocxToPdf(docxPath, pdfDir);
            String pdfKey = "generated/tma/722e4/" + runId + "/" + pdfPath.getFileName().toString();
            storageService.putFile(pdfPath, pdfKey, "application/pdf");
            out.pdfUrl = storageService.getDownloadUrl(pdfKey, 3600);
            files.put("pdf", out.pdfUrl);

            // Record history only once we have upload keys (docx always present).
            historyService.record("tma_722e4", username, displayName, issueDate, docxKey, pdfKey);
            auditService.record("generate_tma_722e4", username, displayName, java.util.Map.of(
                    "runId", runId,
                    "issueDate", issueDate,
                    "docxKey", docxKey,
                    "pdfKey", pdfKey
            ));
        } catch (Exception conversionEx) {
            pdfConversionError = conversionEx.getMessage();
            historyService.record("tma_722e4", username, displayName, issueDate, docxKey, null);
            java.util.Map<String, Object> meta = new java.util.HashMap<>();
            meta.put("runId", runId);
            meta.put("issueDate", issueDate);
            meta.put("docxKey", docxKey);
            meta.put("pdfError", pdfConversionError);
            auditService.record("generate_tma_722e4", username, displayName, meta);
        }
        out.files = files;
        out.durationSeconds = (System.nanoTime() - start) / 1_000_000_000.0;
        out.error = null;
        out.logs = "Maps generated:\n" + String.join("\n", generatedMaps) +
                "\nDOCX available at:\n" + out.docxUrl;
        if (out.pdfUrl != null) {
            out.logs = out.logs + "\nPDF generated:\n" + out.pdfUrl;
        } else {
            out.logs = out.logs + "\nPDF generation not available (soffice missing or conversion failed).";
            if (pdfConversionError != null) {
                out.logs = out.logs + "\nDetails: " + pdfConversionError;
            }
        }
        return out;
    }

    @PostMapping("/dmd/multirisk/generate")
    @PreAuthorize("hasRole('DMD') or hasRole('ADMIN')")
    public GenerateResult generateDmd(@RequestBody GenerateDmdMultiriskRequest req) {
        long start = System.nanoTime();
        GenerateResult out = new GenerateResult();

        Path baseOutput = Path.of(System.getProperty("user.dir"), "output");
        Path mapsDir = baseOutput.resolve("maps");
        Path dmdDocxDir = baseOutput.resolve("dmd");
        List<String> generatedMaps = new ArrayList<>();

        JsonNode payload = req.payload;
        int bulletinNumber = payload.has("bulletin_number") ? payload.get("bulletin_number").asInt(1) : 1;
        String issueDate = payload.has("issue_date") ? payload.get("issue_date").asText() : null;
        String mapDateStr = issueDate == null ? "unknown" : issueDate.replace("-", "");

        // Build per-day tier district sets from district_summaries
        JsonNode summaries = payload.get("district_summaries");
        java.util.Map<Integer, java.util.Map<String, Set<String>>> tierSetsByDay = new java.util.HashMap<>();

        if (summaries != null && summaries.isArray()) {
            for (JsonNode s : summaries) {
                int dn = s.get("day_number").asInt();
                Set<String> major = new HashSet<>();
                Set<String> warning = new HashSet<>();
                Set<String> advisory = new HashSet<>();

                for (JsonNode x : s.get("major_warning")) if (x.isTextual()) major.add(x.asText());
                for (JsonNode x : s.get("warning")) if (x.isTextual()) warning.add(x.asText());
                for (JsonNode x : s.get("advisory")) if (x.isTextual()) advisory.add(x.asText());

                var dayMap = new java.util.HashMap<String, Set<String>>();
                dayMap.put("major_warning", major);
                dayMap.put("warning", warning);
                dayMap.put("advisory", advisory);
                tierSetsByDay.put(dn, dayMap);
            }
        }

        // Generate maps for each day that has a summary.
        Set<Integer> dayNumbers = new HashSet<>(tierSetsByDay.keySet());
        if (dayNumbers.isEmpty()) {
            JsonNode days = payload.get("days");
            if (days != null && days.isArray()) {
                for (JsonNode d : days) dayNumbers.add(d.get("day_number").asInt());
            }
        }

        for (int dn : dayNumbers) {
            var sets = tierSetsByDay.get(dn);
            Set<String> major = new HashSet<>();
            Set<String> warning = new HashSet<>();
            Set<String> advisory = new HashSet<>();
            if (sets != null) {
                major = sets.getOrDefault("major_warning", Set.of());
                warning = sets.getOrDefault("warning", Set.of());
                advisory = sets.getOrDefault("advisory", Set.of());
            }

            Set<String> allAffected = new HashSet<>();
            allAffected.addAll(major);
            allAffected.addAll(warning);
            allAffected.addAll(advisory);

            // Hazard maps (match current Python auto_maps keys: day{dn}_{hazard})
            // In Python auto_maps highlights `all_affected` for each hazard panel.
            List<String> hazardKeys = List.of("heavy_rain", "large_waves", "strong_wind", "floods");
            for (String hz : hazardKeys) {
                String outputName = "mr_" + bulletinNumber + "_" + mapDateStr + "_day" + dn + "_" + hz + ".png";
                Path outPath = mapsDir.resolve(outputName);
                mapRenderingService.renderDistrictMap(allAffected, "#FFFF00", outPath, 900, 750);
                generatedMaps.add(outPath.toString());
            }

            // Summary map
            String summaryName = "mr_" + bulletinNumber + "_" + mapDateStr + "_day" + dn + "_summary.png";
            Path summaryOutPath = mapsDir.resolve(summaryName);
            mapRenderingService.renderMultiTierDistrictMap(major, warning, advisory, summaryOutPath, 900, 850);
            generatedMaps.add(summaryOutPath.toString());
        }

        Path docxPath = docxGenerationService.generateMultiriskDocx(payload, mapsDir, dmdDocxDir);
        out.docxUrl = docxPath.toString();
        out.pdfUrl = null;
        String pdfConversionError = null;
        java.util.Map<String, String> files = new java.util.HashMap<>();

        String runId = java.util.UUID.randomUUID().toString();
        String username = SecurityContextHolder.getContext().getAuthentication() == null
                ? "unknown"
                : SecurityContextHolder.getContext().getAuthentication().getName();
        String displayName = null;
        Object details = SecurityContextHolder.getContext().getAuthentication() == null
                ? null
                : SecurityContextHolder.getContext().getAuthentication().getDetails();
        if (details instanceof java.util.Map<?, ?> m) {
            Object dn = m.get("displayName");
            if (dn instanceof String s) displayName = s;
        }

        String docxKey = "generated/dmd/multirisk/" + runId + "/" + docxPath.getFileName().toString();
        storageService.putFile(docxPath, docxKey, "application/vnd.openxmlformats-officedocument.wordprocessingml.document");
        out.docxUrl = storageService.getDownloadUrl(docxKey, 3600);
        files.put("docx", out.docxUrl);

        try {
            Path pdfDir = baseOutput.resolve("pdf").resolve("dmd");
            Path pdfPath = pdfConversionService.convertDocxToPdf(docxPath, pdfDir);
            String pdfKey = "generated/dmd/multirisk/" + runId + "/" + pdfPath.getFileName().toString();
            storageService.putFile(pdfPath, pdfKey, "application/pdf");
            out.pdfUrl = storageService.getDownloadUrl(pdfKey, 3600);
            files.put("pdf", out.pdfUrl);

            historyService.record("dmd_multirisk", username, displayName, payload.get("issue_date").asText(), docxKey, pdfKey);
            auditService.record("generate_dmd_multirisk", username, displayName, java.util.Map.of(
                    "runId", runId,
                    "issueDate", payload.get("issue_date").asText(),
                    "docxKey", docxKey,
                    "pdfKey", pdfKey
            ));
        } catch (Exception conversionEx) {
            pdfConversionError = conversionEx.getMessage();
            historyService.record("dmd_multirisk", username, displayName, payload.get("issue_date").asText(), docxKey, null);
            java.util.Map<String, Object> meta = new java.util.HashMap<>();
            meta.put("runId", runId);
            meta.put("issueDate", payload.get("issue_date").asText());
            meta.put("docxKey", docxKey);
            meta.put("pdfError", pdfConversionError);
            auditService.record("generate_dmd_multirisk", username, displayName, meta);
        }
        out.files = files;
        out.durationSeconds = (System.nanoTime() - start) / 1_000_000_000.0;
        out.error = null;
        out.logs = "Maps generated:\n" + String.join("\n", generatedMaps) +
                "\nDOCX available at:\n" + out.docxUrl;
        if (out.pdfUrl != null) {
            out.logs = out.logs + "\nPDF generated:\n" + out.pdfUrl;
        } else {
            out.logs = out.logs + "\nPDF generation not available (soffice missing or conversion failed).";
            if (pdfConversionError != null) {
                out.logs = out.logs + "\nDetails: " + pdfConversionError;
            }
        }
        return out;
    }
}

