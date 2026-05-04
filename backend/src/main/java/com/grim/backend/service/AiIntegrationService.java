package com.grim.backend.service;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.grim.backend.model.AnalysisResult;
import com.grim.backend.model.ContractChunk;
import com.grim.backend.model.RiskReport;
import com.fasterxml.jackson.databind.JsonNode;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import org.springframework.web.reactive.function.client.WebClient;
import org.springframework.web.reactive.function.client.WebClientResponseException;
import reactor.core.publisher.Mono;

import java.time.Duration;
import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * Live bridge between Spring Boot and the Python AI microservice.
 *
 * All four endpoints the Python service exposes are called here:
 *   POST   /api/ai/embed
 *   POST   /api/ai/analyze
 *   POST   /api/ai/search
 *   DELETE /api/ai/contract/{id}
 *
 * Error handling strategy:
 *   - Network errors (connection refused, timeout) → throw AiServiceException
 *     so callers can decide to retry or fall back.
 *   - 4xx from Python → re-throw with the Python error body included.
 *   - 5xx from Python → throw AiServiceException (Python-side crash).
 *   - Retries: up to maxRetries attempts with retryDelayMs pause between them.
 *
 * When app.ai.service.enabled=false every method falls back to a stub so
 * the Spring Boot app still starts and serves pages without Python running.
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class AiIntegrationService {

    private final WebClient aiWebClient;

    @Value("${app.ai.service.enabled:true}")
    private boolean aiServiceEnabled;

    @Value("${app.ai.service.timeout-seconds:120}")
    private int timeoutSeconds;

    @Value("${app.ai.service.max-retries:2}")
    private int maxRetries;

    @Value("${app.ai.service.retry-delay-ms:1000}")
    private long retryDelayMs;

    // ══════════════════════════════════════════════════════════
    //  1. EMBED — POST /api/ai/embed
    // ══════════════════════════════════════════════════════════

    /**
     * Send contract chunks to Python for sentence-transformer embedding + FAISS storage.
     *
     * Python request:
     *   { "contractId": "...", "chunks": [{ "index": 0, "text": "..." }] }
     *
     * Python response:
     *   { "contractId": "...", "embeddingIds": ["uuid1", ...], "chunksEmbedded": 5 }
     *
     * @return map of chunkIndex → FAISS embeddingId (empty if AI disabled / error)
     */
    public Map<Integer, String> sendChunksForEmbedding(String contractId,
                                                       List<ContractChunk> chunks) {
        if (!aiServiceEnabled) {
            log.warn("[AI DISABLED] sendChunksForEmbedding skipped for contractId={}", contractId);
            return Map.of();
        }
        if (chunks == null || chunks.isEmpty()) return Map.of();

        log.info("[embed] Sending {} chunks → Python  contractId={}", chunks.size(), contractId);

        List<Map<String, Object>> chunkPayload = chunks.stream()
                .map(c -> Map.<String, Object>of("index", c.getIndex(), "text", c.getText()))
                .toList();

        Map<String, Object> body = Map.of("contractId", contractId, "chunks", chunkPayload);

        JsonNode response = callWithRetry("/api/ai/embed", body, "embed");

        Map<Integer, String> result = new HashMap<>();
        if (response != null && response.has("embeddingIds")) {
            JsonNode ids = response.get("embeddingIds");
            for (int i = 0; i < ids.size() && i < chunks.size(); i++) {
                result.put(chunks.get(i).getIndex(), ids.get(i).asText());
            }
        }
        log.info("[embed] Received {} embedding IDs for contractId={}", result.size(), contractId);
        return result;
    }

    // ══════════════════════════════════════════════════════════
    //  2. ANALYZE — POST /api/ai/analyze
    // ══════════════════════════════════════════════════════════

    /**
     * Run full RAG analysis: Python retrieves relevant chunks from FAISS,
     * runs two Ollama LLM passes (summary + risk), and returns structured results.
     *
     * Python request:
     *   { "contractId": "...", "chunkTexts": ["chunk1", "chunk2", ...] }
     *
     * Python response:
     *   { "summary": "...", "riskScore": 4.2,
     *     "penaltyClauses": [...], "terminationRisks": [...],
     *     "liabilityIssues": [...], "otherFlags": [...], "chunksUsed": 7 }
     *
     * @throws AiServiceException if the Python service is unreachable or returns an error
     */
    public AnalysisResult analyze(String contractId,
                                  String contractFileName,
                                  List<ContractChunk> chunks) {
        if (!aiServiceEnabled) {
            log.warn("[AI DISABLED] analyze() returning stub for contractId={}", contractId);
            return buildStubResult(contractId, contractFileName, chunks.size());
        }

        log.info("[analyze] Starting RAG analysis  contractId={}  chunks={}", contractId, chunks.size());

        List<String> chunkTexts = chunks.stream().map(ContractChunk::getText).toList();
        Map<String, Object> body = Map.of("contractId", contractId, "chunkTexts", chunkTexts);

        JsonNode response = callWithRetry("/api/ai/analyze", body, "analyze");

        AnalysisResult result = parseAnalysisResponse(contractId, contractFileName, response);
        log.info("[analyze] Done  contractId={}  riskScore={}  chunksUsed={}",
                contractId, result.getRiskScore(), result.getChunksUsed());
        return result;
    }

    // ══════════════════════════════════════════════════════════
    //  3. SEARCH — POST /api/ai/search
    // ══════════════════════════════════════════════════════════

    /**
     * Encode the user's query and search FAISS for semantically similar chunks.
     *
     * Python request:
     *   { "contractId": "...", "query": "...", "topK": 5 }
     *
     * Python response:
     *   { "results": [{ "chunkIndex": 2, "text": "...", "score": 0.91 }], "count": 1 }
     */
    public List<Map<String, Object>> semanticSearch(String contractId,
                                                    String query,
                                                    int topK) {
        if (!aiServiceEnabled) {
            log.warn("[AI DISABLED] semanticSearch skipped for query='{}'", query);
            return List.of(Map.of(
                    "chunkIndex", 0,
                    "text", "AI service is disabled. Set app.ai.service.enabled=true to activate.",
                    "score", 0.0
            ));
        }

        log.info("[search] query='{}' contractId={} topK={}", query, contractId, topK);

        Map<String, Object> body = new HashMap<>();
        if (contractId != null) body.put("contractId", contractId);
        body.put("query", query);
        body.put("topK", topK);

        JsonNode response = callWithRetry("/api/ai/search", body, "search");

        List<Map<String, Object>> results = new ArrayList<>();
        if (response != null && response.has("results")) {
            for (JsonNode node : response.get("results")) {
                Map<String, Object> item = new HashMap<>();
                item.put("chunkIndex", node.path("chunkIndex").asInt(0));
                item.put("text",       node.path("text").asText(""));
                item.put("score",      node.path("score").asDouble(0.0));
                if (node.has("contractId")) item.put("contractId", node.path("contractId").asText());
                results.add(item);
            }
        }
        log.info("[search] Returned {} results", results.size());
        return results;
    }

    // ══════════════════════════════════════════════════════════
    //  4. DELETE — DELETE /api/ai/contract/{id}
    // ══════════════════════════════════════════════════════════

    /**
     * Tell Python to remove all FAISS vectors for a contract.
     * Called by ContractService.deleteContract().
     * Non-fatal — a warning is logged if the call fails.
     */
    public void deleteContractVectors(String contractId) {
        if (!aiServiceEnabled) {
            log.warn("[AI DISABLED] deleteContractVectors skipped for contractId={}", contractId);
            return;
        }
        try {
            aiWebClient.delete()
                    .uri("/api/ai/contract/{id}", contractId)
                    .retrieve()
                    .toBodilessEntity()
                    .timeout(Duration.ofSeconds(10))
                    .block();
            log.info("[delete] FAISS vectors removed for contractId={}", contractId);
        } catch (Exception e) {
            log.warn("[delete] Could not remove vectors for contractId={}: {}",
                    contractId, simplifyError(e));
        }
    }

    // ══════════════════════════════════════════════════════════
    //  INTERNAL — retry loop + parsing helpers
    // ══════════════════════════════════════════════════════════

    /**
     * POST to the Python AI service with automatic retry on transient errors.
     * Throws {@link AiServiceException} after all retries are exhausted.
     */
    private JsonNode callWithRetry(String uri, Object body, String operation) {
        Exception lastException = null;

        for (int attempt = 1; attempt <= maxRetries + 1; attempt++) {
            try {
                String response = aiWebClient.post()
                        .uri(uri)
                        .bodyValue(body)
                        .retrieve()
                        .onStatus(
                                status -> status.is4xxClientError(),
                                resp -> resp.bodyToMono(String.class).flatMap(errBody ->
                                        Mono.error(new AiServiceException("[" + operation + "] Python returned "
                                                + resp.statusCode().value() + ": " + errBody)))
                        )
                        .onStatus(
                                status -> status.is5xxServerError(),
                                resp -> resp.bodyToMono(String.class).flatMap(errBody ->
                                        Mono.error(new AiServiceException("[" + operation + "] Python server error "
                                                + resp.statusCode().value() + ": " + errBody)))
                        )
                        .bodyToMono(String.class)
                        .timeout(Duration.ofSeconds(timeoutSeconds))
                        .block();

                // 🔥 ADD THIS (CRITICAL)
                log.info("[{}] RAW RESPONSE: {}", operation, response);

                // 🔥 Parse manually
                ObjectMapper mapper = new ObjectMapper();
                return mapper.readTree(response);

            } catch (Exception e) {
                lastException = e;
                String simplified = simplifyError(e);

                if (attempt <= maxRetries) {
                    log.warn("[{}] Attempt {}/{} failed: {}. Retrying...",
                            operation, attempt, maxRetries + 1, simplified);
                    try { Thread.sleep(retryDelayMs); } catch (InterruptedException ie) {
                        Thread.currentThread().interrupt();
                    }
                } else {
                    log.error("[{}] All attempts failed. Last error: {}", operation, simplified);
                }
            }
        }

        throw new AiServiceException(
                "[" + operation + "] Python AI service unreachable after "
                        + (maxRetries + 1) + " attempts. " + simplifyError(lastException),
                lastException);
    }

    private AnalysisResult parseAnalysisResponse(String contractId,
                                                 String contractFileName,
                                                 JsonNode resp) {
        if (resp == null)
            throw new AiServiceException("[analyze] Null response body from Python");

        double riskScore = Math.max(0.0, Math.min(10.0, resp.path("riskScore").asDouble(0.0)));

        RiskReport riskReport = RiskReport.builder()
                .penaltyClauses(jsonArrayToList(resp.path("penaltyClauses")))
                .terminationRisks(jsonArrayToList(resp.path("terminationRisks")))
                .liabilityIssues(jsonArrayToList(resp.path("liabilityIssues")))
                .otherFlags(jsonArrayToList(resp.path("otherFlags")))
                .build();

        return AnalysisResult.builder()
                .contractId(contractId)
                .contractFileName(contractFileName)
                .summary(resp.path("summary").asText("No summary returned."))
                .riskScore(riskScore)
                .riskLevel(AnalysisResult.levelFromScore(riskScore))
                .riskReport(riskReport)
                .chunksUsed(resp.path("chunksUsed").asInt(0))
                .analyzedAt(LocalDateTime.now())
                .build();
    }

    private AnalysisResult buildStubResult(String contractId,
                                           String contractFileName,
                                           int chunkCount) {
        return AnalysisResult.builder()
                .contractId(contractId)
                .contractFileName(contractFileName)
                .summary("⚠ AI Service Disabled\n\n"
                        + "Document uploaded and split into " + chunkCount + " chunks.\n"
                        + "Set app.ai.service.enabled=true and start the Python AI service "
                        + "on port 5000 to activate analysis.")
                .riskScore(0.0)
                .riskLevel(AnalysisResult.RiskLevel.LOW)
                .riskReport(RiskReport.builder().build())
                .chunksUsed(0)
                .analyzedAt(LocalDateTime.now())
                .build();
    }

    private List<String> jsonArrayToList(JsonNode node) {
        List<String> list = new ArrayList<>();
        if (node != null && node.isArray()) {
            for (JsonNode item : node) { if (!item.asText().isBlank()) list.add(item.asText()); }
        }
        return list;
    }

    private String simplifyError(Exception e) {
        if (e == null) return "null";
        String msg = e.getMessage();
        if (msg == null) return e.getClass().getSimpleName();
        if (msg.contains("Connection refused"))
            return "Connection refused — is the Python AI service running on port 5000?";
        if (msg.contains("timeout") || msg.contains("Timeout"))
            return "Request timed out — Ollama LLM may be loading a model";
        return msg.length() > 200 ? msg.substring(0, 200) + "…" : msg;
    }

    // ── Custom exception ─────────────────────────────────────────────────────

    public static class AiServiceException extends RuntimeException {
        public AiServiceException(String message) { super(message); }
        public AiServiceException(String message, Throwable cause) { super(message, cause); }
    }
}
