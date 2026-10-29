# Ingest: OpenF1 client (P0.4)

## Class diagram

```mermaid
classDiagram
    class Transport {
        <<Protocol>>
        +get(endpoint, params) Response
    }
    class Response {
        <<frozen dataclass>>
        +status: int
        +body: bytes
    }
    class HttpTransport {
        -client: httpx.Client
        +create(base_url, timeout)$ HttpTransport
        +get(endpoint, params) Response
        +close()
    }
    class CachedTransport {
        -inner: Transport
        -cache_dir: Path
        +get(endpoint, params) Response
    }
    class OpenF1Client {
        -transport: Transport
        -chunk: timedelta
        +query(endpoint, params) list~Row~
        +sessions(year, circuit, name) list~Session~
        +drivers(session_key) list~Driver~
        +locations(session_key, start, end, driver) list~LocationSample~
    }
    class Session {
        <<frozen dataclass>>
    }
    class Driver {
        <<frozen dataclass>>
    }
    class LocationSample {
        <<frozen dataclass>>
    }

    Transport <|.. HttpTransport
    Transport <|.. CachedTransport
    CachedTransport o-- Transport : wraps
    OpenF1Client --> Transport : depends on
    OpenF1Client ..> Session : builds
    OpenF1Client ..> Driver : builds
    OpenF1Client ..> LocationSample : builds
    Transport ..> Response
```

## Sequence: locations()

```mermaid
sequenceDiagram
    participant N as Notebook
    participant C as OpenF1Client
    participant K as CachedTransport
    participant H as HttpTransport
    participant O as OpenF1 API

    N->>C: locations(9590, start, end, driver=16)
    C->>C: validate tz-aware and end not before start
    loop each 10-min window
        C->>C: validate fields (typo raises InvalidQueryError)
        C->>K: get("location", params)
        alt cache hit
            K-->>C: Response 200 from disk
        else cache miss
            K->>H: get(...)
            H->>O: HTTP GET
            alt network failure
                H-->>C: raise SourceError (cause: httpx error)
            else got response
                O-->>H: status + body
                H-->>K: Response
                K->>K: if 200, atomic write to disk
                K-->>C: Response
            end
        end
        C->>C: 404 = no rows, 200 = parse JSON, other = SourceError
        C->>C: rows to LocationSample (bad shape raises SchemaError)
        C->>C: dedupe by (time, driver)
    end
    C-->>N: sorted list of LocationSample
```

## Decisions

1. **Transport returns status, doesn't raise on it.** "404 means empty" is an
   OpenF1 rule, so the client interprets status; the transport only raises
   SourceError for network failures.
2. **Caching is a decorator.** CachedTransport wraps any Transport. Only 200
   responses are cached, so errors and empties never get stuck.
3. **Atomic cache writes.** Write to .tmp, then rename: no half-written files
   after a crash.
4. **Validate filters before sending.** OpenF1 answers unknown fields with the
   same 404 as "no results" (the drive_number bug), so typos are rejected locally.
5. **Typed models at the boundary.** Rows become frozen dataclasses on arrival;
   shape problems raise SchemaError there, not deep inside later code.
6. **ValueError for caller bugs, PitwallError for world problems.** Naive
   datetimes and negative chunks are programmer errors; a 401 is not.
7. **No printing in the library.** It uses logging; the caller decides output.
8. **Composition at the edge.** The notebook wires CachedTransport(HttpTransport)
   into OpenF1Client; the client knows nothing about caching or httpx.
