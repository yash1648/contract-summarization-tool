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
import java.util.ArrayList;
import java.util.List;

/**
 * Represents a single uploaded contract document.
 *
 * MongoDB collection: "contracts"
 *
 * Fields that belong to the AI pipeline (embeddings, summary, risk)
 * are stored in a linked AnalysisResult document to keep this collection lean.
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
@Document(collection = "contracts")
public class Contract {

    @Id
    private String id;

    /** Original filename as uploaded by the user */
    @Indexed
    private String fileName;

    /** MIME type: "application/pdf" or "application/vnd.openxmlformats-..." */
    private String fileType;

    /** Size in bytes */
    private long fileSize;

    /** Path on server where the raw file is stored */
    private String storagePath;

    /**
     * Full extracted text from the document.
     * Stored here so the extraction step only runs once.
     * For very large contracts consider moving this to GridFS.
     */
    private String extractedText;

    /**
     * Text split into overlapping chunks ready for embedding.
     * Populated by ChunkingService after extraction.
     */
    @Builder.Default
    private List<ContractChunk> chunks = new ArrayList<>();

    /** Total number of chunks generated */
    private int totalChunks;

    /** Current processing status */
    @Builder.Default
    private ProcessingStatus status = ProcessingStatus.UPLOADED;

    /** ID of the linked AnalysisResult (null until analysis completes) */
    private String analysisResultId;

    @CreatedDate
    private LocalDateTime createdAt;

    private LocalDateTime processedAt;

    /** ── Nested enum ─────────────────────────────────────── */
    public enum ProcessingStatus {
        UPLOADED,        // File saved, not yet extracted
        EXTRACTING,      // Text extraction in progress
        CHUNKING,        // Splitting text into chunks
        PENDING_AI,      // Chunks ready, waiting for Python AI service
        ANALYZING,       // Python AI service is working
        COMPLETED,       // Full analysis done
        FAILED           // Any step failed
    }
}
