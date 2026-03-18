package com.ew.system.contract.dmd;

import java.time.LocalDate;
import java.util.ArrayList;
import java.util.List;

import com.ew.system.contract.common.MapImage;

public class MultiriskDayForecast {
    public LocalDate date;
    public int day_number;

    // Page A
    public List<HazardMapPanel> hazard_panels = new ArrayList<>();
    public MapImage summary_map;
    public List<AlertTierEntry> alert_tiers = new ArrayList<>();

    // Recommendations section
    public String recommendation_intro;
    public List<String> recommendations = new ArrayList<>();
    public String committee_note;

    // Page B comments
    public TmaComment tma_comment;
    public MowComment mow_comment;
    public DmdComment dmd_comment;
}

