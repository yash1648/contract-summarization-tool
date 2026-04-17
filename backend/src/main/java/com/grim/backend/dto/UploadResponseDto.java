package com.grim.backend.dto;

import com.grim.backend.model.Contract;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.LocalDateTime;

/**
 * Response payload returned after a successful file upload.
 * Contains enough information for the UI to redirect and show progress.
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class UploadResponseDto {

    private String contractId;
    private String fileName;
    private String fileType;
    private long fileSizeBytes;
    private int totalChunks;
    private Contract.ProcessingStatus status;
    private LocalDateTime uploadedAt;
    private String message;
}
