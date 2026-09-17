package com.checkmate.domain.contract.service;

import com.checkmate.domain.contract.dto.request.ContractUploadsRequest;
import com.checkmate.domain.contract.dto.request.SignatureRequest;
import com.checkmate.domain.contract.dto.response.*;
import com.checkmate.domain.contract.entity.*;
import com.checkmate.domain.contract.repository.ContractRepository;
import com.checkmate.domain.contractcategory.entity.ContractCategory;
import com.checkmate.domain.contractcategory.service.ContractCategoryService;
import com.checkmate.domain.template.dto.response.TemplateResponseDto;
import com.checkmate.domain.template.service.TemplateService;
import com.checkmate.domain.user.entity.User;
import com.checkmate.domain.user.service.UserService;
import com.checkmate.global.common.exception.CustomException;
import com.checkmate.global.common.exception.ErrorCode;
import com.checkmate.global.common.service.S3Service;
import com.dropbox.sign.api.SignatureRequestApi;
import com.dropbox.sign.model.SignatureRequestResponse;
import com.dropbox.sign.model.SignatureRequestSendRequest;
import com.dropbox.sign.model.SubSignatureRequestSigner;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.ApplicationEventPublisher;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.io.InputStream;
import java.io.OutputStream;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

@Slf4j
@Service
@RequiredArgsConstructor
public class ContractService {

    private final UserService userService;
    private final ContractCategoryService categoryService;
    private final ContractFileService contractFileService;
    private final ContractRepository contractRepository;
    private final TemplateService templateService;
    private final SignatureRequestApi signatureRequestApi;
    private final S3Service s3Service;
    private final ApplicationEventPublisher applicationEventPublisher;

    @Value("${hs.client.id:}")
    private String clientId;

    /**
     * 계약서 업로드
     * 계약서를 업로드하고 분석 이벤트를 발행
     *
     * @param userId 사용자 ID
     * @param request 계약서 업로드 요청 정보
     * @return 업로드된 계약서 정보
     */
    @Transactional
    public ContractUploadResponse uploadContract(Integer userId, ContractUploadsRequest request) {

        User user = userService.findUserById(userId);
        ContractCategory category = categoryService.findContractCategoryById(request.getCategoryId());

        Contract contract = Contract.builder()
                .user(user)
                .category(category)
                .title(request.getTitle())
                .editStatus(EditStatus.COMPLETED)
                .sourceType(SourceType.USER_UPLOAD)
                .signatureStatus(SignatureStatus.PENDING)
                .questionGenerationStatus(QuestionGenerationStatus.PENDING)
                .build();
        contract = contractRepository.save(contract);

        FileNumberResponse response = contractFileService.uploadContractFiles(contract, request.getFiles());
        contract.setPageNo(response.getPageNo());

        // 트랜잭션 완료 후 분석 이벤트 발행
        applicationEventPublisher.publishEvent(
            new ContractUploadCompletedEvent(contract.getId(), category.getId(), category.getName())
        );

        return ContractUploadResponse.builder()
                .contractId(contract.getId())
                .title(contract.getTitle())
                .createdAt(contract.getCreatedAt())
                .build();

    }

    /**
     * 내 계약서 목록 조회
     * 사용자의 모든 계약서 목록 조회
     *
     * @param userId 사용자 ID
     * @return 사용자의 계약서 목록
     */
    @Transactional(readOnly = true)
    public List<MyContractResponse> getMyContracts(Integer userId) {

        User user = userService.findUserById(userId);

        List<Contract> contracts = contractRepository.findAllByUser(user);

        return contracts.stream()
                .map(contract -> MyContractResponse.builder()
                        .contractId(contract.getId())
                        .categoryId(contract.getCategory().getId())
                        .title(contract.getTitle())
                        .sourceType(contract.getSourceType())
                        .editStatus(contract.getEditStatus())
                        .updatedAt(contract.getUpdatedAt())
                        .build()
                )
                .collect(Collectors.toList());
    }

