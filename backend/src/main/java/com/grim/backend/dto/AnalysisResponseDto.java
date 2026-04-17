package com.grim.backend.dto;

import com.grim.backend.model.AnalysisResult;
import com.grim.backend.model.RiskReport;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.LocalDateTime;

/**
 * Response payload for the analysis results page.
 * Combines fields from Contract + AnalysisResult into one flat DTO
 * so the Thymeleaf template only needs a single model attribute.
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class AnalysisResponseDto {

    private String contractId;
    private String analysisId;
    private String fileName;
    private int totalChunks;

    // ── Summary ────────────────────────────────────────────
    private String summary;

    // ── Risk ───────────────────────────────────────────────
    private double riskScore;
    private AnalysisResult.RiskLevel riskLevel;
    private RiskReport riskReport;

    // ── Meta ───────────────────────────────────────────────
    private LocalDateTime analyzedAt;

    /**
     * Whether this DTO was populated by the live AI service or
     * by the TODO stub. The UI displays a banner when stubbed = true.
     */
    private boolean aiServiceActive;
}
