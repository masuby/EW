package com.ew.system.contract.dmd;

import java.util.ArrayList;
import java.util.List;

import com.ew.system.contract.common.RatingPair;

public class DmdComment {
    public String header_text;
    public List<String> impact_bullets = new ArrayList<>();
    public RatingPair rating;
}

