package com.grim.backend.model;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.util.ArrayList;
import java.util.List;
import java.util.Set;
import java.util.HashSet;
import java.util.stream.Collectors;

/**
 * Structured extraction data from the extraction-first pipeline.
 *
 * Produced by the Python AI service's /api/ai/extract endpoint.
 * Java receives per-chunk extractions and merges them into this unified structure.
 *
 * Key design principles:
 * - Deduplication: identical entries across chunks are merged
 * - Normalization: lowercase, trimmed, sorted
 * - Deterministic: same input always produces same output
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class ExtractedData {

    @Builder.Default
    private List<String> parties = new ArrayList<>();

    @Builder.Default
    private List<String> obligations = new ArrayList<>();

    @Builder.Default
    private List<String> paymentTerms = new ArrayList<>();

    @Builder.Default
    private List<String> dates = new ArrayList<>();

    @Builder.Default
    private List<String> penalties = new ArrayList<>();

    @Builder.Default
    private List<String> termination = new ArrayList<>();

    /**
     * Merge another ExtractedData into this one, deduplicating entries.
     * Normalization: lowercase, trim, then deduplicate.
     */
    public void merge(ExtractedData other) {
        if (other == null) return;

        parties = mergeAndNormalize(parties, other.parties);
        obligations = mergeAndNormalize(obligations, other.obligations);
        paymentTerms = mergeAndNormalize(paymentTerms, other.paymentTerms);
        dates = mergeAndNormalize(dates, other.dates);
        penalties = mergeAndNormalize(penalties, other.penalties);
        termination = mergeAndNormalize(termination, other.termination);
    }

    /**
     * Merge two lists, normalize each entry, and deduplicate.
     */
    private List<String> mergeAndNormalize(List<String> existing, List<String> incoming) {
        Set<String> normalized = new HashSet<>();
        for (String s : existing) {
            String n = normalize(s);
            if (!n.isEmpty()) normalized.add(n);
        }
        for (String s : incoming) {
            String n = normalize(s);
            if (!n.isEmpty()) normalized.add(n);
        }
        return normalized.stream()
                .sorted()
                .collect(Collectors.toList());
    }

    /**
     * Normalize a string: lowercase, trim, collapse whitespace.
     */
    private String normalize(String s) {
        if (s == null) return "";
        return s.toLowerCase().trim().replaceAll("\\s+", " ");
    }

    /**
     * Total count of all extracted items.
     */
    public int totalItems() {
        return parties.size() + obligations.size() + paymentTerms.size()
                + dates.size() + penalties.size() + termination.size();
    }

    /**
     * Check if all fields are empty.
     */
    public boolean isEmpty() {
        return parties.isEmpty() && obligations.isEmpty() && paymentTerms.isEmpty()
                && dates.isEmpty() && penalties.isEmpty() && termination.isEmpty();
    }
}