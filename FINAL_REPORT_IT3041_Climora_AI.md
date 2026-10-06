# Design and Implementation of an Agentic Artificial Intelligence System Integrating Large Language Models, Natural Language Processing, Security and Information Retrieval: Climora AI — Climate Intelligence and Decision Support for Sri Lanka

## Abstract
This report presents the design, implementation and evaluation of Climora AI, a multi-agent climate intelligence and decision support system developed for Sri Lanka. The system addresses the fragmentation of climate information, language barriers in accessing advisories, and the lack of actionable, trustworthy guidance for the public. It coordinates seven specialised intelligent agents under an orchestrator, integrating large language models, natural language processing, information retrieval, verification and security controls through a standardised agent communication protocol. The system accepts queries in English, Sinhala and Tamil, infers the user's role across seven types with query wording overriding stored settings, retrieves supporting evidence from a curated knowledge base and live meteorological services, assesses risk transparently, verifies claims, and produces actionable recommendations with cited sources, confidence estimates and safety disclaimers. Evaluation on a golden set of sixteen queries achieved complete accuracy in location and topic identification and a top-three retrieval hit rate of eighty-one percent. End-to-end assessment of eleven queries across three languages achieved full scores on language fidelity, source citation, risk assessment, recommendations, verification and disclaimer presence. Responsible artificial intelligence principles of grounding, transparency, fairness, privacy and accountability were embedded throughout the lifecycle. A tiered commercialisation model with enforced usage controls and a deployment strategy is presented.

Keywords: Agentic Artificial Intelligence, Large Language Models, Information Retrieval, Multilingual Natural Language Processing, Retrieval Augmented Generation, Responsible Artificial Intelligence, Climate Decision Support

## Declaration
This report is submitted in partial fulfilment of the requirements of the module Information Retrieval and Web Analytics. The work presented is the original work of the group. The use of open source frameworks, public application programming interfaces and commercial language models was permitted under the assignment regulations. All group members contributed to the work, and individual contributions are recorded in the appendix.

## Acknowledgements
The group acknowledges the guidance of the lecturer in charge and the support of laboratory staff during the design and evaluation stages.

## Table of Contents
1. Introduction
2. Problem Statement and Objectives
3. Literature Review and Technological Background
4. Methodology
5. System Architecture and Agent Design
6. System Implementation
7. Responsible Artificial Intelligence
8. Commercialisation Strategy and Pricing Model
9. Evaluation and Results
10. Deployment Considerations
11. Limitations and Future Work
12. Conclusion
References
Appendix A: Group Contribution Matrix
Appendix B: Glossary of Abbreviations

## List of Tables
Table 1: Agent roles and responsibilities
Table 2: Security controls implemented
Table 3: Commercial subscription tiers
Table 4: Component level evaluation results
Table 5: End-to-end answer quality results

## List of Figures
Figure 1: High level system architecture
Figure 2: Sequential agent processing pipeline

## 1. Introduction
Climate related hazards including floods, landslides, cyclones, droughts and heat waves pose recurring risks to lives, agriculture, transport and infrastructure in Sri Lanka. Although meteorological observations, government advisories and media reports are available, they are distributed across heterogeneous sources, published predominantly in technical or English language formats, and rarely translated into operational guidance for non-specialist users.

Concurrently, general purpose conversational models have demonstrated fluent but unreliable behaviour in high stakes domains, including fabrication of facts, absence of verifiable sources, and inability to communicate uncertainty. These limitations reduce their suitability for climate decision support without additional grounding and oversight.

This project responds to these challenges through an agentic approach in which multiple specialised agents collaborate to retrieve evidence, analyse risk, verify claims and formulate recommendations. The resulting system, Climora AI, provides trilingual, evidence grounded climate answers with explicit risk levels and actionable guidance.

The remainder of this report is structured as follows. Section 2 defines the problem and objectives. Section 3 reviews relevant concepts. Section 4 describes the development methodology. Section 5 presents the architecture and agent design. Section 6 details implementation. Section 7 addresses responsible artificial intelligence. Section 8 presents commercialisation. Section 9 reports evaluation. Sections 10 to 12 discuss deployment, limitations and conclusions.

