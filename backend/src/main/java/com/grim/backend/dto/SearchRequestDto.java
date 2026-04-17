package com.grim.backend.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;
import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;

/**
 * Request body for the semantic search endpoint.
 *
 * The contractId scopes the search to a single contract;
 * passing null searches across all contracts (future feature).
 */
@Data
@NoArgsConstructor
@AllArgsConstructor
public class SearchRequestDto {

    /** Optional: restrict search to a specific contract */
    private String contractId;

    @NotBlank(message = "Search query must not be blank")
    @Size(min = 3, max = 500, message = "Query must be between 3 and 500 characters")
    private String query;

    /** Maximum number of results to return (default 5, max 20) */
    private int topK = 5;
}
