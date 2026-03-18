package com.ew.system.contract.dmd;

import java.time.LocalDate;
import java.time.LocalTime;
import java.util.ArrayList;
import java.util.List;

import com.ew.system.contract.common.Language;

public class MultiriskBulletin {
    public int bulletin_number;
    public LocalDate issue_date;
    public LocalTime issue_time;
    public Language language;

    public List<MultiriskDayForecast> days = new ArrayList<>();
    public List<DaySummary> day_summaries = new ArrayList<>();

    public String header_variant;
}

