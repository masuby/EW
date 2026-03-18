package com.ew.system.security;

import java.util.ArrayList;
import java.util.List;

import org.springframework.boot.context.properties.ConfigurationProperties;

@ConfigurationProperties(prefix = "security.users")
public class SecurityUsersProperties {
    private List<UserEntry> list = new ArrayList<>();

    public List<UserEntry> getList() {
        return list;
    }

    public void setList(List<UserEntry> list) {
        this.list = list;
    }

    public static class UserEntry {
        private String username;
        private String passwordHash;
        private String role;
        private String displayName;

        public String getUsername() {
            return username;
        }

        public void setUsername(String username) {
            this.username = username;
        }

        public String getPasswordHash() {
            return passwordHash;
        }

        public void setPasswordHash(String passwordHash) {
            this.passwordHash = passwordHash;
        }

        public String getRole() {
            return role;
        }

        public void setRole(String role) {
            this.role = role;
        }

        public String getDisplayName() {
            return displayName;
        }

        public void setDisplayName(String displayName) {
            this.displayName = displayName;
        }
    }
}