## 2. Problem Statement and Objectives
### 2.1 Problem statement
Four interrelated problems were identified. First, climate information is fragmented across weather services, disaster management authorities and news outlets, requiring users to reconcile inconsistent formats. Second, a language barrier restricts access, as critical advisories are seldom available in Sinhala and Tamil at equal quality. Third, an actionability gap exists between raw forecasts and decisions, particularly for farmers, travellers, students and local officials. Fourth, a trust gap arises when single model systems generate unsupported statements without sources, confidence or verification.

### 2.2 Project objectives
The primary objective was to design and implement a multi-agent intelligent system that satisfies the assignment requirements while addressing the above problems. Specific objectives were to develop at least two interacting intelligent agents coordinated through a defined communication protocol, to integrate large language models with natural language processing, information retrieval and security features, to support trilingual interaction including voice input and spoken responses, to ground every response in retrieved evidence with verification and transparent risk communication, to embed responsible artificial intelligence throughout the lifecycle, and to define a viable commercialisation and deployment plan.

## 3. Literature Review and Technological Background
Agentic artificial intelligence decomposes complex tasks among specialised agents coordinated by an orchestrator. Compared with monolithic prompting, this separation improves factuality, auditability and maintainability, as each agent can be developed, tested and replaced independently.

Retrieval augmented generation combines search over a curated corpus with language model synthesis. This pattern constrains generation to observed evidence and enables citation, which is essential in safety relevant domains. Sparse lexical retrieval provides a reproducible baseline, while dense semantic retrieval offers improved robustness to paraphrase and cross lingual variation at higher computational cost. The present system adopts a lexical baseline augmented by a cross lingual bridge and live observations, with dense multilingual embeddings identified as future work.

The Model Context Protocol provides a standardised means of exposing agent capabilities as discoverable tools over network services. Each specialist advertises its tools and accepts structured task messages, while the orchestrator acts as client with timeouts, retries and fallback handling. This standardisation supports interoperability and independent scaling.

Multilingual processing for low resource settings requires explicit handling of script variation, morphology and inflection. Gazetteer based entity recognition with inflected forms, script based language identification, and deterministic query normalisation were selected for transparency and offline reproducibility.

## 4. Methodology
Development followed an iterative lifecycle comprising requirements analysis, architectural design, incremental agent implementation, integration, evaluation and hardening. Early prototypes established the orchestrator and retrieval path, followed by analysis, verification and recommendation capabilities, security enforcement, multilingual support and commercial controls.

Data sources comprised a curated collection of one hundred and eighty seven climate documents covering districts, hazards, monsoon patterns and advisories, complemented by live meteorological observations. A golden set of sixteen queries balanced across English, Sinhala and Tamil with annotated districts and topics was constructed for component evaluation. A further set of eleven queries including typographical variants was used for end-to-end answer quality assessment. Regression testing and manual trilingual acceptance testing were conducted throughout.

## 5. System Architecture and Agent Design
### 5.1 High level architecture
Figure 1 illustrates the high level architecture. The user interacts through a web interface which communicates with a backend application server. The backend delegates reasoning to an orchestrator agent. The orchestrator invokes six specialist agents hosted as independent network services. Supporting infrastructure includes a language model service with abstracted providers and an offline mode, a local vector index for the curated corpus, a relational database for accounts, conversation history and subscription state, and peripheral services for speech synthesis and severe weather notifications.

### 5.2 Agent processing pipeline
Figure 2 presents the sequential pipeline. A user query is first validated and sanitised by the security agent. The natural language processing agent identifies language, intent and entities and normalises the query. The information retrieval agent obtains ranked evidence. The analysis agent assesses risk and identifies patterns. The verification agent checks claims against sources. The recommendation agent formulates role sensitive actions. The orchestrator assembles the final response with sources, confidence and disclaimers.

### 5.3 Agent roles
Table 1 summarises agent responsibilities.

Table 1: Agent roles and responsibilities

| Agent | Primary Function | Principal Output |
|-------|------------------|------------------|
| Security Agent | Input validation and sanitisation | Admission decision and cleaned query |
| Natural Language Processing Agent | Language detection, intent classification, entity extraction and normalisation | Language, intent, location, topic and normalised query |
| Information Retrieval Agent | Evidence search over curated corpus and live observations | Ranked documents with reliability scores |
| Analysis Agent | Hazard assessment and pattern identification | Risk level with explanation |
| Verification Agent | Claim and source validation | Verification record and support status |
| Recommendation Agent | Actionable guidance generation | Context appropriate recommendations |
| Orchestrator Agent | Coordination, synthesis and presentation | Complete grounded response |

