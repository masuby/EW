package com.ew.system.api;

import com.ew.system.api.dto.SpatialIntersectionRequest;
import com.ew.system.api.dto.SpatialIntersectionResponse;

import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.security.access.prepost.PreAuthorize;

import com.ew.system.spatial.SpatialIntersectionService;

@RestController
@RequestMapping("/api/maps")
public class SpatialController {

    private final SpatialIntersectionService intersectionService;

    public SpatialController(SpatialIntersectionService intersectionService) {
        this.intersectionService = intersectionService;
    }

    @PostMapping("/intersections")
    @PreAuthorize("isAuthenticated()")
    public SpatialIntersectionResponse intersect(@RequestBody SpatialIntersectionRequest req) {
        SpatialIntersectionResponse resp = new SpatialIntersectionResponse();
        resp.selected = intersectionService.intersect(req.level, req.geometry);
        return resp;
    }
}

