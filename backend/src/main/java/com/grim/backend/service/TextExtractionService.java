package com.grim.backend.service;

import com.grim.backend.exception.FileProcessingException;
import lombok.extern.slf4j.Slf4j;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.text.PDFTextStripper;
import org.apache.poi.xwpf.extractor.XWPFWordExtractor;
import org.apache.poi.xwpf.usermodel.XWPFDocument;
import org.springframework.stereotype.Service;
import org.springframework.web.multipart.MultipartFile;

import java.io.IOException;
import java.io.InputStream;

/**
 * Extracts plain text from uploaded PDF and DOCX files.
 *
 * Libraries used:
 *   PDF  → Apache PDFBox 3.x
 *   DOCX → Apache POI (XWPFDocument)
 */
@Slf4j
@Service
public class TextExtractionService {

    /**
     * Extract text from an uploaded MultipartFile.
     *
     * @param file     the uploaded file
     * @param mimeType the MIME type detected at upload time
     * @return cleaned plain-text content of the document
     * @throws FileProcessingException if the file cannot be parsed
     */
    public String extractText(MultipartFile file, String mimeType) {
        log.info("Extracting text from file: {} (type: {})", file.getOriginalFilename(), mimeType);

        try (InputStream inputStream = file.getInputStream()) {
            return switch (mimeType) {
                case "application/pdf" -> extractFromPdf(inputStream);
                case "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                        -> extractFromDocx(inputStream);
                default -> throw new FileProcessingException(
                        "Unsupported file type: " + mimeType + ". Only PDF and DOCX are accepted.");
            };
        } catch (IOException e) {
            log.error("Failed to extract text from {}: {}", file.getOriginalFilename(), e.getMessage());
            throw new FileProcessingException("Could not read file: " + e.getMessage(), e);
        }
    }

    // ── Private helpers ──────────────────────────────────────────────────

    /**
     * Extract text from a PDF using PDFBox.
     * PDFTextStripper reads all pages and preserves paragraph spacing.
     */
    private String extractFromPdf(InputStream inputStream) throws IOException {
        try (PDDocument document = Loader.loadPDF(inputStream.readAllBytes())) {
            if (document.isEncrypted()) {
                throw new FileProcessingException("Encrypted PDFs are not supported.");
            }
            PDFTextStripper stripper = new PDFTextStripper();
            stripper.setSortByPosition(true); // maintain reading order
            String rawText = stripper.getText(document);
            log.debug("PDF extraction: {} pages, {} characters extracted",
                    document.getNumberOfPages(), rawText.length());
            return cleanText(rawText);
        }
    }

    /**
     * Extract text from a DOCX using Apache POI.
     * XWPFWordExtractor retrieves text from all paragraphs, tables, and headers.
     */
    private String extractFromDocx(InputStream inputStream) throws IOException {
        try (XWPFDocument document = new XWPFDocument(inputStream);
             XWPFWordExtractor extractor = new XWPFWordExtractor(document)) {
            String rawText = extractor.getText();
            log.debug("DOCX extraction: {} characters extracted", rawText.length());
            return cleanText(rawText);
        }
    }

    /**
     * Basic text cleaning:
     *   - Collapse multiple blank lines into one
     *   - Normalise Windows line endings
     *   - Trim leading/trailing whitespace
     */
    private String cleanText(String raw) {
        if (raw == null || raw.isBlank()) return "";
        return raw
                .replace("\r\n", "\n")     // Windows → Unix line endings
                .replace("\r", "\n")        // Old Mac line endings
                .replaceAll("\\n{3,}", "\n\n")  // max 2 consecutive blank lines
                .replaceAll("[ \\t]{2,}", " ")  // collapse multiple spaces/tabs
                .strip();
    }
}
