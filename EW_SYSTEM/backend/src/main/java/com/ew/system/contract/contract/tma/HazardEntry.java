package com.ew.system.contract.tma;

import java.util.List;

import com.ew.system.contract.common.AlertLevel;
import com.ew.system.contract.common.HazardType;
import com.ew.system.contract.common.MapImage;
import com.ew.system.contract.common.RatingPair;

import com.fasterxml.jackson.annotation.JsonInclude;

@JsonInclude(JsonInclude.Include.NON_NULL)
public class HazardEntry {
    public HazardType type;
    public AlertLevel alert_level;
    public String description;
    public RatingPair likelihood_impact;
    public String impacts_expected;

    // Optional spatial selection data
    public List<String> regions;
    public List<Object> drawn_shapes; // GeoJSON features produced by frontend draw tool

    // Optional map image for this hazard (future use)
    public MapImage map_image;
}

