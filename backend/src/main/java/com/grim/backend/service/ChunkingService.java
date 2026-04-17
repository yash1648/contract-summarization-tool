package com.grim.backend.service;

import com.grim.backend.model.ContractChunk;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import java.util.ArrayList;
import java.util.List;

/**
 * Splits a contract's extracted plain text into overlapping chunks.
 *
 * Strategy:
 *   1. Try to split on paragraph boundaries (\n\n) first so chunks
 *      preserve semantic units.
 *   2. If a paragraph is longer than chunkSize, it is further split
 *      at sentence boundaries (". ").
 *   3. Final fallback: hard-split at chunkSize characters.
 *
 * Overlap:
 *   The last `overlapSize` characters of the previous chunk are
 *   prepended to the next chunk. This ensures that information at
 *   chunk boundaries is not lost during RAG retrieval.
 *
 * Configuration (application.properties):
 *   app.chunking.chunk-size  = 1600   (~400 tokens at 4 chars/token)
 *   app.chunking.overlap-size = 200
 */
@Slf4j
@Service
public class ChunkingService {

    @Value("${app.chunking.chunk-size:1600}")
    private int chunkSize;

    @Value("${app.chunking.overlap-size:200}")
    private int overlapSize;

    /**
     * Split text into overlapping ContractChunk objects.
     *
     * @param text the full extracted text of the contract
     * @return ordered list of chunks, each with index and offset metadata
     */
    public List<ContractChunk> chunk(String text) {
        if (text == null || text.isBlank()) {
            return List.of();
        }

        List<String> rawChunks = splitIntoRawChunks(text);
        List<ContractChunk> chunks = new ArrayList<>();
        int charOffset = 0;

        for (int i = 0; i < rawChunks.size(); i++) {
            String chunkText = rawChunks.get(i).strip();
            if (chunkText.isBlank()) continue;

            int start = text.indexOf(chunkText, Math.max(0, charOffset - overlapSize));
            int end   = start + chunkText.length();

            chunks.add(ContractChunk.builder()
                    .index(i)
                    .text(chunkText)
                    .startOffset(Math.max(start, 0))
                    .endOffset(end)
                    .embedded(false)
                    .build());

            charOffset = end;
        }

        log.info("Chunking complete: {} raw segments → {} chunks (chunkSize={}, overlap={})",
                rawChunks.size(), chunks.size(), chunkSize, overlapSize);
        return chunks;
    }

    // ── Private helpers ─────────────────────────────────────────────────

    /**
     * Core split logic with overlap injection.
     */
    private List<String> splitIntoRawChunks(String text) {
        // Step 1: split on paragraph breaks
        String[] paragraphs = text.split("\\n\\n+");
        List<String> segments = new ArrayList<>();

        for (String para : paragraphs) {
            if (para.length() <= chunkSize) {
                segments.add(para);
            } else {
                // Step 2: paragraph is too long — split on sentence boundaries
                segments.addAll(splitLongParagraph(para));
            }
        }

        // Step 3: merge short adjacent segments and inject overlap
        return mergeAndOverlap(segments);
    }

    /**
     * Split a long paragraph at sentence boundaries.
     * Sentence boundary heuristic: ". " or ".\n"
     */
    private List<String> splitLongParagraph(String paragraph) {
        List<String> parts = new ArrayList<>();
        StringBuilder current = new StringBuilder();

        String[] sentences = paragraph.split("(?<=\\.[ \\n])");
        for (String sentence : sentences) {
            if (current.length() + sentence.length() > chunkSize && current.length() > 0) {
                parts.add(current.toString().strip());
                current = new StringBuilder();
            }
            current.append(sentence).append(" ");
        }
        if (!current.toString().isBlank()) {
            parts.add(current.toString().strip());
        }
        return parts;
    }

    /**
     * Merge consecutive short segments so we don't produce tiny chunks,
     * then inject overlap from the previous chunk's tail.
     */
    private List<String> mergeAndOverlap(List<String> segments) {
        List<String> result = new ArrayList<>();
        StringBuilder buffer = new StringBuilder();

        for (String seg : segments) {
            if (buffer.length() + seg.length() + 1 <= chunkSize) {
                if (!buffer.isEmpty()) buffer.append("\n\n");
                buffer.append(seg);
            } else {
                if (!buffer.isEmpty()) {
                    result.add(buffer.toString());
                }
                // Prepend overlap from end of previous chunk
                String overlap = "";
                if (!result.isEmpty()) {
                    String prev = result.get(result.size() - 1);
                    overlap = prev.substring(Math.max(0, prev.length() - overlapSize));
                }
                buffer = new StringBuilder(overlap);
                if (!overlap.isEmpty()) buffer.append(" ");
                buffer.append(seg);
            }
        }
        if (!buffer.isEmpty()) result.add(buffer.toString());

        return result;
    }
}
