package com.ew.system.api;

import java.nio.charset.StandardCharsets;

import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RestController;

import com.ew.system.storage.StorageService;

@RestController
public class FileController {
    private final StorageService storageService;

    public FileController(StorageService storageService) {
        this.storageService = storageService;
    }

    @GetMapping("/api/files/{key:.+}")
    public ResponseEntity<byte[]> download(@PathVariable("key") String key) {
        byte[] bytes = storageService.getBytes(key);

        String filename = key;
        int lastSlash = key.lastIndexOf('/');
        if (lastSlash >= 0 && lastSlash + 1 < key.length()) {
            filename = key.substring(lastSlash + 1);
        }

        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_OCTET_STREAM);
        headers.set(HttpHeaders.CONTENT_DISPOSITION, "attachment; filename=\"" + filename + "\"");
        headers.setContentLength(bytes.length);
        return ResponseEntity.ok()
                .headers(headers)
                .body(bytes);
    }
}

