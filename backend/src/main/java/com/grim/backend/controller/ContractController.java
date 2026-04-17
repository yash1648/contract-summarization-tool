package com.grim.backend.controller;

import com.grim.backend.dto.UploadResponseDto;
import com.grim.backend.model.Contract;
import com.grim.backend.service.ContractService;
import jakarta.validation.constraints.NotBlank;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Controller;
import org.springframework.ui.Model;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;
import org.springframework.web.servlet.mvc.support.RedirectAttributes;

import java.util.List;

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
            redirectAttributes.addFlashAttribute("successMessage",
                    "✓ " + response.getFileName() + " uploaded successfully. "
                    + response.getTotalChunks() + " chunks ready.");
            redirectAttributes.addFlashAttribute("uploadResult", response);
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
        model.addAttribute("contract", contract);
        // Show first 3 chunks as preview
        int previewCount = Math.min(3, contract.getChunks().size());
        model.addAttribute("previewChunks", contract.getChunks().subList(0, previewCount));
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
}
