package com.ew.system;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.boot.context.properties.ConfigurationPropertiesScan;

@SpringBootApplication
@ConfigurationPropertiesScan
public class EwSystemApplication {
    public static void main(String[] args) {
        SpringApplication.run(EwSystemApplication.class, args);
    }
}

