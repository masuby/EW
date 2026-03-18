package com.ew.system.contract.common;

public enum AlertLevel {
    NO_WARNING("NO_WARNING"),
    ADVISORY("ADVISORY"),
    WARNING("WARNING"),
    MAJOR_WARNING("MAJOR_WARNING");

    private final String value;

    AlertLevel(String value) {
        this.value = value;
    }

    public String getValue() {
        return value;
    }
}

