package com.grim.backend.controller;

import com.grim.backend.model.Contract;
import com.grim.backend.service.AnalysisService;
import com.grim.backend.service.ContractService;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Controller;
import org.springframework.ui.Model;
import org.springframework.web.bind.annotation.GetMapping;

/**
 * Home / Dashboard controller.
 *
 * Routes:
 *   GET /       -> redirects to /dashboard
 *   GET /dashboard -> main dashboard with stats
 */
@Controller
@RequiredArgsConstructor
public class DashboardController {

    private final ContractService  contractService;
    private final AnalysisService  analysisService;

    @GetMapping("/")
    public String home() {
        return "redirect:/dashboard";
    }
    @GetMapping("/dashboard")
    public String dashboard(Model model) {
        model.addAttribute("totalContracts",    contractService.countAll());
        model.addAttribute("completedContracts",
                contractService.countByStatus(Contract.ProcessingStatus.COMPLETED));
        model.addAttribute("pendingContracts",
                contractService.countByStatus(Contract.ProcessingStatus.PENDING_AI));
        model.addAttribute("failedContracts",
                contractService.countByStatus(Contract.ProcessingStatus.FAILED));
        model.addAttribute("highRiskContracts", analysisService.countHighRisk());
        model.addAttribute("recentContracts",   contractService.getAllContracts()
                .stream().limit(5).toList());
        model.addAttribute("recentAnalyses",    analysisService.getAllResults()
                .stream().limit(5).toList());
        return "index";
    }
}