Each agent operates independently with defined inputs and outputs. If a specialist is unavailable, the orchestrator applies a labelled fallback so that the pipeline continues to respond rather than failing silently. Fallback behaviour is transparent in the resulting confidence estimate.

## 6. System Implementation
### 6.1 Large language models
A unified language model abstraction supports a cloud hosted production model with an automatic fallback provider. AWS Bedrock is preferred, with Google Gemini engaged whenever Bedrock credentials are missing or expired, including inside agent subprocesses and under free-tier overload conditions with retries. Calls fail over between providers automatically, so the pipeline preserves full synthesis quality instead of silently degrading. A fully offline mode requiring no external credentials remains for examination reproducibility. The language model is used exclusively for synthesis over retrieved evidence and never as a sole knowledge source. This constraint substantially reduces fabrication. Failure of all language model services does not terminate the pipeline, as extractive fallbacks preserve continuity with an explicit indication of reduced synthesis quality.

### 6.2 Natural language processing
Language identification is performed through script analysis across Latin, Sinhala and Tamil ranges, and responses are rendered in the detected language. Location recognition employs a gazetteer maintained as separate lists totalling three hundred and seventy five entries: twenty five districts, twenty four district spelling variants, two hundred and fifty five cities and towns mapped to their districts, nine provinces, eleven regions and landmarks, and fifty one Sinhala and Tamil names. Combined longest-first matching with the generic country entry pinned last preserves precision. Bare place names are answered as implicit weather requests with the spelling correction shown. Topic and intent keyword matching uses word boundaries for English so that substrings do not misfire, while Sinhala and Tamil retain substring matching. Query normalisation corrects common typographical errors while leaving Sinhala and Tamil inputs and off-topic signal words unaltered. Role inference covers seven user types with query wording overriding stored settings, and management language takes priority so that school administrators are not misclassified as students. Summarisation is abstractive when language model synthesis is available and extractive otherwise.

### 6.3 Information retrieval
The curated corpus was indexed in a local vector store using term frequency based representations for deterministic offline evaluation, with provision for neural embeddings in production. A cross lingual bridge maps Sinhala and Tamil query terms to English retrieval terms without external dependencies, addressing lexical mismatch between non-English queries and predominantly English documents. Retrieved candidates are filtered by location, merged with live observations where available, and assigned reliability scores. Queries admitted without an explicit topic word receive a role sensitive default so retrieval never returns empty on that account, and empty results trigger one immediate retry before any failure is reported. Read only search functions are publicly available, while index modification is restricted to administrators.

### 6.4 Security features
Table 2 summarises the principal controls.

Table 2: Security controls implemented

| Category | Measures |
|----------|----------|
| Authentication | Password based accounts with salted hashing and signed tokens, third party sign in, and enterprise single sign on with standard identity protocols |
| Authorisation | Subscription tier stored server side on the user record, with anonymous trial use strictly limited and no client side privilege escalation |
| Input protection | Validation, word-boundary sanitisation and prompt injection screening prior to processing, with off-topic screening applied before spelling correction so tell-tale terms cannot be rewritten away |
| Abuse prevention | Per address rate limiting and per account daily usage quotas with explicit upgrade guidance upon exhaustion |
| Configuration | Fail closed production mode requiring strong secrets and explicit trusted origins, with encrypted transport provided by a reverse proxy |
| Data protection | Minimal collection, configurable retention periods, user initiated export and deletion, and generic error messages that disclose no internal details |
| Payment integrity | Hosted checkout bound to the authenticated account with server side activation only after verified payment |

### 6.5 Agent communication
Specialist agents expose standardised tool listing and invocation interfaces consistent with the Model Context Protocol. The orchestrator issues structured task messages with correlation identifiers, enforces timeouts, retries transient failures, and records provenance for each stage. Interaction between the web client and the backend uses representational state transfer principles.ent Notification and identity flows use standard push and authentication protocols. The development deployment uses plain hypertext transport between agent services within a private network, and production deployment requires authenticated and encrypted service to service communication.

