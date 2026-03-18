package com.ew.system.contract.common;

public enum Language {
    EN("en"),
    SW("sw");

    private final String value;

    Language(String value) {
        this.value = value;
    }

    public String getValue() {
        return value;
    }
}

