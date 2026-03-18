package com.ew.system.api.dto;

public class LoginResponse {
    public String token;
    public String role;
    public String displayName;

    public LoginResponse() {}

    public LoginResponse(String token, String role, String displayName) {
        this.token = token;
        this.role = role;
        this.displayName = displayName;
    }
}