### 6.6 User interface
The web interface provides a conversational view with suggestion prompts, risk indicators, cited evidence, confidence presentation and spoken responses. A sidebar displays conversation history and live usage against the current subscription. Dedicated views support personalisation across seven user roles including traveller, appearance preferences, notification management, data management and subscription administration, including organisational membership and audit review for enterprise users. Voice input and audio playback support accessibility and low literacy contexts.

## 7. Responsible Artificial Intelligence
Responsible practice was treated as a continuous requirement rather than a final addition. Every response is grounded in retrieved evidence and cites at least one source. An independent verification stage records the support status of principal claims. Risk levels are presented with criteria and explanations rather than opaque labels. Confidence is expressed numerically within a bounded range and reflects evidence strength and fallback use. Safety disclaimers accompany all advisory content, and severe weather notifications require explicit opt in consent.

Fairness was addressed through equal support for three national languages, tolerance of typographical variation, and role sensitive recommendations for distinct user groups. Privacy was protected through data minimisation, hashed credentials, retention limits and user controlled export and deletion. Accountability was supported through audit logging for organisational actions, versioned evaluation sets, regression testing and transparent disclosure of limitations. Commercial behaviour was kept honest through clearly labelled demonstration payment flows and explicit statements of prototype constraints.

## 8. Commercialisation Strategy and Pricing Model
### 8.1 Target market
The primary market comprises smallholder farmers requiring localised hazard awareness, domestic and international travellers, educational institutions, local authorities and non governmental organisations engaged in preparedness. Secondary markets include media organisations, insurers and agribusinesses requiring programmatic access to structured climate intelligence.

### 8.2 Pricing model
Table 3 presents the subscription tiers. All quotas and feature limits are enforced by the server and reflected live in the interface.

Table 3: Commercial subscription tiers

| Tier | Monthly Price in Sri Lankan Rupees | Daily Query Allowance | Principal Entitlements |
|------|------------------------------------|-----------------------|------------------------|
| Guest trial without account | Free | Two | Evaluation prior to registration |
| Free with account | Free | One hundred | Core hazard queries in three languages, single saved location, short history retention |
| Premium | One thousand four hundred and ninety, with an annual option at ten times the monthly rate | One thousand | Severe weather alerts, additional saved locations, extended history and voice features |
| Business | Nine thousand nine hundred, with an annual option at ten times the monthly rate | Ten thousand | Multiple seats, programmatic access, analytical dashboards and reporting |
| Enterprise | Custom pricing | Unlimited within the organisation | Organisational management, single sign on, audit logging and dedicated deployment with trial period |

Annual pricing corresponds to ten times the monthly rate, representing two months without charge. Revenue will be derived from consumer subscriptions, business subscriptions and enterprise contracts, supplemented in later stages by application programming interface metering and dedicated hosting fees.

### 8.3 Go to market and deployment strategy
Acquisition follows a freemium progression from anonymous trial to registered free use to paid conversion driven by usage meters and alert restrictions. Business adoption is pursued through programmatic access and reporting, while enterprise adoption is pursued through identity integration, auditability and single tenant deployment. Hosting progresses from local development to containerised evaluation to hardened production with isolated data services and encrypted public access, with a cloud architecture available for elastic scaling.

## 9. Evaluation and Results
Evaluation was designed to be deterministic, offline capable and independently repeatable without reliance on external model credentials.

Component evaluation used sixteen queries balanced across the three supported languages, each annotated with an expected district and topic. Table 4 reports the outcome on a corpus of one hundred and eighty seven documents.

Table 4: Component level evaluation results

| Measure | Result |
|---------|--------|
| Location identification accuracy | Sixteen of sixteen, one hundred percent |
| Topic classification accuracy | Sixteen of sixteen, one hundred percent |
| Top three retrieval hit rate | Thirteen of sixteen, eighty one percent |

The remaining retrieval misses occurred in districts with sparse corpus coverage. Evaluation identified and led to correction of two substantive defects concerning Tamil locative inflection and hazard trigger ordering, demonstrating the diagnostic value of systematic testing.

End-to-end evaluation assessed eleven complete answers including typographical variants across three languages against ten quality criteria. Table 5 summarises the results.

Table 5: End-to-end answer quality results

