# System Low-Level Design (LLD): AI-Powered LibreOffice Extension

**Role:** System Architect / LLD Designer
**Standards:** SOLID, Design Patterns (Factory, Observer, Bridge), Async Architecture.

---

## 1. System Architecture Diagram
This diagram shows the high-level boundaries between LibreOffice (Main Thread) and the Python Async Engine (Background Thread).

```mermaid
graph TD
    subgraph "LibreOffice Process (Main Thread)"
        UI[Native UNO Dialog]
        DISP[Dispatch Interceptor]
        DOC[Document Context]
        POLL[MainThreadPoller / Timer]
    end

    subgraph "Python Runtime (Background Thread)"
        LOOP[Asyncio Event Loop]
        ORCH[AI Orchestrator]
        PROV[AI Providers: Google/OpenAI]
    end

    subgraph "Shared Thread-Safe Boundary"
        IQ[Input Queue]
        OQ[Output Queue]
    end

    DISP --> UI
    UI --> IQ
    IQ --> LOOP
    LOOP --> ORCH
    ORCH --> PROV
    PROV -- "Streaming Chunks" --> OQ
    OQ --> POLL
    POLL --> UI
    UI -- "Apply Changes" --> DOC
```

---

## 2. Class Diagram
Detailed breakdown of classes, interfaces, and their relationships.

```mermaid
classDiagram
    class XDispatchProvider {
        <<interface>>
        +queryDispatch(url, name, searchFlags)
    }
    class AI_Extension_Component {
        +initialize()
        +execute()
    }
    XDispatchProvider <|.. AI_Extension_Component

    class IAIProvider {
        <<interface>>
        +generate_stream(prompt) AsyncGenerator
    }
    class GoogleProvider {
        -api_key: str
        +generate_stream(prompt)
    }
    class OpenAIProvider {
        -api_key: str
        +generate_stream(prompt)
    }
    IAIProvider <|-- GoogleProvider
    IAIProvider <|-- OpenAIProvider

    class ProviderFactory {
        +get_provider(type: str) IAIProvider
    }
    ProviderFactory ..> IAIProvider : creates

    class AsyncEngine {
        -loop: asyncio.Loop
        -worker_thread: Thread
        +post_task(payload)
    }

    class MainThreadPoller {
        -timer: XTimer
        +on_timer_tick()
    }

    class DocumentContext {
        +get_selection() str
        +write_text(text) void
    }

    AI_Extension_Component --> AsyncEngine
    AI_Extension_Component --> MainThreadPoller
    AsyncEngine --> ProviderFactory
    MainThreadPoller --> DocumentContext
```

---

## 3. Sequence Diagram: Asynchronous Streaming Flow
This diagram details how text flows from the user's selection to the AI and back to the dialog without freezing the UI.

```mermaid
sequenceDiagram
    participant User
    participant Dialog as Native UNO Dialog
    participant Main as MainThreadPoller
    participant IQ as Input Queue
    participant Loop as Async Event Loop
    participant AI as AI Provider (SDK)
    participant OQ as Output Queue

    User->>Dialog: Clicks "Generate"
    Dialog->>IQ: Push(Selection + Provider)
    Loop->>IQ: Pop()
    Loop->>AI: generate_stream(prompt)
    
    loop Streaming
        AI-->>Loop: Chunk
        Loop->>OQ: Push(Chunk)
        Main->>OQ: Pop() (Every 100ms)
        Main->>Dialog: Update Textbox
    end

    User->>Dialog: Clicks "Apply"
    Dialog->>User: Text written to document
```

---

## 4. Entity-Relationship (ER) Diagram: Configuration Store
Shows how user preferences and secure keys are managed.

```mermaid
erDiagram
    CONFIGURATION {
        string last_used_provider
        int max_tokens
        boolean stream_enabled
    }
    PROVIDER_SETTINGS {
        string provider_id PK
        string model_name
        string api_key_ref
    }
    SECURE_STORE {
        string key_ref PK
        string encrypted_value
    }
    CONFIGURATION ||--o{ PROVIDER_SETTINGS : uses
    PROVIDER_SETTINGS ||--|| SECURE_STORE : "refers to"
```

---

## 5. Design Pattern Explanations

### 1. Abstract Factory (ProviderFactory)
Used to decouple the extension from specific AI SDKs. When the user selects "Google" or "OpenAI" in the dialog, the `ProviderFactory` returns an object that implements the `IAIProvider` interface. This allows us to add new models (like Anthropic) in the future without changing the core UI logic.

### 2. Bridge Pattern (AsyncEngine/MainThreadPoller)
Used to bridge the synchronous world of LibreOffice (C++) and the asynchronous world of Python. The `Input/Output Queues` act as the bridge, ensuring neither thread directly accesses the other's internal state, preventing race conditions and crashes.

### 3. Command Pattern (DispatchInterceptor)
The extension implements `XDispatchProvider`, treating user actions (menu clicks) as commands. This allows for a clean separation between the "UI Trigger" and the "Logic Execution."

### 4. SOLID Implementation Details
- **S (SRP):** `DocumentContext` has one job: translation between Python strings and UNO `XText` objects.
- **O (OCP):** New AI Providers can be added by creating a new class implementing `IAIProvider`.
- **D (DIP):** The `NativeUI` depends on the `IAIProvider` abstraction, not on concrete `GoogleSDK` or `OpenAISDK` classes.
