# /pre-design <slug>
You are Claude Code. Generate a lightweight pre-design document that compares 2-4 design approaches for a given requirement.

## Input
- **slug**: An existing requirement folder at `.sdp/specs/<slug>/` containing `requirement.md`

## Language Configuration

Read `.sdp/config/language.yml` to determine the output language:
- If `language: en`, generate all content in **English**
- If `language: ja`, generate all content in **Japanese**

Use templates from `.sdp/templates/<lang>/` directory based on the configured language.

## Context Files
Read these for context:
- `.sdp/specs/<slug>/requirement.md` - The requirement to design
- `.sdp/tech.md` - Technical stack and constraints
- `.sdp/structure.md` - Code structure and architecture
- `.sdp/product.md` - Business context and goals

## Pre-Check

Before starting, verify that:
- `.sdp/specs/<slug>/` directory exists
- `.sdp/specs/<slug>/requirement.md` file exists

Claude Code will automatically check these conditions and report errors if requirements are missing.

## Pre-Design Process

### 1. Understand the Requirement & Architecture Context
- Read and analyze the requirement thoroughly
- Extract key constraints from NFRs (security, performance, etc.)
- Identify technical boundaries from `.sdp/tech.md`
- Inspect `.sdp/structure.md` and existing source directories to infer the prevailing architecture style (e.g., Clean Architecture, Hexagonal, Layered, Microservices, Event-Driven, Serverless)
- Capture explicit architecture signals:
  - **Clean / Onion / Hexagonal**: presence of `domain/`, `usecase/`, `application/`, `adapter/`, `interface/`
  - **Layered (MVC, MVVM, etc.)**: directories such as `controllers/`, `views/`, `services/`
  - **Microservices / Modular Monolith**: multiple service directories, independent deployment manifests
  - **Event-Driven**: `events/`, `subscribers/`, `queues/`
  - **CQRS / DDD**: `aggregates/`, `read-model/`, `write-model/`
- Record any architecture-specific rules that must be honored (e.g., "domain layer must remain free of framework dependencies")

### 2. Generate 2-4 Design Options

**IMPORTANT**: Keep this lightweight and focused on comparison. **DO NOT** include detailed specifications in this document. Save detailed design for the next step.

For each alternative (2-4 alternatives):

**Overview** (2-3 sentences)
- High-level description of the approach
- Key distinguishing characteristics

**Architecture** (Simple text diagram or brief description)
- Show key components and data flow
- Highlight the flow of control between layers/modules
- **NO** detailed class diagrams, **NO** detailed sequence diagrams

**Architecture Alignment & Best Practices**
- Explain how the alternative respects the inferred architecture style (e.g., keeps domain logic inside `domain/`, isolates adapters)
- Note required layering rules (e.g., "presentation layer references application services only")
- Mention any deviations and remediation measures

**Domain Logic Placement**
- Describe where core business rules reside
- For Clean / Hexagonal architectures: ensure use cases and entities stay framework-agnostic, adapters remain thin
- For Layered architectures: clarify service/business layer responsibilities vs. controllers/views
- For Microservices: outline bounded context boundaries and data ownership

**Pros** (3-5 bullet points)
- Key advantages (link to NFRs, architecture goals, business KPIs when possible)
- Cite maintainability/security/performance impacts with concrete evidence

**Cons** (3-5 bullet points)
- Drawbacks and limitations
- Be honest about trade-offs and any architecture rule violations

**Implementation Complexity**: Low / Med / High
- Brief justification (1 sentence)
- Reference migration effort if refactoring existing layers/modules is required

**Primary Risks** (1-2 sentences)
- Main technical risks associated with this approach
- Include architecture integrity risks (e.g., "risk of domain leakage into adapter layer")

### 3. Comparative Analysis

Create a comparison table with criteria such as:
- Implementation effort (person-days estimate)
- Architecture fit / Cleanliness (High/Med/Low) — how well the option respects existing layering boundaries
- Domain model impact (Strong/Neutral/Weak) — clarity of domain ownership, aggregate boundaries, invariants
- Maintainability (High/Med/Low)
- Performance characteristics (concrete metrics when possible)
- Scalability (High/Med/Low)
- Team familiarity (High/Med/Low)
- Technical debt implications (Low/Med/High)
- Security (High/Med/Low)
- Cost (Low/Med/High)
- Operational complexity / deployment impact (Low/Med/High)

**Adjust criteria based on the specific requirement and project context.**

### 4. Recommended Solution

**Selection rationale** (3-5 sentences)
- Why this design was chosen over alternatives
- How it preserves or intentionally evolves the current architecture style
- What key factors (NFRs, business goals, domain boundaries) drove the decision
- Reference to product.md business goals when applicable

**Key Trade-offs** (2-4 bullet points)
- What we're sacrificing and why it's acceptable
- Be explicit about what we're NOT optimizing for
- Call out any architecture rule exceptions and planned mitigation (e.g., temporary coupling, transitional adapters)

## Document Length Guidelines

**Target length: 200-400 lines**

