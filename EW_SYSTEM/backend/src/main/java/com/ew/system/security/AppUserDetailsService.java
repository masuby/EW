package com.ew.system.security;

import java.util.List;

import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.security.core.userdetails.User;
import org.springframework.security.core.userdetails.UserDetails;
import org.springframework.security.core.userdetails.UserDetailsService;
import org.springframework.security.core.userdetails.UsernameNotFoundException;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;

@Service
@EnableConfigurationProperties(SecurityUsersProperties.class)
public class AppUserDetailsService implements UserDetailsService {

    private final SecurityUsersProperties users;
    private final PasswordEncoder passwordEncoder;

    private final String devUsername = "admin";
    private final String devRole = "admin";
    private final String devPassword;

    public AppUserDetailsService(SecurityUsersProperties users,
                                  PasswordEncoder passwordEncoder) {
        this.users = users;
        this.passwordEncoder = passwordEncoder;
        this.devPassword = System.getenv().getOrDefault("EW_DEV_ADMIN_PASSWORD", "Admin123");
    }

    @Override
    public UserDetails loadUserByUsername(String username) throws UsernameNotFoundException {
        // Bootstrap a dev admin account if no configured users exist yet.
        if (users.getList() == null || users.getList().isEmpty()) {
            if (devUsername.equals(username)) {
                return User.withUsername(devUsername)
                        .password(passwordEncoder.encode(devPassword))
                        .authorities(List.of(new SimpleGrantedAuthority("ROLE_" + devRole.toUpperCase())))
                        .build();
            }
            throw new UsernameNotFoundException("user_not_found");
        }

        SecurityUsersProperties.UserEntry match = null;
        for (SecurityUsersProperties.UserEntry u : users.getList()) {
            if (u.getUsername() != null && u.getUsername().equals(username)) {
                match = u;
                break;
            }
        }
        if (match == null) {
            throw new UsernameNotFoundException("user_not_found");
        }

        String role = match.getRole() == null ? "user" : match.getRole();
        // Spring Security expects ROLE_* naming for hasRole checks
        String authority = "ROLE_" + role.toUpperCase();

        // passwordHash is already a bcrypt hash (like streamlit-authenticator uses).
        // If you store non-bcrypt hashes later, update this logic accordingly.
        return User.withUsername(match.getUsername())
                .password(match.getPasswordHash())
                .authorities(List.of(new SimpleGrantedAuthority(authority)))
                .build();
    }
}

