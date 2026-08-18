"""
NLP Agent (Query & NLP Agent) - MCP Server

Responsibilities:
- Intent detection: Identify what the user wants (risk_awareness, forecast, preparedness, etc.)
- Entity extraction: Extract location, date/time, climate topic, hazard type
- Query expansion: Add related terms to improve retrieval
- Summarization: Condense long text into concise evidence snippets

Tools exposed via MCP:
- process_query: Full NLP pipeline on user input
- extract_entities: Named Entity Recognition for climate entities
- expand_query: Query expansion for better retrieval
- summarize_text: Summarize retrieved documents

Tech suggestions:
- spaCy for NER and tokenization
- transformers for intent classification
- LLM (via Bedrock) for complex understanding

Port: 8101

TODO: Implement this agent
"""

from app.mcp.base_agent_server import BaseAgentServer


class NLPAgent(BaseAgentServer):
    """NLP Agent for intent detection, entity extraction, and query processing."""

    def __init__(self):
        super().__init__(
            name="nlp_agent",
            port=8101,
            description="Handles intent detection, entity extraction, query expansion and summarization",
        )

        # Register tools
        self.register_tool(
            "process_query",
            self.process_query,
            "Full NLP processing: intent detection + entity extraction + query structuring",
        )
        self.register_tool(
            "extract_entities",
            self.extract_entities,
            "Extract named entities (location, date, topic, hazard) from text",
        )
        self.register_tool(
            "expand_query",
            self.expand_query,
            "Expand query with related terms for better retrieval",
        )
        self.register_tool(
            "summarize_text",
            self.summarize_text,
            "Summarize long text into concise snippets",
        )

    async def process_query(self, arguments: dict) -> dict:
        """
        Full NLP pipeline on user input.

        Input:
            - query (str): User's raw query text
            - location (str, optional): Provided location
            - user_type (str, optional): Type of user

        Output:
            - intent (str): Detected intent
            - entities (dict): Extracted entities
            - structured_query (dict): Structured version for IR
            - expanded_terms (list): Additional search terms
        """
        # TODO: Implement NLP processing
        # Suggestions:
        # 1. Use spaCy for NER to extract locations, dates
        # 2. Use a classifier (or LLM) for intent detection
        # 3. Use LLM for query expansion
        raise NotImplementedError("NLP Agent not yet implemented")

    async def extract_entities(self, arguments: dict) -> dict:
        """
        Extract named entities from text.

        Input:
            - text (str): Text to extract entities from

        Output:
            - entities (dict): {location: [], date: [], topic: [], hazard: []}
        """
        # TODO: Implement entity extraction using spaCy or transformers
        raise NotImplementedError("Entity extraction not yet implemented")

    async def expand_query(self, arguments: dict) -> dict:
        """
        Expand a query with related terms for better retrieval.

        Input:
            - query (str): Original query
            - entities (dict): Extracted entities

        Output:
            - expanded_terms (list): Additional search terms
            - expanded_query (str): Full expanded query string
        """
        # TODO: Implement query expansion
        raise NotImplementedError("Query expansion not yet implemented")

    async def summarize_text(self, arguments: dict) -> dict:
        """
        Summarize long text into concise snippets.

        Input:
            - text (str): Long text to summarize
            - max_length (int): Maximum summary length

        Output:
            - summary (str): Condensed text
        """
        # TODO: Implement summarization using LLM
        raise NotImplementedError("Summarization not yet implemented")


# Entry point for running this agent standalone
if __name__ == "__main__":
    agent = NLPAgent()
    agent.run()
