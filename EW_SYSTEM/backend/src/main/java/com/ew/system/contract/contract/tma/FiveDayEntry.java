package com.ew.system.contract.tma;

import java.time.LocalDate;
import java.util.ArrayList;
import java.util.List;

import com.ew.system.contract.common.MapImage;
import com.ew.system.contract.common.AlertLevel;

public class FiveDayEntry {
    public LocalDate date;
    public List<HazardEntry> hazards = new ArrayList<>();
    public MapImage map_image;

    public FiveDayEntry() {}

    public boolean is_no_warning() {
        if (hazards == null || hazards.isEmpty()) return true;
        return hazards.stream().allMatch(h -> h.alert_level == AlertLevel.NO_WARNING);
    }
}

