package com.ew.system.storage;

import java.io.IOException;
import java.nio.file.Path;

import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.stereotype.Service;

import software.amazon.awssdk.auth.credentials.AwsBasicCredentials;
import software.amazon.awssdk.auth.credentials.StaticCredentialsProvider;
import software.amazon.awssdk.core.sync.RequestBody;
import software.amazon.awssdk.regions.Region;
import software.amazon.awssdk.services.s3.S3Client;
import software.amazon.awssdk.services.s3.model.GetObjectRequest;
import software.amazon.awssdk.services.s3.model.PutObjectRequest;
import software.amazon.awssdk.services.s3.model.S3Exception;
import software.amazon.awssdk.services.s3.model.HeadObjectRequest;
import software.amazon.awssdk.services.s3.presigner.S3Presigner;
import software.amazon.awssdk.services.s3.model.NoSuchKeyException;
import software.amazon.awssdk.services.s3.presigner.model.GetObjectPresignRequest;

@Service
@ConditionalOnProperty(name = "ew.storage.type", havingValue = "s3")
public class S3StorageService implements StorageService {

    private final StorageProperties properties;
    private final S3Client s3;
    private final S3Presigner presigner;

    public S3StorageService(StorageProperties properties) {
        this.properties = properties;

        StorageProperties.S3 p = properties.getS3();
        AwsBasicCredentials creds = AwsBasicCredentials.create(p.getAccessKey(), p.getSecretKey());
        StaticCredentialsProvider provider = StaticCredentialsProvider.create(creds);

        var s3Builder = S3Client.builder()
                .credentialsProvider(provider)
                .region(Region.of(p.getRegion() != null ? p.getRegion() : "us-east-1"));

        var presignerBuilder = S3Presigner.builder()
                .credentialsProvider(provider)
                .region(Region.of(p.getRegion() != null ? p.getRegion() : "us-east-1"));

        if (p.getEndpoint() != null && !p.getEndpoint().isBlank()) {
            // For MinIO / S3-compatible storage.
            s3Builder.endpointOverride(java.net.URI.create(p.getEndpoint()));
            presignerBuilder.endpointOverride(java.net.URI.create(p.getEndpoint()));
        }

        this.s3 = s3Builder.build();
        this.presigner = presignerBuilder.build();
    }

    @Override
    public String putFile(Path filePath, String key, String contentType) {
        StorageProperties.S3 p = properties.getS3();

        PutObjectRequest req = PutObjectRequest.builder()
                .bucket(p.getBucket())
                .key(key)
                .contentType(contentType)
                .build();

        s3.putObject(req, RequestBody.fromFile(filePath));
        return key;
    }

    @Override
    public String getDownloadUrl(String key, long expiresSeconds) {
        StorageProperties.S3 p = properties.getS3();

        GetObjectRequest getReq = GetObjectRequest.builder()
                .bucket(p.getBucket())
                .key(key)
                .build();

        GetObjectPresignRequest presignReq = GetObjectPresignRequest.builder()
                .signatureDuration(java.time.Duration.ofSeconds(expiresSeconds))
                .getObjectRequest(getReq)
                .build();

        return presigner.presignGetObject(presignReq).url().toString();
    }

    @Override
    public byte[] getBytes(String key) {
        StorageProperties.S3 p = properties.getS3();
        try (var in = s3.getObject(GetObjectRequest.builder()
                .bucket(p.getBucket())
                .key(key)
                .build())) {
            return in.readAllBytes();
        } catch (NoSuchKeyException e) {
            throw new RuntimeException("S3 object not found: " + key, e);
        } catch (IOException e) {
            throw new RuntimeException("Failed reading S3 object: " + key, e);
        } catch (S3Exception e) {
            throw new RuntimeException("S3 error reading object: " + key, e);
        }
    }

    @Override
    public void putBytes(String key, byte[] bytes, String contentType) {
        StorageProperties.S3 p = properties.getS3();
        PutObjectRequest req = PutObjectRequest.builder()
                .bucket(p.getBucket())
                .key(key)
                .contentType(contentType)
                .build();
        s3.putObject(req, RequestBody.fromBytes(bytes));
    }

    @Override
    public boolean exists(String key) {
        StorageProperties.S3 p = properties.getS3();
        try {
            s3.headObject(HeadObjectRequest.builder()
                    .bucket(p.getBucket())
                    .key(key)
                    .build());
            return true;
        } catch (S3Exception e) {
            // If the object doesn't exist, S3 typically returns 404 status code.
            if (e.statusCode() == 404) return false;
            throw e;
        }
    }
}

