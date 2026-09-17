package com.checkmate.global.config;


import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.scheduling.annotation.EnableAsync;
import org.springframework.scheduling.concurrent.ThreadPoolTaskExecutor;
import org.springframework.web.reactive.function.client.WebClient;

@Configuration
@EnableAsync
public class AsyncConfig {

    /**
     * ClamAV 바이러스 검사용 스레드 풀 설정
     * 파일 업로드 시 멀웨어 검사를 위한 전용 스레드 풀
     *
     * @return 설정된 ThreadPoolTaskExecutor
     */
    @Bean(name = "clamavExecutor")
    public ThreadPoolTaskExecutor clamavExecutor() {
        ThreadPoolTaskExecutor executor = new ThreadPoolTaskExecutor();
        executor.setCorePoolSize(10);
        executor.setMaxPoolSize(50);
        executor.setQueueCapacity(500);
        executor.setThreadNamePrefix("clamav-");
        executor.setKeepAliveSeconds(120);
        executor.initialize();
        return executor;
    }

    /**
     * WebClient 빌더 설정
     * 비동기 HTTP 요청을 위한 WebClient 빌더 제공
     *
     * @return WebClient.Builder 인스턴스
     */
    @Bean
    public WebClient.Builder webClient() {
        return WebClient.builder();
    }
}
