package com.checkmate.domain.missingclausereport.service;

import java.util.List;
import java.util.stream.Collectors;

import com.checkmate.domain.aianalysisreport.service.AiAnalysisReportAccessValidator;
import org.bson.types.ObjectId;
import org.springframework.stereotype.Service;

import com.checkmate.domain.missingclausereport.dto.response.MissingResponseDto;
import com.checkmate.domain.missingclausereport.entity.MissingClauseReport;
import com.checkmate.domain.missingclausereport.repository.MissingClauseReportRepository;
import com.checkmate.global.common.exception.CustomException;
import com.checkmate.global.common.exception.ErrorCode;

import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;

@Slf4j
@Service
@RequiredArgsConstructor
public class MissingClauseReportService {
	private final MissingClauseReportRepository missingClauseReportRepository;
	private final AiAnalysisReportAccessValidator accessValidator;

	/**
	 * 각 ai 분석 리포트에 해당되는 누락 사항 리포트를 데이터베이스에서 조회
	 *
	 * @param aiAnalysisIdHex ai 분석 리포트 ID
	 * @param userId 유저 ID
	 * @return 누락 사항 리포트 DTO 리스트
	 */
	public List<MissingResponseDto> getMissingClauseReportByAiAnalysisId(String aiAnalysisIdHex, int userId) {
		ObjectId aiAnalysisId = accessValidator.validateAndGetId(aiAnalysisIdHex, userId,
				ErrorCode.MISSING_REPORT_ACCESS_DENIED);
		List<MissingClauseReport> missingClauseReport = missingClauseReportRepository
			.findAllByAiAnalysisReportId(aiAnalysisId);
		if (missingClauseReport.isEmpty()) {
			throw new CustomException(ErrorCode.MISSING_REPORT_NOT_FOUND);
		}
		return missingClauseReport.stream()
			.map(MissingResponseDto::fromEntity)
			.collect(Collectors.toList());
	}
}
