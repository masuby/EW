package com.ew.system.storage;

import java.nio.file.Path;

public interface StorageService {
    /**
     * Uploads a local file to storage under the given key.
     * Returns the stored key (may be same as input).
     */
    String putFile(Path filePath, String key, String contentType);

    /**
     * Returns a URL the frontend can use to download the file.
     * For local storage this will be an internal API URL.
     * For S3-compatible storage this will be a presigned URL.
     */
    String getDownloadUrl(String key, long expiresSeconds);

    byte[] getBytes(String key);

    void putBytes(String key, byte[] bytes, String contentType);

    boolean exists(String key);
}

