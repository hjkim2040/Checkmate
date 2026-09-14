package com.checkmate.global.config;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.MediaType;
import org.springframework.web.reactive.function.client.WebClient;

import com.checkmate.domain.aianalysisreport.dto.request.AiContractAnalysisRequestDto;
import com.checkmate.domain.question.dto.request.QuestionGenerationRequestDtp;

import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import reactor.core.publisher.Mono;

@Configuration
@RequiredArgsConstructor
@Slf4j
public class WebClientConfig {

	private final WebClient.Builder webClient;
	private final NaverApiConfig naverApiConfig;

	@Value("${fastapi.baseUrl}")
	private String analysisApiUrl;


	/**
	 * 네이버 API 호출을 위한 WebClient 생성
	 * 네이버 API 인증 헤더가 설정된 WebClient 빈 등록
	 *
	 * @return 네이버 API용 WebClient
	 */
    @Bean
    public WebClient naverWebClient() {
        return WebClient.builder()
                .baseUrl(naverApiConfig.newsUrl)
                .defaultHeader("X-Naver-Client-id", naverApiConfig.clientId)
                .defaultHeader("X-Naver-Client-Secret", naverApiConfig.clientSecret)
                .build();
    }

	/**
	 * 계약서 분석 API 호출
	 * AI 서비스에 계약서 분석 요청을 전송
	 *
	 * @param contractId 계약서 ID
	 * @param categoryId 카테고리 ID
	 * @return 요청 처리 결과를 담은 Mono 객체
	 */
	public Mono<Void> analyzeContract(int contractId, int categoryId, String categoryName) {
		AiContractAnalysisRequestDto request = AiContractAnalysisRequestDto.builder()
			.contractId(contractId)
			.contractCategoryId(categoryId)
			.contractCategoryName(categoryName)
			.build();

		return webClient.build()
			.post()
			.uri(analysisApiUrl + "/ocr")
			.contentType(MediaType.APPLICATION_JSON)
			.bodyValue(request)
			.retrieve()
			.bodyToMono(Void.class)
			.doOnSuccess(v -> log.info("계약서 분석 요청 성공: contractId={}", contractId))
			.doOnError(e -> log.error("계약서 분석 요청 실패: contractId={}, error={}", contractId, e.getMessage()))
			.onErrorComplete();
	}

	/**
	 * 계약서 질문 생성 API 호출
	 * AI 서비스에 계약서 관련 질문 생성 요청을 전송
	 *
	 * @param contractId 계약서 ID
	 * @param categoryId 카테고리 ID
	 * @return 요청 처리 결과를 담은 Mono 객체
	 */
	public Mono<Void> generateQuestions(int contractId, int categoryId, String categoryName) {
		QuestionGenerationRequestDtp request = QuestionGenerationRequestDtp.builder()
			.contractId(contractId)
			.contractCategoryId(categoryId)
			.contractCategoryName(categoryName)
			.build();

		return webClient.build()
			.post()
			.uri(analysisApiUrl + "/questions/generate")
			.contentType(MediaType.APPLICATION_JSON)
			.bodyValue(request)
			.retrieve()
			.bodyToMono(Void.class)
			.doOnSuccess(v -> log.info("계약서 질문 생성 요청 성공: contractId={}", contractId))
			.doOnError(e -> log.error("계약서 질문 생성 요청 실패: contractId={}, error={}",
				contractId, e.getMessage()))
			.onErrorComplete();
	}
}
