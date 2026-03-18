package com.ew.system.contract.common;

public enum LikelihoodLevel {
    LOW("LOW"),
    MEDIUM("MEDIUM"),
    HIGH("HIGH");

    private final String value;

    LikelihoodLevel(String value) {
        this.value = value;
    }

    public String getValue() {
        return value;
    }
}

