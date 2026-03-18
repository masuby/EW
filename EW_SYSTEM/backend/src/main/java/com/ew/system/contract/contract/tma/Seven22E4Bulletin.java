package com.ew.system.contract.tma;

import java.time.LocalDate;
import java.time.LocalTime;
import java.util.ArrayList;
import java.util.List;

public class Seven22E4Bulletin {
    public LocalDate issue_date;
    public LocalTime issue_time;
    public List<FiveDayEntry> days = new ArrayList<>();

    public Seven22E4Bulletin() {}
}

