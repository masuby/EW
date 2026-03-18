package com.ew.system.storage;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;

import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.stereotype.Service;

@Service
@ConditionalOnProperty(name = "ew.storage.type", havingValue = "local", matchIfMissing = true)
public class LocalStorageService implements StorageService {
    private final StorageProperties properties;

    public LocalStorageService(StorageProperties properties) {
        this.properties = properties;
    }

    @Override
    public String putFile(Path filePath, String key, String contentType) {
        if (filePath == null || !Files.exists(filePath)) {
            throw new IllegalArgumentException("File not found: " + filePath);
        }
        Path baseDir = Path.of(properties.getLocal().getDir());
        Path target = baseDir.resolve(key);
        try {
            Files.createDirectories(target.getParent());
            Files.copy(filePath, target, StandardCopyOption.REPLACE_EXISTING);
        } catch (IOException e) {
            throw new RuntimeException("Local upload failed", e);
        }
        return key;
    }

    @Override
    public String getDownloadUrl(String key, long expiresSeconds) {
        // Local storage uses the backend API for downloads.
        return "/api/files/" + key;
    }

    @Override
    public byte[] getBytes(String key) {
        Path baseDir = Path.of(properties.getLocal().getDir());
        Path target = baseDir.resolve(key);
        try {
            return Files.readAllBytes(target);
        } catch (IOException e) {
            throw new RuntimeException("Local read failed: " + key, e);
        }
    }

    @Override
    public void putBytes(String key, byte[] bytes, String contentType) {
        Path baseDir = Path.of(properties.getLocal().getDir());
        Path target = baseDir.resolve(key);
        try {
            Files.createDirectories(target.getParent());
            Files.write(target, bytes);
        } catch (IOException e) {
            throw new RuntimeException("Local putBytes failed: " + key, e);
        }
    }

    @Override
    public boolean exists(String key) {
        Path baseDir = Path.of(properties.getLocal().getDir());
        Path target = baseDir.resolve(key);
        return Files.exists(target);
    }
}

