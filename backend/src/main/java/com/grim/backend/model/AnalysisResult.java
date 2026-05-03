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
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
@Document(collection = "analysis_results")
public class AnalysisResult {

    @Id
    private String id;

    /**
     * Reference back to the parent Contract
     */
    @Indexed
    private String contractId;

    /**
     * Optional: differentiate multiple analysis runs
     */
    private String analysisRunId;

    /**
     * Filename of the parent contract
     */
    private String contractFileName;

    /**
     * AI-generated summary
     */
    private String summary;

    /**
     * Optional deterministic summary (recommended)
     */
    private String templateSummary;

    /**
     * Structured risk report
     */
    private RiskReport riskReport;

/**
 * Score: 0.0 → 10.0
 */
private double riskScore;

/**
 * Human-readable risk level (derived from riskScore)
 */
private RiskLevel riskLevel;

/**
 * Number of retrieved RAG chunks
 */
private int chunksUsed;

    /**
     * Structured extracted data
     */
    @Builder.Default
    private ExtractedData extractedData = new ExtractedData();

    @CreatedDate
    @Indexed
    private LocalDateTime analyzedAt;

    /**
     * ── Risk Level Enum ─────────────────────────────
     */
    public enum RiskLevel {
        LOW,
        MEDIUM,
        HIGH
    }

/**
 * Derived risk level - returns stored value if set, otherwise computes from score
 */
public RiskLevel getRiskLevel() {
    if (this.riskLevel != null) {
        return this.riskLevel;
    }
    return levelFromScore(this.riskScore);
}

    /**
     * Static mapper
     */
    public static RiskLevel levelFromScore(double score) {
        if (score <= 3.3) return RiskLevel.LOW;
        if (score <= 6.6) return RiskLevel.MEDIUM;
        return RiskLevel.HIGH;
    }

    /**
     * Clamp risk score between 0 and 10
     */
    public void setRiskScore(double riskScore) {
        this.riskScore = Math.max(0, Math.min(10, riskScore));
    }

    /**
     * Deterministic summary (no hallucination)
     */
    public String generateTemplateSummary() {

        ExtractedData data = this.extractedData;

        if (data == null || data.isEmpty()) {
            return "No structured data could be extracted from this contract.";
        }

        StringBuilder sb = new StringBuilder();

        if (!data.getParties().isEmpty()) {
            sb.append("PARTIES:\n");
            data.getParties().forEach(p -> sb.append("  • ").append(p).append("\n"));
            sb.append("\n");
        }

        if (!data.getObligations().isEmpty()) {
            sb.append("KEY OBLIGATIONS:\n");
            data.getObligations().forEach(o -> sb.append("  • ").append(o).append("\n"));
            sb.append("\n");
        }

        if (!data.getPaymentTerms().isEmpty()) {
            sb.append("PAYMENT TERMS:\n");
            data.getPaymentTerms().forEach(p -> sb.append("  • ").append(p).append("\n"));
            sb.append("\n");
        }

        if (!data.getDates().isEmpty()) {
            sb.append("KEY DATES:\n");
            data.getDates().forEach(d -> sb.append("  • ").append(d).append("\n"));
            sb.append("\n");
        }

        if (!data.getPenalties().isEmpty()) {
            sb.append("PENALTIES:\n");
            data.getPenalties().forEach(p -> sb.append("  • ").append(p).append("\n"));
            sb.append("\n");
        }

        if (!data.getTermination().isEmpty()) {
            sb.append("TERMINATION CONDITIONS:\n");
            data.getTermination().forEach(t -> sb.append("  • ").append(t).append("\n"));
        }

        return sb.toString().trim();
    }
}