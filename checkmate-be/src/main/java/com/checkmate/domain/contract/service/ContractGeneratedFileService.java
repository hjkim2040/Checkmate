package com.checkmate.domain.contract.service;

import com.checkmate.domain.contract.dto.response.ContractGeneratedFileResponseDto;
import com.checkmate.domain.contract.dto.response.ContractGeneratedFileSavedEvent;
import com.checkmate.domain.contract.entity.Contract;
import com.checkmate.domain.contract.entity.ContractFile;
import com.checkmate.domain.contract.entity.EditStatus;
import com.checkmate.domain.contract.entity.FileCategory;
import com.checkmate.domain.contract.entity.QuestionGenerationStatus;
import com.checkmate.domain.contract.repository.ContractFileRepository;
import com.checkmate.domain.contract.repository.ContractRepository;
import com.checkmate.global.common.exception.CustomException;
import com.checkmate.global.common.exception.ErrorCode;
import com.checkmate.global.common.service.KeyShareMongoService;
import com.checkmate.global.common.service.S3Service;

import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;

import org.springframework.context.ApplicationEventPublisher;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.multipart.MultipartFile;

import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.List;
import java.util.Optional;

@Slf4j
@Service
@RequiredArgsConstructor
public class ContractGeneratedFileService {

    private final ContractRepository contractRepository;
    private final ContractFileRepository contractFileRepository;
    private final S3Service s3Service;
    private final KeyShareMongoService keyShareMongo;
    private final ApplicationEventPublisher applicationEventPublisher;
    private static final long MAX_FILE_SIZE = 100L * 1024 * 1024;

    /**
     * 생성된 계약서 파일 저장
     * 사용자가 작성 완료한 계약서 파일을 저장하고 계약서 상태를 업데이트
     *
     * @param userId 사용자 ID
     * @param contractId 계약서 ID
     * @param file 저장할 PDF 파일
     * @param fileName 파일명 (선택사항)
     * @return 파일 저장 결과 정보
     */
    @Transactional
    public ContractGeneratedFileResponseDto saveGeneratedFile(Integer userId, Integer contractId, MultipartFile file, String fileName) {
        log.info("saveGeneratedFile 시작: contractId={}, userId={}", contractId, userId);

        // 1. 계약서 존재 확인 및 권한 체크
        Contract contract = contractRepository.findById(contractId)
                .orElseThrow(() -> new CustomException(ErrorCode.CONTRACT_NOT_FOUND));

        // 계약서 소유자 확인
        if (!contract.getUser().getUserId().equals(userId)) {
            throw new CustomException(ErrorCode.CONTRACT_ACCESS_DENIED);
        }

        // 2. 파일 검증
        validatePdfFile(file);

        // 3. 파일명 생성 (제공되지 않은 경우)
        String finalFileName = (fileName != null && !fileName.isEmpty())
                ? fileName
                : generateFileName(contractId);

        List<S3Service.SplitEncryptedResult> splits = new ArrayList<>();

        try {
            // 4. 암호화 + 키 분할 업로드
            S3Service.SplitEncryptedResult res = s3Service.uploadEncryptedFileWithKeySplit(
                    file, S3Service.PDF_PREFIX);
            splits.add(res);

            log.info("파일 업로드 성공: {}", res.getUrl());

            // 5. 기존 파일 확인 (삭제할 필요가 있는 경우를 위해)
            Optional<ContractFile> existingFile = contractFileRepository
                    .findByContractIdAndFileCategory(contractId, FileCategory.VIEWER);

            // 기존 파일이 있으면 S3에서 삭제
            if (existingFile.isPresent()) {
                try {
                    s3Service.deleteFile(existingFile.get().getFileAddress());
                } catch (Exception e) {
                    log.warn("기존 파일 삭제 실패: {}", e.getMessage());
                }
                // DB에서도 삭제
                contractFileRepository.delete(existingFile.get());
            }

            // 6. 새 파일 생성
            ContractFile contractFile = ContractFile.builder()
                    .contract(contract)
                    .fileType("pdf")
                    .fileAddress(res.getUrl())
                    .fileCategory(FileCategory.VIEWER)
                    .encryptedDataKey(res.getShareA())
                    .iv(res.getIv())
                    .uploadAt(LocalDateTime.now())
                    .build();

            // 7. DB에 저장
            ContractFile savedFile = contractFileRepository.save(contractFile);

            // 8. MongoDB에 shareB 저장
            keyShareMongo.saveShareB(Long.valueOf(savedFile.getId()), res.getShareB());

            // 9. 계약서 상태 업데이트 - EDITING → COMPLETED
            contract.setEditStatus(EditStatus.COMPLETED);
            contract.setQuestionGenerationStatus(QuestionGenerationStatus.PENDING);
            contractRepository.save(contract);

            log.info("계약서 생성 파일 저장 및 상태 업데이트 완료: contractId={}, fileId={}, status=COMPLETED",
                    contractId, savedFile.getId());

            applicationEventPublisher.publishEvent(
                    new ContractGeneratedFileSavedEvent(
                            contractId,
                            contract.getCategory().getId(),
                            contract.getCategory().getName()
                    )
            );

            // 10. 응답 생성
            return ContractGeneratedFileResponseDto.builder()
                    .contractId(contractId)
                    .fileName(finalFileName)
                    .message("계약서 파일이 성공적으로 저장되었습니다.")
                    .build();

        } catch (Exception e) {
            log.error("파일 저장 중 오류 발생: {}", e.getMessage(), e);

            // 업로드된 암호문만 삭제 (롤백)
            splits.forEach(r -> {
                try {
                    s3Service.deleteFile(r.getUrl());
                } catch (Exception ignored) {}
            });

            throw new CustomException(ErrorCode.FILE_UPLOAD_FAILED);
        }
    }

    /**
     * PDF 파일 유효성 검사
     * 업로드된 PDF 파일의 유효성을 검증
     *
     * @param file 검증할 PDF 파일
     */
    private void validatePdfFile(MultipartFile file) {
        if (file == null || file.isEmpty()) {
            throw new CustomException(ErrorCode.FILE_NOT_FOUND);
        }

        if (file.getSize() > MAX_FILE_SIZE) {
            throw new CustomException(ErrorCode.FILE_TOO_LARGE);
        }

        String contentType = file.getContentType();
        if (contentType == null || !contentType.equals("application/pdf")) {
            throw new CustomException(ErrorCode.UNSUPPORTED_FILE_TYPE);
        }
    }

    /**
     * 파일명 생성
     * 파일명이 제공되지 않은 경우 계약서 ID와 타임스탬프를 이용해 파일명 생성
     *
     * @param contractId 계약서 ID
     * @return 생성된 파일명
     */
    private String generateFileName(Integer contractId) {
        LocalDateTime now = LocalDateTime.now();
        String timestamp = now.format(DateTimeFormatter.ofPattern("yyyyMMdd_HHmmss"));
        return "contract_" + contractId + "_" + timestamp + ".pdf";
    }
}