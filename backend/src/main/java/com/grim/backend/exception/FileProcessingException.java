package com.grim.backend.exception;

import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.ResponseStatus;

@ResponseStatus(HttpStatus.BAD_REQUEST)
public class FileProcessingException extends RuntimeException {
    public FileProcessingException(String message) { super(message); }
    public FileProcessingException(String message, Throwable cause) { super(message, cause); }
}
