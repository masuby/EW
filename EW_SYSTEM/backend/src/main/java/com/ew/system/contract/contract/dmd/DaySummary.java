package com.ew.system.contract.dmd;

import java.util.ArrayList;
import java.util.List;

public class DaySummary {
    public int day_number;
    public List<String> major_warning_districts = new ArrayList<>();
    public List<String> warning_districts = new ArrayList<>();
    public List<String> advisory_districts = new ArrayList<>();
}

