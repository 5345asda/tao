# /design <slug> [alternative-number]
You are Claude Code. Generate a comprehensive detailed design document based on a selected pre-design option.

## Input
- **slug**: An existing requirement folder at `.sdp/specs/<slug>/`
- **alternative-number** (optional): Which alternative to detail (1, 2, 3, or 4). If not specified, use the recommended solution from pre-design.md

## Language Configuration

Read `.sdp/config/language.yml` to determine the output language:
- If `language: en`, generate all content in **English**
- If `language: ja`, generate all content in **Japanese**

Use templates from `.sdp/templates/<lang>/` directory based on the configured language.

## Context Files
Read these for context (in order of importance):
1. `.sdp/specs/<slug>/pre-design.md` - The pre-design options (REQUIRED)
2. `.sdp/specs/<slug>/requirement.md` - The requirement specification
3. `.sdp/tech.md` - Technical stack and constraints
4. `.sdp/structure.md` - Code structure and architecture
5. `.sdp/product.md` - Business context and goals

## Pre-Check

Before starting, verify that:
- `.sdp/specs/<slug>/` directory exists
- `.sdp/specs/<slug>/requirement.md` file exists
- `.sdp/specs/<slug>/pre-design.md` file exists

Claude Code will automatically check these conditions and report errors if requirements are missing.

## Alternative Selection Logic

1. If `alternative-number` is provided (e.g., 1, 2, 3, 4):
   - Read `pre-design.md` and extract the specified alternative
   - Verify the alternative number exists
   - Use that alternative as the basis for detailed design

2. If `alternative-number` is NOT provided:
   - Read `pre-design.md`
   - Extract the "Recommended Solution" section
   - Determine which alternative was recommended
   - Use the recommended alternative as the basis for detailed design

3. Output a clear statement at the beginning indicating which alternative is being detailed

## Detailed Design Process

### 1. Extract Base Design
- Read the selected alternative from pre-design.md
- Extract the overview, architecture, pros, cons as foundation
- Keep the rationale and trade-offs from the recommendation

### 2. Expand to Implementation-Ready Detail

**IMPORTANT**: This document should be comprehensive enough for implementation. Include ALL necessary details.

#### Architecture Details
- **System Architecture**: Detailed component diagrams (use Mermaid when appropriate)
- **Data Flow**: Detailed data flow diagrams showing all major paths
- **Module Structure**: Detailed breakdown of modules/packages/services
- **Integration Points**: How components interact with each other and external systems

#### Data Model Details
- **ER Diagrams**: Full entity-relationship diagrams (use Mermaid)
- **Table Definitions**: Complete DDL with all columns, types, constraints, indexes
- **Data Validation Rules**: Field-level validation requirements
- **Migration Strategy**: How to migrate from current state (if applicable)

#### API Specifications
- **Endpoint Definitions**: Full REST/GraphQL/gRPC endpoint specifications
- **Request/Response Schemas**: Complete schemas with examples
- **Error Responses**: All error cases with codes and messages
- **Authentication/Authorization**: Security requirements for each endpoint

#### Security Design
- **Authentication**: Detailed authentication mechanism
- **Authorization**: Role-based or attribute-based access control details
- **Data Protection**: Encryption at rest and in transit
- **Security Headers**: Required HTTP headers
- **Rate Limiting**: Specific rate limit rules
- **Input Validation**: Validation and sanitization requirements

#### Performance Design
- **Performance Targets**: Specific latency/throughput requirements
- **Caching Strategy**: What to cache, where, and for how long
- **Database Optimization**: Indexes, query optimization, connection pooling
- **Scalability Plan**: Horizontal/vertical scaling approach

#### Error Handling
- **Error Categories**: Define error types and codes
- **Logging Strategy**: What to log, at what level, where
- **Monitoring**: Key metrics to track
- **Alerting**: When to alert and whom

#### Implementation Guidelines
- **File Structure**: Detailed file and directory organization
- **Naming Conventions**: Specific naming rules for files, classes, functions
- **Coding Standards**: Language-specific coding conventions
- **Testing Strategy**: Unit, integration, e2e testing approach
- **Implementation Order**: Step-by-step implementation sequence
- **Dependencies**: New dependencies to add (with versions)

### 3. Address Trade-offs and Risks
- Expand on trade-offs mentioned in pre-design.md
- Provide detailed mitigation strategies for identified risks
- Add new risks discovered during detailed design
- Create risk matrix with probability, impact, and mitigation

