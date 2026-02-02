"""
Korean stopwords for keyword extraction filtering.
Includes common Korean particles, conjunctions, and low-information words.
Also includes tech term lists for boosting relevant keywords.
"""

# Tech terms to prioritize (English)
TECH_TERMS = {
    # AI/ML
    "AI", "ML", "LLM", "GPT", "NLP", "AGI", "ASI",
    "ChatGPT", "Claude", "Gemini", "Copilot",
    "OpenAI", "Anthropic", "DeepMind", "Meta", "Google", "Microsoft",
    "DeepSeek", "Mistral", "Llama", "Qwen",
    
    # Hardware
    "GPU", "TPU", "NPU", "CPU", "NVIDIA", "AMD", "Intel",
    "CUDA", "Blackwell", "Hopper",
    
    # Cloud/Infra
    "AWS", "Azure", "GCP", "Cloud",
    "Kubernetes", "Docker", "Terraform",
    "API", "REST", "GraphQL", "gRPC",
    
    # Data
    "Data", "Database", "SQL", "NoSQL", "PostgreSQL", "MongoDB",
    "Snowflake", "Databricks", "Spark", "Kafka",
    "ETL", "ELT", "DataOps", "MLOps",
    
    # Programming
    "Python", "JavaScript", "TypeScript", "Rust", "Go", "Java",
    "React", "Vue", "Next", "Node",
    "FastAPI", "Django", "Flask",
    
    # Concepts
    "RAG", "Vector", "Embedding", "Transformer",
    "Agent", "Agentic", "Workflow", "Automation",
    "RL", "RLHF", "Fine-tuning", "Training", "Inference",
    
    # Business
    "SaaS", "PaaS", "IaaS", "B2B", "B2C",
    "Startup", "Enterprise", "VC", "IPO",
    
    # General tech
    "Tech", "Software", "Hardware", "Platform",
    "Security", "Privacy", "Compliance",
    "Open-source", "Opensource",
}

# Tech terms in Korean
TECH_TERMS_KOREAN = {
    # AI/ML
    "인공지능", "머신러닝", "딥러닝", "생성형AI", "거대언어모델",
    "챗봇", "에이전트", "자동화", "추론", "학습", "모델",
    
    # Infrastructure
    "클라우드", "인프라", "데이터센터", "서버", "네트워크",
    "컨테이너", "쿠버네티스", "도커",
    
    # Data
    "데이터", "데이터베이스", "분석", "파이프라인",
    "빅데이터", "데이터웨어하우스", "레이크하우스",
    
    # Development
    "개발", "프로그래밍", "코딩", "소프트웨어", "플랫폼",
    "프레임워크", "라이브러리", "오픈소스",
    "프론트엔드", "백엔드", "풀스택",
    
    # Business
    "스타트업", "기업", "투자", "펀딩", "시장",
    "비즈니스", "서비스", "제품", "솔루션",
    
    # Trends
    "트렌드", "혁신", "기술", "디지털", "전환",
}

# Korean stopwords list
# 조사, 접속사, 대명사, 감탄사 등 의미 전달이 적은 단어들
KOREAN_STOPWORDS = {
    # 조사 (Particles)
    "은", "는", "이", "가", "을", "를", "의", "에", "에서", "로", "으로",
    "와", "과", "하고", "이나", "나", "든지", "든가", "이든", "부터", "까지",
    "만", "도", "조차", "마저", "밖에", "뿐", "만큼", "처럼", "같이",
    "보다", "에게", "한테", "께", "더러", "에게서", "한테서", "께서",
    "라고", "이라고", "고", "라", "이라",
    
    # 대명사 (Pronouns)
    "나", "너", "저", "우리", "저희", "그", "그녀", "그것", "이것", "저것",
    "여기", "저기", "거기", "어디", "무엇", "누구", "언제", "어떻게", "왜",
    "이", "그", "저", "이런", "그런", "저런", "어떤",
    
    # 접속사/연결 (Conjunctions)
    "그리고", "그러나", "그런데", "그래서", "따라서", "하지만", "그렇지만",
    "또한", "또", "및", "혹은", "또는", "즉", "곧", "만약", "만일",
    
    # 부사 (Adverbs) - 의미가 적은 것들
    "매우", "아주", "너무", "정말", "진짜", "참", "꽤", "상당히", "다소",
    "약간", "조금", "좀", "많이", "적게", "더", "덜", "가장", "제일",
    "항상", "늘", "자주", "가끔", "때때로", "종종", "이미", "벌써", "아직",
    "곧", "바로", "금방", "방금", "지금", "현재", "오늘", "어제", "내일",
    
    # 동사/형용사 어미 관련
    "하다", "되다", "있다", "없다", "이다", "아니다",
    "것", "수", "등", "때", "중", "위", "후", "전", "내", "외",
    
    # 일반적인 저정보 단어
    "통해", "대해", "대한", "관련", "관한", "경우", "따른", "인한",
    "위한", "의한", "말", "바", "데", "줄", "만큼", "정도",
    
    # 숫자 관련
    "하나", "둘", "셋", "넷", "다섯", "여섯", "일곱", "여덟", "아홉", "열",
    "첫", "두", "세", "네", "번째", "개", "명", "번", "차",
    
    # 기타 흔한 저정보 단어
    "씨", "님", "분", "측", "측면", "부분", "점", "면", "쪽",
    "가지", "종류", "방법", "방식", "형태", "형식",
}

# English stopwords (common ones to filter)
ENGLISH_STOPWORDS = {
    "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "as", "is", "was", "are", "were", "been",
    "be", "have", "has", "had", "do", "does", "did", "will", "would",
    "could", "should", "may", "might", "must", "shall", "can", "need",
    "this", "that", "these", "those", "it", "its", "he", "she", "they",
    "we", "you", "i", "my", "your", "his", "her", "their", "our",
    "what", "which", "who", "whom", "when", "where", "why", "how",
    "all", "each", "every", "both", "few", "more", "most", "other",
    "some", "such", "no", "not", "only", "same", "so", "than", "too",
    "very", "just", "also", "now", "here", "there", "then",
    "about", "after", "before", "between", "into", "through", "during",
    "above", "below", "up", "down", "out", "off", "over", "under",
    "again", "further", "once", "any", "if", "because", "until", "while",
}

# Combined stopwords
ALL_STOPWORDS = KOREAN_STOPWORDS | ENGLISH_STOPWORDS


def is_stopword(word: str) -> bool:
    """
    Check if a word is a stopword.
    
    Args:
        word: Word to check (case-insensitive for English)
        
    Returns:
        True if word is a stopword
    """
    return word.lower() in ALL_STOPWORDS


def filter_stopwords(words: list[str]) -> list[str]:
    """
    Filter stopwords from a list of words.
    
    Args:
        words: List of words to filter
        
    Returns:
        Filtered list without stopwords
    """
    return [w for w in words if not is_stopword(w)]
