package com.ew.system.security;

import java.time.Instant;
import java.time.temporal.ChronoUnit;
import java.util.Date;
import java.util.Map;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import io.jsonwebtoken.Jwts;
import io.jsonwebtoken.SignatureAlgorithm;

@Service
public class JwtService {
    @Value("${security.jwt.secret:dev-only-secret-change-me}")
    private String secret;

    @Value("${security.jwt.issuer:ew-system}")
    private String issuer;

    public String createToken(String username, Map<String, String> claims, String role) {
        Instant now = Instant.now();
        Instant exp = now.plus(8, ChronoUnit.HOURS);
        return Jwts.builder()
                .setIssuer(issuer)
                .setSubject(username)
                .setClaims(claims)
                .claim("role", role)
                .setIssuedAt(Date.from(now))
                .setExpiration(Date.from(exp))
                .signWith(io.jsonwebtoken.security.Keys.hmacShaKeyFor(secret.getBytes()), SignatureAlgorithm.HS256)
                .compact();
    }
}

