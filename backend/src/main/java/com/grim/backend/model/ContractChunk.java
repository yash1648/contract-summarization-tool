package com.grim.backend.model;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

/**
 * A single text chunk produced by ChunkingService.
 *
 * Embedded inside the Contract document (not a separate collection).
 * Each chunk is independently sent to the Python AI service for embedding.
 *
 * The embeddingId field is a reference to the vector stored inside FAISS
 * (managed entirely on the Python side). Spring Boot only stores the ID
 * so it can request specific chunks when needed.
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class ContractChunk {

    /** Zero-based position of this chunk in the document */
    private int index;

    /** The actual text content of this chunk */
    private String text;

    /** Character offset where this chunk starts in the full extracted text */
    private int startOffset;

    /** Character offset where this chunk ends */
    private int endOffset;

    /**
     * Reference ID returned by the Python AI service after
     * this chunk's embedding is stored in FAISS.
     *
     * NULL until the Python AI service has processed this chunk.
     *
     * TODO: Populated by AiIntegrationService.sendChunksForEmbedding()
     */
    private String embeddingId;

    /** True once the Python service confirms embedding is stored */
    @Builder.Default
    private boolean embedded = false;
}
