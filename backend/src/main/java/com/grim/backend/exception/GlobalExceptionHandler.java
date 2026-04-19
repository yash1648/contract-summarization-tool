package com.grim.backend.exception;

import com.grim.backend.service.AiIntegrationService;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.HttpStatus;
import org.springframework.ui.Model;
import org.springframework.web.bind.annotation.ControllerAdvice;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.multipart.MaxUploadSizeExceededException;

/**
 * Global exception handler.
 * Returns the error.html Thymeleaf view for all unhandled exceptions.
 */
@Slf4j
@ControllerAdvice
public class GlobalExceptionHandler {

    @ExceptionHandler(ContractNotFoundException.class)
    @ResponseStatus(HttpStatus.NOT_FOUND)
    public String handleNotFound(ContractNotFoundException ex, Model model) {
        model.addAttribute("errorTitle",   "Contract Not Found");
        model.addAttribute("errorMessage", ex.getMessage());
        model.addAttribute("statusCode",   404);
        return "error";
    }

    @ExceptionHandler(FileProcessingException.class)
    @ResponseStatus(HttpStatus.BAD_REQUEST)
    public String handleFileProcessing(FileProcessingException ex, Model model) {
        model.addAttribute("errorTitle",   "File Processing Error");
        model.addAttribute("errorMessage", ex.getMessage());
        model.addAttribute("statusCode",   400);
        return "error";
    }

    @ExceptionHandler(MaxUploadSizeExceededException.class)
    @ResponseStatus(HttpStatus.PAYLOAD_TOO_LARGE)
    public String handleFileSizeLimit(MaxUploadSizeExceededException ex, Model model) {
        model.addAttribute("errorTitle",   "File Too Large");
        model.addAttribute("errorMessage", "The uploaded file exceeds the 20 MB size limit.");
        model.addAttribute("statusCode",   413);
        return "error";
    }

    @ExceptionHandler(AiIntegrationService.AiServiceException.class)
    @ResponseStatus(HttpStatus.SERVICE_UNAVAILABLE)
    public String handleAiServiceError(AiIntegrationService.AiServiceException ex, Model model) {
        log.error("AI service error: {}", ex.getMessage());
        model.addAttribute("errorTitle",   "AI Service Unavailable");
        model.addAttribute("errorMessage", ex.getMessage()
                + "\n\nMake sure the Python AI service is running on port 5000 "
                + "and Ollama has the configured model loaded (check .env OLLAMA_MODEL).");
        model.addAttribute("statusCode",   503);
        return "error";
    }

    @ExceptionHandler(IllegalStateException.class)
    @ResponseStatus(HttpStatus.CONFLICT)
    public String handleIllegalState(IllegalStateException ex, Model model) {
        model.addAttribute("errorTitle",   "Processing Error");
        model.addAttribute("errorMessage", ex.getMessage());
        model.addAttribute("statusCode",   409);
        return "error";
    }

    @ExceptionHandler(Exception.class)
    @ResponseStatus(HttpStatus.INTERNAL_SERVER_ERROR)
    public String handleGeneric(Exception ex, Model model) {
        log.error("Unhandled exception: {}", ex.getMessage(), ex);
        model.addAttribute("errorTitle",   "Unexpected Error");
        model.addAttribute("errorMessage", "Something went wrong: " + ex.getMessage());
        model.addAttribute("statusCode",   500);
        return "error";
    }
}
