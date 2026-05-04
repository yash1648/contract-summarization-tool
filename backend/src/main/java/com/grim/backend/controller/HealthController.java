package com.grim.backend.controller;

import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

/**
 * Handles various browser and health check requests
 */
@RestController
public class HealthController {

    /**
     * Handle Chrome DevTools protocol requests - return empty 200 OK
     * These requests come from Chrome browser trying to detect server capabilities
     */
    @GetMapping("/.well-known/appspecific/com.chrome.devtools.json")
    public ResponseEntity<Void> handleChromeDevTools() {
        return ResponseEntity.ok().build();
    }

    /**
     * Simple health check endpoint
     */
    @GetMapping("/health")
    public ResponseEntity<String> health() {
        return ResponseEntity.ok("OK");
    }
}