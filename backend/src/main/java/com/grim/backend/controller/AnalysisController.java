package com.grim.backend.controller;

import com.grim.backend.dto.AnalysisResponseDto;
import com.grim.backend.dto.SearchRequestDto;
import com.grim.backend.service.AnalysisService;
import com.grim.backend.service.ContractService;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.ResponseEntity;
import org.springframework.stereotype.Controller;
import org.springframework.ui.Model;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.servlet.mvc.support.RedirectAttributes;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Map;

/**
 * Handles analysis triggering, results display, and semantic search.
 *
 * Routes:
 *   POST /analysis/{contractId}/run          -> trigger AI analysis
 *   GET  /analysis/{contractId}/results      -> results page (Thymeleaf)
 *   POST /analysis/search (JSON)             -> semantic search API
 *   GET  /analysis                           -> list all analysis results
 */
@Slf4j
@Controller
@RequiredArgsConstructor
public class AnalysisController {

    private final AnalysisService analysisService;
    private final ContractService  contractService;

    /** Trigger analysis for a given contract (redirects to results) */
    @PostMapping("/analysis/{contractId}/run")
    public String runAnalysis(@PathVariable String contractId,
                              RedirectAttributes redirectAttributes) {
        try {
            log.info("Analysis triggered for contractId={}", contractId);
            AnalysisResponseDto result = analysisService.analyzeContract(contractId);
            redirectAttributes.addFlashAttribute("successMessage",
                    "Analysis complete. Risk score: " + String.format("%.1f", result.getRiskScore()) + "/10");
            return "redirect:/analysis/" + contractId + "/results";
        } catch (Exception e) {
            log.error("Analysis failed for contractId={}: {}", contractId, e.getMessage());
            redirectAttributes.addFlashAttribute("errorMessage",
                    "Analysis failed: " + e.getMessage());
            return "redirect:/contracts/" + contractId;
        }
    }

    /** Display analysis results for a contract */
    @GetMapping("/analysis/{contractId}/results")
    public String showResults(@PathVariable String contractId, Model model) {
        AnalysisResponseDto result = analysisService.getAnalysisForContract(contractId);
        model.addAttribute("analysis", result);
        model.addAttribute("riskBadgeClass", riskBadgeClass(result.getRiskScore()));
        return "analysis";
    }

    /** List all analysis results (dashboard view) */
    @GetMapping("/analysis")
    public String listAllAnalyses(Model model) {
        model.addAttribute("results", analysisService.getAllResults());
        return "analysis-list";
    }

    /**
     * Semantic search endpoint — returns JSON with a synthesised answer + chunk citations.
     * Accepts a JSON body with { contractId, query, topK }.
     *
     * Response shape:
     *   { "query": "...", "answer": "AI answer...", "results": [...], "count": N }
     *   When AI is disabled, answer is null and results contain term-matched chunks.
     */
    @PostMapping("/analysis/search")
    @ResponseBody
    public ResponseEntity<Map<String, Object>> semanticSearch(
            @Valid @RequestBody SearchRequestDto request) {

        log.info("Semantic search: contractId={}, query='{}', topK={}",
                request.getContractId(), request.getQuery(), request.getTopK());

        Map<String, Object> result = analysisService.search(
                request.getContractId(),
                request.getQuery(),
                request.getTopK()
        );

        return ResponseEntity.ok(result);
    }

    /**
     * Polling endpoint for frontend toast notifications.
     * Returns contracts whose analysis COMPLETED or FAILED in the last
     * 60 seconds.  The frontend calls this every 5 s and deduplicates
     * by contractId so the user gets a toast without manual reload.
     */
    @GetMapping("/api/analysis/updates")
    @ResponseBody
    public ResponseEntity<List<Map<String, Object>>> getUpdates() {
        LocalDateTime since = LocalDateTime.now().minusSeconds(60);
        List<Map<String, Object>> updates = contractService.getRecentUpdates(since);
        return ResponseEntity.ok(updates);
    }

    // ── Helper ───────────────────────────────────────────────

    private String riskBadgeClass(double score) {
        if (score <= 3.3) return "badge-low";
        if (score <= 6.6) return "badge-medium";
        return "badge-high";
    }
}