    /**
     * 내 계약서 삭제
     * 특정 계약서와 관련 파일을 삭제
     *
     * @param userId 사용자 ID
     * @param contractId 삭제할 계약서 ID
     */
    @Transactional
    public void deleteMyContract(int userId, Integer contractId) {
        Contract contract = contractRepository.findById(contractId)
                .orElseThrow(() -> new CustomException(ErrorCode.CONTRACT_NOT_FOUND));

        if (!contract.getUser().getUserId().equals(userId)) {
            throw new CustomException(ErrorCode.CONTRACT_ACCESS_DENIED);
        }

        contract.getFiles().forEach(file -> contractFileService.deleteFileByAddress(file.getFileAddress()));

        contractRepository.deleteById(contractId);
    }

    /**
     * 계약서 상세 정보 조회
     * 계약서 ID로 계약서 템플릿 구조와 저장된 값을 함께 조회
     *
     * @param userId 사용자 ID
     * @param contractId 계약서 ID
     * @return 계약서 템플릿 구조와 저장된 값
     */
    @Transactional(readOnly = true)
    public ContractDetailsResponseDto getContractWithTemplateAndValues(Integer userId, Integer contractId) {

        Contract contract = contractRepository.findById(contractId)
                .orElseThrow(() -> new CustomException(ErrorCode.CONTRACT_NOT_FOUND));

        if (!contract.getUser().getUserId().equals(userId)) {
            throw new CustomException(ErrorCode.CONTRACT_ACCESS_DENIED);
        }

        // 템플릿 응답 정보 조회 (기존 서비스 활용)
        TemplateResponseDto templateResponse = templateService.getTemplate(contract.getTemplate().getId());

        Map<String, Object> valueMap = new HashMap<>();
        contract.getFieldValues().forEach(fieldValue ->
                valueMap.put(fieldValue.getField().getFieldKey(), fieldValue.getValue())
        );

        // 통합 응답 생성
        return ContractDetailsResponseDto.builder()
                .contract(TemplateResponseDto.ContractDto.builder()
                        .id(contract.getId())
                        .build())
                .template(templateResponse.getTemplate())
                .sections(templateResponse.getSections())
                .values(valueMap)
                .build();
    }

    /**
     * 계약서 전자서명 업로드 및 요청
     * 계약서 파일을 서명 서비스에 업로드하고 서명 요청 처리
     *
     * @param userId 사용자 ID
     * @param contractId 계약서 ID
     * @param signer 서명자 정보
     * @return 서명 요청 결과 정보
     */
    @Transactional
    public ContractSignatureUploadResponse uploadAndRequestSignature(
            Integer userId,
            Integer contractId,
            SignatureRequest signer
    ) throws Exception {

        if (contractRepository.existsByIdAndSignatureStatus(contractId, SignatureStatus.COMPLETED)) {
            throw new CustomException(ErrorCode.CONTRACT_ALREADY_SIGNED);
        }

        PdfMetadata meta = contractFileService.loadViewerPdfMetadata(userId, contractId);

        InputStream decrypted = s3Service.getDecryptedStream(
                meta.getFileUrl().split("\\?")[0].replaceFirst("https://[^/]+/", ""),
                meta.getIv(),
                meta.getShareA(),
                meta.getFileId()
        );

        Path tempPdf = Files.createTempFile("hs-sign-", ".pdf");
        try (OutputStream os = Files.newOutputStream(tempPdf)) {
            byte[] buffer = new byte[4096];
            int len;
            while ((len = decrypted.read(buffer)) != -1) {
                os.write(buffer, 0, len);
            }
        }

        SignatureRequestSendRequest sendRequest = new SignatureRequestSendRequest()
                .testMode(true)
                .clientId(clientId)
                .addFilesItem(tempPdf.toFile())
                .addSignersItem(new SubSignatureRequestSigner()
                        .name(signer.getName())
                        .emailAddress(signer.getEmail())
                        .order(0)
                );

        SignatureRequestResponse signatureResponse = signatureRequestApi
                .signatureRequestSend(sendRequest)
                .getSignatureRequest();
        String requestId = signatureResponse.getSignatureRequestId();

        Contract contract = contractRepository.findById(contractId)
                .orElseThrow(() -> new CustomException(ErrorCode.CONTRACT_NOT_FOUND));
        contract.setSignatureRequestId(requestId);
        contract.setSignatureStatus(SignatureStatus.PENDING);
        contractRepository.save(contract);

        Files.deleteIfExists(tempPdf);

        return ContractSignatureUploadResponse.builder()
                .contractId(contract.getId())
                .createdAt(contract.getCreatedAt())
                .signatureRequestId(requestId)
                .build();
    }

}