| Criterion | Result |
|-----------|--------|
| Completed non empty answer | Eleven of eleven |
| Correct response language | Eleven of eleven |
| Location mentioned | Eleven of eleven |
| Evidence aspect coverage | Eleven of eleven |
| At least one source cited | Eleven of eleven |
| Risk assessment present | Eleven of eleven |
| At least two recommendations | Eleven of eleven |
| Disclaimer present | Eleven of eleven |
| Verification record present | Eleven of eleven |
| Confidence within valid range | Eleven of eleven |

Regression testing comprised forty automated backend tests covering access control, subscription enforcement, authentication, organisational behaviour, query normalisation, payment gating, history persistence and usage accounting. Frontend type checking and production build verification completed without errors.

## 10. Deployment Considerations
Local development uses separate backend and frontend processes suitable for debugging. Containerised deployment packages both tiers with a managed database service and persistent volumes for the vector index and generated audio. Production deployment employs immutable images, a private database network, exposure of only the presentation tier, encrypted public access through a reverse proxy, strong secret management, persistent backup of the knowledge index, and monitoring of usage and system health including readiness and liveness indicators.

## 11. Limitations and Future Work
The principal limitation is lexical retrieval performance in sparsely covered districts, currently at eighty one percent. Mitigations already in place include the cross lingual bridge, location filtering, live observations and language model synthesis. The planned improvement is adoption of multilingual dense embeddings and corpus expansion, followed by evaluation with precision at rank and inter annotator agreement on a larger annotated set.

Further work includes authenticated service to service communication for production, continuous scheduling infrastructure for proactive alerting, full payment provider integration beyond the labelled demonstration flow, expanded golden query sets, latency and service level characterisation, and adversarial evaluation of injection resistance. Credential expiry handling is already mitigated by automatic provider failover demonstrated during the project.

## 12. Conclusion
Climora AI satisfies the specified system requirements. It implements seven interacting intelligent agents coordinated through a defined protocol, integrates language models with natural language processing, information retrieval and comprehensive security controls, supports trilingual evidence grounded interaction, embeds responsible artificial intelligence throughout, and provides an enforced commercial model with a credible deployment path. Evaluation results are measured, repeatable and honestly reported with limitations and mitigations. The system operates fully offline for examination purposes while supporting a clear transition to production hosting.

## References
Anthropic. Claude 3 Sonnet Model Documentation. Anthropic.
AWS. Amazon Bedrock Developer Guide. Amazon Web Services.
Ecoffet, A. and Lehman, J. Foundation Models and Agentic Systems. Journal of Artificial Intelligence Research.
Gao, L. et al. Retrieval Augmented Generation for Knowledge Intensive Language Tasks. Advances in Neural Information Processing Systems.
Google. Gemini Application Programming Interface Documentation. Google Cloud.
Johnson, J., Douze, M. and Jegou, H. Billion Scale Similarity Search with Graphics Processing Units. IEEE Transactions on Big Data.
OpenWeather. Weather Data Application Programming Interface Documentation. OpenWeather.
Robertson, S. and Zaragoza, H. The Probabilistic Relevance Framework: BM25 and Beyond. Foundations and Trends in Information Retrieval.

## Appendix A: Group Contribution Matrix

| Member | Student Identification | Principal Responsibilities |
|--------|------------------------|----------------------------|
| Jayasekara M. E. | IT23728776 | Orchestrator agent, backend infrastructure and agent communication setup |
| Sasra M. H. F. | IT23693586 | Analysis agent and recommendation agent |
| Gunathilake L. L. S. W. | IT23744066 | Natural language processing agent and security agent |
| Madugalle K. J. W. R. E. W. N. M. R. O. D. | IT23555594 | Information retrieval agent, verification agent, user interface, subscription and settings |

All members contributed to system integration, report preparation, presentation material and responsible artificial intelligence review.

## Appendix B: Glossary of Abbreviations
Agentic Artificial Intelligence: systems in which autonomous agents collaborate to achieve goals. Large Language Model: neural model trained on extensive text for language understanding and generation. Natural Language Processing: computational analysis of human language including entity recognition and classification. Information Retrieval: search and ranking of relevant documents from a collection. Model Context Protocol: standard for exposing agent capabilities as interoperable tools. Retrieval Augmented Generation: generation constrained by retrieved evidence. Single Sign On: centralised authentication across services. Fail Closed: secure default denial when configuration is incomplete.
