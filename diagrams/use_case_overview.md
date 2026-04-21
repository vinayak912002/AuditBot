# User Journey Sequence Diagrams

This document highlights the specific sequences triggered by user actions.

## 1. User Registration Flow
Triggered when the user runs the registration command to authorize their Google Drive.

```mermaid
sequenceDiagram
    autonumber
    actor User
    participant CLI as src.watcher.drive_watcher (CLI)
    participant Watcher as MultiUserDriveWatcher
    participant GAuth as Google OAuth2 (Browser)
    participant GAPI as Google Identity API
    participant DB as PostgreSQL (UserCredential Table)

    User->>CLI: python -m src.watcher.drive_watcher --register
    CLI->>Watcher: register_new_user()
    Watcher->>GAuth: flow.run_local_server()
    GAuth-->>User: Opens Browser for Login
    User->>GAuth: Grants Permission
    GAuth-->>Watcher: Returns Auth Code/Token
    Watcher->>GAPI: service.userinfo().get()
    GAPI-->>Watcher: Returns user email
    Watcher->>DB: SessionLocal (Save/Update token_data)
    DB-->>Watcher: Commit
    Watcher-->>User: "Registered new user: email@example.com"
```

## 2. File Upload & Processing Flow
Triggered when a user adds a new invoice to their monitored Google Drive folder.

```mermaid
sequenceDiagram
    autonumber
    actor User
    participant GDrive as Google Drive (Folder)
    participant Watcher as src.watcher.drive_watcher (Watcher Loop)
    participant DB as PostgreSQL (InvoiceJob Table)
    participant Consumer as src.consumer.processor (Consumer Service)
    participant AI as src.consumer.ai_providers (AI Factory)

    Note over User,GDrive: User uploads Invoice.pdf to Drive
    
    loop Every POLL_INTERVAL
        Watcher->>DB: Query UserCredential table
        DB-->>Watcher: List of registered users
        Watcher->>GDrive: service.files().list(query)
        GDrive-->>Watcher: List of File IDs
        Watcher->>DB: Idempotency check (filter_by file_id)
        alt File is New
            Watcher->>DB: Add InvoiceJob(status=NEW)
        end
    end

    loop Worker Loop
        Consumer->>DB: SELECT FOR UPDATE SKIP LOCKED (status=NEW)
        DB-->>Consumer: Returns Job
        Consumer->>DB: Update status=PROCESSING
        
        rect rgb(37, 13, 78)
            Note right of Consumer: _run_pipeline()
            Consumer->>GDrive: _download_file() (get_media)
            GDrive-->>Consumer: Raw Bytes
            Consumer->>Consumer: _parse_with_mineru() (Mock Parser)
            Consumer->>AI: extract_invoice_data(parsed_text)
            AI-->>Consumer: Extracted JSON
        end

        Consumer->>DB: Update status=PROCESSED, extracted_data=JSON
        DB-->>Consumer: Commit
    end
```
