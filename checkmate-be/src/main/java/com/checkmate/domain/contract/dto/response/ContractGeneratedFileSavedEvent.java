package com.checkmate.domain.contract.dto.response;

public record ContractGeneratedFileSavedEvent(
        int contractId,
        int contractCategoryId,
        String contractCategoryName
) {}