Keep it concise:
- ✅ Focus on comparison and decision-making
- ✅ Simple architecture diagrams (ASCII/text)
- ✅ Brief pros/cons lists
- ❌ NO detailed API specifications
- ❌ NO detailed database schemas
- ❌ NO detailed implementation code
- ❌ NO detailed security measures
- ❌ NO detailed file structures

**The goal is to help the user choose a direction, not to provide implementation details.**

## Deliverable

Create `.sdp/specs/<slug>/pre-design.md` following `.sdp/templates/<lang>/pre-design.md` structure (use the language-specific template).

## Pre-Design Document Structure

The output must include:

1. **Overview**: Summary of what's being designed (2-3 sentences)
2. **Alternative 1**: First design approach
3. **Alternative 2**: Second design approach
4. **Alternative 3**: Third design approach (optional but recommended)
5. **Alternative 4**: Fourth design approach (optional)
  - Each alternative must include: Overview, Architecture outline, Architecture Alignment & Best Practices, Domain Logic Placement, Pros/Cons, Complexity, Risks
6. **Comparison Matrix**: Side-by-side comparison table emphasizing architecture/domain fit
7. **Recommended Solution**: Selected design with rationale and trade-offs
8. **Next Steps**: Instructions for proceeding to detailed design

## Output Format

Generate all content based on the configured language (`.sdp/config/language.yml`).

After writing the file, print a summary in the same language as the content:

For Japanese:
```
【設計案作成完了】
📐 Slug: <slug>
📝 タイトル: <設計タイトル>
📁 ファイル: .sdp/specs/<slug>/pre-design.md

📊 評価した設計案: <数>件
✅ 推奨案: <推奨する設計名>
📌 主要な選定理由: <1行要約>

💡 次のステップ:
  - 設計案を確認し、修正が必要な場合は自然言語で指示してください
  - 推奨案で進める場合: /sdp:design <slug>
  - 別の設計案を選ぶ場合: /sdp:design <slug> <設計案番号>
```

For English:
```
【Pre-Design Completed】
📐 Slug: <slug>
📝 Title: <design title>
📁 File: .sdp/specs/<slug>/pre-design.md

📊 Alternatives Evaluated: <number>
✅ Recommended: <recommended design name>
📌 Key Rationale: <one-line summary>

💡 Next Steps:
  - Review alternatives and provide feedback if changes needed
  - To proceed with recommended: /sdp:design <slug>
  - To select different alternative: /sdp:design <slug> <alternative-number>
```

## User Iteration Support

After generating the design alternatives:
- User can provide natural language feedback
- Update the alternatives document based on feedback
- Add new alternatives if requested
- Refine comparison matrix if needed
- Re-evaluate recommendation if requested

## Design Quality Guidelines

### Ensure Alternatives are Truly Different
- Each alternative should represent a fundamentally different approach
- Avoid alternatives that are just minor variations
- Consider different: architectures, technologies, paradigms, complexity levels

### Make Comparisons Objective
- Use concrete metrics when possible (e.g., "100ms response time" vs "fast")
- Provide evidence from tech.md or product.md
- Acknowledge uncertainty when estimating

### Align with Project Context
- Reference constraints from tech.md (stack, infrastructure, skills)
- Reference goals from product.md (KPIs, user needs)
- Reference existing patterns from structure.md
- Consider team's current skill level and learning curve

### Architecture-Aware Heuristics
- **Clean / Onion / Hexagonal Architecture**
  - Keep domain entities and use cases pure (no framework dependencies)
  - Push IO, persistence, and external integrations to adapter layers
  - Prefer dependency inversion (interfaces in domain/application layers)
  - Highlight boundary tests and contract enforcement between layers
- **Layered (MVC, MVVM, 3-tier)**
  - Ensure controllers remain thin; business logic resides in service/domain layer
  - Validate DTO ↔ domain conversions and mapping responsibilities
  - Consider caching, validation, and transaction boundaries at appropriate layers
- **Microservices / Modular Monolith**
  - Define bounded contexts, data ownership, and integration patterns (sync/async)
  - Address cross-cutting concerns (observability, auth) consistently across services
  - Evaluate deployment, API versioning, and rollback strategies per service
- **Event-Driven / CQRS**
  - Separate write/read models when justified; ensure eventual consistency patterns are explicit
  - Document event contracts, delivery guarantees, and failure handling
  - Ensure domain events remain ubiquitous language artifacts, not infrastructure leaks
- **Serverless / FaaS**
  - Clarify function boundaries, stateless requirements, and cold-start mitigations
  - Plan shared service layers (auth, data access) that prevent logic duplication
  - Highlight observability, idempotency, and retry strategies

### Be Honest About Trade-offs
- Every design has trade-offs - make them explicit
- Don't oversell the recommended solution
- Acknowledge what you're NOT optimizing for

## Cross-Platform Compatibility

This command works on all platforms (Windows, macOS, Linux) as it uses Claude Code's native file operations instead of shell-specific commands.

## Allowed Tools
Read, Write, Edit, File Search, Grep only
