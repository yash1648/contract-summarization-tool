package com.grim.backend.service;

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

import java.time.Duration;
import java.time.LocalDateTime;
import java.util.List;
import java.util.Map;

/**
 * ============================================================
 *  AI INTEGRATION SERVICE
 *  Spring Boot ↔ Python AI Microservice
 * ============================================================
 *
 *  This service is the bridge between the Spring Boot backend
 *  and the Python AI service (FastAPI + FAISS + LLM).
 *
 *  Current state:
 *    app.ai.service.enabled=false  →  all methods return STUB data
 *    app.ai.service.enabled=true   →  live HTTP calls to Python
 *
 * ──────────────────────────────────────────────────────────────
 *  TODO — Python AI Service Endpoints (implement on Python side):
 *
 *  POST /api/ai/embed
 *    Request : { "contractId": "...", "chunks": [{ "index": 0, "text": "..." }, ...] }
 *    Response: { "embeddingIds": ["uuid1", "uuid2", ...] }
 *    Action  : Generates sentence-transformer embeddings, stores them in FAISS,
 *              returns one UUID per chunk.
 *
 *  POST /api/ai/analyze
 *    Request : { "contractId": "...", "chunkTexts": ["..."] }
 *    Response: { "summary": "...", "riskScore": 4.2,
 *                "penaltyClauses": [...], "terminationRisks": [...],
 *                "liabilityIssues": [...], "otherFlags": [...],
 *                "chunksUsed": 7 }
 *    Action  : Runs RAG retrieval + LLM summarization + risk analysis.
 *
 *  POST /api/ai/search
 *    Request : { "contractId": "...", "query": "...", "topK": 5 }
 *    Response: { "results": [{ "chunkIndex": 2, "text": "...", "score": 0.91 }, ...] }
 *    Action  : Embeds the query, queries FAISS for top-k chunks.
 *
 *  DELETE /api/ai/contract/{contractId}
 *    Response: { "deleted": true }
 *    Action  : Removes all FAISS vectors for a contract.
 * ──────────────────────────────────────────────────────────────
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class AiIntegrationService {

    private final WebClient aiWebClient;

    @Value("${app.ai.service.enabled:false}")
    private boolean aiServiceEnabled;

    @Value("${app.ai.service.timeout-seconds:30}")
    private int timeoutSeconds;

    // ══════════════════════════════════════════════════════════
    //  1. SEND CHUNKS FOR EMBEDDING
    // ══════════════════════════════════════════════════════════

    /**
     * Send contract chunks to the Python service for embedding generation.
     * Returns a map of chunkIndex → FAISS embeddingId.
     *
     * When AI service is disabled: returns empty map (stubs remain unembedded).
     *
     * @param contractId the contract's MongoDB ID
     * @param chunks     the list of chunks to embed
     * @return map from chunk index to embeddingId assigned by Python service
     */
    public Map<Integer, String> sendChunksForEmbedding(String contractId,
                                                        List<ContractChunk> chunks) {
        if (!aiServiceEnabled) {
            log.warn("TODO [AI SERVICE DISABLED] — sendChunksForEmbedding skipped for contractId={}. "
                    + "Enable app.ai.service.enabled=true once Python service is running.", contractId);
            return Map.of();
        }

        log.info("Sending {} chunks for embedding — contractId={}", chunks.size(), contractId);

        try {
            // Build request body
            List<Map<String, Object>> chunkPayload = chunks.stream()
                    .map(c -> Map.<String, Object>of("index", c.getIndex(), "text", c.getText()))
                    .toList();

            Map<String, Object> requestBody = Map.of(
                    "contractId", contractId,
                    "chunks", chunkPayload
            );

            // Call Python service
            JsonNode response = aiWebClient.post()
                    .uri("/api/ai/embed")
                    .bodyValue(requestBody)
                    .retrieve()
                    .bodyToMono(JsonNode.class)
                    .timeout(Duration.ofSeconds(timeoutSeconds))
                    .block();

            // Parse embeddingIds array from response
            java.util.HashMap<Integer, String> result = new java.util.HashMap<>();
            if (response != null && response.has("embeddingIds")) {
                JsonNode ids = response.get("embeddingIds");
                for (int i = 0; i < ids.size() && i < chunks.size(); i++) {
                    result.put(chunks.get(i).getIndex(), ids.get(i).asText());
                }
            }
            log.info("Embedding complete: {} embedding IDs received", result.size());
            return result;

        } catch (WebClientResponseException e) {
            log.error("AI service returned error {} for embedding request: {}",
                    e.getStatusCode(), e.getResponseBodyAsString());
            throw new RuntimeException("AI service embedding failed: " + e.getMessage(), e);
        }
    }

    // ══════════════════════════════════════════════════════════
    //  2. RUN FULL ANALYSIS (SUMMARIZATION + RISK)
    // ══════════════════════════════════════════════════════════

    /**
     * Request a full RAG-based analysis from the Python service.
     * Returns a populated AnalysisResult.
     *
     * When AI service is disabled: returns a stub AnalysisResult
     * with placeholder text and a note in the summary field.
     *
     * @param contractId the contract's MongoDB ID
     * @param contractFileName the original filename (for display)
     * @param chunks     all chunks for this contract
     * @return AnalysisResult ready to be saved to MongoDB
     */
    public AnalysisResult analyze(String contractId,
                                   String contractFileName,
                                   List<ContractChunk> chunks) {
        if (!aiServiceEnabled) {
            log.warn("TODO [AI SERVICE DISABLED] — analyze() returning STUB result for contractId={}. "
                    + "Connect Python AI service and set app.ai.service.enabled=true.", contractId);
            return buildStubResult(contractId, contractFileName, chunks.size());
        }

        log.info("Requesting AI analysis — contractId={}, chunks={}", contractId, chunks.size());

        try {
            List<String> chunkTexts = chunks.stream()
                    .map(ContractChunk::getText)
                    .toList();

            Map<String, Object> requestBody = Map.of(
                    "contractId", contractId,
                    "chunkTexts", chunkTexts
            );

            JsonNode response = aiWebClient.post()
                    .uri("/api/ai/analyze")
                    .bodyValue(requestBody)
                    .retrieve()
                    .bodyToMono(JsonNode.class)
                    .timeout(Duration.ofSeconds(timeoutSeconds))
                    .block();

            return parseAnalysisResponse(contractId, contractFileName, response);

        } catch (WebClientResponseException e) {
            log.error("AI service returned error {} for analyze request: {}",
                    e.getStatusCode(), e.getResponseBodyAsString());
            throw new RuntimeException("AI analysis failed: " + e.getMessage(), e);
        }
    }

    // ══════════════════════════════════════════════════════════
    //  3. SEMANTIC SEARCH
    // ══════════════════════════════════════════════════════════

    /**
     * Query the Python AI service for semantically similar chunks.
     *
     * When AI service is disabled: returns a list with a single
     * "service unavailable" message so the UI degrades gracefully.
     *
     * @param contractId (optional) restrict search to one contract
     * @param query      natural language search string
     * @param topK       number of results to return
     * @return list of matching chunk texts with similarity scores
     */
    public List<Map<String, Object>> semanticSearch(String contractId,
                                                     String query,
                                                     int topK) {
        if (!aiServiceEnabled) {
            log.warn("TODO [AI SERVICE DISABLED] — semanticSearch() returning empty for query='{}'", query);
            return List.of(Map.of(
                    "chunkIndex", 0,
                    "text", "⚠ AI service is not yet connected. "
                            + "Enable app.ai.service.enabled=true to activate semantic search.",
                    "score", 0.0
            ));
        }

        try {
            Map<String, Object> requestBody = new java.util.HashMap<>();
            if (contractId != null) requestBody.put("contractId", contractId);
            requestBody.put("query", query);
            requestBody.put("topK", topK);

            JsonNode response = aiWebClient.post()
                    .uri("/api/ai/search")
                    .bodyValue(requestBody)
                    .retrieve()
                    .bodyToMono(JsonNode.class)
                    .timeout(Duration.ofSeconds(timeoutSeconds))
                    .block();

            List<Map<String, Object>> results = new java.util.ArrayList<>();
            if (response != null && response.has("results")) {
                for (JsonNode node : response.get("results")) {
                    results.add(Map.of(
                            "chunkIndex", node.get("chunkIndex").asInt(),
                            "text",       node.get("text").asText(),
                            "score",      node.get("score").asDouble()
                    ));
                }
            }
            return results;

        } catch (WebClientResponseException e) {
            log.error("AI service search error: {}", e.getMessage());
            throw new RuntimeException("Semantic search failed: " + e.getMessage(), e);
        }
    }

    // ══════════════════════════════════════════════════════════
    //  4. DELETE CONTRACT VECTORS
    // ══════════════════════════════════════════════════════════

    /**
     * Tell the Python service to remove all FAISS vectors for a contract.
     * Called when a contract is deleted from MongoDB.
     *
     * TODO: call this from ContractService.deleteContract()
     */
    public void deleteContractVectors(String contractId) {
        if (!aiServiceEnabled) {
            log.warn("TODO [AI SERVICE DISABLED] — deleteContractVectors() skipped for contractId={}", contractId);
            return;
        }
        try {
            aiWebClient.delete()
                    .uri("/api/ai/contract/{id}", contractId)
                    .retrieve()
                    .toBodilessEntity()
                    .timeout(Duration.ofSeconds(10))
                    .block();
            log.info("FAISS vectors deleted for contractId={}", contractId);
        } catch (WebClientResponseException e) {
            log.warn("Could not delete vectors for contractId={}: {}", contractId, e.getMessage());
        }
    }

    // ── Private helpers ─────────────────────────────────────────────────

    /**
     * Parse the JSON response from POST /api/ai/analyze into an AnalysisResult.
     */
    private AnalysisResult parseAnalysisResponse(String contractId,
                                                   String contractFileName,
                                                   JsonNode response) {
        if (response == null) {
            throw new RuntimeException("Null response from AI analysis endpoint");
        }

        double riskScore = response.path("riskScore").asDouble(0.0);

        RiskReport riskReport = RiskReport.builder()
                .penaltyClauses(jsonArrayToList(response.path("penaltyClauses")))
                .terminationRisks(jsonArrayToList(response.path("terminationRisks")))
                .liabilityIssues(jsonArrayToList(response.path("liabilityIssues")))
                .otherFlags(jsonArrayToList(response.path("otherFlags")))
                .build();

        return AnalysisResult.builder()
                .contractId(contractId)
                .contractFileName(contractFileName)
                .summary(response.path("summary").asText("No summary available."))
                .riskScore(riskScore)
                .riskLevel(AnalysisResult.levelFromScore(riskScore))
                .riskReport(riskReport)
                .chunksUsed(response.path("chunksUsed").asInt(0))
                .analyzedAt(LocalDateTime.now())
                .build();
    }

    /**
     * Build a stub AnalysisResult used when the AI service is disabled.
     * The summary field clearly communicates the TODO status to the UI.
     */
    private AnalysisResult buildStubResult(String contractId,
                                            String contractFileName,
                                            int chunkCount) {
        return AnalysisResult.builder()
                .contractId(contractId)
                .contractFileName(contractFileName)
                .summary("⚠ AI Service Not Connected\n\n"
                        + "The document was successfully uploaded, extracted into "
                        + chunkCount + " chunks, and is ready for analysis.\n\n"
                        + "To activate AI summarization and risk detection:\n"
                        + "1. Start the Python AI service (FastAPI on port 5000)\n"
                        + "2. Set app.ai.service.enabled=true in application.properties\n"
                        + "3. Re-trigger analysis via the 'Analyze' button\n\n"
                        + "TODO: Python AI service — POST /api/ai/analyze")
                .riskScore(0.0)
                .riskLevel(AnalysisResult.RiskLevel.LOW)
                .riskReport(RiskReport.builder().build())
                .chunksUsed(0)
                .analyzedAt(LocalDateTime.now())
                .build();
    }

    /** Convert a JsonNode array to a Java List<String> */
    private List<String> jsonArrayToList(JsonNode arrayNode) {
        List<String> list = new java.util.ArrayList<>();
        if (arrayNode != null && arrayNode.isArray()) {
            for (JsonNode item : arrayNode) {
                list.add(item.asText());
            }
        }
        return list;
    }
}
