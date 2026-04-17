package com.grim.backend.service;

import com.grim.backend.dto.AnalysisResponseDto;
import com.grim.backend.exception.ContractNotFoundException;
import com.grim.backend.model.AnalysisResult;
import com.grim.backend.model.Contract;
import com.grim.backend.repository.AnalysisResultRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

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

        AnalysisResult result = aiIntegrationService.analyze(
                contractId,
                contract.getFileName(),
                contract.getChunks()
        );

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

    public List<Map<String, Object>> search(String contractId, String query, int topK) {
        return aiIntegrationService.semanticSearch(contractId, query, topK);
    }

    // ── Dashboard stats ──────────────────────────────────────

    public long countHighRisk() {
        return analysisResultRepository.findByRiskLevel(AnalysisResult.RiskLevel.HIGH).size();
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
                .analyzedAt(result.getAnalyzedAt())
                .aiServiceActive(aiActive)
                .build();
    }
}
