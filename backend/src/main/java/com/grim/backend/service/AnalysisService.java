package com.grim.backend.service;

import com.grim.backend.dto.AnalysisResponseDto;
import com.grim.backend.exception.ContractNotFoundException;
import com.grim.backend.model.AnalysisResult;
import com.grim.backend.model.Contract;
import com.grim.backend.model.ContractChunk;
import com.grim.backend.repository.AnalysisResultRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * Orchestrates the AI analysis pipeline for a contract.
 *
 * Flow:
 *   analyzeContract()
 *     -> AiIntegrationService.analyze()   (LLM summarize + risk)
 *     -> Save AnalysisResult to MongoDB
 *     -> ContractService.markCompleted()  (update Contract status)
 *     -> Return AnalysisResponseDto
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class AnalysisService {

    private final ContractService          contractService;
    private final AiIntegrationService     aiIntegrationService;
    private final AnalysisResultRepository analysisResultRepository;

    // ── Analyze ──────────────────────────────────────────────

    /**
     * Run full AI analysis on a previously uploaded contract.
     * Safe to call multiple times — overwrites any prior result.
     */
    public AnalysisResponseDto analyzeContract(String contractId) {
        Contract contract = contractService.getById(contractId);
        log.info("Starting analysis for contractId={}", contractId);

        if (contract.getChunks() == null || contract.getChunks().isEmpty()) {
            throw new IllegalStateException(
                    "Contract has no chunks. Upload may not have completed successfully.");
        }

        // Delete any existing analysis result before creating a fresh one
        analysisResultRepository.deleteByContractId(contractId);

        // Delegate to AI integration service
        contract.setStatus(Contract.ProcessingStatus.ANALYZING);
        contractService.save(contract);

        AnalysisResult result;
        try {
            result = aiIntegrationService.analyze(
                    contractId,
                    contract.getFileName(),
                    contract.getChunks()
            );
        } catch (Exception e) {
            log.error("AI Analysis explicitly failed for contract {}: {}", contractId, e.getMessage(), e);
            contractService.markFailed(contract, "Analysis failed: " + e.getMessage());
            throw e;
        }

        // Persist result
        result = analysisResultRepository.save(result);
        log.info("Analysis saved id={}, riskScore={}", result.getId(), result.getRiskScore());

        // Update contract status
        contractService.markCompleted(contractId, result.getId());

        return toDto(result, contract.getTotalChunks());
    }

    // ── Retrieval ────────────────────────────────────────────

    public AnalysisResponseDto getAnalysisForContract(String contractId) {
        AnalysisResult result = analysisResultRepository.findByContractId(contractId)
                .orElseThrow(() -> new ContractNotFoundException(
                        "No analysis found for contractId: " + contractId));
        Contract contract = contractService.getById(contractId);
        return toDto(result, contract.getTotalChunks());
    }

    public List<AnalysisResult> getAllResults() {
        return analysisResultRepository.findAllByOrderByAnalyzedAtDesc();
    }

    // ── Semantic Search ──────────────────────────────────────

    /**
     * AI-powered semantic search with automatic local fallback.
     *
     * Finds the top-K relevant chunks (via FAISS or local text matching),
     * then — if AI is available — synthesises a natural-language answer
     * from those chunks using the Python LLM service.
     *
     * Returns a map with:
     *   "query"   → the original query
     *   "answer"  → AI-synthesised answer (null if AI disabled)
     *   "results" → list of matching chunks as citations
     *   "count"   → number of results
     */
    public Map<String, Object> search(String contractId, String query, int topK) {
        // 1. Get relevant chunks (AI FAISS search or local fallback)
        List<Map<String, Object>> chunks;
        try {
            List<Map<String, Object>> aiResults = aiIntegrationService.semanticSearch(contractId, query, topK);
            if (aiResults != null && !aiResults.isEmpty()
                    && !isAiStubResult(aiResults)) {
                log.info("[search] AI returned {} results for query='{}'", aiResults.size(), query);
                chunks = aiResults;
            } else {
                log.info("[search] AI returned stub or empty results, falling back to local search");
                chunks = localTextSearch(contractId, query, topK);
            }
        } catch (Exception e) {
            log.warn("[search] AI search failed for query='{}': {}. Using local fallback.",
                    query, e.getMessage());
            chunks = localTextSearch(contractId, query, topK);
        }

        // 2. If we found chunks and AI is available, synthesise an answer
        String answer = null;
        if (!chunks.isEmpty()) {
            List<String> chunkTexts = chunks.stream()
                    .map(c -> (String) c.get("text"))
                    .toList();
            answer = aiIntegrationService.askQuestion(contractId, query, chunkTexts);
        }

        // 3. Build response map
        Map<String, Object> result = new HashMap<>();
        result.put("query", query);
        result.put("answer", answer);
        result.put("results", chunks);
        result.put("count", chunks.size());
        return result;
    }

    /**
     * Detect the single-result "AI service disabled" stub.
     */
    private boolean isAiStubResult(List<Map<String, Object>> results) {
        if (results.size() != 1) return false;
        Object text = results.get(0).get("text");
        return text != null && text.toString().contains("AI service is disabled");
    }

    /**
     * Simple term-matching search over contract chunks (or extracted text).
     * Works entirely offline — no Python service needed.
     */
    private List<Map<String, Object>> localTextSearch(String contractId, String query, int topK) {
        if (contractId == null) {
            log.info("[localSearch] contractId is null — cross-contract search not supported locally");
            return List.of();
        }

        Contract contract;
        try {
            contract = contractService.getById(contractId);
        } catch (Exception e) {
            log.warn("[localSearch] Contract not found: {}", contractId);
            return List.of();
        }

        // Gather searchable text segments: chunks first, then paragraphs from raw text
        List<ContractChunk> segments = new ArrayList<>();

        if (contract.getChunks() != null && !contract.getChunks().isEmpty()) {
            segments.addAll(contract.getChunks());
        } else if (contract.getExtractedText() != null && !contract.getExtractedText().isBlank()) {
            // No chunks — split extracted text into paragraphs as virtual segments
            String[] paragraphs = contract.getExtractedText().split("\\n\\n+");
            for (int i = 0; i < paragraphs.length; i++) {
                String p = paragraphs[i].trim();
                if (!p.isEmpty()) {
                    ContractChunk virtual = ContractChunk.builder()
                            .index(i).text(p).build();
                    segments.add(virtual);
                }
            }
            log.info("[localSearch] Created {} virtual segments from extracted text", segments.size());
        }

        if (segments.isEmpty()) {
            log.info("[localSearch] No text content found for contractId={}", contractId);
            return List.of();
        }

        // Tokenize query into significant terms (min 3 chars)
        String[] queryTerms = query.toLowerCase().split("\\s+");
        boolean hasLongTerms = false;
        for (String t : queryTerms) { if (t.length() >= 3) { hasLongTerms = true; break; } }

        // Score each segment by term frequency
        List<Map<String, Object>> scored = new ArrayList<>();
        for (ContractChunk seg : segments) {
            String segText = seg.getText();
            if (segText == null || segText.isBlank()) continue;

            String lower = segText.toLowerCase();
            int matchCount = 0;

            if (hasLongTerms) {
                // Count occurrences of each term (min 3 chars)
                for (String term : queryTerms) {
                    if (term.length() >= 3) {
                        int idx = 0;
                        int cnt = 0;
                        while ((idx = lower.indexOf(term, idx)) != -1) {
                            cnt++;
                            idx += term.length();
                        }
                        matchCount += cnt;
                    }
                }
            } else {
                // All terms are short (< 3 chars) — use the full query as a phrase
                int idx = 0;
                while ((idx = lower.indexOf(query.toLowerCase(), idx)) != -1) {
                    matchCount++;
                    idx += query.length();
                }
            }

            if (matchCount > 0) {
                double score = Math.min(1.0, (double) matchCount / (segText.length() / 100.0 + 1));
                Map<String, Object> item = new HashMap<>();
                item.put("chunkIndex", seg.getIndex());
                item.put("text", segText);
                item.put("score", score);
                scored.add(item);
            }
        }

        // Sort by score descending, limit to topK
        scored.sort((a, b) -> Double.compare(
                (Double) b.getOrDefault("score", 0.0),
                (Double) a.getOrDefault("score", 0.0)));

        List<Map<String, Object>> results = scored.stream().limit(topK).toList();
        log.info("[localSearch] Found {} results for query='{}'", results.size(), query);
        return results;
    }

    // ── Dashboard stats ──────────────────────────────────────

    public long countHighRisk() {
        return analysisResultRepository.countByRiskLevel(AnalysisResult.RiskLevel.HIGH);
    }

    // ── Mapper ───────────────────────────────────────────────

    private AnalysisResponseDto toDto(AnalysisResult result, int totalChunks) {
        // Determine whether a real AI response was returned
        // (stub summaries start with the warning emoji)
        boolean aiActive = result.getSummary() != null
                && !result.getSummary().startsWith("⚠");

        return AnalysisResponseDto.builder()
                .contractId(result.getContractId())
                .analysisId(result.getId())
                .fileName(result.getContractFileName())
                .totalChunks(totalChunks)
                .summary(result.getSummary())
                .riskScore(result.getRiskScore())
                .riskLevel(result.getRiskLevel())
                .riskReport(result.getRiskReport())
                .chunksUsed(result.getChunksUsed())
                .analyzedAt(result.getAnalyzedAt())
                .aiServiceActive(aiActive)
                .build();
    }
}
