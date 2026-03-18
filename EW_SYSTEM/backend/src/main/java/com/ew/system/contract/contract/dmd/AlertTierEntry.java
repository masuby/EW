package com.ew.system.contract.dmd;

import java.util.ArrayList;
import java.util.List;

import com.ew.system.contract.common.AlertLevel;
import com.fasterxml.jackson.annotation.JsonInclude;

@JsonInclude(JsonInclude.Include.NON_NULL)
public class AlertTierEntry {
    public AlertLevel alert_level;
    public String text;
    public List<String> recommendations = new ArrayList<>();
}

