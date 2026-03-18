package com.ew.system.api;

import java.util.Map;

import org.springframework.http.ResponseEntity;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class MeController {

    @GetMapping("/api/auth/me")
    public ResponseEntity<Map<String, Object>> me() {
        Authentication auth = SecurityContextHolder.getContext().getAuthentication();
        if (auth == null || auth.getPrincipal() == null) {
            return ResponseEntity.status(401).body(Map.of("error", "unauthorized"));
        }

        String username = auth.getName();
        String displayName = null;
        Object details = auth.getDetails();
        if (details instanceof Map<?, ?> map) {
            Object dn = map.get("displayName");
            if (dn instanceof String s) {
                displayName = s;
            }
        }

        String role = null;
        for (var ga : auth.getAuthorities()) {
            String a = ga.getAuthority();
            if (a != null && a.startsWith("ROLE_")) {
                role = a.substring("ROLE_".length()).toLowerCase();
                break;
            }
        }

        return ResponseEntity.ok(Map.of(
                "username", username,
                "role", role,
                "displayName", displayName
        ));
    }
}

