package com.ew.system.contract.common;

public class MapImage {
    /**
     * Storage key or URL to a map image.
     * In Python this is `file_path`; in production this will be S3 key/URL.
     */
    public String uri;

    public MapImage() {}

    public MapImage(String uri) {
        this.uri = uri;
    }
}

