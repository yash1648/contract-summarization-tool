package com.grim.backend.service;

import com.grim.backend.model.ContractChunk;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import java.util.ArrayList;
import java.util.List;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * Splits a contract's extracted plain text into semantic chunks for RAG.
 *
 * Strategy:
 *   1. Split on paragraph boundaries (\n\n) first to preserve semantic units.
 *   2. Within each paragraph, split on robust sentence boundaries
 *      (., !, ? followed by whitespace or end-of-string).
 *   3. Accumulate sentences into chunks up to chunkSize, keeping
 *      sentences intact — never split mid-sentence.
 *   4. Inject overlap from the previous chunk's tail so boundary
 *      information isn't lost during vector search.
 *
 * Key improvements over the previous version:
 *   - Robust sentence splitter: handles ". ", "! ", "? ", and end-of-string
 *   - Sentences are NEVER split mid-way — chunk boundaries always fall at
 *     sentence boundaries
 *   - Overlap is injected from the tail of the previous chunk for context
 */
@Slf4j
@Service
public class ChunkingService {

    @Value("${app.chunking.size:2000}")
    private int chunkSize;

    @Value("${app.chunking.overlap:200}")
    private int overlapSize;

    /**
     * Regex that matches sentence boundaries: end-of-sentence punctuation
     * (. ! ?) followed by whitespace or end of string.
     *
     * Uses a lookbehind so the delimiter is not consumed, preserving
     * the punctuation on the sentence.
     */
    private static final Pattern SENTENCE_BOUNDARY =
            Pattern.compile("(?<=[.!?])\\s+|(?<=[.!?])$");

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

        // 1. Split into paragraphs first
        String[] paragraphs = text.split("\\n\\n+");

        // 2. Convert paragraphs into sentence-level segments
        List<String> sentences = new ArrayList<>();
        for (String para : paragraphs) {
            if (para.isBlank()) continue;
            splitSentences(para, sentences);
        }

        if (sentences.isEmpty()) {
            return List.of();
        }

        // 3. Accumulate sentences into chunks + inject overlap
        List<ContractChunk> chunks = buildChunksWithOverlap(sentences, text);

        log.info("Chunking complete: {} sentences → {} chunks (chunkSize={}, overlap={})",
                sentences.size(), chunks.size(), chunkSize, overlapSize);
        return chunks;
    }

    // ── Private helpers ─────────────────────────────────────────────────

    /**
     * Split a paragraph into individual sentences using a robust boundary
     * pattern that handles ".", "!", "?" followed by whitespace or end-of-string.
     *
     * Sentences shorter than 3 chars are discarded (likely artifacts).
     */
    private void splitSentences(String paragraph, List<String> out) {
        Matcher matcher = SENTENCE_BOUNDARY.matcher(paragraph);
        int start = 0;

        while (matcher.find()) {
            int end = matcher.start();
            String sentence = paragraph.substring(start, end).strip();
            if (sentence.length() >= 3) {
                out.add(sentence);
            }
            start = matcher.end();
        }

        // Last sentence (or the whole paragraph if no boundary matched)
        if (start < paragraph.length()) {
            String sentence = paragraph.substring(start).strip();
            if (sentence.length() >= 3) {
                out.add(sentence);
            }
        }
    }

    /**
     * Build chunks by accumulating sentences up to chunkSize, then injecting
     * overlap from the tail of the previous chunk.
     *
     * Each chunk boundary falls at a sentence boundary — sentences are NEVER
     * split mid-way. The overlap consists of whole sentences (not arbitrary
     * characters) for clean vector embedding boundaries.
     */
    private List<ContractChunk> buildChunksWithOverlap(List<String> sentences, String fullText) {
        List<ContractChunk> chunks = new ArrayList<>();
        int chunkIndex = 0;
        int sentenceIdx = 0;

        while (sentenceIdx < sentences.size()) {
            StringBuilder buffer = new StringBuilder();
            int firstSentenceInChunk = sentenceIdx;

            // Accumulate sentences until we hit chunkSize
            while (sentenceIdx < sentences.size()) {
                String next = sentences.get(sentenceIdx);
                int projectedLen = buffer.length() + next.length() + 1;
                if (buffer.isEmpty()) {
                    projectedLen = next.length();
                }
                if (projectedLen > chunkSize && !buffer.isEmpty()) {
                    break;  // Chunk is full; don't include this sentence
                }
                if (!buffer.isEmpty()) buffer.append(" ");
                buffer.append(next);
                sentenceIdx++;
            }

            String chunkText = buffer.toString().strip();
            if (chunkText.isBlank()) continue;

            // Find position in full text for offset tracking
            int start = findApproxOffset(fullText, chunkText, chunks);
            int end = start + chunkText.length();

            chunks.add(ContractChunk.builder()
                    .index(chunkIndex)
                    .text(chunkText)
                    .startOffset(Math.max(start, 0))
                    .endOffset(end)
                    .embedded(false)
                    .build());

            chunkIndex++;

            // Inject overlap: rewind sentenceIdx to include overlap sentences
            // from the end of the current chunk (if there are more sentences)
            if (sentenceIdx < sentences.size()) {
                sentenceIdx = computeOverlapStart(firstSentenceInChunk, sentenceIdx, sentences);
            }
        }

        return chunks;
    }

    /**
     * Compute how far back to rewind for overlap. Walks backward from
     * the end of the current chunk to include ~overlapSize chars worth
     * of whole sentences. This ensures smooth transitions between chunks.
     */
    private int computeOverlapStart(int chunkFirstSentence, int chunkEndSentence,
                                    List<String> sentences) {
        int overlapLen = 0;
        int cursor = chunkEndSentence - 1;

        while (cursor > chunkFirstSentence && overlapLen < overlapSize) {
            overlapLen += sentences.get(cursor).length() + 1;
            cursor--;
        }
        // Return the overlap start (don't go earlier than the first sentence of the chunk)
        return Math.max(cursor, chunkFirstSentence);
    }

    /**
     * Approximate the offset of a chunk text within the full document.
     * Walks from the last known position to find the text.
     */
    private int findApproxOffset(String fullText, String chunkText,
                                  List<ContractChunk> existingChunks) {
        int searchFrom = 0;
        if (!existingChunks.isEmpty()) {
            ContractChunk last = existingChunks.get(existingChunks.size() - 1);
            searchFrom = Math.max(0, last.getEndOffset() - overlapSize);
        }
        int idx = fullText.indexOf(chunkText, searchFrom);
        return idx >= 0 ? idx : searchFrom;
    }
}
