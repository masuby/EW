# syntax=docker/dockerfile:1

## Build stage
FROM maven:3.9.6-eclipse-temurin-17 AS build
WORKDIR /app

COPY pom.xml .
COPY src ./src

RUN mvn -q -DskipTests package

## Runtime stage
FROM eclipse-temurin:17-jre-jammy

# Headless office for DOCX -> PDF conversion
RUN apt-get update && apt-get install -y --no-install-recommends \
    libreoffice-core \
    libreoffice-writer \
  && rm -rf /var/lib/apt/lists/*

WORKDIR /app
# Copy the repackaged Spring Boot executable jar (exclude original-* jars).
COPY --from=build /app/target/ew-system-backend-0.1.0.jar /app/ew-system-backend.jar

EXPOSE 8080
ENTRYPOINT ["java", "-jar", "/app/ew-system-backend.jar"]

