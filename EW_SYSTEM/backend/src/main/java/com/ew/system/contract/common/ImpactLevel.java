package com.ew.system.contract.common;

public enum ImpactLevel {
    LOW("LOW"),
    MEDIUM("MEDIUM"),
    HIGH("HIGH");

    private final String value;

    ImpactLevel(String value) {
        this.value = value;
    }

    public String getValue() {
        return value;
    }
}

