package com.ew.system.contract.dmd;

import com.ew.system.contract.common.HazardType;
import com.ew.system.contract.common.MapImage;

import com.fasterxml.jackson.annotation.JsonInclude;

@JsonInclude(JsonInclude.Include.NON_NULL)
public class HazardMapPanel {
    public HazardType hazard_type;
    public MapImage map_image;
}

