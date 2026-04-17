package com.grim.backend.model;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.util.ArrayList;
import java.util.List;

/**
 * Detailed breakdown of risk findings within a contract.
 *
 * Embedded inside AnalysisResult (not a separate collection).
 *
 * Each list holds the verbatim clause text (or a short excerpt)
 * identified by the Python AI service as a risk of that type.
 *
 * TODO: All lists are populated by AiIntegrationService when the
 *       Python service is enabled. Until then, they remain empty
 *       and the UI displays a "pending" state.
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class RiskReport {

    /**
     * Penalty clauses — financial penalties for breach of contract,
     * late delivery, SLA violations, etc.
     */
    @Builder.Default
    private List<String> penaltyClauses = new ArrayList<>();

    /**
     * Termination risks — one-sided termination rights, automatic
     * renewal traps, short notice periods.
     */
    @Builder.Default
    private List<String> terminationRisks = new ArrayList<>();

    /**
     * Liability issues — unlimited liability, exclusion of consequential
     * damages, indemnification obligations.
     */
    @Builder.Default
    private List<String> liabilityIssues = new ArrayList<>();

    /**
     * Other flagged clauses that do not fit the above categories
     * (e.g., jurisdiction surprises, IP assignment, confidentiality traps).
     */
    @Builder.Default
    private List<String> otherFlags = new ArrayList<>();

    /** Total count of flagged items across all categories */
    public int totalFlags() {
        return penaltyClauses.size()
                + terminationRisks.size()
                + liabilityIssues.size()
                + otherFlags.size();
    }
}
