"""
Run all agent MCP servers.

Usage:
    python -m app.mcp.run_agents          # Start all agents
    python -m app.mcp.run_agents nlp ir   # Start specific agents

Each agent runs on its own port:
    - Security Agent:       port 8100
    - NLP Agent:            port 8101
    - IR Agent:             port 8102
    - Analysis Agent:       port 8103
    - Verification Agent:   port 8104
    - Recommendation Agent: port 8105
"""

import sys
import asyncio
import multiprocessing


def run_security_agent():
    """Start the Security Agent server."""
    from app.agents.security_agent.security_agent import SecurityAgent
    agent = SecurityAgent()
    agent.run()


def run_nlp_agent():
    """Start the NLP Agent server."""
    from app.agents.nlp_agent.nlp_agent import NLPAgent
    agent = NLPAgent()
    agent.run()


def run_ir_agent():
    """Start the IR Agent server."""
    from app.agents.ir_agent.ir_agent import IRAgent
    agent = IRAgent()
    agent.run()


def run_analysis_agent():
    """Start the Analysis Agent server."""
    from app.agents.analysis_agent.analysis_agent import AnalysisAgent
    agent = AnalysisAgent()
    agent.run()


def run_verification_agent():
    """Start the Verification Agent server."""
    from app.agents.verification_agent.verification_agent import VerificationAgent
    agent = VerificationAgent()
    agent.run()


def run_recommendation_agent():
    """Start the Recommendation Agent server."""
    from app.agents.recommendation_agent.recommendation_agent import RecommendationAgent
    agent = RecommendationAgent()
    agent.run()


AGENT_RUNNERS = {
    "security": run_security_agent,
    "nlp": run_nlp_agent,
    "ir": run_ir_agent,
    "analysis": run_analysis_agent,
    "verification": run_verification_agent,
    "recommendation": run_recommendation_agent,
}


def main():
    """Start agent servers as separate processes."""
    # Determine which agents to start
    requested = sys.argv[1:] if len(sys.argv) > 1 else list(AGENT_RUNNERS.keys())

    processes = []

    print("=" * 60)
    print("  CLIMORA AI - Agent MCP Servers")
    print("=" * 60)

    for agent_name in requested:
        if agent_name not in AGENT_RUNNERS:
            print(f"  ✗ Unknown agent: {agent_name}")
            print(f"    Available: {', '.join(AGENT_RUNNERS.keys())}")
            continue

        print(f"  Starting: {agent_name} agent...")
        process = multiprocessing.Process(
            target=AGENT_RUNNERS[agent_name],
            name=f"agent-{agent_name}",
            daemon=True,
        )
        process.start()
        processes.append((agent_name, process))

    print("=" * 60)
    print(f"  {len(processes)} agent(s) started. Press Ctrl+C to stop all.")
    print("=" * 60)

    try:
        # Keep main process alive
        for _, process in processes:
            process.join()
    except KeyboardInterrupt:
        print("\n  Stopping all agents...")
        for name, process in processes:
            process.terminate()
            print(f"  ✓ {name} stopped")
        print("  All agents stopped.")


if __name__ == "__main__":
    main()
