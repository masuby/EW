package com.ew.system.docx;

import java.io.ByteArrayInputStream;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.LocalDate;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.List;
import java.util.Set;

import org.apache.poi.util.Units;
import org.apache.poi.xwpf.usermodel.Document;
import org.apache.poi.xwpf.usermodel.ParagraphAlignment;
import org.apache.poi.xwpf.usermodel.XWPFDocument;
import org.apache.poi.xwpf.usermodel.XWPFParagraph;
import org.apache.poi.xwpf.usermodel.XWPFRun;
import org.apache.poi.openxml4j.exceptions.InvalidFormatException;

import org.springframework.stereotype.Service;

import com.fasterxml.jackson.databind.JsonNode;

@Service
public class DocxGenerationService {

    public Path generateTma722e4Docx(JsonNode payload,
                                      Path mapsDir,
                                      Path outputDir) {
        try {
            Files.createDirectories(outputDir);
        } catch (IOException e) {
            throw new RuntimeException("Failed to create docx output dir", e);
        }

        LocalDate issueDate = LocalDate.parse(payload.get("issue_date").asText());
        DateTimeFormatter fileFmt = DateTimeFormatter.ofPattern("dd-MM-yyyy");
        String baseName = "722E_4_Five_days_" + issueDate.format(fileFmt);
        Path outPath = outputDir.resolve(baseName + ".docx");

        XWPFDocument doc = new XWPFDocument();

        // Title
        XWPFParagraph title = doc.createParagraph();
        title.setAlignment(ParagraphAlignment.CENTER);
        XWPFRun tRun = title.createRun();
        tRun.setText("722E_4 Five Days Severe Weather Impact-Based Forecast");

        XWPFParagraph issue = doc.createParagraph();
        XWPFRun iRun = issue.createRun();
        iRun.setText("Issued on: " + payload.get("issue_date").asText() + " " + payload.get("issue_time").asText());

        JsonNode days = payload.get("days");
        if (days != null && days.isArray()) {
            String mapDateStr = payload.get("issue_date").asText().replace("-", "");
            int dayCount = Math.min(days.size(), 5);
            for (int i = 0; i < dayCount; i++) {
                JsonNode day = days.get(i);
                int dayNumber = i + 1;
                String dateStr = day.has("date") ? day.get("date").asText() : "";

                XWPFParagraph dPara = doc.createParagraph();
                XWPFRun dRun = dPara.createRun();
                dRun.setText("Day " + dayNumber + " - " + dateStr);

                // Insert day map
                Path mapPath = mapsDir.resolve("722e4_" + mapDateStr + "_day" + dayNumber + ".png");
                if (Files.exists(mapPath)) {
                    XWPFParagraph imgPara = doc.createParagraph();
                    imgPara.setAlignment(ParagraphAlignment.CENTER);
                    XWPFRun imgRun = imgPara.createRun();
                    addPng(imgRun, mapPath, "map_" + dayNumber, 7.2, 5.4);
                } else {
                    XWPFParagraph p = doc.createParagraph();
                    p.createRun().setText("[Missing map: " + mapPath.getFileName() + "]");
                }

                JsonNode hazards = day.get("hazards");
                if (hazards != null && hazards.isArray() && hazards.size() > 0) {
                    for (JsonNode hazard : hazards) {
                        String alert = hazard.has("alert_level") ? hazard.get("alert_level").asText() : "";
                        String type = hazard.has("type") ? hazard.get("type").asText() : "";
                        String desc = hazard.has("description") ? hazard.get("description").asText() : "";

                        XWPFParagraph hPara = doc.createParagraph();
                        XWPFRun hRun = hPara.createRun();
                        hRun.setText(alert + " (" + type + "): " + desc);

                        if (hazard.has("impacts_expected")) {
                            XWPFParagraph imp = doc.createParagraph();
                            imp.createRun().setText("Impacts expected: " + hazard.get("impacts_expected").asText());
                        }
                        if (hazard.has("likelihood") && hazard.has("impact")) {
                            XWPFParagraph rat = doc.createParagraph();
                            rat.createRun().setText("Likelihood: " + hazard.get("likelihood").asText() +
                                    ", Impact: " + hazard.get("impact").asText());
                        }
                    }
                } else {
                    XWPFParagraph nw = doc.createParagraph();
                    nw.createRun().setText("NO WARNING");
                }
            }
        }

        try {
            doc.write(Files.newOutputStream(outPath));
            doc.close();
        } catch (IOException e) {
            throw new RuntimeException("Failed writing DOCX", e);
        }

        return outPath;
    }

