package com.grim.backend.repository;

import com.grim.backend.model.AnalysisResult;
import org.springframework.data.mongodb.repository.MongoRepository;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.Optional;

/**
 * Spring Data MongoDB repository for AnalysisResult documents.
 */
@Repository
public interface AnalysisResultRepository extends MongoRepository<AnalysisResult, String> {

    /** Find the analysis for a specific contract */
    Optional<AnalysisResult> findByContractId(String contractId);

    /** All results ordered newest first (for dashboard listing) */
    List<AnalysisResult> findAllByOrderByAnalyzedAtDesc();

    /** High-risk results (riskScore >= threshold) — for admin dashboard */
    List<AnalysisResult> findByRiskScoreGreaterThanEqual(double threshold);

    /** Results by risk level */
    List<AnalysisResult> findByRiskLevel(AnalysisResult.RiskLevel riskLevel);

    /** Delete analysis when contract is deleted */
    void deleteByContractId(String contractId);
}
