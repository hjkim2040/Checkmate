package com.checkmate.domain.chatbot.service;

import java.util.List;
import java.util.Map;

import org.springframework.ai.chat.messages.SystemMessage;
import org.springframework.ai.chat.messages.UserMessage;
import org.springframework.ai.chat.model.ChatModel;
import org.springframework.ai.chat.prompt.Prompt;
import org.springframework.ai.chat.prompt.PromptTemplate;
import org.springframework.stereotype.Service;

import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import reactor.core.publisher.Mono;

@Service
@Slf4j
@RequiredArgsConstructor
public class OpenAIService {
	private final ChatModel chatModel;

	/**
	 * 응답 생성
	 *
	 * @param userMessage 유저가 보낸 메세지
	 * @return openai api로 요청 보내기
	 */
	public Mono<String> generateResponse(String userMessage) {
		// 시스템 프롬프트 템플릿 생성
		PromptTemplate systemPromptTemplate = PromptTemplate.builder()
			.template("당신은 {role} 전문 AI입니다. 답변은 {style} 제공하세요.")
			.variables(Map.of(
				"role", "법률",
				"style", "간결하고 일반인도 이해하기 쉽게"
			))
			.build();

		// 시스템 메시지 생성
		SystemMessage systemMessage = new SystemMessage(systemPromptTemplate.render());

		// 사용자 메시지
		UserMessage userMsg = new UserMessage(userMessage);

		// 프롬프트 구성
		Prompt prompt = new Prompt(List.of(systemMessage, userMsg));

		// stream()으로 Non-blocking 호출 후, 모든 스트림 조각을 하나의 문자열로 합침
		return chatModel.stream(prompt)
				.map(chatResponse -> {
					var output = chatResponse.getResult().getOutput().getText();
					return output != null ? output : "";
				})
				.reduce("", (acc, text) -> acc + text);
	}
}
