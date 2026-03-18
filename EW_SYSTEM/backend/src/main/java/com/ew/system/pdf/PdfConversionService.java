package com.ew.system.pdf;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;
import java.util.concurrent.TimeUnit;

import org.springframework.stereotype.Service;

@Service
public class PdfConversionService {

    /**
     * Converts a DOCX to PDF using headless LibreOffice (`soffice`).
     * In Docker/production, ensure LibreOffice is installed and `soffice` is on PATH.
     */
    public Path convertDocxToPdf(Path docxPath, Path pdfOutputDir) {
        if (docxPath == null || !Files.exists(docxPath)) {
            throw new IllegalArgumentException("DOCX not found: " + docxPath);
        }

        try {
            Files.createDirectories(pdfOutputDir);
        } catch (IOException e) {
            throw new RuntimeException("Failed to create pdf output dir: " + pdfOutputDir, e);
        }

        List<String> cmd = List.of(
                "soffice",
                "--headless",
                "--nologo",
                "--convert-to", "pdf",
                "--outdir", pdfOutputDir.toString(),
                docxPath.toString()
        );

        Process process;
        try {
            process = new ProcessBuilder(cmd)
                    .redirectErrorStream(true)
                    .start();
        } catch (IOException e) {
            throw new RuntimeException("Failed to execute soffice (is LibreOffice installed?): " + e.getMessage(), e);
        }

        String output = "";
        try {
            output = new String(process.getInputStream().readAllBytes(), StandardCharsets.UTF_8);
        } catch (IOException ignored) {
        }

        try {
            boolean finished = process.waitFor(180, TimeUnit.SECONDS);
            if (!finished) {
                process.destroyForcibly();
                throw new RuntimeException("PDF conversion timed out. Output: " + output);
            }
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            throw new RuntimeException("PDF conversion interrupted", e);
        }

        Path pdfPath = pdfOutputDir.resolve(docxPath.getFileName().toString().replaceAll("\\.docx$", "") + ".pdf");
        if (!Files.exists(pdfPath)) {
            throw new RuntimeException("Expected PDF not found after conversion: " + pdfPath + "\nOutput: " + output);
        }
        return pdfPath;
    }
}

