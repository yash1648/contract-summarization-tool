package com.grim.backend.config;

import jakarta.annotation.PostConstruct;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.web.reactive.function.client.WebClient;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;

/**
 * Application-level beans:
 *   - WebClient for calling the Python AI microservice
 *   - Upload directory initialisation
 */
@Configuration
public class AppConfig {

    @Value("${app.ai.service.url}")
    private String aiServiceUrl;

    @Value("${app.upload.dir}")
    private String uploadDir;

    /**
     * Reactive WebClient pre-configured with the Python AI service base URL.
     * Used by AiIntegrationService to POST contract chunks and receive results.
     *
     * TODO: When the Python service is ready, ensure app.ai.service.url is
     *       set correctly in application.properties and flip
     *       app.ai.service.enabled=true.
     */
    @Bean
    public WebClient aiWebClient() {
        return WebClient.builder()
                .baseUrl(aiServiceUrl)
                .defaultHeader("Content-Type", "application/json")
                .codecs(configurer ->
                        configurer.defaultCodecs().maxInMemorySize(10 * 1024 * 1024)) // 10 MB
                .build();
    }

    /**
     * Ensure the upload directory exists on application startup.
     * Creates the directory (and any missing parents) if it doesn't exist.
     */
    @PostConstruct
    public void initUploadDirectory() throws IOException {
        Path uploadPath = Paths.get(uploadDir).toAbsolutePath();
        if (!Files.exists(uploadPath)) {
            Files.createDirectories(uploadPath);
        }
    }
}
