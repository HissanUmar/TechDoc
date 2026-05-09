# Workflow Diagram

```mermaid
flowchart LR
  subgraph SupervisorLayer
    Sup[Supervisor]
  end

  subgraph Infra
    Bus[SimpleMessageBus]
    State[(InMemoryStateStore)]
    Worker[AgentWorker (consumer)]
  end

  Sup -->|schedule tasks / orchestrate DAG| Bus
  Bus -->|deliver task| Worker

  Worker --> Analyst[RequirementsAnalyst\n(Mistral requested)]
  Analyst -->|publish requirements| Bus
  Analyst -->|write| State

  Bus --> Architect[ArchitectureDesigner]
  Architect -->|call LLM| HfClient[HfClient]
  Architect -->|write design| State
  Architect -->|publish design| Bus

  Bus --> Validator[SecurityValidator]
  Validator -->|call LLM| HfClient
  Validator -->|publish validation| Bus
  Validator -->|write| State

  Bus --> Perf[PerformanceAnalyzer]
  Perf -->|call LLM| HfClient
  Perf -->|publish perf report| Bus
  Perf -->|write| State

  Bus --> Doc[DocumentationGenerator]
  Doc -->|call LLM| HfClient
  Doc -->|store docs| State

  Analyst --> Clarify[ClarificationEngine]
  Clarify -->|questions| User[End User]
  User -->|answers| Clarify
  Clarify -->|clarified requirements| Analyst

  HfClient -->|primary| Mistral[Mistral (requested)]
  HfClient -->|fallback| Llama[Llama-2]
  HfClient -->|fallback| Falcon[Falcon-7B]
  HfClient -->|fallback| Flan[Flan-T5]
  HfClient -->|final stub| GPT2[gpt2 (local stub)]

  Sup -->|snapshot / checkpoint| State
```
