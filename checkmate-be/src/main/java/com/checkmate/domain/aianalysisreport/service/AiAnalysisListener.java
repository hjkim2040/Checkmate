package com.checkmate.domain.aianalysisreport.service;

import com.checkmate.domain.contract.dto.response.ContractGeneratedFileSavedEvent;
import org.springframework.stereotype.Component;
import org.springframework.transaction.event.TransactionPhase;
import org.springframework.transaction.event.TransactionalEventListener;

import com.checkmate.domain.contract.dto.response.ContractUploadCompletedEvent;
import com.checkmate.global.config.WebClientConfig;

import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;

@Component
@RequiredArgsConstructor
@Slf4j
public class AiAnalysisListener {
	private final WebClientConfig webClientConfig;

	/**
	 * 계약서 업로드 완료 이벤트 처리
	 * 트랜잭션 커밋 후 비동기적으로 계약서 분석 요청을 처리
	 *
	 * @param event 계약서 업로드 완료 이벤트 (계약서 ID, 계약서 카테고리 ID 포함)
	 */
	@TransactionalEventListener(phase = TransactionPhase.AFTER_COMMIT)
	public void handleContractUploaded(ContractUploadCompletedEvent event) {
		log.info("계약서 업로드 완료 이벤트 수신: contractId={}", event.contractId());
		webClientConfig.analyzeContract(
				event.contractId(),
				event.contractCategoryId(),
				event.contractCategoryName()
		).subscribe();
	}

	/**
	 * 생성 계약서 파일 저장 완료 이벤트 처리
	 * 트랜잭션 커밋 후 비동기적으로 질문 생성 요청을 처리
	 *
	 * @param event 생성 파일 저장 완료 이벤트
	 */
	@TransactionalEventListener(phase = TransactionPhase.AFTER_COMMIT)
	public void handleGeneratedFileSaved(ContractGeneratedFileSavedEvent event) {
		log.info("생성 계약서 저장 완료 이벤트 수신: contractId={}", event.contractId());
		webClientConfig.generateQuestions(
				event.contractId(),
				event.contractCategoryId(),
				event.contractCategoryName()
		).subscribe();
	}
}
