package com.ew.system.contract.common;

public enum HazardType {
    HEAVY_RAIN("HEAVY_RAIN"),
    STRONG_WIND("STRONG_WIND"),
    LARGE_WAVES("LARGE_WAVES"),
    FLOODS("FLOODS"),
    LANDSLIDES("LANDSLIDES"),
    EXTREME_TEMPERATURE("EXTREME_TEMPERATURE");

    private final String value;

    HazardType(String value) {
        this.value = value;
    }

    public String getValue() {
        return value;
    }
}

