package com.grim.backend.controller;

import com.grim.backend.dto.UploadResponseDto;
import com.grim.backend.model.Contract;
import com.grim.backend.service.AnalysisService;
import com.grim.backend.service.ContractService;
import jakarta.annotation.PreDestroy;
import jakarta.validation.constraints.NotBlank;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Controller;
import org.springframework.ui.Model;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;
import org.springframework.web.servlet.mvc.support.RedirectAttributes;

import java.util.List;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.TimeUnit;

/**
 * Handles contract upload and listing pages.
 *
 * Routes:
 *   GET  /contracts          -> list all contracts
 *   GET  /contracts/upload   -> upload form
 *   POST /contracts/upload   -> process upload
 *   POST /contracts/{id}/delete -> delete a contract
 */
@Slf4j
@Controller
@RequestMapping("/contracts")
@RequiredArgsConstructor
public class ContractController {

    private final ContractService contractService;
    private final AnalysisService analysisService;

    /**
     * Dedicated executor for background analysis tasks.
     * Using a virtual thread executor for lightweight concurrency
     * without blocking the common ForkJoinPool.
     */
    private final ExecutorService analysisExecutor = Executors.newFixedThreadPool(2);

    /** List all uploaded contracts */
    @GetMapping
    public String listContracts(Model model) {
        List<Contract> contracts = contractService.getAllContracts();
        model.addAttribute("contracts", contracts);
        model.addAttribute("totalCount",     contracts.size());
        model.addAttribute("completedCount", contracts.stream()
                .filter(c -> c.getStatus() == Contract.ProcessingStatus.COMPLETED).count());
        model.addAttribute("pendingCount", contracts.stream()
                .filter(c -> c.getStatus() == Contract.ProcessingStatus.PENDING_AI
                          || c.getStatus() == Contract.ProcessingStatus.UPLOADED).count());
        return "contracts";
    }

    /** Upload form page */
    @GetMapping("/upload")
    public String uploadForm() {
        return "upload";
    }

    /** Handle file upload submission */
    @PostMapping("/upload")
    public String handleUpload(@RequestParam("file") MultipartFile file,
                               RedirectAttributes redirectAttributes) {
        try {
            UploadResponseDto response = contractService.uploadAndProcess(file);

            // Auto-trigger analysis asynchronously on a dedicated thread pool
            final String contractId = response.getContractId();
            analysisExecutor.submit(() -> {
                try {
                    log.info("Starting async analysis for contractId={}", contractId);
                    analysisService.analyzeContract(contractId);
                    log.info("Async analysis completed for contractId={}", contractId);
                } catch (Exception e) {
                    log.error("Async analysis failed for contractId={}: {}", contractId, e.getMessage(), e);
                }
            });

            redirectAttributes.addFlashAttribute("successMessage",
                    "✓ " + response.getFileName() + " uploaded successfully. AI Analysis is running in the background.");

            return "redirect:/contracts/" + response.getContractId();
        } catch (Exception e) {
            log.error("Upload failed: {}", e.getMessage());
            redirectAttributes.addFlashAttribute("errorMessage",
                    "Upload failed: " + e.getMessage());
            return "redirect:/contracts/upload";
        }
    }

    /** Contract detail page */
    @GetMapping("/{id}")
    public String contractDetail(@PathVariable String id, Model model) {
        Contract contract = contractService.getById(id);
        long embeddedCount = contract.getChunks() == null ? 0 :
                contract.getChunks().stream()
                .filter(c -> c.isEmbedded())
                .count();

        model.addAttribute("contract", contract);
        model.addAttribute("embeddedCount", embeddedCount);

        // 🔥 ALSO ADD ENUMS
        model.addAttribute("STATUS_COMPLETED", Contract.ProcessingStatus.COMPLETED);
        model.addAttribute("STATUS_ANALYZING", Contract.ProcessingStatus.ANALYZING);
        model.addAttribute("STATUS_PENDING", Contract.ProcessingStatus.PENDING_AI);
        return "contract-detail";
    }

    /** Delete a contract and all its data */
    @PostMapping("/{id}/delete")
    public String deleteContract(@PathVariable @NotBlank String id,
                                 RedirectAttributes redirectAttributes) {
        try {
            contractService.deleteContract(id);
            redirectAttributes.addFlashAttribute("successMessage",
                    "Contract deleted successfully.");
        } catch (Exception e) {
            log.error("Delete failed for id={}: {}", id, e.getMessage());
            redirectAttributes.addFlashAttribute("errorMessage",
                    "Delete failed: " + e.getMessage());
        }
        return "redirect:/contracts";
    }

    /**
     * Gracefully shut down the analysis executor on application context destruction.
     * Prevents thread leaks during redeployment or shutdown.
     */
    @PreDestroy
    public void shutdown() {
        log.info("Shutting down analysis analysis executor...");
        analysisExecutor.shutdown();
        try {
            if (!analysisExecutor.awaitTermination(30, TimeUnit.SECONDS)) {
                log.warn("Analysis executor did not terminate gracefully, forcing shutdown");
                analysisExecutor.shutdownNow();
            }
        } catch (InterruptedException e) {
            log.error("Interrupted while waiting for analysis executor shutdown");
            analysisExecutor.shutdownNow();
            Thread.currentThread().interrupt();
        }
    }
}
