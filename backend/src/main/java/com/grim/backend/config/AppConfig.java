package com.grim.backend.config;

import io.netty.channel.ChannelOption;
import io.netty.handler.timeout.ReadTimeoutHandler;
import io.netty.handler.timeout.WriteTimeoutHandler;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.context.annotation.Primary;
import org.springframework.http.client.reactive.ReactorClientHttpConnector;
import org.springframework.web.reactive.function.client.ExchangeFilterFunction;
import org.springframework.web.reactive.function.client.WebClient;
import org.springframework.web.servlet.config.annotation.ResourceHandlerRegistry;
import org.springframework.web.servlet.config.annotation.WebMvcConfigurer;
import reactor.core.publisher.Mono;
import reactor.netty.http.client.HttpClient;
import lombok.extern.slf4j.Slf4j;

import jakarta.annotation.PostConstruct;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.time.Duration;
import java.util.concurrent.TimeUnit;

/**
 * Application configuration.
 *
 * Configures a production-grade WebClient for the Python AI service:
 *   - Connect timeout: 10 s
 *   - Read timeout: driven by app.ai.service.timeout-seconds (default 120 s)
 *   - Request/response logging at DEBUG level
 *   - 10 MB codec buffer (LLM summaries can be large)
 */
@Slf4j
@Configuration
public class AppConfig {

    @Value("${app.ai.service.url}")
    private String aiServiceUrl;

    @Value("${app.ai.service.timeout-seconds:120}")
    private int aiTimeoutSeconds;

    @Value("${app.upload.dir}")
    private String uploadDir;

    @Bean
    @Primary
    public WebClient aiWebClient() {
        // Netty HTTP client with explicit connection + read timeouts
        HttpClient httpClient = HttpClient.create()
                .option(ChannelOption.CONNECT_TIMEOUT_MILLIS, 10_000)
                .responseTimeout(Duration.ofSeconds(aiTimeoutSeconds))
                .doOnConnected(conn -> conn
                        .addHandlerLast(new ReadTimeoutHandler(aiTimeoutSeconds, TimeUnit.SECONDS))
                        .addHandlerLast(new WriteTimeoutHandler(30, TimeUnit.SECONDS)));

        return WebClient.builder()
                .baseUrl(aiServiceUrl)
                .clientConnector(new ReactorClientHttpConnector(httpClient))
                .defaultHeader("Content-Type", "application/json")
                .defaultHeader("Accept", "application/json")
                .codecs(cfg -> cfg.defaultCodecs().maxInMemorySize(10 * 1024 * 1024))
                .filter(logRequest())
                .filter(logResponse())
                .build();
    }

    @Bean
    public WebMvcConfigurer faviconConfigurer() {
        return new WebMvcConfigurer() {
            @Override
            public void addResourceHandlers(ResourceHandlerRegistry registry) {
                registry.addResourceHandler("/favicon.ico")
                        .addResourceLocations("classpath:/static/");
            }
        };
    }


    /** Log outgoing request method + URI at DEBUG level. */
    private ExchangeFilterFunction logRequest() {
        return ExchangeFilterFunction.ofRequestProcessor(req -> {
            log.debug("AI → {} {}", req.method(), req.url());
            return Mono.just(req);
        });
    }

    /** Log response status code at DEBUG (WARN on 4xx/5xx). */
    private ExchangeFilterFunction logResponse() {
        return ExchangeFilterFunction.ofResponseProcessor(resp -> {
            if (resp.statusCode().isError()) {
                log.warn("AI ← {} {}", resp.statusCode().value(), resp.statusCode());
            } else {
                log.debug("AI ← {}", resp.statusCode().value());
            }
            return Mono.just(resp);
        });
    }

    @PostConstruct
    public void initUploadDirectory() throws IOException {
        Path uploadPath = Paths.get(uploadDir).toAbsolutePath();
        if (!Files.exists(uploadPath)) {
            Files.createDirectories(uploadPath);
            log.info("Created upload directory: {}", uploadPath);
        }
    }
}
