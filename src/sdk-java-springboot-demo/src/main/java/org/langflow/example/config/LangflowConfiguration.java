package org.langflow.example.config;

import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration
@EnableConfigurationProperties(LangflowProperties.class)
public class LangflowConfiguration {
    @Bean(destroyMethod = "close")
    org.langflow.sdk.v1.LangflowClient langflowV1Client(LangflowProperties p) {
        return org.langflow.sdk.v1.LangflowClient.builder(p.host(), p.port())
                .scheme(p.scheme()).apiKey(p.apiKey())
                .connectTimeout(p.timeout().connect()).readTimeout(p.timeout().read())
                .writeTimeout(p.timeout().write()).callTimeout(p.timeout().call()).build();
    }

    @Bean(destroyMethod = "close")
    org.langflow.sdk.v2.LangflowClient langflowV2Client(LangflowProperties p) {
        return org.langflow.sdk.v2.LangflowClient.builder(p.host(), p.port())
                .scheme(p.scheme()).apiKey(p.apiKey())
                .connectTimeout(p.timeout().connect()).readTimeout(p.timeout().read())
                .writeTimeout(p.timeout().write()).callTimeout(p.timeout().call()).build();
    }
}
