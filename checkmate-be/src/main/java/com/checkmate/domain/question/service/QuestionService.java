package com.checkmate.domain.question.service;

import java.util.Collections;
import java.util.List;
import java.util.stream.Collectors;

import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import com.checkmate.domain.contract.entity.Contract;
import com.checkmate.domain.contract.entity.QuestionGenerationStatus;
import com.checkmate.domain.contract.repository.ContractRepository;
import com.checkmate.domain.question.dto.response.QuestionResponseDto;
import com.checkmate.domain.question.dto.response.QuestionResultDto;
import com.checkmate.domain.question.entity.Question;
import com.checkmate.domain.question.repository.QuestionRepository;
import com.checkmate.global.common.exception.CustomException;
import com.checkmate.global.common.exception.ErrorCode;

import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;

@Slf4j
@Service
@RequiredArgsConstructor
public class QuestionService {
	private final QuestionRepository questionRepository;
	private final ContractRepository contractRepository;

	/**
	 * 각 계약서에 해당하는 질문 리스트를 데이터베이스에서 조회
	 *
	 * @param contractId 계약서 ID
	 * @param userId 유저 ID
	 * @return 질문 리스트 DTO
	 */
	@Transactional(readOnly = true)
	public QuestionResultDto getQuestions(int contractId, int userId) {
		Contract contract = contractRepository.findById(contractId)
			.orElseThrow(() -> new CustomException(ErrorCode.CONTRACT_NOT_FOUND));
		if (!contract.getUser().getUserId().equals(userId)) {
			throw new CustomException(ErrorCode.QUESTION_LIST_ACCESS_DENIED);
		}
		QuestionGenerationStatus status = contract.getQuestionGenerationStatus();
		if (status == QuestionGenerationStatus.PENDING) {
			// 생성 진행 중인 경우
			return QuestionResultDto.builder()
				.status("pending")
				.message("질문이 생성 중입니다. 잠시 후 다시 시도해주세요.")
				.questions(Collections.emptyList())
				.build();
		} else if (status == QuestionGenerationStatus.FAILED) {
			// 생성 실패한 경우
			return QuestionResultDto.builder()
				.status("failed")
				.message("질문 생성에 실패했습니다.")
				.questions(Collections.emptyList())
				.build();
		}

		// 생성 완료된 경우 (COMPLETED)
		List<Question> questions = questionRepository.findAllByContractId(contractId);
		List<QuestionResponseDto> questionDtos = questions.stream()
			.map(QuestionResponseDto::fromEntity)
			.collect(Collectors.toList());

		return QuestionResultDto.builder()
			.status("completed")
			.message("질문 생성이 완료되었습니다.")
			.questions(questionDtos)
			.build();
	}
}
