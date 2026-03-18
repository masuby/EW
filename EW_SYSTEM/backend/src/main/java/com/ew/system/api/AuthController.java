package com.ew.system.api;

import java.util.HashMap;
import java.util.Map;

import com.ew.system.security.JwtService;
import com.ew.system.security.SecurityUsersProperties;

import jakarta.validation.Valid;

import org.springframework.security.authentication.AuthenticationManager;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.userdetails.UserDetails;
import org.springframework.security.core.userdetails.UserDetailsService;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RestController;

import com.ew.system.api.dto.LoginRequest;
import com.ew.system.api.dto.LoginResponse;

import org.springframework.security.core.GrantedAuthority;

@RestController
public class AuthController {
    private final AuthenticationManager authenticationManager;
    private final JwtService jwtService;
    private final UserDetailsService userDetailsService;
    private final SecurityUsersProperties users;

    public AuthController(AuthenticationManager authenticationManager,
                           JwtService jwtService,
                           UserDetailsService userDetailsService,
                           SecurityUsersProperties users) {
        this.authenticationManager = authenticationManager;
        this.jwtService = jwtService;
        this.userDetailsService = userDetailsService;
        this.users = users;
    }

    @PostMapping("/api/auth/login")
    public LoginResponse login(@Valid @RequestBody LoginRequest request) {
        Authentication auth = authenticationManager.authenticate(
                new UsernamePasswordAuthenticationToken(request.username, request.password)
        );

        UserDetails user = (UserDetails) auth.getPrincipal();

        String role = "USER";
        for (GrantedAuthority a : user.getAuthorities()) {
            String authName = a.getAuthority();
            if (authName != null && authName.startsWith("ROLE_")) {
                role = authName.substring("ROLE_".length());
            }
        }

        // Attach extra claims for the frontend (role + displayName).
        String displayName = request.username;
        for (var u : users.getList()) {
            if (u.getUsername() != null && u.getUsername().equals(request.username)) {
                if (u.getDisplayName() != null) displayName = u.getDisplayName();
            }
        }

        Map<String, String> claims = new HashMap<>();
        claims.put("displayName", displayName);

        String token = jwtService.createToken(request.username, Map.of("displayName", displayName), role);
        return new LoginResponse(token, role.toLowerCase(), displayName);
    }
}

