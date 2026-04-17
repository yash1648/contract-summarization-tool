package com.grim.backend.repository;

import com.grim.backend.model.Contract;
import org.springframework.data.mongodb.repository.MongoRepository;
import org.springframework.data.mongodb.repository.Query;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.Optional;

/**
 * Spring Data MongoDB repository for Contract documents.
 *
 * MongoRepository provides built-in CRUD:
 *   save(), findById(), findAll(), deleteById(), count(), existsById()
 *
 * Custom queries below use Spring Data derived query methods or
 * explicit @Query annotations with MongoDB JSON syntax.
 */
@Repository
public interface ContractRepository extends MongoRepository<Contract, String> {

    /** All contracts ordered newest first */
    List<Contract> findAllByOrderByCreatedAtDesc();

    /** Look up by exact original filename */
    Optional<Contract> findByFileName(String fileName);

    /** All contracts in a given processing state */
    List<Contract> findByStatus(Contract.ProcessingStatus status);

    /**
     * Contracts that have been chunked but not yet sent to the AI service.
     * Used by a future scheduled job to retry pending analyses.
     */
    List<Contract> findByStatusOrderByCreatedAtAsc(Contract.ProcessingStatus status);

    /** Contracts that completed analysis (have a linked analysis result) */
    @Query("{ 'analysisResultId': { $ne: null }, 'status': 'COMPLETED' }")
    List<Contract> findCompletedContracts();

    /** Count by status — used on the dashboard */
    long countByStatus(Contract.ProcessingStatus status);

    /** Check if a file has already been uploaded (by name) */
    boolean existsByFileName(String fileName);
}
