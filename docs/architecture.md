# System Architecture

## Data Flow

```mermaid
graph TD
    subgraph Scraping
        A[SEC EDGAR] -->|Rate-limited requests| B["EDGARScraper
        (edgar_scraper.py)"]
        B -->|Validates & Stores| C["SQLite DB
        (def14a_filings/filings.db)"]
        B -->|Saves| D["HTML Files
        (def14a_filings/*.htm)"]
    end

    subgraph Parsing
        D -->|Reads| E["Executive Parser
        (parse_exec_compensation.py)"]
        E -->|Uses| F[DeepSeek AI]
        F -->|Section Identification| E
        F -->|Information Extraction| E
        E -->|Stores| C
    end

    subgraph Data Model
        C -->|Companies| G["Company Info
        (companies table)"]
        C -->|Filings| H["Filing Data
        (filings table)"]
        C -->|Executives| I["Executive Data
        (executive_data table)"]
        C -->|Status| J["Processing Status
        (processing_status table)"]
    end
```

## Component Interaction

```mermaid
sequenceDiagram
    participant SEC as SEC EDGAR API
    participant Scraper as EDGARScraper<br/>(edgar_scraper.py)
    participant DB as SQLite DB<br/>(filings.db)
    participant Parser as Executive Parser<br/>(parse_exec_compensation.py)
    participant AI as DeepSeek AI<br/>(AI Service)

    Scraper->>SEC: Request company CIKs
    SEC-->>Scraper: Return company list

    loop For each company
        Scraper->>SEC: Request DEF 14A filings
        SEC-->>Scraper: Return filing links

        loop For each filing
            Scraper->>SEC: Download filing
            SEC-->>Scraper: Return HTML content
            Scraper->>Scraper: Validate content
            Scraper->>DB: Store filing metadata
        end
    end

    Parser->>DB: Get unprocessed filings
    DB-->>Parser: Return filing paths

    loop For each filing
        Parser->>AI: Request section identification
        AI-->>Parser: Return relevant sections
        Parser->>AI: Extract executive information
        AI-->>Parser: Return structured data
        Parser->>DB: Store executive data
        Parser->>DB: Update processing status
    end
```

## System Components

### EDGARScraper (edgar_scraper.py)

- **Responsibility**: Downloads and validates DEF 14A filings
- **Key Features**:
  - Rate limiting
  - Content validation
  - Multi-threading
  - Progress tracking

### Executive Parser (parse_exec_compensation.py)

- **Responsibility**: Extracts structured data from filings
- **Key Features**:
  - AI-powered extraction
  - Section identification
  - Data validation
  - Error handling

### SQLite Database (def14a_filings/filings.db)

- **Responsibility**: Persistent storage
- **Tables**:
  - Companies
  - Filings
  - Executive Data
  - Processing Status

### DeepSeek AI Integration

- **Responsibility**: Intelligent text analysis
- **Functions**:
  - Section identification
  - Information extraction
  - Data structuring

## Error Handling and Recovery

```mermaid
graph TD
    A[Error Occurs] --> B{Error Type}
    B -->|Network| C[Exponential Backoff]
    B -->|Validation| D[Skip & Log]
    B -->|Parsing| E[Mark for Review]

    C --> F[Retry Request]
    F -->|Success| G[Continue]
    F -->|Failure| H[Max Retries]

    D --> I[Next Item]
    E --> I

    H -->|Exceeded| J[Alert & Skip]
    J --> I
