package com.ew.system.api.dto;

import com.fasterxml.jackson.databind.JsonNode;

/**
 * DTO intentionally uses JsonNode so we can accept the same schema
 * produced by the existing Streamlit UI (validated in Python today).
 *
 * In the next iteration, port validation into explicit Java DTOs.
 */
public class GenerateTma722e4Request {
    public JsonNode payload;
}