    public Path generateMultiriskDocx(JsonNode payload,
                                       Path mapsDir,
                                       Path outputDir) {
        try {
            Files.createDirectories(outputDir);
        } catch (IOException e) {
            throw new RuntimeException("Failed to create docx output dir", e);
        }

        int bulletinNumber = payload.get("bulletin_number").asInt(1);
        LocalDate issueDate = LocalDate.parse(payload.get("issue_date").asText());
        DateTimeFormatter fileFmt = DateTimeFormatter.ofPattern("dd_MM_yyyy");
        String lang = payload.has("language") ? payload.get("language").asText() : "sw";
        String langSuffix = "sw".equalsIgnoreCase(lang) ? "_SW" : "";
        String baseName = "Tanzania_Multirisk" + langSuffix + "_" + bulletinNumber + "_" + issueDate.format(fileFmt);
        Path outPath = outputDir.resolve(baseName + ".docx");

        XWPFDocument doc = new XWPFDocument();

        XWPFParagraph title = doc.createParagraph();
        title.setAlignment(ParagraphAlignment.CENTER);
        title.createRun().setText("Tanzania Multirisk Three Days Impact-Based Forecast Bulletin");

        XWPFParagraph meta = doc.createParagraph();
        meta.createRun().setText("No. " + bulletinNumber + " | Issue: " + payload.get("issue_date").asText() + " " + payload.get("issue_time").asText());

        JsonNode days = payload.get("days");
        if (days != null && days.isArray()) {
            String mapDateStr = payload.get("issue_date").asText().replace("-", "");
            for (JsonNode day : days) {
                int dn = day.has("day_number") ? day.get("day_number").asInt() : 0;
                String dateStr = day.has("date") ? day.get("date").asText() : "";

                XWPFParagraph dPara = doc.createParagraph();
                dPara.createRun().setText("Day " + dn + " - " + dateStr);

                // Summary map
                Path summaryPath = mapsDir.resolve("mr_" + bulletinNumber + "_" + mapDateStr + "_day" + dn + "_summary.png");
                if (Files.exists(summaryPath)) {
                    XWPFParagraph imgPara = doc.createParagraph();
                    imgPara.setAlignment(ParagraphAlignment.CENTER);
                    addPng(imgPara.createRun(), summaryPath, "summary_" + dn, 7.2, 7.0);
                }

                // Hazard panels
                List<String> hazardKeys = List.of("heavy_rain", "large_waves", "strong_wind", "floods");
                for (String hz : hazardKeys) {
                    Path mapPath = mapsDir.resolve("mr_" + bulletinNumber + "_" + mapDateStr + "_day" + dn + "_" + hz + ".png");
                    if (Files.exists(mapPath)) {
                        XWPFParagraph hp = doc.createParagraph();
                        hp.createRun().setText("Hazard: " + hz);
                        XWPFParagraph imgPara = doc.createParagraph();
                        imgPara.setAlignment(ParagraphAlignment.CENTER);
                        addPng(imgPara.createRun(), mapPath, hz + "_" + dn, 4.3, 3.2);
                    }
                }

                // Recommendations and committee note
                if (day.has("recommendations")) {
                    JsonNode recs = day.get("recommendations");
                    if (recs.isArray()) {
                        for (JsonNode rec : recs) {
                            if (rec != null && rec.isTextual()) {
                                XWPFParagraph rp = doc.createParagraph();
                                rp.createRun().setText("Recommendation: " + rec.asText());
                            }
                        }
                    }
                }
                if (day.has("committee_note")) {
                    XWPFParagraph c = doc.createParagraph();
                    c.createRun().setText("Committee note: " + day.get("committee_note").asText());
                }
            }
        }

        try {
            doc.write(Files.newOutputStream(outPath));
            doc.close();
        } catch (IOException e) {
            throw new RuntimeException("Failed writing DOCX", e);
        }

        return outPath;
    }

    private void addPng(XWPFRun run,
                         Path imagePath,
                         String filename,
                         double widthInches,
                         double heightInches) {
        try {
            byte[] bytes = Files.readAllBytes(imagePath);
            try (ByteArrayInputStream is = new ByteArrayInputStream(bytes)) {
                int pictureType = Document.PICTURE_TYPE_PNG;
                int widthEmu = (int) Math.round(widthInches * 914400);
                int heightEmu = (int) Math.round(heightInches * 914400);
                run.addPicture(is, pictureType, filename, widthEmu, heightEmu);
            }
        } catch (IOException | InvalidFormatException e) {
            // Ignore missing image errors to keep generation resilient.
        }
    }
}

