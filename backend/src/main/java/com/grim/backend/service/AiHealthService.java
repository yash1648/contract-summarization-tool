package com.grim.backend.service;

import lombok.Getter;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import org.springframework.web.reactive.function.client.WebClient;

import jakarta.annotation.PostConstruct;
import java.time.Duration;
import java.time.LocalDateTime;

/**
 * Tracks the live health of the Python AI microservice.
 *
 * Calls GET /api/ai/health on startup and on every call to check().
 * Results are cached for up to 30 seconds so the dashboard doesn't
 * hammer the Python service on every page load.
 *
 * Fields exposed to Thymeleaf templates via DashboardController:
 *   aiStatus.up           → boolean
 *   aiStatus.ollamaReachable → boolean
 *   aiStatus.embeddingModel
 *   aiStatus.ollamaModel
 *   aiStatus.totalIndexes
 *   aiStatus.lastChecked
 *   aiStatus.errorMessage
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class AiHealthService {

    private final WebClient aiWebClient;

    @Value("${app.ai.service.enabled:true}")
    private boolean aiEnabled;

    @Value("${app.ai.service.health-timeout-seconds:5}")
    private int healthTimeoutSeconds;

    // Cache TTL: re-check at most every 30 seconds
    private static final long CACHE_TTL_SECONDS = 30;

    @Getter
    private AiStatus lastStatus = AiStatus.unknown();
    private LocalDateTime lastCheckedAt;

    /** Called once on startup to establish initial status. */
    @PostConstruct
    public void checkOnStartup() {
        if (!aiEnabled) {
            lastStatus = AiStatus.disabled();
            log.info("AI service disabled via app.ai.service.enabled=false");
            return;
        }
        lastStatus = fetchStatus();
        lastCheckedAt = LocalDateTime.now();
        if (lastStatus.isUp()) {
            log.info("AI service ONLINE  model={}  ollama={}  indexes={}",
                    lastStatus.getOllamaModel(),
                    lastStatus.isOllamaReachable(),
                    lastStatus.getTotalIndexes());
        } else {
            log.warn("AI service OFFLINE on startup: {}", lastStatus.getErrorMessage());
        }
    }

    /**
     * Return current status, refreshing from the Python service
     * if the cache has expired (> CACHE_TTL_SECONDS old).
     */
    public AiStatus check() {
        if (!aiEnabled) return AiStatus.disabled();

        boolean cacheExpired = lastCheckedAt == null
                || Duration.between(lastCheckedAt, LocalDateTime.now()).getSeconds() > CACHE_TTL_SECONDS;

        if (cacheExpired) {
            lastStatus = fetchStatus();
            lastCheckedAt = LocalDateTime.now();
        }
        return lastStatus;
    }

    /** Always fetch fresh, bypassing the cache. Used on health endpoint. */
    public AiStatus checkNow() {
        if (!aiEnabled) return AiStatus.disabled();
        lastStatus = fetchStatus();
        lastCheckedAt = LocalDateTime.now();
        return lastStatus;
    }

    // ── Private ──────────────────────────────────────────────────────────────

    private AiStatus fetchStatus() {
        try {
            HealthResponse resp = aiWebClient.get()
                    .uri("/api/ai/health")
                    .retrieve()
                    .bodyToMono(HealthResponse.class)
                    .timeout(Duration.ofSeconds(healthTimeoutSeconds))
                    .block();

            if (resp == null) return AiStatus.error("Empty response from /api/ai/health");

            return AiStatus.builder()
                    .up(true)
                    .ollamaReachable(resp.ollamaReachable())
                    .embeddingModel(resp.embeddingModel())
                    .ollamaModel(resp.ollamaModel())
                    .totalIndexes(resp.totalIndexes())
                    .serviceStatus(resp.status())
                    .lastChecked(LocalDateTime.now())
                    .build();

        } catch (Exception e) {
            String msg = simplifyError(e);
            log.debug("AI health check failed: {}", msg);
            return AiStatus.error(msg);
        }
    }

    private String simplifyError(Exception e) {
        String msg = e.getMessage();
        if (msg == null) return "Unknown error";
        if (msg.contains("Connection refused"))
            return "Connection refused — is the Python AI service running on port 5000?";
        if (msg.contains("timeout") || msg.contains("Timeout"))
            return "Health check timed out — Python service may be loading the embedding model";
        return msg.length() > 120 ? msg.substring(0, 120) + "…" : msg;
    }

    // ── Inner types ──────────────────────────────────────────────────────────

    /** Response shape from GET /api/ai/health (Python side). */
    public record HealthResponse(
            String status,
            String embeddingModel,
            String ollamaModel,
            boolean ollamaReachable,
            int totalIndexes
    ) {}

    /** Status snapshot shown in the dashboard. */
    @Getter
    @lombok.Builder
    public static class AiStatus {
        private final boolean      up;
        private final boolean      ollamaReachable;
        private final String       embeddingModel;
        private final String       ollamaModel;
        private final int          totalIndexes;
        private final String       serviceStatus;   // "ok" | "degraded"
        private final LocalDateTime lastChecked;
        private final String       errorMessage;
        private final boolean      disabled;

        public static AiStatus unknown() {
            return AiStatus.builder().up(false).errorMessage("Not yet checked").build();
        }
        public static AiStatus disabled() {
            return AiStatus.builder().up(false).disabled(true)
                    .errorMessage("AI service disabled (app.ai.service.enabled=false)").build();
        }
        public static AiStatus error(String msg) {
            return AiStatus.builder().up(false).errorMessage(msg)
                    .lastChecked(LocalDateTime.now()).build();
        }

        /** True only if the service is up AND Ollama has the model loaded. */
        public boolean isFullyOperational() {
            return up && ollamaReachable;
        }
    }
}
