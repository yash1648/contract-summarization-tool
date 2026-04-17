package com.grim.backend.service;

import com.grim.backend.dto.UploadResponseDto;
import com.grim.backend.exception.ContractNotFoundException;
import com.grim.backend.exception.FileProcessingException;
import com.grim.backend.model.Contract;
import com.grim.backend.model.ContractChunk;
import com.grim.backend.repository.AnalysisResultRepository;
import com.grim.backend.repository.ContractRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import org.springframework.web.multipart.MultipartFile;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.nio.file.StandardCopyOption;
import java.time.LocalDateTime;
import java.util.List;
import java.util.Map;
import java.util.UUID;

/**
 * Core service orchestrating the contract upload pipeline:
 *   validate  ->  save to disk  ->  extract text
 *   ->  chunk  ->  embed (AI)  ->  persist to MongoDB
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class ContractService {

    private final ContractRepository       contractRepository;
    private final AnalysisResultRepository analysisResultRepository;
    private final TextExtractionService    textExtractionService;
    private final ChunkingService          chunkingService;
    private final AiIntegrationService     aiIntegrationService;

    @Value("${app.upload.dir}")
    private String uploadDir;

    @Value("${app.upload.allowed-types}")
    private String allowedTypes;

    // ── Upload & Process ─────────────────────────────────────

    public UploadResponseDto uploadAndProcess(MultipartFile file) {
        validateFile(file);

        String mimeType = resolveMimeType(file);
        log.info("Processing upload: {} ({} bytes)", file.getOriginalFilename(), file.getSize());

        String storagePath = saveFileToDisk(file);

        Contract contract = Contract.builder()
                .fileName(file.getOriginalFilename())
                .fileType(mimeType)
                .fileSize(file.getSize())
                .storagePath(storagePath)
                .status(Contract.ProcessingStatus.UPLOADED)
                .build();
        contract = contractRepository.save(contract);
        log.info("Contract saved id={}", contract.getId());

        // Extract
        contract.setStatus(Contract.ProcessingStatus.EXTRACTING);
        contractRepository.save(contract);

        String extractedText = textExtractionService.extractText(file, mimeType);
        if (extractedText.isBlank()) {
            markFailed(contract, "Extraction produced no content.");
            throw new FileProcessingException("Document appears empty or image-only.");
        }
        contract.setExtractedText(extractedText);

        // Chunk
        contract.setStatus(Contract.ProcessingStatus.CHUNKING);
        contractRepository.save(contract);

        List<ContractChunk> chunks = chunkingService.chunk(extractedText);
        contract.setChunks(chunks);
        contract.setTotalChunks(chunks.size());
        log.info("Chunking complete: {} chunks", chunks.size());

        // Embed (non-fatal if AI offline)
        contract.setStatus(Contract.ProcessingStatus.PENDING_AI);
        contract = contractRepository.save(contract);

        try {
            Map<Integer, String> embeddingIds =
                    aiIntegrationService.sendChunksForEmbedding(contract.getId(), chunks);
            if (!embeddingIds.isEmpty()) {
                for (ContractChunk chunk : contract.getChunks()) {
                    String eid = embeddingIds.get(chunk.getIndex());
                    if (eid != null) { chunk.setEmbeddingId(eid); chunk.setEmbedded(true); }
                }
            }
        } catch (Exception e) {
            log.warn("Embedding step failed (AI may be offline): {}", e.getMessage());
        }

        contractRepository.save(contract);

        return UploadResponseDto.builder()
                .contractId(contract.getId())
                .fileName(contract.getFileName())
                .fileType(contract.getFileType())
                .fileSizeBytes(contract.getFileSize())
                .totalChunks(contract.getTotalChunks())
                .status(contract.getStatus())
                .uploadedAt(LocalDateTime.now())
                .message("Uploaded and processed. " + chunks.size() + " chunks ready for analysis.")
                .build();
    }

    // ── Retrieval ────────────────────────────────────────────

    public List<Contract> getAllContracts() {
        return contractRepository.findAllByOrderByCreatedAtDesc();
    }

    public Contract getById(String id) {
        return contractRepository.findById(id)
                .orElseThrow(() -> new ContractNotFoundException("Contract not found: " + id));
    }

    // ── Delete ───────────────────────────────────────────────

    public void deleteContract(String id) {
        Contract contract = getById(id);
        analysisResultRepository.deleteByContractId(id);
        aiIntegrationService.deleteContractVectors(id);
        try { Files.deleteIfExists(Paths.get(contract.getStoragePath())); }
        catch (IOException e) { log.warn("Could not delete file: {}", e.getMessage()); }
        contractRepository.deleteById(id);
        log.info("Deleted contract id={}", id);
    }

    // ── Status helpers ───────────────────────────────────────

    public void markCompleted(String contractId, String analysisResultId) {
        Contract c = getById(contractId);
        c.setStatus(Contract.ProcessingStatus.COMPLETED);
        c.setAnalysisResultId(analysisResultId);
        c.setProcessedAt(LocalDateTime.now());
        contractRepository.save(c);
    }

    public void markFailed(Contract contract, String reason) {
        log.error("Contract {} FAILED: {}", contract.getId(), reason);
        contract.setStatus(Contract.ProcessingStatus.FAILED);
        contractRepository.save(contract);
    }

    // ── Stats ────────────────────────────────────────────────

    public long countByStatus(Contract.ProcessingStatus status) {
        return contractRepository.countByStatus(status);
    }

    public long countAll() { return contractRepository.count(); }

    // ── Private helpers ──────────────────────────────────────

    private void validateFile(MultipartFile file) {
        if (file == null || file.isEmpty())
            throw new FileProcessingException("No file provided or file is empty.");
        String mime = resolveMimeType(file);
        if (!allowedTypes.contains(mime))
            throw new FileProcessingException("File type not allowed: " + mime);
        if (file.getSize() > 20L * 1024 * 1024)
            throw new FileProcessingException("File exceeds 20 MB limit.");
    }

    private String resolveMimeType(MultipartFile file) {
        String ct = file.getContentType();
        if (ct != null && !ct.isBlank() && !ct.equals("application/octet-stream"))
            return ct.trim().toLowerCase();
        String name = file.getOriginalFilename() != null ? file.getOriginalFilename().toLowerCase() : "";
        if (name.endsWith(".pdf")) return "application/pdf";
        if (name.endsWith(".docx"))
            return "application/vnd.openxmlformats-officedocument.wordprocessingml.document";
        return ct != null ? ct : "unknown";
    }

    private String saveFileToDisk(MultipartFile file) {
        try {
            Path dir = Paths.get(uploadDir).toAbsolutePath();
            Files.createDirectories(dir);
            String safeName = UUID.randomUUID() + "_" + sanitize(file.getOriginalFilename());
            Path target = dir.resolve(safeName);
            Files.copy(file.getInputStream(), target, StandardCopyOption.REPLACE_EXISTING);
            return target.toString();
        } catch (IOException e) {
            throw new FileProcessingException("Failed to save file: " + e.getMessage(), e);
        }
    }

    private String sanitize(String name) {
        if (name == null) return "upload";
        return name.replaceAll("[^a-zA-Z0-9._-]", "_");
    }
}
