package com.grim.backend.controller;

import com.grim.backend.model.Contract;
import com.grim.backend.service.AiHealthService;
import com.grim.backend.service.AnalysisService;
import com.grim.backend.service.ContractService;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.stereotype.Controller;
import org.springframework.ui.Model;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.ResponseBody;

import java.util.Map;


/**
 * Dashboard and system health controller.
 *
 * Routes:
 *   GET /            → redirect to /dashboard
 *   GET /dashboard   → main dashboard with live AI status
 *   GET /api/health  → JSON health endpoint (for monitoring tools)
 */
@Controller
@RequiredArgsConstructor
public class DashboardController {

    private final ContractService  contractService;
    private final AnalysisService  analysisService;
    private final AiHealthService  aiHealthService;

    @GetMapping("/")
    public String home() {
        return "redirect:/dashboard";
    }

    @GetMapping("/dashboard")
    public String dashboard(Model model) {
        model.addAttribute("totalContracts",     contractService.countAll());
        model.addAttribute("completedContracts",
                contractService.countByStatus(Contract.ProcessingStatus.COMPLETED));
        model.addAttribute("pendingContracts",
                contractService.countByStatus(Contract.ProcessingStatus.PENDING_AI));
        model.addAttribute("failedContracts",
                contractService.countByStatus(Contract.ProcessingStatus.FAILED));
        model.addAttribute("highRiskContracts",  analysisService.countHighRisk());
        model.addAttribute("recentContracts",    contractService.getAllContracts()
                .stream().limit(5).toList());
        model.addAttribute("recentAnalyses",     analysisService.getAllResults()
                .stream().limit(5).toList());

        // Live AI service status (cached 30 s)
        model.addAttribute("aiStatus", aiHealthService.check());

        return "index";
    }

    @GetMapping("/search")
    public String searchPage(Model model) {
        model.addAttribute("contracts", contractService.getAllContracts());
        return "search";
    }

    /**
     * JSON health endpoint — always fetches fresh status.
     * Useful for Docker health-checks and monitoring dashboards.
     *
     *   GET /api/health
     *   → { "springBoot": "UP", "aiService": "UP|DOWN", "ollama": true|false, ... }
     */
    @GetMapping("/api/health")
    @ResponseBody
    public ResponseEntity<Map<String, Object>> health() {
        AiHealthService.AiStatus ai = aiHealthService.checkNow();
        java.util.Map<String, Object> result = new java.util.LinkedHashMap<>();
        result.put("springBoot",     "UP");
        result.put("aiService",      ai.isUp() ? "UP" : "DOWN");
        result.put("ollamaReachable",ai.isOllamaReachable());
        result.put("ollamaModel",    ai.getOllamaModel());
        result.put("embeddingModel", ai.getEmbeddingModel());
        result.put("totalFaissIndexes", ai.getTotalIndexes());
        result.put("errorMessage",   ai.getErrorMessage());
        return ResponseEntity.ok(result);
    }
}
