package com.grim.backend.model;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;
import org.springframework.data.annotation.CreatedDate;
import org.springframework.data.annotation.Id;
import org.springframework.data.mongodb.core.index.Indexed;
import org.springframework.data.mongodb.core.mapping.Document;

import java.time.LocalDateTime;

/**
 * Stores the output of the AI analysis pipeline for a contract.
 *
 * MongoDB collection: "analysis_results"
 *
 * This is a separate document from Contract to:
 *   1. Keep the contracts collection lean
 *   2. Allow re-analysis without re-uploading
 *   3. Support multiple analysis runs on the same contract (future)
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
@Document(collection = "analysis_results")
public class AnalysisResult {

    @Id
    private String id;

    /** Reference back to the parent Contract */
    @Indexed
    private String contractId;

    /** Filename of the parent contract (denormalised for display convenience) */
    private String contractFileName;

    /**
     * AI-generated abstractive summary of the contract.
     *
     * TODO: Populated by AiIntegrationService when Python service is enabled.
     *       Until then, this is set to a placeholder message.
     */
    private String summary;

    /** Structured risk report (penalty, termination, liability flags) */
    private RiskReport riskReport;

    /**
     * Overall risk score from 0.0 (no risk) to 10.0 (extreme risk).
     * Computed by the Python AI service based on detected risk factors.
     *
     * TODO: Populated by AiIntegrationService.
     */
    private double riskScore;

    /** Human-readable risk level derived from riskScore */
    private RiskLevel riskLevel;

    /** Number of chunks that were retrieved for this analysis (RAG context) */
    private int chunksUsed;

    @CreatedDate
    private LocalDateTime analyzedAt;

    /** ── Nested enum ─────────────────────────────────────── */
    public enum RiskLevel {
        LOW,      // score 0.0 – 3.3
        MEDIUM,   // score 3.4 – 6.6
        HIGH      // score 6.7 – 10.0
    }

    /** Convenience factory — derives RiskLevel from a numeric score */
    public static RiskLevel levelFromScore(double score) {
        if (score <= 3.3) return RiskLevel.LOW;
        if (score <= 6.6) return RiskLevel.MEDIUM;
        return RiskLevel.HIGH;
    }
}
