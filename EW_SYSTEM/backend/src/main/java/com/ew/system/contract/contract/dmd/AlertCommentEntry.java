package com.ew.system.contract.dmd;

import com.ew.system.contract.common.AlertLevel;
import com.ew.system.contract.common.RatingPair;

import com.fasterxml.jackson.annotation.JsonInclude;

@JsonInclude(JsonInclude.Include.NON_NULL)
public class AlertCommentEntry {
    public AlertLevel alert_level;
    public String description;
    public RatingPair rating;
}

