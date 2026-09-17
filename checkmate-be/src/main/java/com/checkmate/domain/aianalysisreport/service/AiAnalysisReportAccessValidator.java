package com.checkmate.domain.aianalysisreport.service;

import com.checkmate.domain.aianalysisreport.entity.AiAnalysisReport;
import com.checkmate.domain.aianalysisreport.repository.AiAnalysisReportRepository;
import com.checkmate.domain.contract.entity.Contract;
import com.checkmate.domain.contract.repository.ContractRepository;
import com.checkmate.global.common.exception.CustomException;
import com.checkmate.global.common.exception.ErrorCode;
import com.checkmate.global.util.IdUtils;
import lombok.RequiredArgsConstructor;
import org.bson.types.ObjectId;
import org.springframework.stereotype.Service;

/**
 * AI 분석 리포트 하위 리포트(위험/개선/누락) 접근 권한 검증
 * 위험·개선·누락 리포트 서비스가 동일하게 수행하던
 * "ObjectId 변환 → 분석 리포트 조회 → 계약서 조회 → 소유자 확인" 절차를
 * 한 곳으로 모은 컴포넌트. 각 서비스는 거부 시 사용할 ErrorCode 만 넘긴다.
 */
@Service
@RequiredArgsConstructor
public class AiAnalysisReportAccessValidator {
    private final AiAnalysisReportRepository aiAnalysisReportRepository;
    private final ContractRepository contractRepository;

    /**
     * 분석 리포트 ID 문자열을 검증하고 ObjectId로 변환
     *
     * @param aiAnalysisIdHex AI 분석 리포트 ID (hex 문자열)
     * @param userId 요청한 사용자 ID
     * @param deniedCode 소유자가 아닐 때 던질 에러 코드
     * @return 검증이 끝난 AI 분석 리포트 ObjectId
     */
    public ObjectId validateAndGetId(String aiAnalysisIdHex, int userId, ErrorCode deniedCode) {
        ObjectId aiAnalysisId = IdUtils.toObjectId(aiAnalysisIdHex);
        AiAnalysisReport report = aiAnalysisReportRepository.findById(aiAnalysisId)
                .orElseThrow(() -> new CustomException(ErrorCode.AI_ANALYSIS_REPORT_NOT_FOUND));
        Contract contract = contractRepository.findById(report.getContractId())
                .orElseThrow(() -> new CustomException(ErrorCode.CONTRACT_NOT_FOUND));
        if (!contract.getUser().getUserId().equals(userId)) {
            throw new CustomException(deniedCode);
        }
        return aiAnalysisId;
    }
}