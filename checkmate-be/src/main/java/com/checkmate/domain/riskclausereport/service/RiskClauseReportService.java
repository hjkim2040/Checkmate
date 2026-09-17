package com.checkmate.domain.riskclausereport.service;

import java.util.List;
import java.util.stream.Collectors;

import com.checkmate.domain.aianalysisreport.service.AiAnalysisReportAccessValidator;
import org.bson.types.ObjectId;
import org.springframework.stereotype.Service;

import com.checkmate.domain.riskclausereport.dto.response.RiskClauseReportResponseDto;
import com.checkmate.domain.riskclausereport.entity.RiskClauseReport;
import com.checkmate.domain.riskclausereport.repository.RiskClauseReportRepository;
import com.checkmate.global.common.exception.CustomException;
import com.checkmate.global.common.exception.ErrorCode;

import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;

@Slf4j
@Service
@RequiredArgsConstructor
public class RiskClauseReportService {
	private final RiskClauseReportRepository riskClauseReportRepository;
	private final AiAnalysisReportAccessValidator accessValidator;

	/**
	 * 각 ai 분석 리포트에 해당되는 위험 사항 리포트를 데이터베이스에서 조회
	 *
	 * @param aiAnalysisIdHex ai 분석 리포트 ID
	 * @param userId 유저 ID
	 * @return 위험 사항 리포트 DTO 리스트
	 */
	public List<RiskClauseReportResponseDto> getRiskClauseReportsByAnalysisId(String aiAnalysisIdHex, int userId) {
		ObjectId aiAnalysisId = accessValidator.validateAndGetId(aiAnalysisIdHex, userId, ErrorCode.RISK_ACCESS_DENIED);
		List<RiskClauseReport> risks = riskClauseReportRepository.findAllByAiAnalysisReportId(aiAnalysisId);
		if (risks.isEmpty()) {
			throw new CustomException(ErrorCode.RISK_NOT_FOUND);
		}
		return risks.stream()
			.map(RiskClauseReportResponseDto::fromEntity)
			.collect(Collectors.toList());
	}
}