### 4. Provide Implementation Guidance
- Break down implementation into clear phases
- Identify critical path items
- Suggest rollback strategies
- Provide testing checkpoints

## Document Length Guidelines

**Target length: 500-800 lines**

Be comprehensive but focused:
- ✅ Complete architecture diagrams
- ✅ Full database schemas with DDL
- ✅ Complete API specifications
- ✅ Detailed security measures
- ✅ Specific implementation steps
- ✅ Concrete file structures
- ❌ NO implementation code (unless small examples for clarity)
- ❌ NO test code (describe test strategy instead)

**The goal is to provide everything needed to implement, without actually implementing.**

## Deliverable

Create or update `.sdp/specs/<slug>/design.md` following `.sdp/templates/<lang>/design.md` structure (use the language-specific template).

**Note**: The existing design.md template is comprehensive and suitable for detailed design. Use it as-is.

## Detailed Design Document Structure

The output must include (based on design.md template):

1. **Title and Overview**: What's being designed (selected alternative)
2. **Design Selection**: Which alternative was chosen and why (reference pre-design.md)
3. **Architecture**: Detailed system architecture with diagrams
4. **Component Design**: Detailed component breakdown
5. **Data Models**: Complete ER diagrams and table definitions
6. **API Design**: Full API specifications
7. **Security Measures**: Comprehensive security design
8. **Performance Optimization**: Caching, indexing, scaling strategies
9. **Trade-offs & Risks**: Detailed risk analysis and mitigation
10. **Implementation Guidelines**: File structure, conventions, implementation order
11. **Testing Strategy**: Unit, integration, e2e testing approach
12. **Open Questions**: Unresolved items (if any)

## Output Format

Generate all content based on the configured language (`.sdp/config/language.yml`).

After writing the file, print a summary in the same language as the content:

For Japanese:
```
【詳細設計完了】
📐 Slug: <slug>
📝 採用案: 設計案<N>: <設計名>
📁 ファイル: .sdp/specs/<slug>/design.md

📊 ドキュメントサイズ: <行数>行
📌 主要コンポーネント: <数>個
🗄️ テーブル数: <数>個
🔌 API数: <数>個

💡 次のステップ:
  - 詳細設計を確認し、修正が必要な場合は自然言語で指示してください
  - 設計が確定したら /sdp:estimate <slug> でタスク分解を実行してください
```

For English:
```
【Detailed Design Completed】
📐 Slug: <slug>
📝 Selected: Alternative <N>: <design name>
📁 File: .sdp/specs/<slug>/design.md

📊 Document Size: <lines> lines
📌 Main Components: <count>
🗄️ Tables: <count>
🔌 APIs: <count>

💡 Next Steps:
  - Review detailed design and provide feedback if changes needed
  - When design is finalized: /sdp:estimate <slug> for task breakdown
```

## User Iteration Support

After generating the detailed design:
- User can provide natural language feedback
- Update the design document based on feedback
- Refine specific sections as requested
- Add missing details if pointed out
- Maintain version notes in the document

## Design Quality Guidelines

### Completeness
- Include all information needed for implementation
- Don't leave critical decisions to implementation phase
- Specify exact technologies, libraries, versions when possible

### Consistency with Context
- **tech.md alignment**: Use stack and patterns from tech.md
- **structure.md alignment**: Follow existing file organization patterns
- **requirement.md alignment**: Satisfy all functional and non-functional requirements

### Specificity
- Use concrete values, not placeholders (e.g., "bcrypt cost factor: 12" not "appropriate cost factor")
- Provide actual examples (e.g., actual JSON schemas, actual SQL DDL)
- Give specific numbers (e.g., "100ms p99 latency" not "fast")

### Implementability
- Implementation order should be clear and logical
- Dependencies should be explicitly stated
- File structure should match structure.md conventions
- No ambiguity about what needs to be built

### Risk Awareness
- Identify technical risks specific to the detailed design
- Provide concrete mitigation strategies
- Acknowledge uncertainties
- Suggest monitoring and validation approaches

## Cross-Platform Compatibility

This command works on all platforms (Windows, macOS, Linux) as it uses Claude Code's native file operations instead of shell-specific commands.

## Allowed Tools
Read, Write, Edit, File Search, Grep only
